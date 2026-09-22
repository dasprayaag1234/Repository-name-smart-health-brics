"""
Emergency simulation: the user picks a footfall surge (e.g. +30%) and
optionally scopes it to one state. We snapshot current national risk
("before"), recompute risk with demand scaled up by the surge factor
("after"), and diff the two so the dashboard can show a clear before/after.

This does not permanently overwrite the live StockRisk table — it's a
what-if sandbox. Only the emergency-simulation endpoints in the API run
this; the main pipeline is untouched.
"""
from core.ml.risk import compute_stock_risk


def _snapshot(facilities, medicines_by_facility, surge_multiplier):
    """
    facilities: iterable of Facility
    medicines_by_facility: {facility_id: [Medicine, ...]} — medicines actually stocked there
    Returns aggregate counts + top at-risk list (kept small for API payload size).
    """
    risk_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    total_shortage_qty = 0.0
    at_risk = []
    for facility in facilities:
        for medicine in medicines_by_facility.get(facility.id, []):
            result = compute_stock_risk(facility, medicine, surge_multiplier=surge_multiplier, use_ml=False)
            risk_counts[result["risk_level"]] += 1
            total_shortage_qty += result["shortage_quantity"]
            if result["risk_level"] in ("high", "critical"):
                at_risk.append({
                    "facility": facility.name,
                    "facility_id": facility.facility_id,
                    "medicine": medicine.name,
                    "risk_level": result["risk_level"],
                    "risk_score": result["risk_score"],
                    "days_of_stock": result["days_of_stock"],
                    "shortage_quantity": result["shortage_quantity"],
                })
    at_risk.sort(key=lambda x: x["risk_score"], reverse=True)
    return {
        "risk_counts": risk_counts,
        "total_shortage_units": round(total_shortage_qty, 1),
        "top_at_risk": at_risk[:25],
        "facilities_scored": len(facilities) if hasattr(facilities, "__len__") else None,
    }


def run_emergency_simulation(surge_pct: float, scope_state: str = ""):
    """
    Returns {before, after, delta} snapshots. Runs on a bounded sample of
    facilities (not the full national set) to keep this interactive —
    it's a what-if tool, not a batch job, and is labelled as sampling the
    national picture when scope_state is empty.
    """
    from core.models import Facility, InventoryHistory

    facilities_qs = Facility.objects.all()
    if scope_state:
        facilities_qs = facilities_qs.filter(state=scope_state)
    facilities = list(facilities_qs[:80])  # bounded sample for interactive response times

    facility_ids = [f.id for f in facilities]
    medicines_by_facility = {}
    for row in (InventoryHistory.objects.filter(facility_id__in=facility_ids)
                .order_by().values("facility_id", "medicine_id").distinct()):
        medicines_by_facility.setdefault(row["facility_id"], []).append(row["medicine_id"])

    from core.models import Medicine
    medicine_cache = {m.id: m for m in Medicine.objects.all()}
    medicines_by_facility = {
        fid: [medicine_cache[mid] for mid in mids if mid in medicine_cache]
        for fid, mids in medicines_by_facility.items()
    }

    before = _snapshot(facilities, medicines_by_facility, surge_multiplier=1.0)
    after = _snapshot(facilities, medicines_by_facility, surge_multiplier=1.0 + surge_pct / 100.0)

    delta = {
        "new_critical": after["risk_counts"]["critical"] - before["risk_counts"]["critical"],
        "new_high": after["risk_counts"]["high"] - before["risk_counts"]["high"],
        "additional_shortage_units": round(after["total_shortage_units"] - before["total_shortage_units"], 1),
    }
    return {
        "surge_pct": surge_pct,
        "scope_state": scope_state or "national (sampled)",
        "sample_size_facilities": len(facilities),
        "before": before,
        "after": after,
        "delta": delta,
    }
