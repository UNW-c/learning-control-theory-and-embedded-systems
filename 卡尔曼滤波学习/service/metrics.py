import numpy as np


def rmse(estimate: np.ndarray, truth: np.ndarray) -> float:
    delta = np.asarray(estimate, dtype=float) - np.asarray(truth, dtype=float)
    return float(np.sqrt(np.mean(delta * delta)))