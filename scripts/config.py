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
CONTENT_ROOT = PROJECT_ROOT / "content"
POSTS_DIR = CONTENT_ROOT / "posts"
PAGES_DIR = CONTENT_ROOT / "page"

# 所有文章统一的整理日期。原文没有标注写作日期，
# 这里用总文档的整理时间，避免编造时间线。
DEFAULT_POST_DATE = "2026-09-16"

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


# 专题文章按学习顺序排列，weight 决定站点首页的先后
POST_RULES: tuple[PostRule, ...] = (
    PostRule(
        title="卡尔曼滤波（一）：到底解决什么问题",
        slug="kalman-1-what-problem",
        description="从光流与加速度计的矛盾出发，说明卡尔曼滤波要解决的是加权融合，本质是互补滤波。",
        start_heading="### 问题",
        end_heading="### 从高斯最优估计推出互补滤波形式（标量）",
        tags=("卡尔曼滤波", "互补滤波", "状态估计"),
        code_section="kalman",
        weight=1,
    ),
    PostRule(
        title="卡尔曼滤波（二）：从高斯最优估计推出五大公式",
        slug="kalman-2-derivation",
        description="标量情形下先证“后验均值即最优估计”，再把互补滤波形式推广成完整的预测与更新递推。",
        start_heading="### 从高斯最优估计推出互补滤波形式（标量）",
        end_heading="### 卡尔曼滤波设计步骤",
        tags=("卡尔曼滤波", "高斯分布", "协方差", "推导"),
        code_section="kalman",
        weight=2,
    ),
    PostRule(
        title="卡尔曼滤波（三）：设计步骤与光流加速度落地",
        slug="kalman-3-design-and-tuning",
        description="把五大公式落成一套可执行的设计流程，并在光流加加速度计的例子上给出运行与调参顺序。",
        start_heading="### 卡尔曼滤波设计步骤",
        end_heading="## 专题二：广义动量观测",
        tags=("卡尔曼滤波", "光流", "调参", "工程实现"),
        code_section="kalman",
        weight=3,
    ),
    PostRule(
        title="广义动量观测（一）：核心思路与一维推导",
        slug="momentum-1-one-dof",
        description="用可测动量构造影子系统，把外力观测问题变成一个比例反馈的误差收敛问题，并给出连续与离散形式。",
        start_heading="### 问题",
        end_heading="### 多自由度推广（n 维刚体 / 机械臂）",
        tags=("广义动量观测", "观测器", "力估计", "一维推导"),
        code_section="momentum",
        weight=4,
    ),
    PostRule(
        title="广义动量观测（二）：多自由度推广与设计要点",
        slug="momentum-2-multi-dof",
        description="把一维结论推广到多维刚体与机械臂，讨论增益选择、模型误差，以及与直接微分和卡尔曼滤波的关系。",
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
    description="两个母题（控制理论、嵌入式开发）的定位，以及从反馈到最优控制的学习顺序。",
    weight=0,
)

# 这些标题行的信息已经由站点页面标题承担，正文里不再重复出现。
# 判定方式为整行精确匹配（忽略行尾空白）。
DROPPED_HEADINGS: tuple[str, ...] = (
    "# 控制算法学习",
    "## 专题一：卡尔曼滤波学习",
    "## 专题二：广义动量观测",
)
