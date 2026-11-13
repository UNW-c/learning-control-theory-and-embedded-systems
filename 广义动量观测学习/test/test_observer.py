"""无界面数值自检：验证观测器收敛与两种形式。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import ForceScenario, ObserverConfig, PlantConfig
from controller.simulation_controller import SimulationController


def main() -> None:
    cases = [
        ("shadow sine", PlantConfig(scenario=ForceScenario.SINE, velocity_noise_std=0.005),
         ObserverConfig(gain_k=25.0, mass_model=1.0, use_shadow_form=True)),
        ("reduced sine", PlantConfig(scenario=ForceScenario.SINE, velocity_noise_std=0.005),
         ObserverConfig(gain_k=25.0, mass_model=1.0, use_shadow_form=False)),
        ("mass 1.2", PlantConfig(scenario=ForceScenario.SINE, velocity_noise_std=0.005),
         ObserverConfig(gain_k=25.0, mass_model=1.2, use_shadow_form=True)),
        ("step", PlantConfig(scenario=ForceScenario.STEP),
         ObserverConfig(gain_k=40.0, use_shadow_form=True)),
        ("high noise shadow", PlantConfig(scenario=ForceScenario.SINE, velocity_noise_std=0.05),
         ObserverConfig(gain_k=15.0, use_shadow_form=True)),
        ("high noise reduced", PlantConfig(scenario=ForceScenario.SINE, velocity_noise_std=0.05),
         ObserverConfig(gain_k=15.0, use_shadow_form=False)),
    ]

    for name, pc, oc in cases:
        c = SimulationController(pc, oc)
        r = c.run(force=True)
        m = r.metrics()
        print(f"{name:20s} rmse={m['rmse']:.4f} mae={m['mae']:.4f} max={m['max_abs']:.4f}")

    # 形式等价性：低噪声下两种形式 RMSE 应接近
    c1 = SimulationController(
        PlantConfig(scenario=ForceScenario.SINE, velocity_noise_std=1e-4),
        ObserverConfig(gain_k=20.0, use_shadow_form=True),
    )
    c2 = SimulationController(
        PlantConfig(scenario=ForceScenario.SINE, velocity_noise_std=1e-4),
        ObserverConfig(gain_k=20.0, use_shadow_form=False),
    )
    m1 = c1.run(force=True).metrics()
    m2 = c2.run(force=True).metrics()
    ratio = m1["rmse"] / max(m2["rmse"], 1e-12)
    print(f"form equivalence rmse ratio shadow/reduced = {ratio:.3f}")
    assert 0.5 < ratio < 2.0, ratio

    print("ALL OK")


if __name__ == "__main__":
    main()
