"""
Demand forecasting: predicts daily medicine consumption per facility/medicine
for 7/14/30-day horizons.

Approach:
- Primary model: XGBoost regressor trained on lag + rolling-window + calendar
  features, built from InventoryHistory.consumed (and HMIS footfall as an
  exogenous driver). Forecasts are generated recursively, one day at a time,
  feeding each prediction back in as a lag feature for the next day.
- Fallback: when there isn't enough history to fit a model (< MIN_HISTORY_DAYS
  observations), falls back to a weighted moving average with day-of-week
  seasonality. This is flagged explicitly (is_demo_fallback=True) — it is
  never silently presented as an ML forecast.

This module works directly off the Django ORM, so it runs identically
whether InventoryHistory was populated from real CSVs or from the demo data
generator.
"""
import logging
from datetime import timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MIN_HISTORY_DAYS = 14
LAGS = [1, 2, 3, 7, 14]
ROLLING_WINDOWS = [3, 7, 14]


def _build_feature_frame(history_df: pd.DataFrame, footfall_df: pd.DataFrame | None = None) -> pd.DataFrame:
    df = history_df.copy().sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    if footfall_df is not None and not footfall_df.empty:
        footfall_df = footfall_df.copy()
        footfall_df["date"] = pd.to_datetime(footfall_df["date"])
        df = df.merge(footfall_df[["date", "opd_footfall"]], on="date", how="left")
        df["opd_footfall"] = df["opd_footfall"].ffill().fillna(0)
    else:
        df["opd_footfall"] = 0

    df["dow"] = df["date"].dt.dayofweek
    for lag in LAGS:
        df[f"lag_{lag}"] = df["consumed"].shift(lag)
    for w in ROLLING_WINDOWS:
        df[f"roll_mean_{w}"] = df["consumed"].shift(1).rolling(w).mean()
    return df


def _fit_xgboost(feature_df: pd.DataFrame):
    from xgboost import XGBRegressor

    feature_cols = [c for c in feature_df.columns if c.startswith("lag_") or c.startswith("roll_mean_")] + ["dow", "opd_footfall"]
    train_df = feature_df.dropna(subset=feature_cols + ["consumed"])
    if len(train_df) < MIN_HISTORY_DAYS:
        return None, feature_cols

    X = train_df[feature_cols]
    y = train_df["consumed"]
    model = XGBRegressor(
        n_estimators=150, max_depth=3, learning_rate=0.08,
        subsample=0.9, colsample_bytree=0.9, reg_lambda=1.0,
        objective="reg:squarederror", random_state=42,
    )
    model.fit(X, y)
    residuals = y - model.predict(X)
    residual_std = float(np.std(residuals)) if len(residuals) > 1 else max(1.0, y.mean() * 0.2)
    return {"model": model, "feature_cols": feature_cols, "residual_std": residual_std}, feature_cols


def _recursive_forecast_xgb(fit, feature_df: pd.DataFrame, horizon_days: int, avg_footfall: float):
    model = fit["model"]
    feature_cols = fit["feature_cols"]
    residual_std = fit["residual_std"]

    history = feature_df[["date", "consumed"]].copy()
    last_date = history["date"].max()
    consumed_series = list(history["consumed"])

    forecasts = []
    for step in range(1, horizon_days + 1):
        row = {}
        for lag in LAGS:
            row[f"lag_{lag}"] = consumed_series[-lag] if len(consumed_series) >= lag else np.mean(consumed_series)
        for w in ROLLING_WINDOWS:
            window = consumed_series[-w:] if len(consumed_series) >= w else consumed_series
            row[f"roll_mean_{w}"] = float(np.mean(window)) if window else 0.0
        next_date = last_date + timedelta(days=step)
        row["dow"] = next_date.dayofweek
        row["opd_footfall"] = avg_footfall
        X_pred = pd.DataFrame([row])[feature_cols]
        pred = max(0.0, float(model.predict(X_pred)[0]))
        consumed_series.append(pred)
        forecasts.append({
            "date": next_date.date().isoformat(),
            "predicted_demand": round(pred, 1),
            "lower": round(max(0.0, pred - 1.28 * residual_std), 1),   # ~80% interval
            "upper": round(pred + 1.28 * residual_std, 1),
        })
    return forecasts


def _fallback_forecast(history_df: pd.DataFrame, horizon_days: int):
    """Weighted moving average + day-of-week seasonality. Used when there's
    too little history to fit a model. Always flagged as a fallback."""
    df = history_df.copy().sort_values("date")
    df["date"] = pd.to_datetime(df["date"])
    if df.empty:
        overall_mean, dow_factor, std = 5.0, {}, 2.0
    else:
        overall_mean = float(df["consumed"].mean()) or 1.0
        df["dow"] = df["date"].dt.dayofweek
        dow_avg = df.groupby("dow")["consumed"].mean()
        dow_factor = (dow_avg / overall_mean).to_dict() if overall_mean else {}
        std = float(df["consumed"].std()) if len(df) > 1 else overall_mean * 0.3

    last_date = df["date"].max() if not df.empty else pd.Timestamp.today()
    forecasts = []
    for step in range(1, horizon_days + 1):
        next_date = last_date + timedelta(days=step)
        factor = dow_factor.get(next_date.dayofweek, 1.0)
        pred = max(0.0, overall_mean * factor)
        forecasts.append({
            "date": next_date.date().isoformat(),
            "predicted_demand": round(pred, 1),
            "lower": round(max(0.0, pred - 1.28 * std), 1),
            "upper": round(pred + 1.28 * std, 1),
        })
    return forecasts


def forecast_demand(facility_id: int, medicine_id: int, horizon_days: int = 14, use_ml: bool = True):
    """
    Returns (forecasts: list[dict], model_used: str, is_demo_fallback: bool)

    use_ml=False skips XGBoost entirely and uses the fast weighted-moving-average
    path. Used for bulk risk scoring across thousands of facility/medicine pairs,
    where fitting a fresh model per pair would be too slow; individual API calls
    (e.g. "show me the forecast for this facility+medicine") use the full model.
    """
    from core.models import InventoryHistory, HMISActivity

    history_qs = InventoryHistory.objects.filter(facility_id=facility_id, medicine_id=medicine_id).values(
        "date", "consumed"
    )
    history_df = pd.DataFrame.from_records(history_qs)

    if not use_ml:
        return _fallback_forecast(history_df, horizon_days), "weighted_moving_average", True

    footfall_qs = HMISActivity.objects.filter(facility_id=facility_id).values("date", "opd_footfall")
    footfall_df = pd.DataFrame.from_records(footfall_qs)
    avg_footfall = float(footfall_df["opd_footfall"].mean()) if not footfall_df.empty else 0.0

    if history_df.empty or len(history_df) < MIN_HISTORY_DAYS:
        return _fallback_forecast(history_df, horizon_days), "weighted_moving_average", True

    try:
        feature_df = _build_feature_frame(history_df, footfall_df)
        fit, _ = _fit_xgboost(feature_df)
        if fit is None:
            return _fallback_forecast(history_df, horizon_days), "weighted_moving_average", True
        forecasts = _recursive_forecast_xgb(fit, feature_df, horizon_days, avg_footfall)
        return forecasts, "xgboost", False
    except Exception:  # noqa: BLE001 - forecasting must never 500 the API; fall back instead
        logger.exception("XGBoost forecast failed for facility=%s medicine=%s, using fallback", facility_id, medicine_id)
        return _fallback_forecast(history_df, horizon_days), "weighted_moving_average", True
