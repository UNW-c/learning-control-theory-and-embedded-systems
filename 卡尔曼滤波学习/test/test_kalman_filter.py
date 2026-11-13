import unittest

import numpy as np

from config.settings import KalmanConfig, SimulationConfig
from driver.simulated_sensor import SimulatedFlowAccelSource
from service.fusion_service import FlowAccelFusionService
from service.kalman_filter import VelocityBiasKalmanFilter


class VelocityBiasKalmanFilterTest(unittest.TestCase):
    def test_zero_noise_zero_bias_tracks_constant_accel(self) -> None:
        dt = 0.02
        config = KalmanConfig(q_velocity=1.0e-6, q_bias=1.0e-8, r_flow=1.0e-6)
        filt = VelocityBiasKalmanFilter(dt=dt, config=config)
        true_accel = 1.5
        true_velocity = 0.0
        for _ in range(200):
            true_velocity += true_accel * dt
            filt.predict(true_accel)
            filt.update(true_velocity)
        self.assertAlmostEqual(filt.velocity, true_velocity, places=3)
        self.assertAlmostEqual(filt.bias, 0.0, places=2)

    def test_covariance_stays_finite_and_symmetric(self) -> None:
        filt = VelocityBiasKalmanFilter(dt=0.01, config=KalmanConfig())
        for index in range(50):
            filt.predict(0.2 * np.sin(index * 0.1))
            filt.update(0.05 * index)
        cov = filt._p
        self.assertTrue(np.all(np.isfinite(cov)))
        self.assertTrue(np.allclose(cov, cov.T))
        eigvals = np.linalg.eigvalsh(cov)
        self.assertTrue(np.all(eigvals > 0.0))


class FusionServiceTest(unittest.TestCase):
    def test_filter_beats_raw_optical_flow_on_default_data(self) -> None:
        sequence = SimulatedFlowAccelSource().generate(SimulationConfig(seed=7))
        result = FlowAccelFusionService().run(sequence, KalmanConfig())
        self.assertLess(result.velocity_rmse, result.flow_rmse)
        self.assertLess(result.velocity_rmse, result.accel_integrated_rmse)
        self.assertEqual(result.velocity_filtered.shape, sequence.time_s.shape)


if __name__ == "__main__":
    unittest.main()