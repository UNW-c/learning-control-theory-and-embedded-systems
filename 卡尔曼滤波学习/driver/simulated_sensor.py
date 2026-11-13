import logging

import numpy as np

from config.settings import SimulationConfig
from driver.sensor_source import ISensorSource
from model.sensor_data import SensorSequence

LOGGER = logging.getLogger(__name__)


class SimulatedFlowAccelSource(ISensorSource):
    """生成一维运动下的光流速度与加速度计观测。

    设计意图：
    - 真值加速度分段变化，便于观察跟踪滞后与过冲
    - 加速度计含常值偏置与随机游走，积分后会明显漂移
    - 光流直接观测速度，无偏但噪声更大
    """

    def generate(self, config: SimulationConfig) -> SensorSequence:
        rng = np.random.default_rng(config.seed)
        sample_count = int(round(config.duration_s / config.dt))
        time_s = np.arange(sample_count, dtype=float) * config.dt
        accel_true = self._build_true_acceleration(time_s)
        velocity_true = self._integrate_euler(accel_true, config.dt, config.initial_velocity)
        bias_true = self._build_true_bias(sample_count, config, rng)
        accel_noise = rng.normal(0.0, config.accel_noise_std, size=sample_count)
        flow_noise = rng.normal(0.0, config.flow_noise_std, size=sample_count)
        accel_meas = accel_true + bias_true + accel_noise
        flow_meas = velocity_true + flow_noise
        LOGGER.info(
            "已生成仿真数据: samples=%s dt=%.4f seed=%s",
            sample_count,
            config.dt,
            config.seed,
        )
        return SensorSequence(
            time_s=time_s,
            dt=config.dt,
            accel_meas=accel_meas,
            flow_meas=flow_meas,
            velocity_true=velocity_true,
            accel_true=accel_true,
            bias_true=bias_true,
        )

    @staticmethod
    def _build_true_acceleration(time_s: np.ndarray) -> np.ndarray:
        accel = np.zeros_like(time_s)
        accel += 1.8 * ((time_s >= 2.0) & (time_s < 5.0))
        accel += -1.6 * ((time_s >= 8.0) & (time_s < 10.5))
        osc_mask = (time_s >= 12.0) & (time_s < 16.5)
        accel += 1.3 * np.sin(2.0 * np.pi * 0.5 * time_s) * osc_mask
        accel += 2.4 * ((time_s >= 17.2) & (time_s < 17.6))
        return accel

    @staticmethod
    def _build_true_bias(
        sample_count: int,
        config: SimulationConfig,
        rng: np.random.Generator,
    ) -> np.ndarray:
        walk_step = config.bias_random_walk_std * np.sqrt(config.dt)
        increments = rng.normal(0.0, walk_step, size=sample_count)
        increments[0] = 0.0
        slow_wave = 0.04 * np.sin(2.0 * np.pi * 0.03 * np.arange(sample_count) * config.dt)
        return config.bias_initial + np.cumsum(increments) + slow_wave

    @staticmethod
    def _integrate_euler(accel: np.ndarray, dt: float, initial_velocity: float) -> np.ndarray:
        velocity = np.empty_like(accel)
        velocity[0] = initial_velocity + accel[0] * dt
        for index in range(1, accel.shape[0]):
            velocity[index] = velocity[index - 1] + accel[index] * dt
        return velocity