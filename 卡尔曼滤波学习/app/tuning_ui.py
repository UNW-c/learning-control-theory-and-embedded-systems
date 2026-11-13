import logging
from math import log10

import matplotlib.pyplot as plt
from matplotlib.widgets import Button, Slider

from config.settings import KalmanConfig, UiConfig
from controller.simulation_controller import SimulationController

LOGGER = logging.getLogger(__name__)

HINT_TEXT = (
    "调参提示\n"
    "R 增大: 更相信加速度模型, 曲线更平滑\n"
    "R 减小: 更相信光流, 跟踪快但更噪\n"
    "Qv 增大: 认为速度预测更不准\n"
    "Qb 增大: 允许偏置变化更快\n"
    "绿线漂移来自加速度计偏置\n"
    "橙线噪声来自光流观测"
)


class KalmanTuningUI:
    """实时调节 Q/R，并同时显示两个数据源与滤波结果。"""

    def __init__(self, controller: SimulationController, ui_config: UiConfig) -> None:
        self._controller = controller
        self._ui_config = ui_config
        self._play_index = None
        self._playing = False
        self._configure_font()
        self._fig = plt.figure(figsize=ui_config.figure_size)
        manager = getattr(self._fig.canvas, 'manager', None)
        if manager is not None:
            manager.set_window_title(ui_config.window_title)
        self._build_axes()
        self._init_lines()
        self._build_controls()
        self._timer = self._fig.canvas.new_timer(interval=ui_config.play_interval_ms)
        self._timer.add_callback(self._on_timer)
        self._redraw()
        self._fig.canvas.mpl_connect("close_event", self._on_close)

    def show(self) -> None:
        plt.show()

    @staticmethod
    def _configure_font() -> None:
        plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

    def _build_axes(self) -> None:
        gs = self._fig.add_gridspec(
            3,
            1,
            left=0.07,
            right=0.68,
            top=0.93,
            bottom=0.08,
            hspace=0.38,
        )
        self._ax_vel = self._fig.add_subplot(gs[0, 0])
        self._ax_acc = self._fig.add_subplot(gs[1, 0])
        self._ax_bias = self._fig.add_subplot(gs[2, 0])
        self._ax_vel.set_title("速度对比：光流 / 加速度积分 / 卡尔曼滤波")
        self._ax_vel.set_ylabel("速度 (m/s)")
        self._ax_acc.set_title("加速度计数据源")
        self._ax_acc.set_ylabel("加速度 (m/s^2)")
        self._ax_bias.set_title("加速度偏置估计")
        self._ax_bias.set_ylabel("偏置 (m/s^2)")
        self._ax_bias.set_xlabel("时间 (s)")
        self._ax_vel.grid(True, alpha=0.3)
        self._ax_acc.grid(True, alpha=0.3)
        self._ax_bias.grid(True, alpha=0.3)

    def _init_lines(self) -> None:
        self._line_flow, = self._ax_vel.plot([], [], color="#f39c12", lw=1.0, alpha=0.85, label="光流速度")
        self._line_integ, = self._ax_vel.plot([], [], color="#27ae60", lw=1.4, label="加速度积分速度")
        self._line_filt, = self._ax_vel.plot([], [], color="#2980b9", lw=2.0, label="卡尔曼滤波速度")
        self._line_vtrue, = self._ax_vel.plot([], [], color="#2c3e50", lw=1.2, ls="--", label="真实速度")
        self._ax_vel.legend(loc="upper left", fontsize=8)

        self._line_ameas, = self._ax_acc.plot([], [], color="#8e44ad", lw=1.0, alpha=0.8, label="加速度计量测")
        self._line_atrue, = self._ax_acc.plot([], [], color="#2c3e50", lw=1.2, ls="--", label="真实加速度")
        self._ax_acc.legend(loc="upper left", fontsize=8)

        self._line_bhat, = self._ax_bias.plot([], [], color="#2980b9", lw=2.0, label="滤波估计偏置")
        self._line_btrue, = self._ax_bias.plot([], [], color="#2c3e50", lw=1.2, ls="--", label="真实偏置")
        self._ax_bias.legend(loc="upper left", fontsize=8)

        self._cursor_vel = self._ax_vel.axvline(0.0, color="#c0392b", lw=0.8, ls=":", visible=False)
        self._cursor_acc = self._ax_acc.axvline(0.0, color="#c0392b", lw=0.8, ls=":", visible=False)
        self._cursor_bias = self._ax_bias.axvline(0.0, color="#c0392b", lw=0.8, ls=":", visible=False)

    def _build_controls(self) -> None:
        kalman = self._controller.kalman_config
        qv_range = self._ui_config.q_velocity_slider
        qb_range = self._ui_config.q_bias_slider
        r_range = self._ui_config.r_flow_slider

        self._sld_qv = Slider(
            self._fig.add_axes([0.73, 0.82, 0.22, 0.03]),
            qv_range.label,
            qv_range.log_min,
            qv_range.log_max,
            valinit=log10(kalman.q_velocity),
            valfmt="%0.2f",
        )
        self._sld_qb = Slider(
            self._fig.add_axes([0.73, 0.74, 0.22, 0.03]),
            qb_range.label,
            qb_range.log_min,
            qb_range.log_max,
            valinit=log10(kalman.q_bias),
            valfmt="%0.2f",
        )
        self._sld_r = Slider(
            self._fig.add_axes([0.73, 0.66, 0.22, 0.03]),
            r_range.label,
            r_range.log_min,
            r_range.log_max,
            valinit=log10(kalman.r_flow),
            valfmt="%0.2f",
        )
        for slider in (self._sld_qv, self._sld_qb, self._sld_r):
            slider.label.set_fontsize(8)
            slider.on_changed(self._on_qr_changed)

        self._btn_regen = Button(self._fig.add_axes([0.73, 0.56, 0.10, 0.045]), "重新生成")
        self._btn_play = Button(self._fig.add_axes([0.85, 0.56, 0.10, 0.045]), "播放")
        self._btn_reset = Button(self._fig.add_axes([0.73, 0.50, 0.22, 0.045]), "显示整段")
        self._btn_regen.on_clicked(self._on_regenerate)
        self._btn_play.on_clicked(self._on_play_pause)
        self._btn_reset.on_clicked(self._on_show_all)

        self._txt_value = self._fig.text(0.73, 0.44, "", fontsize=9, family="sans-serif", va="top")
        self._fig.text(0.73, 0.22, HINT_TEXT, fontsize=8, va="top", color="#34495e")

    def _current_qr(self) -> tuple[float, float, float]:
        return (
            10.0 ** float(self._sld_qv.val),
            10.0 ** float(self._sld_qb.val),
            10.0 ** float(self._sld_r.val),
        )

    def _on_qr_changed(self, _value: float) -> None:
        q_velocity, q_bias, r_flow = self._current_qr()
        self._controller.update_qr(q_velocity, q_bias, r_flow)
        self._redraw()

    def _on_regenerate(self, _event) -> None:
        next_seed = self._controller.simulation_config.seed + 1
        self._play_index = None
        self._stop_play()
        self._controller.regenerate(new_seed=next_seed)
        self._redraw()

    def _on_play_pause(self, _event) -> None:
        if self._playing:
            self._stop_play()
            return
        sequence = self._controller.sequence
        if self._play_index is None or self._play_index >= sequence.time_s.shape[0]:
            self._play_index = 1
        self._playing = True
        self._btn_play.label.set_text("暂停")
        self._timer.start()

    def _on_show_all(self, _event) -> None:
        self._stop_play()
        self._play_index = None
        self._redraw()

    def _on_timer(self) -> None:
        if not self._playing:
            return
        sample_count = self._controller.sequence.time_s.shape[0]
        stride = max(1, sample_count // self._ui_config.play_frames)
        self._play_index = min(sample_count, (self._play_index or 1) + stride)
        if self._play_index >= sample_count:
            self._stop_play()
        self._redraw()

    def _stop_play(self) -> None:
        self._playing = False
        self._timer.stop()
        self._btn_play.label.set_text("播放")

    def _on_close(self, _event) -> None:
        self._stop_play()

    def _redraw(self) -> None:
        sequence = self._controller.sequence
        result = self._controller.result
        end = sequence.time_s.shape[0] if self._play_index is None else self._play_index
        end = max(1, min(end, sequence.time_s.shape[0]))
        time_s = sequence.time_s[:end]

        self._line_flow.set_data(time_s, sequence.flow_meas[:end])
        self._line_integ.set_data(time_s, result.velocity_accel_integrated[:end])
        self._line_filt.set_data(time_s, result.velocity_filtered[:end])
        self._line_vtrue.set_data(time_s, sequence.velocity_true[:end])
        self._line_ameas.set_data(time_s, sequence.accel_meas[:end])
        self._line_atrue.set_data(time_s, sequence.accel_true[:end])
        self._line_bhat.set_data(time_s, result.bias_filtered[:end])
        self._line_btrue.set_data(time_s, sequence.bias_true[:end])

        show_cursor = self._play_index is not None
        cursor_x = float(time_s[-1])
        for cursor in (self._cursor_vel, self._cursor_acc, self._cursor_bias):
            cursor.set_xdata([cursor_x, cursor_x])
            cursor.set_visible(show_cursor)

        self._ax_vel.relim()
        self._ax_vel.autoscale_view()
        self._ax_acc.relim()
        self._ax_acc.autoscale_view()
        self._ax_bias.relim()
        self._ax_bias.autoscale_view()
        self._ax_vel.set_xlim(0.0, float(sequence.time_s[-1]))
        self._ax_acc.set_xlim(0.0, float(sequence.time_s[-1]))
        self._ax_bias.set_xlim(0.0, float(sequence.time_s[-1]))

        self._update_info_text()
        self._fig.canvas.draw_idle()

    def _update_info_text(self) -> None:
        kalman: KalmanConfig = self._controller.kalman_config
        result = self._controller.result
        sim = self._controller.simulation_config
        text = (
            f"当前参数\n"
            f"Q = diag({kalman.q_velocity:.2e}, {kalman.q_bias:.2e})\n"
            f"R = [{kalman.r_flow:.2e}]\n"
            f"dt = {sim.dt:.3f}s  seed = {sim.seed}\n\n"
            f"速度 RMSE (m/s)\n"
            f"  滤波: {result.velocity_rmse:.3f}\n"
            f"  光流: {result.flow_rmse:.3f}\n"
            f"  加速度积分: {result.accel_integrated_rmse:.3f}\n"
            f"偏置 RMSE: {result.bias_rmse:.3f} m/s^2"
        )
        self._txt_value.set_text(text)