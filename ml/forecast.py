"""Global quantile LSTM and generic N-BEATS adaptation on SIMULATED sales.

N-BEATS retains residual backcasts and additive forecasts, augmented with
calendar/price covariates and ordered quantile heads. It is not a reproduction
of the paper's interpretable trend/seasonality architecture or benchmark.
"""

from .tracking import tracked

from copy import deepcopy
from functools import lru_cache
import json
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn import functional as F
from app.ml.calendar import features
from app.ml.forecast import croston
from .core import ARTIFACTS, config, snapshot, forecast_metrics, save_json, write_report
from .baselines import panel, fit_forecast, predict_forecast


def scales(y: np.ndarray, end: int) -> np.ndarray:
    """Only the observed prefix contributes to per-series scaling."""
    if end < 1 or end > y.shape[1]:
        raise ValueError("Invalid scaling cutoff")
    return np.maximum(1, np.mean(np.abs(y[:, :end]), axis=1)).astype(np.float32)


@lru_cache(maxsize=2048)
def calendar_features(day):
    return features(day.date())


def window(y, dates, meta, availability, sid, origin, scale, c):
    if origin < c["lookback"]:
        raise ValueError("Insufficient lookback")
    past_dates = dates[origin - c["lookback"] : origin]
    future_dates = pd.date_range(
        dates[origin - 1] + pd.Timedelta(weeks=1), periods=c["horizon"], freq="W-MON"
    )
    static = [np.log1p(meta[sid]["price"]) / 10, meta[sid]["size_ml"] / 200]
    past = np.asarray(
        [
            [
                y[sid, t] / scale[sid],
                float(not availability[sid, t]),
                *calendar_features(day),
                *static,
            ]
            for t, day in zip(range(origin - c["lookback"], origin), past_dates)
        ],
        np.float32,
    )
    future = np.asarray(
        [[*calendar_features(day), *static] for day in future_dates], np.float32
    )
    return past, future


def examples(y, dates, meta, availability, scale, c, first, end):
    past, future, ids, target, masks = [], [], [], [], []
    for origin in range(max(c["lookback"], first), end - c["horizon"] + 1):
        for sid in range(len(y)):
            a, b = window(y, dates, meta, availability, sid, origin, scale, c)
            past.append(a)
            future.append(b)
            ids.append(sid)
            target.append(y[sid, origin : origin + c["horizon"]] / scale[sid])
            masks.append(availability[sid, origin : origin + c["horizon"]])
    if not ids:
        raise ValueError("No complete temporal windows")
    return (
        torch.tensor(np.asarray(past)),
        torch.tensor(np.asarray(future)),
        torch.tensor(ids),
        torch.tensor(np.asarray(target), dtype=torch.float32),
        torch.tensor(np.asarray(masks), dtype=torch.float32),
    )


def ordered(raw: torch.Tensor) -> torch.Tensor:
    # Clipping permits genuine zero-demand quantiles without quantile crossing.
    increments = torch.cat([raw[..., :1], F.softplus(raw[..., 1:])], -1)
    return torch.cumsum(increments, dim=-1).clamp_min(0)


def pinball(
    pred: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
    quantiles=(0.1, 0.5, 0.9),
) -> torch.Tensor:
    error = target[..., None] - pred
    q = pred.new_tensor(quantiles)
    loss = torch.maximum(q * error, (q - 1) * error)
    return (loss * mask[..., None]).sum() / (mask.sum().clamp_min(1) * len(quantiles))


class LSTM(nn.Module):
    def __init__(self, series: int, c: dict):
        super().__init__()
        self.ids = nn.Embedding(series, c["id_dim"])
        self.lstm = nn.LSTM(13, c["hidden"], batch_first=True)
        self.head = nn.Sequential(
            nn.Linear(c["hidden"] + c["id_dim"] + 11, c["hidden"]),
            nn.ReLU(),
            nn.Linear(c["hidden"], 3),
        )

    def forward(self, past, future, ids):
        context = self.lstm(past)[0][:, -1]
        context = torch.cat([context, self.ids(ids)], -1)[:, None].expand(
            -1, future.shape[1], -1
        )
        return ordered(self.head(torch.cat([context, future], -1)))


class NBEATS(nn.Module):
    def __init__(self, series: int, c: dict):
        super().__init__()
        self.c = c
        self.ids = nn.Embedding(series, c["id_dim"])
        width = c["nbeats_width"]
        inputs = c["lookback"] * 13 + c["horizon"] * 11 + c["id_dim"]
        self.blocks = nn.ModuleList()
        self.backcasts = nn.ModuleList()
        self.forecasts = nn.ModuleList()
        for _ in range(c["nbeats_blocks"]):
            layers = [nn.Linear(inputs, width), nn.ReLU()]
            for _ in range(3):
                layers += [nn.Linear(width, width), nn.ReLU()]
            self.blocks.append(nn.Sequential(*layers))
            self.backcasts.append(nn.Linear(width, c["lookback"]))
            self.forecasts.append(nn.Linear(width, c["horizon"] * 3))

    def forward(self, past, future, ids):
        residual = past[..., 0]
        covariates = torch.cat(
            [past[..., 1:].flatten(1), future.flatten(1), self.ids(ids)], -1
        )
        forecast = past.new_zeros((len(past), self.c["horizon"] * 3))
        for block, backcast, head in zip(self.blocks, self.backcasts, self.forecasts):
            hidden = block(torch.cat([residual, covariates], -1))
            residual = residual - backcast(hidden)
            forecast = forecast + head(hidden)
        return ordered(forecast.reshape(-1, self.c["horizon"], 3))


def learn(y, dates, meta, availability, origin, c, kind, seed, epochs=None):
    torch.manual_seed(seed)
    torch.set_num_threads(c["threads"])
    torch.use_deterministic_algorithms(True)
    # Early stopping uses the latest complete horizon within the observed prefix.
    training_end = origin if epochs is not None else origin - c["horizon"]
    scale = scales(y, training_end)
    training = examples(
        y, dates, meta, availability, scale, c, c["lookback"], training_end
    )
    validation = (
        None
        if epochs is not None
        else examples(y, dates, meta, availability, scale, c, training_end, origin)
    )
    model = (LSTM if kind == "lstm" else NBEATS)(len(y), c)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=c["learning_rate"], weight_decay=c["weight_decay"]
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=c["epochs"])
    generator = torch.Generator().manual_seed(seed)
    best, best_epoch, stale, saved = float("inf"), 1, 0, None
    for epoch in range(epochs or c["epochs"]):
        model.train()
        order = torch.randperm(len(training[2]), generator=generator)
        for start in range(0, len(order), c["batch_size"]):
            ix = order[start : start + c["batch_size"]]
            a, b, ids, target, mask = (v[ix] for v in training)
            loss = pinball(model(a, b, ids), target, mask, c["quantiles"])
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), c["gradient_clip"])
            optimizer.step()
        scheduler.step()
        if validation is not None:
            model.eval()
            with torch.no_grad():
                a, b, ids, target, mask = validation
                value = float(pinball(model(a, b, ids), target, mask, c["quantiles"]))
            if value < best - 1e-6:
                best, best_epoch, stale, saved = (
                    value,
                    epoch + 1,
                    0,
                    deepcopy(model.state_dict()),
                )
            else:
                stale += 1
            if stale >= c["patience"]:
                break
    if saved is not None:
        model.load_state_dict(saved)
    return model.eval(), scale, (epochs or best_epoch)


def predict(model, y, dates, meta, availability, origin, scale, c):
    inputs = [
        window(y, dates, meta, availability, sid, origin, scale, c)
        for sid in range(len(y))
    ]
    with torch.no_grad():
        result = model(
            torch.tensor(np.asarray([a for a, b in inputs])),
            torch.tensor(np.asarray([b for a, b in inputs])),
            torch.arange(len(y)),
        ).numpy()
    return result * scale[:, None, None]


@tracked("forecast")
def train() -> dict:
    d, c = snapshot(), config("forecast")
    y, dates, meta, availability = panel(d)
    n = len(d["variants"])
    folder = ARTIFACTS / "forecast"
    folder.mkdir(parents=True, exist_ok=True)
    baseline = json.loads((ARTIFACTS / "baselines.json").read_text())
    if baseline["data_hash"] != d["data_hash"]:
        raise ValueError("Baseline dataset differs; rebuild baselines")
    results, rows, future, tracking = {}, [], {}, []
    validation_slice = slice(
        c["validation_origin"], c["validation_origin"] + c["horizon"]
    )
    for kind, groups in baseline["forecast"].items():
        results[kind] = {
            group: {"mean": metrics, "variance": {k: 0.0 for k in metrics}, "seeds": 1}
            for group, metrics in groups.items()
        }
        rows.extend(
            {"Model": kind, "Group": group, "Seeds": 1, **metrics, "wape_variance": 0.0}
            for group, metrics in groups.items()
        )
        validation_model = (
            None
            if kind == "seasonal_naive"
            else fit_forecast(y, dates, meta, c["validation_origin"], availability)
        )
        val_pred = predict_forecast(
            validation_model, y, dates, meta, c["validation_origin"], c["horizon"]
        )
        width80 = float(np.quantile(np.abs(y[:, validation_slice] - val_pred), 0.8))
        width95 = float(np.quantile(np.abs(y[:, validation_slice] - val_pred), 0.95))
        final_model = (
            None
            if kind == "seasonal_naive"
            else fit_forecast(y, dates, meta, len(dates), availability)
        )
        center = predict_forecast(final_model, y, dates, meta, len(dates), c["horizon"])
        future[kind] = {
            "quantiles": np.stack(
                [np.maximum(0, center - width80), center, center + width80], -1
            ),
            "width95": np.full(len(y), width95),
        }
    for kind in ["lstm", "nbeats"]:
        by_group = {"sku": [], "category": []}
        serving, widths = [], []
        for seed in c["seeds"]:
            _, _, epochs = learn(
                y, dates, meta, availability, c["validation_origin"], c, kind, seed
            )
            # Refit the selected epoch count; calibrate 95% widths before any test origin.
            vm, vs, _ = learn(
                y,
                dates,
                meta,
                availability,
                c["validation_origin"],
                c,
                kind,
                seed,
                epochs,
            )
            vp = predict(
                vm, y, dates, meta, availability, c["validation_origin"], vs, c
            )
            errors = np.abs(y[:, validation_slice] - vp[..., 1]) / vs[:, None]
            width = np.empty(len(y))
            for segment in [slice(0, n), slice(n, None)]:
                width[segment] = np.quantile(errors[segment], 0.95)
            observed = {"sku": [], "category": []}
            for origin in c["origins"]:
                model, scale, _ = learn(
                    y, dates, meta, availability, origin, c, kind, seed, epochs
                )
                quantiles = predict(
                    model, y, dates, meta, availability, origin, scale, c
                )[:, : c["evaluation_horizon"]]
                for group, segment in [
                    ("sku", slice(0, n)),
                    ("category", slice(n, None)),
                ]:
                    observed[group].append(
                        forecast_metrics(
                            y[segment, origin : origin + c["evaluation_horizon"]],
                            quantiles[segment, :, 1],
                            y[segment, :origin],
                            quantiles[segment, :, 0],
                            quantiles[segment, :, 2],
                        )
                    )
                if seed == c["seeds"][0]:
                    for i, m in enumerate(meta[:n]):
                        for step in range(c["evaluation_horizon"]):
                            tracking.append(
                                {
                                    "sku": m["sku"],
                                    "origin": str(dates[origin].date()),
                                    "week": str(dates[origin + step].date()),
                                    "model": kind,
                                    "actual": float(y[i, origin + step]),
                                    "prediction": float(quantiles[i, step, 1]),
                                }
                            )
            for group, scores in observed.items():
                by_group[group].append(
                    {k: float(np.mean([r[k] for r in scores])) for k in scores[0]}
                )
            final, scale, _ = learn(
                y, dates, meta, availability, len(dates), c, kind, seed, epochs
            )
            serving.append(
                predict(final, y, dates, meta, availability, len(dates), scale, c)
            )
            widths.append(width * scale)
            torch.save(
                {
                    "state_dict": final.state_dict(),
                    "scale": scale,
                    "config": c,
                    "seed": seed,
                    "epochs": epochs,
                },
                folder / f"{kind}-{seed}.pt",
            )
            print(kind, seed, by_group["sku"][-1], flush=True)
        results[kind] = {}
        for group, scores in by_group.items():
            mean = {k: float(np.mean([r[k] for r in scores])) for k in scores[0]}
            variance = {
                k: float(np.var([r[k] for r in scores], ddof=1)) for k in scores[0]
            }
            results[kind][group] = {
                "mean": mean,
                "variance": variance,
                "seeds": len(scores),
            }
            rows.append(
                {
                    "Model": kind,
                    "Group": group,
                    "Seeds": len(scores),
                    **mean,
                    "wape_variance": variance["wape"],
                }
            )
        # Final serving uses a fixed first seed, not a test-selected winner or untested ensemble.
        future[kind] = {"quantiles": serving[0], "width95": widths[0]}
    products = d["products"].set_index("id")
    models, category_models, inventory = {}, {}, []
    for kind, output in future.items():
        series = []
        for i, original in enumerate(meta):
            m = original.copy()
            if i < n:
                p = products.loc[m["product_id"]]
            else:
                p = pd.Series({"brand": "Aggregate", "name": m["category"]})
                selected = [
                    j
                    for j, sku in enumerate(meta[:n])
                    if sku["category"] == m["category"]
                ]
                volume = sum(float(y[j].sum()) for j in selected)
                m["price"] = sum(
                    float(y[j].sum()) * meta[j]["price"] for j in selected
                ) / max(1, volume)
            quantiles = output["quantiles"][i]
            predictions = []
            for step, q in enumerate(quantiles):
                lower95 = min(q[0], max(0, q[1] - output["width95"][i]))
                upper95 = max(q[2], q[1] + output["width95"][i])
                predictions.append(
                    {
                        "week": str((dates[-1] + pd.Timedelta(weeks=step + 1)).date()),
                        "prediction": float(q[1]),
                        "lower80": float(q[0]),
                        "upper80": float(q[2]),
                        "lower95": float(lower95),
                        "upper95": float(upper95),
                        "revenue": float(q[1] * m["price"]),
                    }
                )
            series.append(
                m
                | {
                    "brand": p.brand,
                    "name": p["name"],
                    "model": kind,
                    "intermittent": bool(np.mean(y[i] > 0) < 0.2),
                    "croston": croston(y[i], c["horizon"]).tolist(),
                    "history": [
                        {
                            "week": str(day.date()),
                            "actual": float(value),
                            "revenue": float(value * m["price"]),
                            "stockout": bool(not availability[i, t]),
                        }
                        for t, (day, value) in enumerate(zip(dates, y[i]))
                    ],
                    "forecast": predictions,
                }
            )
            if kind == "lightgbm" and i < n:
                demand = float(np.mean(quantiles[:4, 1]))
                safety = int(
                    np.ceil(
                        c["safety_z"]
                        * np.std(y[i, -12:])
                        * np.sqrt(c["lead_time_weeks"])
                    )
                )
                inventory.append(
                    {
                        "variant_id": m["id"],
                        "sku": m["sku"],
                        "name": p["name"],
                        "brand": p.brand,
                        "weekly_demand": demand,
                        "safety_stock": safety,
                        "reorder_point": int(
                            np.ceil(demand * c["lead_time_weeks"] + safety)
                        ),
                        "target_stock": int(np.ceil(demand * 4 + safety)),
                        "intermittent": series[-1]["intermittent"],
                    }
                )
        models[kind] = series[:n]
        category_models[kind] = series[n:]
    metrics = results["lightgbm"]["sku"]["mean"] | {
        "comparison": results,
        "interval_note": "DL P10–P90 bands are learned quantiles. Baseline serving bands and approximate 95% widths use pre-test validation residuals. Aggregate SKU bounds are sums, not calibrated joint intervals; four-week backtests do not validate the full 12-week horizon.",
    }
    output = {
        "data_hash": d["data_hash"],
        "simulated_data": True,
        "config": c,
        "results": results,
        "models": models,
        "category_models": category_models,
        "series": models["lightgbm"],
        "inventory": inventory,
        "tracking": tracking,
        "metrics": metrics,
        "as_of": str(dates[-1].date()),
    }
    save_json(ARTIFACTS / "forecast.json", output)
    write_report(
        "forecast",
        rows,
        f"Hash `{d['data_hash']}`. Shared expanding test origins {c['origins']}; first four steps scored for every model. Lookback/horizon {c['lookback']}/{c['horizon']}; all settings in YAML. Per-series scaling and training windows use observed prefixes only; stockout targets are masked for DL training (observed sales, not latent demand). Validation origin 52 selects epochs, never test scores. LSTM and generic residual N-BEATS covariate/quantile adaptation use seeds {c['seeds']}; mean metrics across origins, then seed means and sample variance. Baseline rows reproduce Phase 2 (one deterministic seed); their 80% interval calibration is the original 52/56/60 four-step procedure, while serving widths use validation weeks 52–63. WAPE and sMAPE are percentages; MASE and measured P10–P90 coverage are reported even when poor. N-BEATS is not the paper's interpretable configuration. Seed 42 serves; no test-selected ensemble. Small catalog, 78 simulated weeks and pooled intervals limit validity; no real-market accuracy claim.",
    )
    save_json(
        folder / "metrics.json",
        {
            "data_hash": d["data_hash"],
            "results": results,
            "simulated_data": True,
            "config": c,
        },
    )
    return output


if __name__ == "__main__":
    train()
