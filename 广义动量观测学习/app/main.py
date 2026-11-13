"""应用入口：装配配置、控制器与 UI。"""

import logging

from app.tuning_ui import GmoTuningUI
from config.settings import ObserverConfig, PlantConfig
from controller.simulation_controller import SimulationController
from model.data import UiConfig
from utils.logging_setup import setup_logging

LOGGER = logging.getLogger(__name__)


def main() -> None:
    setup_logging(logging.INFO)

    plant_config = PlantConfig()
    observer_config = ObserverConfig(
        gain_k=20.0,
        mass_model=plant_config.mass_true,
        use_shadow_form=True,
    )
    controller = SimulationController(plant_config, observer_config)

    result = controller.run(force=True)
    metrics = result.metrics()
    LOGGER.info(
        "startup check | rmse=%.4f mae=%.4f samples=%d",
        metrics["rmse"],
        metrics["mae"],
        len(result.t),
    )

    ui = GmoTuningUI(controller, UiConfig())
    ui.show()


if __name__ == "__main__":
    main()
