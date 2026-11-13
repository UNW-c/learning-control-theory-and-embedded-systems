"""仿真与观测器配置。"""

from dataclasses import dataclass
from enum import Enum


class ForceScenario(str, Enum):
    """外部力 fe 的典型波形。"""

    STEP = "阶跃"
    SINE = "正弦"
    SQUARE = "方波"
    PULSE = "脉冲串"


@dataclass
class PlantConfig:
    """被控对象（真值系统）参数。"""

    mass_true: float = 1.0
    duration: float = 20.0
    dt: float = 0.002
    drive_amplitude: float = 0.5
    drive_frequency: float = 0.3
    fe_amplitude: float = 2.0
    fe_frequency: float = 0.25
    velocity_noise_std: float = 0.01
    scenario: ForceScenario = ForceScenario.SINE


@dataclass
class ObserverConfig:
    """广义动量观测器参数。"""

    gain_k: float = 10.0
    mass_model: float = 1.0
    # True: 影子动量积分形式（数值更稳）
    # False: 约简形式（对应原伪代码 rk_1 = rk + k*(p_k - p_prev - F*dt - r*dt)）
    use_shadow_form: bool = True
