from datetime import datetime
import numpy as np
import pandas as pd
import pytest
from ml.core import split, rank_metrics, forecast_metrics, BM25
from ml.baselines import forecast_row, predict_forecast


def test_temporal_boundaries_and_leakage():
    rows = pd.DataFrame(
        {
            "created_at": pd.to_datetime(
                ["2026-03-29", "2026-03-30", "2026-06-28", "2026-06-29", "2026-09-28"]
            )
        }
    )
    a, b, c = split(
        rows,
        pd.Timestamp("2026-03-30"),
        pd.Timestamp("2026-06-29"),
        pd.Timestamp("2026-09-28"),
    )
    assert len(a) == 1 and len(b) == 2 and len(c) == 1
    assert (
        a.created_at.max() < b.created_at.min()
        and b.created_at.max() < c.created_at.min()
    )
    assert set(a.index).isdisjoint(b.index) and set(b.index).isdisjoint(c.index)


def test_ranking_metrics_hand_computed_and_graded():
    r = rank_metrics([1, 2, 3], {1, 3}, 3)
    assert r["precision"] == pytest.approx(2 / 3) and r["recall"] == 1
    assert r["ndcg"] == pytest.approx(1.5 / (1 + 1 / np.log2(3))) and r["mrr"] == 1
    assert rank_metrics([0, 1], {1}, 2)["mrr"] == 0.5
    assert rank_metrics([9], set(), 3)["ndcg"] == 0
    assert rank_metrics([1, 2], {1: 3, 2: 1}, 2)["ndcg"] == 1


def test_forecast_metrics_and_zero_edge_cases():
    r = forecast_metrics(
        [2, 4], [1, 5], [1, 2, 3, 4], lower=np.array([0, 3]), upper=np.array([3, 6])
    )
    assert r["wape"] == pytest.approx(100 * 2 / 6)
    assert r["smape"] == pytest.approx(200 * (1 / 3 + 1 / 9) / 2)
    assert r["mase"] == 1 and r["coverage80"] == 1
    zero = forecast_metrics([0, 0], [0, 0], [0, 0])
    assert zero["wape"] is None and zero["mase"] is None and zero["smape"] == 0
    seasonal = forecast_metrics([2], [0], np.arange(60), season=52)
    assert seasonal["mase"] == pytest.approx(2 / 52)
    with pytest.raises(ValueError):
        forecast_metrics([1, 2], [1], [1, 2])


def test_bm25_exact_terms_and_unknown_query():
    bm = BM25(["rose jasmine perfume", "cedar sandalwood scent"])
    assert bm.score("rose")[0] > bm.score("rose")[1]
    assert np.all(bm.score("unfindable") == 0)


def test_forecast_lags_ignore_future_actuals():
    y = np.arange(78)[None, :].astype(float)
    dates = pd.date_range("2025-03-31", periods=78, freq="W-MON")
    meta = [{"product_id": 1, "size_ml": 50, "price": 120}]
    a = predict_forecast(None, y, dates, meta, 65, 4)
    y[:, 65:] = 999
    assert np.array_equal(a, predict_forecast(None, y, dates, meta, 65, 4))
    assert a.tolist() == [[13.0, 14.0, 15.0, 16.0]]
