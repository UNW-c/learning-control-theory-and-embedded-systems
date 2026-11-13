from dataclasses import dataclass, field


@dataclass(frozen=True)
class SimulationConfig:
    """仿真与传感器噪声相关配置，全部外部化，避免硬编码进算法。"""

    dt: float = 0.02
    duration_s: float = 20.0
    seed: int = 42
    accel_noise_std: float = 0.18
    flow_noise_std: float = 0.28
    bias_initial: float = 0.35
    bias_random_walk_std: float = 0.015
    initial_velocity: float = 0.0


@dataclass
class KalmanConfig:
    """卡尔曼滤波可调参数。Q 为对角过程噪声，R 为光流量测噪声。"""

    q_velocity: float = 1.0e-2
    q_bias: float = 1.0e-4
    r_flow: float = 1.0e-1
    p0_velocity: float = 1.0
    p0_bias: float = 1.0
    v0: float = 0.0
    b0: float = 0.0


@dataclass(frozen=True)
class SliderRange:
    """对数滑条范围，值为 log10(协方差参数)。"""

    log_min: float
    log_max: float
    label: str


@dataclass(frozen=True)
class UiConfig:
    q_velocity_slider: SliderRange = field(
        default_factory=lambda: SliderRange(-6.0, 1.0, "Qv 速度过程噪声")
    )
    q_bias_slider: SliderRange = field(
        default_factory=lambda: SliderRange(-8.0, 0.0, "Qb 偏置过程噪声")
    )
    r_flow_slider: SliderRange = field(
        default_factory=lambda: SliderRange(-4.0, 1.5, "R 光流量测噪声")
    )
    window_title: str = "光流-加速度计 卡尔曼滤波调参"
    figure_size: tuple = (14.8, 8.6)
    play_interval_ms: int = 40
    play_frames: int = 250