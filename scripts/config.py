"""学习文档拆分规则配置。

本模块只存数据，不含逻辑：把“哪一段原文变成哪一篇文章”这件事集中在一处，
方便增补专题时只改这里，不碰切分代码。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# 工作区根目录（scripts/ 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parents[1]

MASTER_DOCUMENT = PROJECT_ROOT / "控制算法学习.md"
COMMS_DOCUMENT_PATH = PROJECT_ROOT / "嵌入式通信学习.md"
CONTENT_ROOT = PROJECT_ROOT / "content"
POSTS_DIR = CONTENT_ROOT / "posts"
PAGES_DIR = CONTENT_ROOT / "page"

# 所有文章统一的整理日期。原文没有标注写作日期，
# 这里用总文档的整理时间，避免编造时间线。
DEFAULT_POST_DATE = "2026-09-16"
COMMS_POST_DATE = "2026-11-15"

# 专题代码目录 -> GitHub 仓库内路径，用于文章末尾的“配套代码”链接。
CODE_REPO_URL = "https://github.com/UNW-c/learning-control-theory-and-embedded-systems"

CODE_SECTIONS: dict[str, str] = {
    "kalman": "卡尔曼滤波学习",
    "momentum": "广义动量观测学习",
}


@dataclass(frozen=True)
class PostRule:
    """一篇站点文章与原文片段的对应关系。

    区间为左闭右开：从 start_heading 所在行开始，
    到 end_heading 所在行之前结束。
    """

    title: str
    slug: str
    description: str
    start_heading: str
    end_heading: str | None
    tags: tuple[str, ...]
    code_section: str | None
    weight: int

    categories: tuple[str, ...] = ("控制理论",)
    date: str = DEFAULT_POST_DATE


@dataclass(frozen=True)
class OverviewRule:
    """总览页：收录未被任何专题文章认领的原文片段。"""

    title: str
    slug: str
    description: str
    weight: int
    date: str = DEFAULT_POST_DATE


@dataclass(frozen=True)
class DocumentSet:
    """一份源文档，以及它拆成站内文章的规则。"""

    label: str
    path: Path
    post_rules: tuple[PostRule, ...]
    dropped_headings: tuple[str, ...]
    overview: OverviewRule | None


# 专题文章按学习顺序排列，weight 决定站点首页的先后
POST_RULES: tuple[PostRule, ...] = (
    PostRule(
        title="卡尔曼滤波（一）：到底解决什么问题",
        slug="kalman-1-what-problem",
        description="光流抖，加速度计积分会漂，只能合起来估速度。合到最后就是个互补滤波。",
        start_heading="### 问题",
        end_heading="### 从高斯最优估计推出互补滤波形式（标量）",
        tags=("卡尔曼滤波", "互补滤波", "状态估计"),
        code_section="kalman",
        weight=1,
    ),
    PostRule(
        title="卡尔曼滤波（二）：从高斯最优估计推出五大公式",
        slug="kalman-2-derivation",
        description="一次融合算出来的就是互补滤波，再把它撑成能一直跑下去的递推。",
        start_heading="### 从高斯最优估计推出互补滤波形式（标量）",
        end_heading="### 卡尔曼滤波设计步骤",
        tags=("卡尔曼滤波", "高斯分布", "协方差", "推导"),
        code_section="kalman",
        weight=2,
    ),
    PostRule(
        title="卡尔曼滤波（三）：设计步骤与光流加速度落地",
        slug="kalman-3-design-and-tuning",
        description="五个公式在设计里怎么用，光流加加速度计这套怎么跑起来、怎么调。",
        start_heading="### 卡尔曼滤波设计步骤",
        end_heading="## 专题二：广义动量观测",
        tags=("卡尔曼滤波", "光流", "调参", "工程实现"),
        code_section="kalman",
        weight=3,
    ),
    PostRule(
        title="广义动量观测（一）：核心思路与一维推导",
        slug="momentum-1-one-dof",
        description="拿可测的动量搭个影子系统，外力观测变成比例反馈，连续和离散都推了一遍。",
        start_heading="### 问题",
        end_heading="### 多自由度推广（n 维刚体 / 机械臂）",
        tags=("广义动量观测", "观测器", "力估计", "一维推导"),
        code_section="momentum",
        weight=4,
    ),
    PostRule(
        title="广义动量观测（二）：多自由度推广与设计要点",
        slug="momentum-2-multi-dof",
        description="一维的结论搬到多维刚体和机械臂上，增益怎么取、模型误差怎么办，跟直接微分差在哪。",
        start_heading="### 多自由度推广（n 维刚体 / 机械臂）",
        end_heading="## 后续专题预留",
        tags=("广义动量观测", "多自由度", "机械臂", "设计要点"),
        code_section="momentum",
        weight=5,
    ),
)

OVERVIEW_RULE = OverviewRule(
    title="总览与学习路线",
    slug="overview",
    description="这里放哪些笔记，以及从反馈到最优控制这一段怎么走。",
    weight=0,
)

# 这些标题行的信息已经由站点页面标题承担，正文里不再重复出现。
# 判定方式为整行精确匹配（忽略行尾空白）。
DROPPED_HEADINGS: tuple[str, ...] = (
    "# 控制算法学习",
    "## 专题一：卡尔曼滤波学习",
    "## 专题二：广义动量观测",
)

# 嵌入式通信这篇的开头是文档级引言，并进第一篇文章。
# 起点用 @lead 标记，指向标题之后的第一行正文，改了引言措辞也不用动这里。
COMMS_POST_RULES: tuple[PostRule, ...] = (
    PostRule(
        title="嵌入式通信（一）：MQTT 与 IPC",
        slug="comms-1-mqtt-ipc",
        description="MQTT 的报文怎么到订阅端，板子上的队列怎么把数据递给另一个任务。",
        start_heading="@lead",
        end_heading="## 从设计原则出发",
        tags=("MQTT", "IPC", "发布订阅"),
        code_section=None,
        weight=6,
        categories=("嵌入式开发",),
        date=COMMS_POST_DATE,
    ),
    PostRule(
        title="嵌入式通信（二）：broker、topic 与 QoS",
        slug="comms-2-broker-topic-qos",
        description="broker 记什么、topic 怎么分层、QoS 三档怎么选，末尾一个完整的客户端。",
        start_heading="## 从设计原则出发",
        end_heading="## TCP",
        tags=("MQTT", "broker", "QoS", "遗嘱"),
        code_section=None,
        weight=7,
        categories=("嵌入式开发",),
        date=COMMS_POST_DATE,
    ),
    PostRule(
        title="嵌入式通信（三）：TCP 与自定义协议",
        slug="comms-3-tcp",
        description="三次握手四次挥手，字节流怎么切帧，CRC 和粘包各怎么处理。",
        start_heading="## TCP",
        end_heading="## UDP",
        tags=("TCP", "自定义协议", "粘包", "CRC"),
        code_section=None,
        weight=8,
        categories=("嵌入式开发",),
        date=COMMS_POST_DATE,
    ),
    PostRule(
        title="嵌入式通信（四）：UDP 与 socket",
        slug="comms-4-udp-socket",
        description="UDP 的数据报和广播，socket 的调用，还有 Linux 下的 SocketCAN。",
        start_heading="## UDP",
        end_heading=None,
        tags=("UDP", "socket", "SocketCAN"),
        code_section=None,
        weight=9,
        categories=("嵌入式开发",),
        date=COMMS_POST_DATE,
    ),
)

COMMS_DROPPED_HEADINGS: tuple[str, ...] = ("# 嵌入式通信学习",)

CONTROL_DOCUMENT = DocumentSet(
    label="控制算法学习",
    path=MASTER_DOCUMENT,
    post_rules=POST_RULES,
    dropped_headings=DROPPED_HEADINGS,
    overview=OVERVIEW_RULE,
)

COMMS_DOCUMENT = DocumentSet(
    label="嵌入式通信学习",
    path=COMMS_DOCUMENT_PATH,
    post_rules=COMMS_POST_RULES,
    dropped_headings=COMMS_DROPPED_HEADINGS,
    overview=None,
)

# 站点内容按这里的顺序生成，先控制理论，再嵌入式
DOCUMENTS: tuple[DocumentSet, ...] = (CONTROL_DOCUMENT, COMMS_DOCUMENT)
