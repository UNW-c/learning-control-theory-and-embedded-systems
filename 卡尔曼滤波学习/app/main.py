import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.tuning_ui import KalmanTuningUI
from config.settings import KalmanConfig, SimulationConfig, UiConfig
from controller.simulation_controller import SimulationController
from driver.simulated_sensor import SimulatedFlowAccelSource
from service.fusion_service import FlowAccelFusionService
from utils.logging_setup import setup_logging

LOGGER = logging.getLogger(__name__)


def build_controller() -> SimulationController:
    return SimulationController(
        sensor_source=SimulatedFlowAccelSource(),
        fusion_service=FlowAccelFusionService(),
        simulation_config=SimulationConfig(),
        kalman_config=KalmanConfig(),
    )


def main() -> None:
    setup_logging()
    LOGGER.info("启动光流-加速度计卡尔曼滤波调参界面")
    ui = KalmanTuningUI(controller=build_controller(), ui_config=UiConfig())
    ui.show()


if __name__ == "__main__":
    main()