from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SensorSequence:
    """一段同步采样的光流速度与加速度计数据，附带真值便于评估调参效果。"""

    time_s: np.ndarray
    dt: float
    accel_meas: np.ndarray
    flow_meas: np.ndarray
    velocity_true: np.ndarray
    accel_true: np.ndarray
    bias_true: np.ndarray

    def __post_init__(self) -> None:
        length = self.time_s.shape[0]
        for name in ("accel_meas", "flow_meas", "velocity_true", "accel_true", "bias_true"):
            value = getattr(self, name)
            if value.shape[0] != length:
                raise ValueError(f"{name} 长度与时间轴不一致")