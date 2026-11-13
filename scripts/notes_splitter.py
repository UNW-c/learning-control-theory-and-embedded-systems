"""把总文档无损拆成站点文章。

设计要点：
1. 只做结构搬家（切分 + 标题层级归一 + 加 front matter），不改动任何正文文字；
2. 每篇文章的片段区间都必须能还原出原文，构建时用整篇比对自证；
3. 原文没有标注日期，不编造时间线，统一用文档整理时间。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from scripts.config import (
    CODE_REPO_URL,
    CODE_SECTIONS,
    DROPPED_HEADINGS,
    OVERVIEW_RULE,
    POST_RULES,
    PostRule,
)

LOGGER = logging.getLogger(__name__)

HEADING_PATTERN = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$")
FENCE_PATTERN = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")

# 文章正文的最小标题层级。文章标题由 front matter 提供，
# 因此正文里的标题最多只能从二级开始。
BODY_MIN_HEADING_LEVEL = 2

POST_FOOTER_TEMPLATE = """

---

## 配套代码

本文对应的可运行工程：[{section}]({repo}/tree/main/{section})
"""


class SplitError(RuntimeError):
    """拆分规则与原文对不上时抛出，避免静默产出错乱内容。"""


@dataclass(frozen=True)
class Heading:
    line_index: int
    level: int
    text: str
    raw: str


@dataclass(frozen=True)
class Interval:
    """原文的某个左闭右开行区间。"""

    start: int
    end: int


@dataclass(frozen=True)
class BodyPiece:
    """一篇文章正文对应的原文区间。"""

    rule: PostRule
    interval: Interval


@dataclass(frozen=True)
class GeneratedFile:
    path: Path
    content: str


@dataclass
class BuildResult:
    files: list[GeneratedFile] = field(default_factory=list)
    source_bytes: int = 0
    verified_lossless: bool = False


class MarkdownScanner:
    """扫描标题行，自动跳过围栏代码块。

    代码块里以 # 开头的行是注释，不是标题，必须排除，
    否则下沉标题层级时会把 Python 注释一起改掉。
    """

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._headings = self._scan()

    @property
    def headings(self) -> list[Heading]:
        return list(self._headings)

    def _scan(self) -> list[Heading]:
        headings: list[Heading] = []
        fence_marker: str | None = None

        for index, line in enumerate(self._lines):
            fence = FENCE_PATTERN.match(line)
            if fence:
                marker = fence.group(1)[0]
                if fence_marker is None:
                    fence_marker = marker
                    continue
                if fence_marker == marker:
                    fence_marker = None
                    continue
            if fence_marker is not None:
                continue

            match = HEADING_PATTERN.match(line.rstrip("\r\n"))
            if match:
                headings.append(
                    Heading(
                        line_index=index,
                        level=len(match.group(1)),
                        text=match.group(2),
                        raw=line,
                    )
                )
        return headings

    def find_next(self, heading_line: str, start: int) -> int:
        """从 start 行开始找第一条与给定文本完全一致的标题行。"""
        needle = heading_line.strip()
        for heading in self._headings:
            if heading.line_index < start:
                continue
            if heading.raw.strip() == needle:
                return heading.line_index
        return -1

    def min_level_between(self, start: int, end: int) -> int | None:
        levels = [
            heading.level
            for heading in self._headings
            if start <= heading.line_index < end
        ]
        return min(levels) if levels else None


class SourceDocument:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.text = path.read_text(encoding="utf-8")
        self.lines = self.text.splitlines(keepends=True)
        self.scanner = MarkdownScanner(self.lines)

    def interval_lines(self, interval: Interval) -> list[str]:
        return self.lines[interval.start : interval.end]


class NotesSplitter:
    """按配置把总文档切成文章，并验证拆分无损。"""

    def __init__(self, document: SourceDocument) -> None:
        self._document = document

    def build(self) -> BuildResult:
        pieces = self._locate_body_pieces()
        dropped = self._locate_dropped_intervals()
        overview_intervals = self._complement(pieces, dropped)

        self._verify_partition(pieces, dropped, overview_intervals)

        result = BuildResult(source_bytes=len(self._document.text.encode("utf-8")))

        for piece in pieces:
            result.files.append(
                GeneratedFile(
                    path=self._post_path(piece.rule),
                    content=self._render_post(piece),
                )
            )

        result.files.append(
            GeneratedFile(
                path=self._overview_path(),
                content=self._render_overview(overview_intervals),
            )
        )

        result.verified_lossless = self._verify_reconstruction(
            pieces, dropped, overview_intervals
        )
        if not result.verified_lossless:
            raise SplitError("拆分结果无法还原原文，已中止写入")

        LOGGER.info(
            "拆分完成：%d 篇文章 + 1 个总览页，原文 %d 字节",
            len(pieces),
            result.source_bytes,
        )
        return result

    # ---- 定位 ----

    def _locate_body_pieces(self) -> list[BodyPiece]:
        scanner = self._document.scanner
        line_count = len(self._document.lines)
        pieces: list[BodyPiece] = []
        cursor = 0

        for rule in POST_RULES:
            start = scanner.find_next(rule.start_heading, cursor)
            if start < 0:
                raise SplitError(
                    f"找不到起点标题：{rule.start_heading!r}（{rule.slug}）"
                )

            if rule.end_heading is None:
                end = line_count
            else:
                end = scanner.find_next(rule.end_heading, start + 1)
                if end < 0:
                    raise SplitError(
                        f"找不到终点标题：{rule.end_heading!r}（{rule.slug}）"
                    )

            if end <= start:
                raise SplitError(f"区间为空：{rule.slug}")

            LOGGER.debug(
                "定位 %-28s 行 %d..%d（%d 行）",
                rule.slug,
                start + 1,
                end,
                end - start,
            )
            pieces.append(BodyPiece(rule=rule, interval=Interval(start, end)))
            cursor = end

        return pieces

    def _locate_dropped_intervals(self) -> list[Interval]:
        scanner = self._document.scanner
        line_count = len(self._document.lines)
        intervals: list[Interval] = []
        cursor = 0

        for heading in DROPPED_HEADINGS:
            start = scanner.find_next(heading, cursor)
            if start < 0:
                raise SplitError(f"找不到需要省略的标题：{heading!r}")

            end = start + 1
            while end < line_count and not self._document.lines[end].strip():
                end += 1

            intervals.append(Interval(start, end))
            cursor = end

        return intervals

    # ---- 校验 ----

    def _complement(
        self, pieces: list[BodyPiece], dropped: list[Interval]
    ) -> list[Interval]:
        claimed = [piece.interval for piece in pieces] + dropped
        claimed.sort(key=lambda item: item.start)

        line_count = len(self._document.lines)
        gaps: list[Interval] = []
        cursor = 0
        for interval in claimed:
            if interval.start > cursor:
                gaps.append(Interval(cursor, interval.start))
            cursor = max(cursor, interval.end)
        if cursor < line_count:
            gaps.append(Interval(cursor, line_count))
        return gaps

    def _verify_partition(
        self,
        pieces: list[BodyPiece],
        dropped: list[Interval],
        gaps: list[Interval],
    ) -> None:
        intervals = [piece.interval for piece in pieces] + dropped + gaps
        intervals.sort(key=lambda item: item.start)

        expected_start = 0
        for interval in intervals:
            if interval.start != expected_start:
                raise SplitError(
                    f"行区间不连续：期望从第 {expected_start + 1} 行开始，"
                    f"实际为第 {interval.start + 1} 行"
                )
            expected_start = interval.end

        if expected_start != len(self._document.lines):
            raise SplitError(
                f"行区间未覆盖全文：覆盖到第 {expected_start} 行，"
                f"全文共 {len(self._document.lines)} 行"
            )

    def _verify_reconstruction(
        self,
        pieces: list[BodyPiece],
        dropped: list[Interval],
        gaps: list[Interval],
    ) -> bool:
        """按原文顺序拼回所有区间，必须与原文逐字节一致。"""
        ordered: list[Interval] = (
            [piece.interval for piece in pieces] + dropped + gaps
        )
        ordered.sort(key=lambda item: item.start)
        rebuilt = "".join(
            "".join(self._document.interval_lines(interval)) for interval in ordered
        )
        if rebuilt != self._document.text:
            LOGGER.error("还原校验失败：拼接结果与原文不一致")
            return False
        LOGGER.debug("还原校验通过：%d 字节逐字节一致", len(rebuilt.encode("utf-8")))
        return True

    # ---- 渲染 ----

    def _post_path(self, rule: PostRule) -> Path:
        from scripts.config import POSTS_DIR

        return POSTS_DIR / f"{rule.slug}.md"

    def _overview_path(self) -> Path:
        from scripts.config import PAGES_DIR

        return PAGES_DIR / OVERVIEW_RULE.slug / "index.md"

    def _render_post(self, piece: BodyPiece) -> str:
        rule = piece.rule
        raw = self._document.interval_lines(piece.interval)
        body = self._normalize_headings(raw, piece.interval)
        body = _trim_blank_edges(body)

        parts = [self._post_front_matter(rule), body]
        if rule.code_section:
            section = CODE_SECTIONS[rule.code_section]
            parts.append(
                POST_FOOTER_TEMPLATE.format(section=section, repo=CODE_REPO_URL)
            )
        return "".join(parts).rstrip() + "\n"

    def _render_overview(self, intervals: list[Interval]) -> str:
        raw: list[str] = []
        for interval in intervals:
            raw.extend(self._document.interval_lines(interval))
        body = _trim_blank_edges(raw)
        front = _overview_front_matter()
        return (front + body).rstrip() + "\n"

    def _normalize_headings(self, raw: list[str], interval: Interval) -> str:
        """把正文标题整体上提到二级，并保持相对层级不变。"""
        min_level = self._document.scanner.min_level_between(
            interval.start, interval.end
        )
        if min_level is None:
            return "".join(raw)

        delta = min_level - BODY_MIN_HEADING_LEVEL
        if delta <= 0:
            return "".join(raw)

        shifted: list[str] = []
        fence_marker: str | None = None
        for line in raw:
            fence = FENCE_PATTERN.match(line)
            if fence:
                marker = fence.group(1)[0]
                if fence_marker is None:
                    fence_marker = marker
                elif fence_marker == marker:
                    fence_marker = None
                shifted.append(line)
                continue

            if fence_marker is not None:
                shifted.append(line)
                continue

            match = HEADING_PATTERN.match(line.rstrip("\r\n"))
            if match and len(match.group(1)) - delta >= BODY_MIN_HEADING_LEVEL:
                new_level = len(match.group(1)) - delta
                shifted.append("#" * new_level + line.lstrip("#"))
            else:
                shifted.append(line)

        return "".join(shifted)

    def _post_front_matter(self, rule: PostRule) -> str:
        tags = "\n".join(f"    - {_toml_string(tag)}" for tag in rule.tags)
        categories = "\n".join(
            f"    - {_toml_string(category)}" for category in rule.categories
        )
        return (
            "---\n"
            f"title: {_toml_string(rule.title)}\n"
            f"slug: {_toml_string(rule.slug)}\n"
            f"date: {rule.date}\n"
            f"lastmod: {rule.date}\n"
            f"description: {_toml_string(rule.description)}\n"
            f"weight: {rule.weight}\n"
            "categories:\n"
            f"{categories}\n"
            "tags:\n"
            f"{tags}\n"
            "---\n\n"
        )


def _overview_front_matter() -> str:
    return (
        "---\n"
        f"title: {_toml_string(OVERVIEW_RULE.title)}\n"
        f"slug: {_toml_string(OVERVIEW_RULE.slug)}\n"
        f"date: {OVERVIEW_RULE.date}\n"
        f"lastmod: {OVERVIEW_RULE.date}\n"
        f"description: {_toml_string(OVERVIEW_RULE.description)}\n"
        f"weight: {OVERVIEW_RULE.weight}\n"
        "---\n\n"
    )


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _trim_blank_edges(lines: list[str]) -> str:
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "".join(lines[start:end])
