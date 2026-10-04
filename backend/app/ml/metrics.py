"""Forecast error calculations shared by training and the slim serving runtime."""

import numpy as np


def metrics(actual, pred, history):
    a = np.asarray(actual, float)
    p = np.asarray(pred, float)
    error = np.abs(a - p)
    denom = np.abs(a) + np.abs(p)
    scale = np.abs(np.diff(history)).mean()
    return {
        "wape": float(100 * error.sum() / a.sum()) if a.sum() else None,
        "smape": float(
            200
            * np.divide(error, denom, out=np.zeros_like(error), where=denom != 0).mean()
        ),
        "mase": float(error.mean() / scale) if scale > 0 else None,
    }
