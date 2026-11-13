"""仿真编排：串联被控对象与观测器，供 UI 调用。"""

import logging

import numpy as np

from config.settings import ForceScenario, ObserverConfig, PlantConfig
from model.data import SimulationResult, TuningDiagnosis
from service.momentum_observer import (
    GeneralizedMomentumObserver,
    direct_diff_force,
    run_observer,
)
from service.plant import RigidBodyPlant

LOGGER = logging.getLogger(__name__)


class SimulationController:
    def __init__(self, plant_config: PlantConfig, observer_config: ObserverConfig) -> None:
        self._plant_config = plant_config
        self._observer_config = observer_config
        self._cache: SimulationResult | None = None
        self._cache_key: tuple | None = None

    @property
    def plant_config(self) -> PlantConfig:
        return self._plant_config

    @property
    def observer_config(self) -> ObserverConfig:
        return self._observer_config

    def set_scenario(self, scenario: ForceScenario) -> None:
        self._plant_config.scenario = scenario
        self._cache = None

    def set_gain(self, k: float) -> None:
        self._observer_config.gain_k = k
        self._cache = None

    def set_mass_model(self, mass: float) -> None:
        self._observer_config.mass_model = mass
        self._cache = None

    def set_velocity_noise(self, std: float) -> None:
        self._plant_config.velocity_noise_std = std
        self._cache = None

    def set_use_shadow_form(self, use_shadow: bool) -> None:
        self._observer_config.use_shadow_form = use_shadow
        self._cache = None

    def run(self, force: bool = False) -> SimulationResult:
        key = self._key()
        if not force and self._cache is not None and self._cache_key == key:
            return self._cache

        plant = RigidBodyPlant(self._plant_config)
        t, v_true, v_meas, p_true, f_drive, fe_true = plant.generate()

        # 模型质量可与真值不同，用于观察标定误差影响
        p_meas = self._observer_config.mass_model * v_meas

        observer = GeneralizedMomentumObserver(
            gain_k=self._observer_config.gain_k,
            mass_model=self._observer_config.mass_model,
            dt=self._plant_config.dt,
            use_shadow_form=self._observer_config.use_shadow_form,
        )
        fe_hat, e_mom, p_hat = run_observer(observer, v_meas, f_drive)

        fe_direct = direct_diff_force(
            v_meas,
            f_drive,
            mass=self._observer_config.mass_model,
            dt=self._plant_config.dt,
        )

        result = SimulationResult(
            t=t,
            v_true=v_true,
            v_meas=v_meas,
            p_true=p_true,
            p_meas=p_meas,
            f_drive=f_drive,
            fe_true=fe_true,
            fe_hat=fe_hat,
            fe_direct=fe_direct,
            e_momentum=e_mom,
            p_hat=p_hat,
        )

        self._cache = result
        self._cache_key = key
        metrics = result.metrics()
        LOGGER.info(
            "sim done | scenario=%s k=%.2f noise=%.4f m=%.2f form=%s | rmse=%.4f mae=%.4f",
            self._plant_config.scenario.value,
            self._observer_config.gain_k,
            self._plant_config.velocity_noise_std,
            self._observer_config.mass_model,
            "shadow" if self._observer_config.use_shadow_form else "reduced",
            metrics["rmse"],
            metrics["mae"],
        )
        return result

    def diagnose(self) -> TuningDiagnosis:
        """当前参数下的调 k 诊断（滞后 / 噪声 / 离散稳定 / 模型）。"""
        result = self.run()
        return result.diagnose(
            k=self._observer_config.gain_k,
            dt=self._plant_config.dt,
            mass_model=self._observer_config.mass_model,
            mass_true=self._plant_config.mass_true,
        )

    def _key(self) -> tuple:
        pc = self._plant_config
        oc = self._observer_config
        return (
            pc.scenario,
            pc.mass_true,
            pc.dt,
            pc.duration,
            pc.velocity_noise_std,
            pc.fe_amplitude,
            pc.fe_frequency,
            oc.gain_k,
            oc.mass_model,
            oc.use_shadow_form,
        )
