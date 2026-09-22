"""
Stock-out risk calculation.

Formula (deterministic, as specified):
    Projected Stock = Current Stock + Incoming Supply - Forecasted Demand

From that we derive days-of-stock, an expected stock-out date, shortage
quantity, and a 0-100 risk score. The ML demand forecast feeds the
"Forecasted Demand" term; everything downstream is transparent arithmetic
so the Gemini assistant (core/ai/assistant.py) can explain risk using the
real numbers computed here rather than inventing any.
"""
from datetime import date, timedelta

from django.utils import timezone

from core.ml.forecasting import forecast_demand


def _risk_level(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def compute_stock_risk(facility, medicine, horizon_days: int = 14, surge_multiplier: float = 1.0, use_ml: bool = True):
    """
    Computes stock-out risk for one facility/medicine pair.
    surge_multiplier > 1.0 is used by the emergency simulation to scale up
    forecasted demand (e.g. 1.3 for a +30% footfall surge) without touching
    the underlying model.

    Returns a dict matching the StockRisk model fields (not yet saved).
    """
    from core.models import InventoryHistory, Order

    latest = (InventoryHistory.objects
              .filter(facility=facility, medicine=medicine)
              .order_by("-date")
              .first())
    current_stock = latest.closing_stock if latest else 0

    forecasts, model_used, is_fallback = forecast_demand(facility.id, medicine.id, horizon_days, use_ml=use_ml)
    forecasted_demand_period = sum(f["predicted_demand"] for f in forecasts) * surge_multiplier

    incoming_supply = sum(
        Order.objects.filter(facility=facility, medicine=medicine, status__in=["approved", "shipped"])
        .values_list("quantity", flat=True)
    )

    projected_stock = current_stock + incoming_supply - forecasted_demand_period

    # days of stock: how many days current_stock (+incoming) lasts at the forecasted daily burn rate
    avg_daily_demand = (forecasted_demand_period / horizon_days) if horizon_days else 0.0
    days_of_stock = ((current_stock + incoming_supply) / avg_daily_demand) if avg_daily_demand > 0 else 999.0

    expected_stockout_date = None
    if avg_daily_demand > 0 and days_of_stock < 365:
        expected_stockout_date = date.today() + timedelta(days=max(0, int(days_of_stock)))

    shortage_quantity = max(0.0, -projected_stock)

    # Risk score: blends how soon we run out against the lead time needed to
    # reorder, plus the raw shortage size. Fully deterministic from the
    # numbers above so it can be explained, not a black box.
    lead_time = medicine.avg_lead_time_days or 7
    if days_of_stock >= 999:
        urgency_component = 0.0
    else:
        # 100 when stock runs out today or before lead time even starts, 0 once
        # days_of_stock is comfortably beyond 2x lead time
        urgency_component = max(0.0, min(100.0, 100.0 * (1 - (days_of_stock - lead_time) / (2 * lead_time))))
    shortage_component = min(100.0, (shortage_quantity / max(1.0, forecasted_demand_period)) * 100.0)
    risk_score = round(0.7 * urgency_component + 0.3 * shortage_component, 1)
    risk_level = _risk_level(risk_score)

    explanation_bits = [
        f"Current stock is {current_stock} units.",
        f"Forecasted demand over the next {horizon_days} days is {round(forecasted_demand_period, 1)} units"
        + (f" (model: {model_used}{', fallback — limited history' if is_fallback else ''})." if True else "."),
        f"Incoming confirmed supply: {incoming_supply} units.",
        f"Projected stock after {horizon_days} days: {round(projected_stock, 1)} units.",
    ]
    if days_of_stock < 999:
        explanation_bits.append(f"At current burn rate, stock lasts about {round(days_of_stock, 1)} days"
                                 + (f", with a supplier lead time of {lead_time} days" if lead_time else "") + ".")
    if shortage_quantity > 0:
        explanation_bits.append(f"Projected shortage of {round(shortage_quantity, 1)} units if nothing changes.")
    explanation = " ".join(explanation_bits)

    return {
        "current_stock": current_stock,
        "forecasted_demand_period": round(forecasted_demand_period, 1),
        "incoming_supply": incoming_supply,
        "projected_stock": round(projected_stock, 1),
        "days_of_stock": round(days_of_stock, 1) if days_of_stock < 999 else None,
        "expected_stockout_date": expected_stockout_date,
        "shortage_quantity": round(shortage_quantity, 1),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "explanation": explanation,
        "model_used": model_used,
        "is_demo_fallback": is_fallback,
        "forecast_daily": forecasts,
    }
