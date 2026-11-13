"""面向调 k 学习的实时 UI：曲线 + 诊断面板 + 滞后/噪声反馈。"""

import logging
from math import log10

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch
from matplotlib.widgets import Button, RadioButtons, Slider

from config.settings import ForceScenario
from controller.simulation_controller import SimulationController
from model.data import TuningDiagnosis, UiConfig

LOGGER = logging.getLogger(__name__)

LEVEL_COLOR = {
    "ok": "#27ae60",
    "lag": "#e67e22",
    "noisy": "#c0392b",
    "unstable": "#8e44ad",
    "model": "#2980b9",
}

LEVEL_TITLE = {
    "ok": "折中尚可",
    "lag": "滞后偏大",
    "noisy": "噪声偏大",
    "unstable": "离散不稳风险",
    "model": "模型偏差主导",
}

LEARN_STEPS = (
    "调 k 步骤（仿真）\n"
    "1. 盯 fe 真值 vs fe_hat\n"
    "2. 滞后 → 增大 k\n"
    "3. 毛刺 → 减小 k\n"
    "4. 保证 k*dt < 0.1\n"
    "5. 阶跃看回零时间 ~3τ~5τ\n"
    "6. τ=1k 决定能跟多快的 fe"
)


class GmoTuningUI:
    def __init__(self, controller: SimulationController, ui_config: UiConfig) -> None:
        self._controller = controller
        self._ui_config = ui_config
        self._playing = False
        self._play_index = 0
        self._configure_font()
        self._fig = plt.figure(figsize=ui_config.figure_size)
        manager = getattr(self._fig.canvas, "manager", None)
        if manager is not None:
            manager.set_window_title(ui_config.window_title)
        self._build_axes()
        self._init_lines()
        self._build_controls()
        self._timer = self._fig.canvas.new_timer(interval=ui_config.play_interval_ms)
        self._timer.add_callback(self._on_timer)
        self._redraw(reset_play=True)
        self._fig.canvas.mpl_connect("close_event", self._on_close)

    def show(self) -> None:
        plt.show()

    @staticmethod
    def _configure_font() -> None:
        plt.rcParams["font.sans-serif"] = [
            "Microsoft YaHei",
            "SimHei",
            "Noto Sans CJK SC",
            "DejaVu Sans",
        ]
        plt.rcParams["axes.unicode_minus"] = False

    def _build_axes(self) -> None:
        gs = self._fig.add_gridspec(
            3,
            1,
            left=0.07,
            right=0.58,
            top=0.93,
            bottom=0.10,
            hspace=0.40,
        )
        self._ax_fe = self._fig.add_subplot(gs[0, 0])
        self._ax_vel = self._fig.add_subplot(gs[1, 0])
        self._ax_err = self._fig.add_subplot(gs[2, 0])

        self._ax_fe.set_title("调 k 主曲线：fe 真值 vs fe_hat（蓝线应贴虚线）")
        self._ax_fe.set_ylabel("fe (N)")
        self._ax_vel.set_title("速度：真值 / 量测（噪声源）")
        self._ax_vel.set_ylabel("v (m/s)")
        self._ax_err.set_title("动量误差 e 与估计 r=fe_hat（同轴可看相位）")
        self._ax_err.set_ylabel("e / r")
        self._ax_err.set_xlabel("时间 (s)")

        for ax in (self._ax_fe, self._ax_vel, self._ax_err):
            ax.grid(True, alpha=0.3)

    def _init_lines(self) -> None:
        (self._line_fe_true,) = self._ax_fe.plot(
            [], [], color="#2c3e50", lw=1.4, ls="--", label="fe 真值"
        )
        (self._line_fe_hat,) = self._ax_fe.plot(
            [], [], color="#2980b9", lw=2.0, label="fe_hat = r"
        )
        (self._line_fe_direct,) = self._ax_fe.plot(
            [], [], color="#e74c3c", lw=1.0, alpha=0.55, label="直接微分(对照)"
        )
        self._ax_fe.legend(loc="upper left", fontsize=8)

        (self._line_v_true,) = self._ax_vel.plot(
            [], [], color="#2c3e50", lw=1.2, ls="--", label="v 真值"
        )
        (self._line_v_meas,) = self._ax_vel.plot(
            [], [], color="#f39c12", lw=0.8, alpha=0.7, label="v 量测"
        )
        self._ax_vel.legend(loc="upper left", fontsize=8)

        (self._line_e,) = self._ax_err.plot(
            [], [], color="#8e44ad", lw=1.2, label="e = p - p_hat"
        )
        (self._line_r,) = self._ax_err.plot(
            [], [], color="#16a085", lw=1.2, alpha=0.9, label="r = fe_hat"
        )
        self._ax_err.legend(loc="upper left", fontsize=8)

        self._settle_marker = self._ax_fe.plot(
            [], [], marker="v", color="#27ae60", ls="none", ms=8, label="阶跃稳定点"
        )[0]
        self._settle_marker.set_visible(False)

        self._cursor_fe = self._ax_fe.axvline(0.0, color="#c0392b", lw=0.8, ls=":", visible=False)
        self._cursor_vel = self._ax_vel.axvline(0.0, color="#c0392b", lw=0.8, ls=":", visible=False)
        self._cursor_err = self._ax_err.axvline(0.0, color="#c0392b", lw=0.8, ls=":", visible=False)

        # 诊断面板背景
        self._panel = FancyBboxPatch(
            (0.60, 0.08),
            0.38,
            0.82,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            transform=self._fig.transFigure,
            facecolor="#f8f9fa",
            edgecolor="#bdc3c7",
            linewidth=1.0,
            zorder=0,
        )
        self._fig.patches.append(self._panel)

        self._diag_title = self._fig.text(0.63, 0.84, "", fontsize=12, weight="bold")
        self._diag_body = self._fig.text(0.63, 0.78, "", fontsize=9, va="top", linespacing=1.45)
        self._advice_box = self._fig.text(0.63, 0.42, "", fontsize=10, va="top", color="#2c3e50")
        self._learn_text = self._fig.text(0.63, 0.28, LEARN_STEPS, fontsize=8, va="top", color="#7f8c8d")

    def _build_controls(self) -> None:
        ui = self._ui_config
        obs = self._controller.observer_config

        # 控制条放到图上方偏右，避免和诊断面板抢地方
        self._sld_k = Slider(
            self._fig.add_axes([0.10, 0.02, 0.30, 0.025]),
            "k",
            ui.k_slider.log_min,
            ui.k_slider.log_max,
            valinit=log10(max(obs.gain_k, 1e-9)),
            valfmt="10^%.2f",
        )
        self._sld_noise = Slider(
            self._fig.add_axes([0.10, 0.055, 0.30, 0.025]),
            "noise",
            ui.noise_slider.log_min,
            ui.noise_slider.log_max,
            valinit=log10(max(self._controller.plant_config.velocity_noise_std, 1e-12)),
            valfmt="10^%.2f",
        )
        self._sld_mass = Slider(
            self._fig.add_axes([0.42, 0.02, 0.14, 0.025]),
            "mass",
            ui.mass_slider.log_min,
            ui.mass_slider.log_max,
            valinit=obs.mass_model,
            valfmt="%0.2f",
        )

        self._sld_k.on_changed(self._on_param_changed)
        self._sld_noise.on_changed(self._on_param_changed)
        self._sld_mass.on_changed(self._on_param_changed)

        self._radio_ax = self._fig.add_axes([0.42, 0.08, 0.14, 0.10])
        self._radio_ax.set_title("fe 场景", fontsize=9)
        scenarios = [s.value for s in ForceScenario]
        active = scenarios.index(self._controller.plant_config.scenario.value)
        self._radio = RadioButtons(self._radio_ax, scenarios, active=active)
        for label in self._radio.labels:
            label.set_fontsize(8)
        self._radio.on_clicked(self._on_scenario)

        self._btn_play_ax = self._fig.add_axes([0.42, 0.22, 0.065, 0.035])
        self._btn_reroll_ax = self._fig.add_axes([0.495, 0.22, 0.065, 0.035])
        self._btn_shadow_ax = self._fig.add_axes([0.42, 0.27, 0.065, 0.035])
        self._btn_reduced_ax = self._fig.add_axes([0.495, 0.27, 0.065, 0.035])
        self._btn_play = Button(self._btn_play_ax, "播放")
        self._btn_reroll = Button(self._btn_reroll_ax, "重采噪声")
        self._btn_shadow = Button(self._btn_shadow_ax, "影子")
        self._btn_reduced = Button(self._btn_reduced_ax, "约简")
        self._btn_play.on_clicked(self._on_play)
        self._btn_reroll.on_clicked(self._on_reroll)
        self._btn_shadow.on_clicked(lambda _e: self._set_form(True))
        self._btn_reduced.on_clicked(lambda _e: self._set_form(False))

    def _set_form(self, use_shadow: bool) -> None:
        self._controller.set_use_shadow_form(use_shadow)
        self._redraw(reset_play=True)

    def _on_param_changed(self, _val: float) -> None:
        k = 10.0 ** self._sld_k.val
        noise = 10.0 ** self._sld_noise.val
        mass = float(self._sld_mass.val)
        self._controller.set_gain(k)
        self._controller.set_velocity_noise(noise)
        self._controller.set_mass_model(mass)
        self._redraw(reset_play=True)

    def _on_scenario(self, label: str) -> None:
        for s in ForceScenario:
            if s.value == label:
                self._controller.set_scenario(s)
                break
        self._redraw(reset_play=True)

    def _on_play(self, _evt) -> None:
        self._playing = not self._playing
        self._btn_play.label.set_text("暂停" if self._playing else "播放")
        if self._playing:
            if self._play_index >= len(self._controller.run().t) - 1:
                self._play_index = 0
            self._timer.start()
        else:
            self._timer.stop()

    def _on_reroll(self, _evt) -> None:
        self._controller.run(force=True)
        self._redraw(reset_play=True)

    def _on_timer(self) -> None:
        if not self._playing:
            return
        result = self._controller.run()
        n = len(result.t)
        step = max(1, n // 200)
        self._play_index = min(self._play_index + step, n - 1)
        self._update_cursor(result, self._play_index)
        self._fig.canvas.draw_idle()
        if self._play_index >= n - 1:
            self._playing = False
            self._btn_play.label.set_text("播放")
            self._timer.stop()

    def _update_cursor(self, result, index: int) -> None:
        t_now = float(result.t[index])
        for cursor in (self._cursor_fe, self._cursor_vel, self._cursor_err):
            cursor.set_visible(True)
            cursor.set_xdata([t_now, t_now])

    def _redraw(self, reset_play: bool = False) -> None:
        result = self._controller.run()
        diag = self._controller.diagnose()
        t = result.t
        n = len(t)

        if reset_play:
            self._play_index = n - 1
            self._playing = False
            self._btn_play.label.set_text("播放")
            self._timer.stop()

        show_n = max(2, self._play_index + 1)
        t_show = t[:show_n]

        self._line_fe_true.set_data(t_show, result.fe_true[:show_n])
        self._line_fe_hat.set_data(t_show, result.fe_hat[:show_n])
        self._line_fe_direct.set_data(t_show, result.fe_direct[:show_n])
        self._line_v_true.set_data(t_show, result.v_true[:show_n])
        self._line_v_meas.set_data(t_show, result.v_meas[:show_n])
        self._line_e.set_data(t_show, result.e_momentum[:show_n])
        self._line_r.set_data(t_show, result.fe_hat[:show_n])

        # 阶跃稳定点标记
        if diag.settle_time is not None and self._controller.plant_config.scenario == ForceScenario.STEP:
            # 找边沿时间
            dfe = np.abs(np.diff(result.fe_true))
            edge_idx = int(np.argmax(dfe > 0.3 * (np.max(dfe) + 1e-12)))
            t_settle = float(t[edge_idx] + diag.settle_time)
            target = float(result.fe_true[min(edge_idx + 1, n - 1)])
            self._settle_marker.set_data([t_settle], [target])
            self._settle_marker.set_visible(True)
        else:
            self._settle_marker.set_visible(False)

        self._autoscale(self._ax_fe, t, [result.fe_true, result.fe_hat, result.fe_direct], show_n)
        self._autoscale(self._ax_vel, t, [result.v_true, result.v_meas], show_n)
        self._autoscale(self._ax_err, t, [result.e_momentum, result.fe_hat], show_n)
        self._update_cursor(result, self._play_index)
        self._update_diag_panel(diag)

        self._fig.canvas.draw_idle()

    def _update_diag_panel(self, d: TuningDiagnosis) -> None:
        color = LEVEL_COLOR.get(d.level, "#2c3e50")
        title = LEVEL_TITLE.get(d.level, d.level)
        self._diag_title.set_text(title)
        self._diag_title.set_color(color)

        pc = self._controller.plant_config
        oc = self._controller.observer_config
        form = "影子" if oc.use_shadow_form else "约简"

        kdt_flag = "OK" if d.k_dt < 0.1 else ("警告" if d.k_dt < 0.2 else "危险")
        settle_txt = f"{d.settle_time*1000:.0f} ms" if d.settle_time is not None else "—"
        if d.settle_time is not None and d.tau > 0:
            settle_txt += f"  (≈{d.settle_time / d.tau:.1f} τ)"

        body = (
            f"k = {d.k:.2f}\n"
            f"τ = 1/k = {d.tau*1000:.1f} ms\n"
            f"k*dt = {d.k_dt:.4f}  [{kdt_flag}]\n"
            f"dt = {pc.dt*1000:.1f} ms\n"
            f"噪声σ = {pc.velocity_noise_std:.4f}\n"
            f"m 模型/真值 = {oc.mass_model:.2f}/{pc.mass_true:.2f}\n"
            f"实现 = {form}\n"
            f"—— 误差 ——\n"
            f"RMSE = {d.rmse:.4f} N\n"
            f"MAE  = {d.mae:.4f} N\n"
            f"fe RMS = {d.fe_rms:.4f} N\n"
            f"—— 跟踪 ——\n"
            f"滞后 ≈ {d.lag_score*1000:.1f} ms\n"
            f"噪声差分RMS = {d.noise_score:.4f}\n"
            f"阶跃稳定时间 = {settle_txt}"
        )
        self._diag_body.set_text(body)

        self._advice_box.set_text("建议\n" + d.advice)
        self._advice_box.set_color(color)

    @staticmethod
    def _autoscale(ax, t: np.ndarray, series_list: list[np.ndarray], show_n: int) -> None:
        values = np.concatenate([s[:show_n] for s in series_list])
        if values.size == 0:
            return
        vmin = float(np.min(values))
        vmax = float(np.max(values))
        if np.isclose(vmin, vmax):
            pad = max(abs(vmin) * 0.1, 0.1)
        else:
            pad = (vmax - vmin) * 0.12
        ax.set_xlim(0.0, max(float(t[-1]), 1e-6))
        ax.set_ylim(vmin - pad, vmax + pad)

    def _on_close(self, _evt) -> None:
        self._playing = False
        try:
            self._timer.stop()
        except Exception:
            LOGGER.debug("timer stop failed", exc_info=True)
