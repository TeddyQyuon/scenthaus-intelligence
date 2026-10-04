"""Pooled features, expanding windows, untouched eight-week holdout."""

import warnings
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX
from .calendar import features

NAMES = ["seasonal_naive", "ets", "sarima", "lightgbm", "croston"]


from .metrics import metrics


def croston(y, h, alpha=0.15):
    nz = np.flatnonzero(y > 0)
    if not len(nz):
        return np.zeros(h)
    z = float(y[nz[0]])
    interval = float(nz[0] + 1)
    last = nz[0]
    for t in nz[1:]:
        z += alpha * (y[t] - z)
        interval += alpha * (t - last - interval)
        last = t
    return np.full(h, (1 - alpha / 2) * z / max(interval, 1))


def statistical(name, y, dates, h):
    if name == "croston":
        return croston(y, h)
    if name == "seasonal_naive":
        return np.array(
            [
                y[len(y) - 52 + i] if len(y) >= 52 and i < 52 else np.mean(y[-4:])
                for i in range(h)
            ]
        )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if name == "ets":
            return np.maximum(
                0,
                ExponentialSmoothing(
                    y,
                    trend="add",
                    damped_trend=True,
                    seasonal="add" if len(y) >= 26 else None,
                    seasonal_periods=13,
                    initialization_method="estimated",
                )
                .fit()
                .forecast(h),
            )
        exog = np.array([features(d)[2:8] for d in dates])
        future = [dates[-1] + pd.Timedelta(weeks=i + 1) for i in range(h)]
        fit = SARIMAX(
            y,
            order=(1, 0, 0),
            seasonal_order=(1, 0, 0, 13),
            exog=exog,
            trend="c",
            enforce_stationarity=False,
            enforce_invertibility=False,
        ).fit(disp=False, maxiter=35)
        return np.maximum(
            0, fit.forecast(h, exog=np.array([features(d)[2:8] for d in future]))
        )


def feature_row(y, day, index, variant):
    return [
        index,
        int(variant.size_ml),
        int(variant.product_id),
        *[float(y[-lag]) if len(y) >= lag else 0 for lag in [1, 2, 4, 8, 13, 52]],
        float(np.mean(y[-4:])),
        float(np.std(y[-4:])),
        float(np.mean(y[-13:])),
        *features(day),
    ]


def pooled(panel, dates, variants, end):
    x = []
    target = []
    for i, v in enumerate(variants.itertuples()):
        for t in range(13, end):
            x.append(feature_row(panel[i, :t], dates[t], i, v))
            target.append(panel[i, t])
    model = LGBMRegressor(
        n_estimators=130,
        learning_rate=0.04,
        num_leaves=15,
        max_depth=5,
        min_child_samples=20,
        reg_lambda=2,
        n_jobs=2,
        verbosity=-1,
        random_state=42,
    )
    return model.fit(np.array(x), target)


def lgb_predict(model, y, dates, i, v, h):
    history = list(y)
    out = []
    for j in range(h):
        day = dates[-1] + pd.Timedelta(weeks=j + 1)
        pred = max(
            0, float(model.predict(np.array([feature_row(history, day, i, v)]))[0])
        )
        out.append(pred)
        history.append(pred)
    return np.array(out)


def train(products, variants, orders):
    variants = variants.sort_values("id").reset_index(drop=True)
    o = orders.copy()
    o["week"] = pd.to_datetime(o.created_at).dt.to_period("W-SUN").dt.start_time
    dates = pd.date_range(o.week.min(), o.week.max(), freq="W-MON")
    panel = np.array(
        [
            o[o.sku == v.sku]
            .groupby("week")
            .quantity.sum()
            .reindex(dates, fill_value=0)
            .values
            for v in variants.itertuples()
        ],
        float,
    )
    if len(dates) < 64:
        raise ValueError("At least 64 weekly observations are required")
    test = len(dates) - 8
    origins = [test - 20, test - 12, test - 4]
    errors = {name: np.zeros(len(variants)) for name in NAMES}
    residuals = {name: [] for name in NAMES}
    failures = []

    def predict(name, i, end, h, lgb):
        try:
            if name == "lightgbm":
                return lgb_predict(
                    lgb,
                    panel[i, :end],
                    dates[:end],
                    i,
                    next(v for n, v in enumerate(variants.itertuples()) if n == i),
                    h,
                )
            return statistical(name, panel[i, :end], dates[:end], h)
        except Exception as exc:
            failures.append(
                {
                    "model": name,
                    "sku": variants.iloc[i].sku,
                    "origin": end,
                    "error": type(exc).__name__,
                }
            )
            return statistical("seasonal_naive", panel[i, :end], dates[:end], h)

    for origin in origins:
        lgb = pooled(panel, dates, variants, origin)
        for i in range(len(variants)):
            for name in NAMES:
                p = predict(name, i, origin, 4, lgb)
                a = panel[i, origin : origin + 4]
                errors[name][i] += np.abs(a - p).mean()
                residuals[name].extend((np.abs(a - p) / (np.sqrt(p) + 1)).tolist())
    chosen = []
    for i in range(len(variants)):
        sparse = np.mean(panel[i, :test] == 0) > 0.45 or panel[i, :test].mean() < 0.8
        chosen.append("croston" if sparse else min(NAMES, key=lambda n: errors[n][i]))
    calibrated = {
        n: [float(np.quantile(residuals[n], q)) for q in [0.8, 0.95]] for n in NAMES
    }
    lgbtest = pooled(panel, dates, variants, test)
    test_predictions = np.zeros((len(variants), 8))
    tracking = []
    ladder = {n: [] for n in NAMES}
    coverage80 = []
    coverage95 = []
    for i, v in enumerate(variants.itertuples()):
        for name in NAMES:
            pred = predict(name, i, test, 8, lgbtest)
            ladder[name].append(metrics(panel[i, test:], pred, panel[i, :test])["wape"])
            if name == chosen[i]:
                test_predictions[i] = pred
        for j, p in enumerate(test_predictions[i]):
            width = (np.sqrt(p) + 1) * np.sqrt(1 + max(0, j - 3) * 0.08)
            q80, q95 = calibrated[chosen[i]]
            a = panel[i, test + j]
            lo80 = max(0, p - width * q80)
            hi80 = p + width * q80
            lo95 = max(0, p - width * q95)
            hi95 = p + width * q95
            coverage80.append(lo80 <= a <= hi80)
            coverage95.append(lo95 <= a <= hi95)
            tracking.append(
                {
                    "sku": v.sku,
                    "week": str(dates[test + j].date()),
                    "actual": float(a),
                    "prediction": float(p),
                    "lower80": float(lo80),
                    "upper80": float(hi80),
                    "lower95": float(lo95),
                    "upper95": float(hi95),
                    "kind": "untouched_holdout",
                }
            )
    lgbfinal = pooled(panel, dates, variants, len(dates))
    output = []
    inventory = []
    for i, v in enumerate(variants.itertuples()):
        pred = predict(chosen[i], i, len(dates), 12, lgbfinal)
        product = products[products.id == v.product_id].iloc[0]
        future = []
        for j, p in enumerate(pred):
            width = (np.sqrt(p) + 1) * np.sqrt(1 + max(0, j - 3) * 0.08)
            q80, q95 = calibrated[chosen[i]]
            future.append(
                {
                    "week": str((dates[-1] + pd.Timedelta(weeks=j + 1)).date()),
                    "prediction": float(p),
                    "lower80": float(max(0, p - width * q80)),
                    "upper80": float(p + width * q80),
                    "lower95": float(max(0, p - width * q95)),
                    "upper95": float(p + width * q95),
                    "revenue": float(p * float(v.price)),
                }
            )
        weekly = float(pred[:4].mean())
        safety = int(np.ceil(1.645 * panel[i, -13:].std() * np.sqrt(v.lead_time_weeks)))
        rop = int(np.ceil(weekly * v.lead_time_weeks + safety))
        target = int(np.ceil(weekly * (v.lead_time_weeks + 4) + safety))
        risk = (
            "stockout"
            if v.stock == 0
            else "reorder"
            if v.stock < rop
            else "overstock"
            if v.stock > max(weekly * 12, safety + 12)
            else "healthy"
        )
        inventory.append(
            {
                "sku": v.sku,
                "variant_id": int(v.id),
                "product_id": int(v.product_id),
                "name": product["name"],
                "stock": int(v.stock),
                "weekly_demand": weekly,
                "lead_time_weeks": int(v.lead_time_weeks),
                "safety_stock": safety,
                "reorder_point": rop,
                "target_stock": target,
                "risk": risk,
                "suggested_reorder": max(0, target - int(v.stock))
                if risk in ["stockout", "reorder"]
                else 0,
                "trend": float(
                    (panel[i, -4:].sum() + 1) / (panel[i, -8:-4].sum() + 1) - 1
                ),
            }
        )
        output.append(
            {
                "sku": v.sku,
                "product_id": int(v.product_id),
                "brand": product.brand,
                "category": product.category,
                "size_ml": int(v.size_ml),
                "price": float(v.price),
                "model": chosen[i],
                "history": [
                    {
                        "week": str(d.date()),
                        "actual": float(a),
                        "revenue": float(a * float(v.price)),
                    }
                    for d, a in zip(dates, panel[i])
                ],
                "forecast": future,
            }
        )
    result = metrics(
        panel[:, test:].ravel(), test_predictions.ravel(), panel[:, :test].ravel()
    )
    # MASE is calculated per series, then averaged; concatenating SKUs gives artificial boundaries.
    mase = [
        metrics(panel[i, test:], test_predictions[i], panel[i, :test])["mase"]
        for i in range(len(variants))
    ]
    result["mase"] = float(np.mean([m for m in mase if m is not None]))
    result |= {
        "coverage80": float(np.mean(coverage80)),
        "coverage95": float(np.mean(coverage95)),
        "model_macro_sku_wape": {
            n: float(np.mean([v for v in values if v is not None]))
            for n, values in ladder.items()
        },
        "validation_origins": [str(dates[t].date()) for t in origins],
        "test_origin": str(dates[test].date()),
        "selection_counts": {n: chosen.count(n) for n in NAMES},
        "failures": failures,
        "interval_note": "Pooled normalized validation residuals, widened beyond four weeks. Aggregated sums of SKU bounds are conservative, not calibrated joint intervals.",
    }
    return {
        "series": output,
        "inventory": inventory,
        "tracking": tracking,
        "metrics": result,
    }
