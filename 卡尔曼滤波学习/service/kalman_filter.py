from abc import ABC, abstractmethod

import numpy as np

from config.settings import KalmanConfig

MIN_COVARIANCE = 1.0e-12


class IKalmanFilter(ABC):
    """离散卡尔曼滤波契约：预测使用控制量，更新使用观测量。"""

    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_process_noise(self, q_velocity: float, q_bias: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_measurement_noise(self, r_flow: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def predict(self, accel_meas: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def update(self, flow_meas: float) -> None:
        raise NotImplementedError

    @abstractmethod
    def state_vector(self) -> np.ndarray:
        raise NotImplementedError


class VelocityBiasKalmanFilter(IKalmanFilter):
    """光流速度 + 加速度计融合的二维卡尔曼滤波。

    状态: x = [v, b]^T
      v: 沿运动轴的速度
      b: 加速度计缓变偏置

    预测模型（欧拉离散）:
      v_k = v_{k-1} + dt * (a_meas - b_{k-1})
      b_k = b_{k-1}
    因此:
      F = [[1, -dt], [0, 1]]
      B = [[dt], [0]]
      u = a_meas

    观测模型:
      z = v + noise_flow
      H = [[1, 0]]

    原始伪代码里 F 的 (1,2) 项写成了 +dt。若偏置定义为
    a_meas = a_true + b，预测时必须扣除 b，故这里使用 -dt。
    """

    def __init__(self, dt: float, config: KalmanConfig) -> None:
        if dt <= 0.0:
            raise ValueError("dt 必须为正")
        self._dt = dt
        self._config = config
        self._f = np.array([[1.0, -dt], [0.0, 1.0]], dtype=float)
        self._b = np.array([[dt], [0.0]], dtype=float)
        self._h = np.array([[1.0, 0.0]], dtype=float)
        self._i = np.eye(2)
        self._q = np.zeros((2, 2), dtype=float)
        self._r = np.zeros((1, 1), dtype=float)
        self._x = np.zeros((2, 1), dtype=float)
        self._p = np.eye(2, dtype=float)
        self.set_process_noise(config.q_velocity, config.q_bias)
        self.set_measurement_noise(config.r_flow)
        self.reset()

    def reset(self) -> None:
        self._x = np.array([[self._config.v0], [self._config.b0]], dtype=float)
        self._p = np.diag([self._config.p0_velocity, self._config.p0_bias]).astype(float)

    def set_process_noise(self, q_velocity: float, q_bias: float) -> None:
        self._q = np.diag(
            [
                max(float(q_velocity), MIN_COVARIANCE),
                max(float(q_bias), MIN_COVARIANCE),
            ]
        )

    def set_measurement_noise(self, r_flow: float) -> None:
        self._r[0, 0] = max(float(r_flow), MIN_COVARIANCE)

    def predict(self, accel_meas: float) -> None:
        control = np.array([[float(accel_meas)]], dtype=float)
        self._x = self._f @ self._x + self._b @ control
        self._p = self._f @ self._p @ self._f.T + self._q

    def update(self, flow_meas: float) -> None:
        innovation = float(flow_meas) - float((self._h @ self._x).item())
        innovation_cov = float((self._h @ self._p @ self._h.T + self._r).item())
        kalman_gain = (self._p @ self._h.T) / innovation_cov
        self._x = self._x + kalman_gain * innovation
        identity_minus_kh = self._i - kalman_gain @ self._h
        self._p = identity_minus_kh @ self._p @ identity_minus_kh.T + kalman_gain @ self._r @ kalman_gain.T

    def state_vector(self) -> np.ndarray:
        return self._x.copy()

    @property
    def velocity(self) -> float:
        return float(self._x[0, 0])

    @property
    def bias(self) -> float:
        return float(self._x[1, 0])