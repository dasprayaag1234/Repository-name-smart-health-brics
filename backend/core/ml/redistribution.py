"""
Redistribution recommendations: for each medicine, find facilities in
shortage (high/critical risk, positive shortage_quantity) and match them
against facilities holding transferable surplus of the same medicine.

"Transferable surplus" = current stock well above the facility's own
safety stock + forecasted need, so donating doesn't create a new shortage
there.
"""
from math import radians, sin, cos, sqrt, atan2

from core.ml.risk import compute_stock_risk


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def find_surplus_facilities(medicine, exclude_facility_ids=None, horizon_days=14, facility_ids=None):
    """Facilities holding medicine with closing_stock comfortably above
    their own safety stock + forecasted need — i.e. stock they could give
    away without creating their own shortage.

    Reuses already-computed StockRisk rows (from the same pipeline run)
    rather than recomputing risk per facility, which is the difference
    between this running in seconds vs. minutes at national scale.
    """
    from core.models import InventoryHistory, StockRisk

    exclude_facility_ids = exclude_facility_ids or set()
    risk_qs = StockRisk.objects.filter(medicine=medicine, risk_level="low").select_related("facility")
    if facility_ids is not None:
        risk_qs = risk_qs.filter(facility_id__in=facility_ids)
    risk_qs = risk_qs.exclude(facility_id__in=exclude_facility_ids)

    facility_id_list = list(risk_qs.values_list("facility_id", flat=True))
    safety_by_facility = {}
    for row in (InventoryHistory.objects
                .filter(medicine=medicine, facility_id__in=facility_id_list)
                .order_by("facility_id", "-date")
                .values("facility_id", "safety_stock")):
        safety_by_facility.setdefault(row["facility_id"], row["safety_stock"])

    candidates = []
    for risk in risk_qs:
        safety_stock = safety_by_facility.get(risk.facility_id, 0)
        surplus_buffer = risk.current_stock - safety_stock - risk.forecasted_demand_period
        if surplus_buffer > 0:
            candidates.append({
                "facility": risk.facility,
                "current_stock": risk.current_stock,
                "transferable_quantity": int(surplus_buffer * 0.5),  # only offer up to half the buffer
            })
    return candidates


def generate_redistribution_recommendations(horizon_days=14, top_n_per_medicine=5):
    """
    Returns a list of dicts ready to become RedistributionRecommendation rows:
    {source_facility, destination_facility, medicine, recommended_quantity, urgency, reason, distance_km}
    """
    from core.models import Medicine, Facility, StockRisk

    recommendations = []
    for medicine in Medicine.objects.all():
        shortages = (StockRisk.objects
                     .filter(medicine=medicine, risk_level__in=["high", "critical"], shortage_quantity__gt=0)
                     .select_related("facility")
                     .order_by("-risk_score")[:top_n_per_medicine])
        if not shortages:
            continue
        surplus_candidates = find_surplus_facilities(
            medicine, exclude_facility_ids={s.facility_id for s in shortages}, horizon_days=horizon_days
        )
        if not surplus_candidates:
            continue

        for shortage in shortages:
            dest = shortage.facility
            # rank surplus candidates by distance to this destination
            ranked = sorted(
                surplus_candidates,
                key=lambda c: haversine_km(dest.latitude, dest.longitude, c["facility"].latitude, c["facility"].longitude)
            )
            need = shortage.shortage_quantity
            for cand in ranked:
                if need <= 0:
                    break
                if cand["transferable_quantity"] <= 0:
                    continue
                qty = int(min(need, cand["transferable_quantity"]))
                if qty <= 0:
                    continue
                distance = haversine_km(dest.latitude, dest.longitude, cand["facility"].latitude, cand["facility"].longitude)
                recommendations.append({
                    "source_facility": cand["facility"],
                    "destination_facility": dest,
                    "medicine": medicine,
                    "recommended_quantity": qty,
                    "urgency": shortage.risk_level,
                    "reason": (
                        f"{dest.name} is {shortage.risk_level} risk for {medicine.name} "
                        f"(projected shortage {round(shortage.shortage_quantity, 1)} units, "
                        f"expected stock-out {shortage.expected_stockout_date or 'imminent'}). "
                        f"{cand['facility'].name} holds transferable surplus ({cand['transferable_quantity']} units) "
                        f"{round(distance, 1)} km away."
                    ),
                    "distance_km": round(distance, 1),
                })
                cand["transferable_quantity"] -= qty
                need -= qty
    return recommendations
