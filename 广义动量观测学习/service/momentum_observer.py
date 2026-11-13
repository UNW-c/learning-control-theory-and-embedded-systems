"""广义动量观测器（一维）。

两种等价实现：

1) 影子动量形式（默认，数值更稳，全程无比分）
   p_hat += dt * (f + r)
   e = p - p_hat
   r = k * e

2) 约简形式（对应原伪代码）
   r_k = r_{k-1} + k * (p_k - p_{k-1} - f*dt - r_{k-1}*dt)

约简形式由影子形式消去 p_hat 得到，代数等价；
但约简形式每步用到 (p_k - p_{k-1})，速度噪声会被差分放大。
"""

import logging

import numpy as np

LOGGER = logging.getLogger(__name__)


class GeneralizedMomentumObserver:
    def __init__(
        self,
        gain_k: float,
        mass_model: float,
        dt: float,
        use_shadow_form: bool = True,
    ) -> None:
        if gain_k <= 0.0:
            raise ValueError("gain_k must be positive")
        if mass_model <= 0.0:
            raise ValueError("mass_model must be positive")
        if dt <= 0.0:
            raise ValueError("dt must be positive")

        self._k = gain_k
        self._m = mass_model
        self._dt = dt
        self._use_shadow = use_shadow_form
        self.reset()

    def reset(self) -> None:
        self._p_hat = 0.0
        self._r = 0.0
        self._p_prev = None
        self._f_prev = 0.0

    @property
    def gain(self) -> float:
        return self._k

    def step(self, v_meas: float, f_drive: float) -> tuple[float, float, float]:
        """单步更新，返回 (fe_hat, e, p_hat)。"""
        p = self._m * v_meas

        if self._use_shadow:
            fe_hat, e, p_hat = self._step_shadow(p, f_drive)
        else:
            fe_hat, e, p_hat = self._step_reduced(p, f_drive)

        self._p_prev = p
        self._f_prev = f_drive
        return fe_hat, e, p_hat

    def _step_shadow(self, p: float, f_drive: float) -> tuple[float, float, float]:
        # 用上一拍 r 积分影子动量，避免代数环
        self._p_hat += self._dt * (f_drive + self._r)
        e = p - self._p_hat
        self._r = self._k * e
        return self._r, e, self._p_hat

    def _step_reduced(self, p: float, f_drive: float) -> tuple[float, float, float]:
        # 原伪代码：rk_1 = rk + k*(pk_1 - pk - F*dt - rk*dt)
        if self._p_prev is None:
            self._p_prev = p
            return 0.0, 0.0, p

        dp = p - self._p_prev
        self._r = self._r + self._k * (dp - f_drive * self._dt - self._r * self._dt)
        # 约简形式不显式存 p_hat；用 p - e 反推，e = r/k
        e = self._r / self._k if self._k != 0.0 else 0.0
        p_hat = p - e
        return self._r, e, p_hat


def run_observer(
    observer: GeneralizedMomentumObserver,
    v_meas: np.ndarray,
    f_drive: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """对整段量测序列跑观测器。"""
    n = len(v_meas)
    fe_hat = np.zeros(n)
    e_hist = np.zeros(n)
    p_hat_hist = np.zeros(n)

    observer.reset()
    for i in range(n):
        fe_hat[i], e_hist[i], p_hat_hist[i] = observer.step(
            float(v_meas[i]), float(f_drive[i])
        )

    return fe_hat, e_hist, p_hat_hist


def direct_diff_force(
    v_meas: np.ndarray,
    f_drive: np.ndarray,
    mass: float,
    dt: float,
) -> np.ndarray:
    """对照：fe ≈ m * dv/dt - f（直接微分，噪声大）。"""
    n = len(v_meas)
    fe = np.zeros(n)
    if n < 2:
        return fe

    dv = np.diff(v_meas) / dt
    fe[1:] = mass * dv - f_drive[1:]
    fe[0] = fe[1]
    return fe
