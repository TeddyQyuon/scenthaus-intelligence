import numpy as np
import pandas as pd
import pytest
import torch
from fastapi.testclient import TestClient
from app.main import app, requests
from app.config import settings
from ml.core import config
from ml.forecast import scales, window, examples, LSTM, NBEATS, ordered, pinball


def fixture():
    c = config("forecast").copy()
    y = np.arange(156, dtype=float).reshape(2, 78)
    dates = pd.date_range("2025-03-31", periods=78, freq="W-MON")
    meta = [{"price": 120.0, "size_ml": 50}] * 2
    available = np.ones(y.shape, bool)
    return c, y, dates, meta, available


def test_scaling_windows_and_targets_do_not_see_future():
    c, y, dates, meta, available = fixture()
    scale = scales(y, 52)
    a, b = window(y, dates, meta, available, 0, 52, scale, c)
    x = examples(y, dates, meta, available, scale, c, 12, 52)
    changed = y.copy()
    changed[:, 52:] = 999999
    assert np.array_equal(scales(changed, 52), scale)
    aa, bb = window(changed, dates, meta, available, 0, 52, scale, c)
    assert np.array_equal(a, aa) and np.array_equal(b, bb)
    xx = examples(changed, dates, meta, available, scale, c, 12, 52)
    assert all(torch.equal(v, w) for v, w in zip(x, xx))
    assert x[3].shape[1] == c["horizon"]
    available[0, 51] = False
    assert window(y, dates, meta, available, 0, 52, scale, c)[0][-1, 1] == 1
    with pytest.raises(ValueError):
        scales(y, 0)


def test_quantile_loss_mask_and_non_crossing():
    prediction = torch.tensor([[[1.0, 2.0, 3.0]]])
    target = torch.tensor([[2.0]])
    assert pinball(prediction, target, torch.ones_like(target)).item() == pytest.approx(
        0.2 / 3
    )
    assert pinball(prediction, target, torch.zeros_like(target)).item() == 0
    q = ordered(torch.randn(5, 12, 3))
    assert torch.all(q >= 0) and torch.all(q[..., 1:] >= q[..., :-1])
    assert torch.all(ordered(torch.full((1, 1, 3), -20.0)) == 0)


@pytest.mark.parametrize("network", [LSTM, NBEATS])
def test_real_networks_train_and_return_twelve_quantiles(network):
    c, y, dates, meta, available = fixture()
    a, b = window(y, dates, meta, available, 0, 52, scales(y, 52), c)
    torch.manual_seed(42)
    model = network(2, c)
    result = model(torch.tensor(a[None]), torch.tensor(b[None]), torch.tensor([0]))
    assert result.shape == (1, 12, 3) and torch.isfinite(result).all()
    loss = pinball(result, torch.ones(1, 12), torch.ones(1, 12))
    loss.backward()
    assert any(
        p.grad is not None and p.grad.abs().sum() > 0 for p in model.parameters()
    )


def test_forecast_endpoints_are_admin_only_and_cached():
    requests.clear()
    with TestClient(app) as client:
        assert client.get("/forecast/sku/1").status_code == 401
        session = client.get("/auth/session").json()
        assert client.get("/forecast/sku/1").status_code == 403
        client.headers.update(
            {"Origin": "http://localhost:5173", "X-CSRF-Token": session["csrf"]}
        )
        login = client.post(
            "/auth/login",
            json={"email": settings.admin_email, "password": settings.admin_password},
        )
        assert login.status_code == 200
        for model in ["seasonal_naive", "lightgbm", "lstm", "nbeats"]:
            r = client.get("/forecast/sku/1", params={"horizon": 12, "model": model})
            assert r.status_code == 200
            data = r.json()
            assert (
                data["model"] == model
                and data["model_version"]
                and data["simulated_data"]
            )
            assert len(data["forecast"]) == 12
            assert all(
                0
                <= f["lower95"]
                <= f["lower80"]
                <= f["prediction"]
                <= f["upper80"]
                <= f["upper95"]
                for f in data["forecast"]
            )
        assert client.get("/forecast/sku/1?model=invalid").status_code == 422
        assert client.get("/forecast/sku/1?horizon=13").status_code == 422
        assert (
            client.get("/forecast/summary?group=brand&key=Dior&model=lstm").json()[
                "skus"
            ]
            > 0
        )
        assert client.get("/forecast/summary?group=invalid").status_code == 422
