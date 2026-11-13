"""将总文档同步为站点文章。

用法（在项目根目录执行）：

    python scripts/build_content.py            # 生成/更新文章
    python scripts/build_content.py --check    # 只校验，不写入，内容过期则退出码 1
    python scripts/build_content.py -v         # 输出定位与校验细节
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.config import MASTER_DOCUMENT  # noqa: E402
from scripts.notes_splitter import (  # noqa: E402
    BuildResult,
    NotesSplitter,
    SourceDocument,
    SplitError,
)

LOGGER = logging.getLogger("build_content")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="把学习文档同步为站点文章")
    parser.add_argument(
        "--check",
        action="store_true",
        help="只比对不写入，站点内容与原文不同步时返回退出码 1",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="输出拆分定位与无损校验细节",
    )
    return parser.parse_args(argv)


def check_files(result: BuildResult) -> list[Path]:
    """返回与生成结果不一致的文件列表。"""
    stale: list[Path] = []
    for generated in result.files:
        if not generated.path.exists():
            stale.append(generated.path)
            continue
        current = generated.path.read_text(encoding="utf-8")
        if current != generated.content:
            stale.append(generated.path)
    return stale


def write_files(result: BuildResult) -> None:
    for generated in result.files:
        generated.path.parent.mkdir(parents=True, exist_ok=True)
        generated.path.write_text(
            generated.content, encoding="utf-8", newline="\n"
        )
        LOGGER.info(
            "写入 %s（%d 行）",
            generated.path.relative_to(PROJECT_ROOT),
            generated.content.count("\n"),
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(message)s",
        stream=sys.stdout,
    )

    if not MASTER_DOCUMENT.exists():
        LOGGER.error("找不到总文档：%s", MASTER_DOCUMENT)
        return 2

    try:
        document = SourceDocument(MASTER_DOCUMENT)
        result = NotesSplitter(document).build()
    except SplitError as error:
        LOGGER.error("拆分失败：%s", error)
        return 3

    if not result.verified_lossless:
        LOGGER.error("无损校验未通过，未写入任何文件")
        return 4

    if args.check:
        stale = check_files(result)
        if stale:
            LOGGER.error("以下文件与总文档不同步：")
            for path in stale:
                LOGGER.error("  %s", path.relative_to(PROJECT_ROOT))
            return 1
        LOGGER.info("校验通过：站点内容与总文档一致")
        return 0

    write_files(result)
    LOGGER.info("完成：共 %d 个文件", len(result.files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
