from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FilterResult:
    """一次完整滤波的输出，包含对比所需的积分速度与误差指标。"""

    velocity_filtered: np.ndarray
    bias_filtered: np.ndarray
    velocity_accel_integrated: np.ndarray
    velocity_rmse: float
    bias_rmse: float
    flow_rmse: float
    accel_integrated_rmse: float