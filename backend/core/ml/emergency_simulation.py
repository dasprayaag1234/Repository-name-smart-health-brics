"""
Emergency simulation.

Uses the latest saved StockRisk records as the "before" state and
recomputes only the deterministic downstream arithmetic for an increased
demand scenario.

This avoids rerunning the expensive forecasting pipeline for every
facility/medicine pair, which keeps the API lightweight enough for
production.
"""

from core.models import Facility, StockRisk


def _risk_level(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def _recalculate_risk(row, surge_multiplier: float, horizon_days: int = 14):
    """
    Reproduce the same deterministic risk calculation used in
    core.ml.risk.compute_stock_risk(), but using the already-stored
    forecasted demand from StockRisk.
    """
    current_stock = float(row.current_stock or 0)
    incoming_supply = float(row.incoming_supply or 0)

    # The forecast itself is not rerun. Only demand is scaled.
    forecasted_demand_period = (
        float(row.forecasted_demand_period or 0) * surge_multiplier
    )

    projected_stock = (
        current_stock
        + incoming_supply
        - forecasted_demand_period
    )

    avg_daily_demand = (
        forecasted_demand_period / horizon_days
        if horizon_days
        else 0.0
    )

    days_of_stock = (
        (current_stock + incoming_supply) / avg_daily_demand
        if avg_daily_demand > 0
        else 999.0
    )

    shortage_quantity = max(0.0, -projected_stock)

    lead_time = row.medicine.avg_lead_time_days or 7

    if days_of_stock >= 999:
        urgency_component = 0.0
    else:
        urgency_component = max(
            0.0,
            min(
                100.0,
                100.0
                * (
                    1
                    - (days_of_stock - lead_time)
                    / (2 * lead_time)
                ),
            ),
        )

    shortage_component = min(
        100.0,
        (shortage_quantity / max(1.0, forecasted_demand_period))
        * 100.0,
    )

    risk_score = round(
        0.7 * urgency_component
        + 0.3 * shortage_component,
        1,
    )

    return {
        "current_stock": current_stock,
        "forecasted_demand_period": forecasted_demand_period,
        "incoming_supply": incoming_supply,
        "projected_stock": projected_stock,
        "days_of_stock": (
            round(days_of_stock, 1)
            if days_of_stock < 999
            else None
        ),
        "shortage_quantity": round(shortage_quantity, 1),
        "risk_score": risk_score,
        "risk_level": _risk_level(risk_score),
    }


def _risk_item(row, result):
    return {
        "facility": row.facility.name,
        "facility_id": row.facility.facility_id,
        "medicine": row.medicine.name,
        "risk_level": result["risk_level"],
        "risk_score": result["risk_score"],
        "days_of_stock": result["days_of_stock"],
        "shortage_quantity": result["shortage_quantity"],
    }


def _build_summary(rows, surge_multiplier=1.0):
    risk_counts = {
        "low": 0,
        "medium": 0,
        "high": 0,
        "critical": 0,
    }

    total_shortage_qty = 0.0
    at_risk = []

    for row in rows:
        result = (
            _recalculate_risk(row, surge_multiplier)
            if surge_multiplier != 1.0
            else {
                "current_stock": row.current_stock,
                "forecasted_demand_period": row.forecasted_demand_period,
                "incoming_supply": row.incoming_supply,
                "projected_stock": row.projected_stock,
                "days_of_stock": row.days_of_stock,
                "shortage_quantity": row.shortage_quantity,
                "risk_score": row.risk_score,
                "risk_level": row.risk_level,
            }
        )

        risk_counts[result["risk_level"]] += 1
        total_shortage_qty += result["shortage_quantity"]

        if result["risk_level"] in ("high", "critical"):
            at_risk.append(_risk_item(row, result))

    at_risk.sort(
        key=lambda x: x["risk_score"],
        reverse=True,
    )

    return {
        "risk_counts": risk_counts,
        "total_shortage_quantity": round(total_shortage_qty, 1),
        "top_at_risk": at_risk[:25],
        "facilities_scored": len(
            {row.facility_id for row in rows}
        ),
    }


def run_emergency_simulation(surge_pct, scope_state=""):
    """
    Run a what-if emergency demand surge without touching StockRisk.

    The latest saved StockRisk record for each facility/medicine pair is
    used as the baseline. The 'after' scenario scales only the saved
    forecasted demand.
    """

    # Keep the simulation bounded to the same 80-facility sample.
    facilities_qs = Facility.objects.all()

    if scope_state:
        facilities_qs = facilities_qs.filter(
            state=scope_state
        )

    facilities = list(
        facilities_qs.order_by("id")[:80]
    )

    facility_ids = [f.id for f in facilities]

    if not facility_ids:
        empty = {
            "risk_counts": {
                "low": 0,
                "medium": 0,
                "high": 0,
                "critical": 0,
            },
            "total_shortage_quantity": 0.0,
            "top_at_risk": [],
            "facilities_scored": 0,
        }

        return {
            "surge_pct": surge_pct,
            "scope_state": scope_state,
            "sample_size_facilities": 0,
            "before": empty,
            "after": empty,
            "delta": {
                "new_critical": 0,
                "new_high": 0,
                "additional_shortage_units": 0.0,
            },
        }

    # Get saved risk rows for the selected facilities.
    # Multiple historical StockRisk rows may exist, so retain only
    # the latest row for each facility/medicine pair.
    stock_risks = (
        StockRisk.objects
        .filter(facility_id__in=facility_ids)
        .select_related("facility", "medicine")
        .order_by("-computed_at")
    )

    latest_by_pair = {}

    for row in stock_risks:
        key = (row.facility_id, row.medicine_id)

        if key not in latest_by_pair:
            latest_by_pair[key] = row

    rows = list(latest_by_pair.values())

    surge_multiplier = 1.0 + (float(surge_pct) / 100.0)

    before = _build_summary(
        rows,
        surge_multiplier=1.0,
    )

    after = _build_summary(
        rows,
        surge_multiplier=surge_multiplier,
    )

    delta = {
        "new_critical": (
            after["risk_counts"]["critical"]
            - before["risk_counts"]["critical"]
        ),
        "new_high": (
            after["risk_counts"]["high"]
            - before["risk_counts"]["high"]
        ),
        "additional_shortage_units": round(
            after["total_shortage_quantity"]
            - before["total_shortage_quantity"],
            1,
        ),
    }

    return {
        "surge_pct": surge_pct,
        "scope_state": scope_state,
        "sample_size_facilities": len(facilities),
        "before": before,
        "after": after,
        "delta": delta,
    }