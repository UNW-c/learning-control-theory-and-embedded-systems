import unittest

from config.settings import SimulationConfig
from driver.simulated_sensor import SimulatedFlowAccelSource


class SimulatedSensorTest(unittest.TestCase):
    def test_sequence_shapes_and_reproducibility(self) -> None:
        source = SimulatedFlowAccelSource()
        config = SimulationConfig(seed=123, duration_s=4.0, dt=0.02)
        first = source.generate(config)
        second = source.generate(config)
        self.assertEqual(first.time_s.shape[0], 200)
        self.assertTrue((first.flow_meas == second.flow_meas).all())
        self.assertTrue((first.accel_meas == second.accel_meas).all())

    def test_seed_changes_measurements(self) -> None:
        source = SimulatedFlowAccelSource()
        a = source.generate(SimulationConfig(seed=1))
        b = source.generate(SimulationConfig(seed=2))
        self.assertFalse((a.flow_meas == b.flow_meas).all())


if __name__ == "__main__":
    unittest.main()