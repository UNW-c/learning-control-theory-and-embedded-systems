from abc import ABC, abstractmethod

from config.settings import SimulationConfig
from model.sensor_data import SensorSequence


class ISensorSource(ABC):
    """传感器数据源接口，上层只依赖该抽象，不耦合具体仿真或硬件。"""

    @abstractmethod
    def generate(self, config: SimulationConfig) -> SensorSequence:
        raise NotImplementedError