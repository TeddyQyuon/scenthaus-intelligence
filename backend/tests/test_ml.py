from datetime import date
import numpy as np
import pytest
from app.ml.calendar import features
from app.ml.forecast import metrics, croston
from app.ml.recommender import quiz_weights, ranking_metrics, mmr, fit
from app.ml.data import load, validate
from app.database import SessionLocal
from app.ml.experiments import ab_simulate


def test_calendar_spikes():
    assert features(date(2026, 2, 16))[2] == 1
    assert features(date(2026, 3, 16))[3] == 1
    assert features(date(2026, 11, 2))[4] == 1
    assert features(date(2026, 11, 9))[6] == 1
    with pytest.raises(ValueError):
        features(date(2027, 1, 1))


def test_zero_safe_forecast_scores():
    r = metrics([0, 0], [0, 0], [0, 0])
    assert r["smape"] == 0 and r["wape"] is None and r["mase"] is None


def test_croston_nonnegative():
    assert (croston(np.array([0, 0, 2, 0, 0, 3, 0]), 12) >= 0).all()


def test_quiz_alignment():
    w = quiz_weights({"mood": "fresh", "occasion": "office", "intensity": "soft"})
    assert w["fresh"] > w["amber"] and w["citrus"] > w["woody"]


def test_rank_metrics():
    p, r, n = ranking_metrics([1, 2, 3, 4, 5], {1, 3})
    assert p == 0.4 and r == 1 and 0 < n < 1


def test_mmr_diversifies_brands():
    model = {"content": np.array([[1, 0.99, 0.1], [0.99, 1, 0.1], [0.1, 0.1, 1]])}
    assert mmr(model, [1, 0.99, 0.9], [0, 1, 2], ["A", "A", "B"], 2) == [0, 2]


def test_validation_rejects_duplicates():
    with SessionLocal() as db:
        p, v, o, w, e = load(db)
        assert validate(p, v, o)["passed"]
        import pandas as pd

        with pytest.raises(ValueError, match="Duplicate"):
            validate(p, v, pd.concat([o, o.iloc[:1]], ignore_index=True))


def test_time_cutoff_no_future_popularity():
    with SessionLocal() as db:
        p, v, o, w, e = load(db)
        cut = __import__("pandas").Timestamp("2026-01-01")
        model, _, _ = fit(p, o, w, e, cut)
        # Four recently launched items have no pre-cutoff signals and must use content fallback.
        assert all(
            model["new"][model["index"][pid]]
            and model["popularity"][model["index"][pid]] == 0
            for pid in [33, 34, 35, 36]
        )


def test_ab_is_reproducible_and_randomized():
    a = ab_simulate(10000, 0.04, 0.1, 42)
    assert a == ab_simulate(10000, 0.04, 0.1, 42)
    assert sum(a["visitors"]) == 10000 and 0 <= a["p_value"] <= 1
