import logging

import numpy as np

from config.settings import KalmanConfig
from model.filter_result import FilterResult
from model.sensor_data import SensorSequence
from service.kalman_filter import VelocityBiasKalmanFilter
from service.metrics import rmse

LOGGER = logging.getLogger(__name__)


class FlowAccelFusionService:
    """在完整时间序列上跑通预测-更新循环，并给出对比曲线。"""

    def run(self, sequence: SensorSequence, kalman_config: KalmanConfig) -> FilterResult:
        filt = VelocityBiasKalmanFilter(dt=sequence.dt, config=kalman_config)
        sample_count = sequence.time_s.shape[0]
        velocity_filtered = np.empty(sample_count, dtype=float)
        bias_filtered = np.empty(sample_count, dtype=float)
        velocity_integrated = np.empty(sample_count, dtype=float)

        integrated = 0.0
        for index in range(sample_count):
            accel = float(sequence.accel_meas[index])
            flow = float(sequence.flow_meas[index])
            filt.predict(accel)
            filt.update(flow)
            velocity_filtered[index] = filt.velocity
            bias_filtered[index] = filt.bias
            integrated += accel * sequence.dt
            velocity_integrated[index] = integrated

        result = FilterResult(
            velocity_filtered=velocity_filtered,
            bias_filtered=bias_filtered,
            velocity_accel_integrated=velocity_integrated,
            velocity_rmse=rmse(velocity_filtered, sequence.velocity_true),
            bias_rmse=rmse(bias_filtered, sequence.bias_true),
            flow_rmse=rmse(sequence.flow_meas, sequence.velocity_true),
            accel_integrated_rmse=rmse(velocity_integrated, sequence.velocity_true),
        )
        LOGGER.debug(
            "滤波完成: vel_rmse=%.4f bias_rmse=%.4f qv=%.3e qb=%.3e r=%.3e",
            result.velocity_rmse,
            result.bias_rmse,
            kalman_config.q_velocity,
            kalman_config.q_bias,
            kalman_config.r_flow,
        )
        return result