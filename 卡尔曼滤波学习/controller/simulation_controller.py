import logging
from dataclasses import replace

from config.settings import KalmanConfig, SimulationConfig
from driver.sensor_source import ISensorSource
from model.filter_result import FilterResult
from model.sensor_data import SensorSequence
from service.fusion_service import FlowAccelFusionService

LOGGER = logging.getLogger(__name__)


class SimulationController:
    """编排数据生成、滤波与参数更新，UI 只通过该控制器交互。"""

    def __init__(
        self,
        sensor_source: ISensorSource,
        fusion_service: FlowAccelFusionService,
        simulation_config: SimulationConfig,
        kalman_config: KalmanConfig,
    ) -> None:
        self._sensor_source = sensor_source
        self._fusion_service = fusion_service
        self._simulation_config = simulation_config
        self._kalman_config = kalman_config
        self._sequence: SensorSequence | None = None
        self._result: FilterResult | None = None
        self.regenerate()

    @property
    def simulation_config(self) -> SimulationConfig:
        return self._simulation_config

    @property
    def kalman_config(self) -> KalmanConfig:
        return self._kalman_config

    @property
    def sequence(self) -> SensorSequence:
        if self._sequence is None:
            raise RuntimeError("尚未生成传感器数据")
        return self._sequence

    @property
    def result(self) -> FilterResult:
        if self._result is None:
            raise RuntimeError("尚未执行滤波")
        return self._result

    def regenerate(self, new_seed: int | None = None) -> None:
        if new_seed is not None:
            self._simulation_config = replace(self._simulation_config, seed=new_seed)
        self._sequence = self._sensor_source.generate(self._simulation_config)
        self.refilter()
        LOGGER.info("数据已刷新, seed=%s", self._simulation_config.seed)

    def update_qr(self, q_velocity: float, q_bias: float, r_flow: float) -> None:
        self._kalman_config.q_velocity = q_velocity
        self._kalman_config.q_bias = q_bias
        self._kalman_config.r_flow = r_flow
        self.refilter()

    def refilter(self) -> None:
        self._result = self._fusion_service.run(self.sequence, self._kalman_config)