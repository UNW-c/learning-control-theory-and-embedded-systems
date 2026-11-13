"""仿真与观测结果的数据结构，以及调 k 诊断指标。"""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class TuningDiagnosis:
    """面向调参学习的诊断：只依赖仿真里能看到的量。"""

    k: float
    dt: float
    tau: float
    k_dt: float
    rmse: float
    mae: float
    lag_score: float
    noise_score: float
    fe_rms: float
    settle_time: float | None
    advice: str
    level: str  # ok / lag / noisy / unstable / model


@dataclass
class SimulationResult:
    """一次完整仿真的时间序列结果。"""

    t: np.ndarray
    v_true: np.ndarray
    v_meas: np.ndarray
    p_true: np.ndarray
    p_meas: np.ndarray
    f_drive: np.ndarray
    fe_true: np.ndarray
    fe_hat: np.ndarray
    fe_direct: np.ndarray
    e_momentum: np.ndarray
    p_hat: np.ndarray

    def metrics(self) -> dict[str, float]:
        """稳态误差指标：忽略前 10% 作为收敛段。"""
        n = len(self.t)
        skip = max(1, n // 10)
        err = self.fe_hat[skip:] - self.fe_true[skip:]
        return {
            "rmse": float(np.sqrt(np.mean(err**2))),
            "mae": float(np.mean(np.abs(err))),
            "max_abs": float(np.max(np.abs(err))),
        }

    def diagnose(
        self,
        k: float,
        dt: float,
        mass_model: float,
        mass_true: float,
    ) -> TuningDiagnosis:
        """根据 fe 真值 vs fe_hat 判断 k：滞后、噪声、离散稳定、模型偏差。"""
        m = self.metrics()
        tau = 1.0 / k if k > 0 else float("inf")
        k_dt = k * dt

        # 滞后：相关峰值时移，或误差与 |fe| 的比值
        lag_score = self._lag_score()

        # 噪声：估计中高频能量（相邻差分 RMS），归一到 fe 幅值
        fe_rms = float(np.sqrt(np.mean(self.fe_true**2))) + 1e-9
        noise_score = self._noise_score() / fe_rms

        settle = self._step_settle_time()

        level, advice = self._judge(
            k_dt=k_dt,
            lag_score=lag_score,
            noise_score=noise_score,
            rmse=m["rmse"],
            fe_rms=fe_rms,
            mass_model=mass_model,
            mass_true=mass_true,
            tau=tau,
        )

        return TuningDiagnosis(
            k=k,
            dt=dt,
            tau=tau,
            k_dt=k_dt,
            rmse=m["rmse"],
            mae=m["mae"],
            lag_score=lag_score,
            noise_score=noise_score,
            fe_rms=fe_rms,
            settle_time=settle,
            advice=advice,
            level=level,
        )

    def _lag_score(self) -> float:
        """用互相关估计归一化滞后（0 附近最好，偏大表示跟踪慢）。"""
        n = len(self.t)
        skip = max(1, n // 10)
        a = self.fe_true[skip:]
        b = self.fe_hat[skip:]
        if a.size < 8:
            return 0.0

        a = a - np.mean(a)
        b = b - np.mean(b)
        denom = float(np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12
        max_shift = min(a.size // 4, int(0.5 / max(self.t[1] - self.t[0], 1e-9)))
        best_corr = -1.0
        best_shift = 0
        for s in range(0, max_shift + 1):
            # fe_hat 滞后 L 时：true(t) 与 hat(t+s) 对齐，s≈L
            if s == 0:
                corr = float(np.dot(a, b) / denom)
            else:
                corr = float(np.dot(a[:-s], b[s:]) / denom)
            if corr > best_corr:
                best_corr = corr
                best_shift = s

        dt = float(self.t[1] - self.t[0]) if n > 1 else 1.0
        # 以时间常数归一：滞后时间 / tau 在 score 里由调用方结合 k 解释
        return best_shift * dt

    def _noise_score(self) -> float:
        """fe_hat 相邻差分 RMS，反映高频抖动。"""
        n = len(self.t)
        skip = max(1, n // 10)
        d = np.diff(self.fe_hat[skip:])
        if d.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(d**2)))

    def _step_settle_time(self) -> float | None:
        """阶跃场景：fe_hat 进入并停留在真值 ±5% 带内的时间。"""
        t = self.t
        fe = self.fe_true
        hat = self.fe_hat
        # 找最后一个明显跳变沿
        dfe = np.abs(np.diff(fe))
        if dfe.size == 0:
            return None
        idx = np.where(dfe > 0.3 * (np.max(dfe) + 1e-12))[0]
        if idx.size == 0:
            return None
        edge = int(idx[0])
        target = float(fe[min(edge + 1, len(fe) - 1)])
        if abs(target) < 1e-6:
            return None

        n = len(t)
        # 噪声底：只用信号末段 20% 估计，避免把阶跃瞬态算进噪声
        tail0 = edge + max(1, (n - edge) // 5)
        if n - tail0 > 2:
            hf = float(np.std(np.diff(hat[tail0:])))
        else:
            hf = 0.0
        band = max(0.10 * abs(target), 3.0 * hf, 1e-6)
        dt = float(t[1] - t[0]) if n > 1 else 1.0
        # 首次进入带内并连续保持 confirm 时长，才算稳定
        confirm = max(5, int(0.05 / max(dt, 1e-9)))
        in_band = np.abs(hat - target) <= band
        for i in range(edge + 1, n - confirm):
            if np.all(in_band[i : i + confirm]):
                return float(t[i] - t[edge])
        return None

    def _judge(
        self,
        k_dt: float,
        lag_score: float,
        noise_score: float,
        rmse: float,
        fe_rms: float,
        mass_model: float,
        mass_true: float,
        tau: float,
    ) -> tuple[str, str]:
        mass_err = abs(mass_model - mass_true) / max(mass_true, 1e-9)

        if k_dt >= 0.2:
            return (
                "unstable",
                f"k*dt={k_dt:.3f} 过大，离散不稳风险高。减小 k 或 dt（建议 k*dt<0.1）。",
            )

        # 模型偏差主导：质量差 >5% 且相对误差仍大
        rel_rmse = rmse / max(fe_rms, 1e-9)
        if mass_err > 0.05 and rel_rmse > 0.35:
            return (
                "model",
                f"模型质量偏差 {mass_err*100:.0f}%，先修 m，再调 k。",
            )

        # 跟踪误差大、但噪声还不大 → 优先增大 k
        if rel_rmse > 0.35 and noise_score < 0.20 * fe_rms:
            return (
                "lag",
                f"跟踪误差偏大(RMSE={rmse:.3f} N)，噪声不大。增大 k（当前 τ={tau*1000:.0f} ms）。",
            )

        # 滞后明显：滞后时间接近或超过 tau
        if lag_score > 1.5 * tau and rel_rmse > 0.25:
            return (
                "lag",
                f"滞后偏大（约 {lag_score*1000:.0f} ms，τ={tau*1000:.0f} ms）。增大 k。",
            )

        if noise_score > 0.35 * fe_rms and k_dt >= 0.05:
            return (
                "noisy",
                f"噪声偏大（差分RMS={noise_score:.3f}）。减小 k，或降低速度噪声。",
            )

        if lag_score > 1.2 * tau and rel_rmse > 0.2:
            return (
                "lag",
                f"跟踪略滞后（{lag_score*1000:.0f} ms）。可略增大 k。",
            )

        if noise_score > 0.25 * fe_rms:
            return (
                "noisy",
                f"估计偏毛刺。可略减小 k，或先滤速度噪声。",
            )

        return (
            "ok",
            f"折中尚可。τ={tau*1000:.0f} ms，k*dt={k_dt:.3f}。继续在滞后/噪声间微调。",
        )


@dataclass
class SliderSpec:
    label: str
    log_min: float
    log_max: float
    initial: float


@dataclass
class UiConfig:
    figure_size: tuple[float, float] = (12.5, 8.2)
    window_title: str = "广义动量观测 | 调 k 学习"
    play_interval_ms: int = 30
    k_slider: SliderSpec = field(
        default_factory=lambda: SliderSpec("log10(k)", -1.0, 3.0, 1.0)
    )
    noise_slider: SliderSpec = field(
        default_factory=lambda: SliderSpec("log10(速度噪声)", -4.0, 0.0, -2.0)
    )
    mass_slider: SliderSpec = field(
        default_factory=lambda: SliderSpec("质量 m (模型)", 0.2, 5.0, 1.0)
    )
