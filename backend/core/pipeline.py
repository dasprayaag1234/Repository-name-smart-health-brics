"""
Runs the full analytics pipeline and persists results:
  inventory/HMIS data -> demand forecast -> stock-out risk -> redistribution
  recommendations -> optimized routes

Called by the `run_pipeline` management command, and by API endpoints that
need fresh numbers (e.g. after an emergency simulation toggle).
"""
import logging

from django.db import transaction

logger = logging.getLogger(__name__)


def run_full_pipeline(horizon_days=14, surge_multiplier=1.0, facility_qs=None):
    """
    Computes StockRisk for every facility/medicine pair that has inventory
    history, then derives RedistributionRecommendation and OptimizedRoute
    from the results. Returns summary counts.
    """
    from core.models import Facility, Medicine, InventoryHistory, StockRisk, RedistributionRecommendation, OptimizedRoute
    from core.ml.risk import compute_stock_risk
    from core.ml.redistribution import generate_redistribution_recommendations
    from core.ml.route_optimization import build_routes_from_recommendations

    facilities = facility_qs if facility_qs is not None else Facility.objects.all()
    pairs = (InventoryHistory.objects
             .filter(facility__in=facilities)
             .order_by()
             .values_list("facility_id", "medicine_id").distinct())

    facility_cache = {f.id: f for f in facilities}
    medicine_cache = {m.id: m for m in Medicine.objects.all()}

    risk_rows = []
    for facility_id, medicine_id in pairs:
        facility = facility_cache.get(facility_id)
        medicine = medicine_cache.get(medicine_id)
        if not facility or not medicine:
            continue
        result = compute_stock_risk(facility, medicine, horizon_days=horizon_days, surge_multiplier=surge_multiplier, use_ml=False)
        risk_rows.append(StockRisk(
            facility=facility, medicine=medicine,
            current_stock=result["current_stock"],
            forecasted_demand_period=result["forecasted_demand_period"],
            incoming_supply=result["incoming_supply"],
            projected_stock=result["projected_stock"],
            days_of_stock=result["days_of_stock"] if result["days_of_stock"] is not None else 999,
            expected_stockout_date=result["expected_stockout_date"],
            shortage_quantity=result["shortage_quantity"],
            risk_score=result["risk_score"],
            risk_level=result["risk_level"],
            explanation=result["explanation"],
        ))

    with transaction.atomic():
        StockRisk.objects.filter(facility__in=facilities).delete()
        StockRisk.objects.bulk_create(risk_rows, batch_size=2000)

        rec_dicts = generate_redistribution_recommendations(horizon_days=horizon_days)
        RedistributionRecommendation.objects.all().delete()
        rec_objs = [RedistributionRecommendation(**d) for d in rec_dicts]
        RedistributionRecommendation.objects.bulk_create(rec_objs)

        route_dicts = build_routes_from_recommendations(rec_objs)
        OptimizedRoute.objects.all().delete()
        route_objs = [
            OptimizedRoute(
                origin_facility=r["origin_facility"], stops=r["stops"],
                total_distance_km=r["total_distance_km"], total_eta_hours=r["total_eta_hours"],
                is_demo_abstraction=True,
            ) for r in route_dicts
        ]
        OptimizedRoute.objects.bulk_create(route_objs)

    return {
        "facility_medicine_pairs_scored": len(risk_rows),
        "critical_or_high_risk": sum(1 for r in risk_rows if r.risk_level in ("high", "critical")),
        "redistribution_recommendations": len(rec_objs),
        "optimized_routes": len(route_objs),
    }
