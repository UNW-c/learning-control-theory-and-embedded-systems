"""一维刚体真值系统：生成速度、动量与外部力真值。"""

import logging

import numpy as np

from config.settings import ForceScenario, PlantConfig

LOGGER = logging.getLogger(__name__)


class RigidBodyPlant:
    """m * a = f_drive + fe，欧拉积分得到 v、p。"""

    def __init__(self, config: PlantConfig, seed: int | None = 0) -> None:
        self._config = config
        self._rng = np.random.default_rng(seed)

    def generate(self) -> tuple[np.ndarray, ...]:
        cfg = self._config
        dt = cfg.dt
        n = int(round(cfg.duration / dt)) + 1
        t = np.arange(n) * dt

        f_drive = cfg.drive_amplitude * np.sin(2 * np.pi * cfg.drive_frequency * t)
        fe_true = self._external_force(t)

        # 真值积分：a = (f + fe) / m
        v = np.zeros(n)
        accel = (f_drive + fe_true) / cfg.mass_true
        for i in range(1, n):
            v[i] = v[i - 1] + accel[i - 1] * dt

        p_true = cfg.mass_true * v
        v_meas = v + self._rng.normal(0.0, cfg.velocity_noise_std, size=n)

        LOGGER.debug(
            "plant generated n=%d dt=%.4f scenario=%s",
            n,
            dt,
            cfg.scenario.value,
        )
        return t, v, v_meas, p_true, f_drive, fe_true

    def _external_force(self, t: np.ndarray) -> np.ndarray:
        cfg = self._config
        amp = cfg.fe_amplitude
        freq = cfg.fe_frequency

        if cfg.scenario == ForceScenario.STEP:
            fe = np.where(t >= 2.0, amp, 0.0)
        elif cfg.scenario == ForceScenario.SINE:
            fe = amp * np.sin(2 * np.pi * freq * t)
        elif cfg.scenario == ForceScenario.SQUARE:
            fe = amp * np.sign(np.sin(2 * np.pi * freq * t))
        elif cfg.scenario == ForceScenario.PULSE:
            period = 1.0 / max(freq, 1e-6)
            phase = np.mod(t, period)
            fe = np.where(phase < 0.15 * period, amp, 0.0)
        else:
            raise ValueError(f"unknown scenario: {cfg.scenario}")

        return fe
