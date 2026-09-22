"""
Route optimization for approved redistribution transfers.

IMPORTANT — labelled demo abstraction:
There is no live traffic/roads API wired in here. Distances are great-circle
(haversine) and ETAs are estimated from an assumed average road speed. This
is exactly the "clearly labelled demo abstraction" the spec calls for
instead of claiming live routing. Every OptimizedRoute this produces sets
is_demo_abstraction=True, and the frontend must always surface that label.

Algorithm: groups transfers by source facility (one vehicle per source),
then orders destination stops with a nearest-neighbor heuristic, optionally
improved with a single 2-opt pass — a reasonable stand-in for a full
OR-Tools VRP solve without requiring a distance-matrix API.
"""
from core.ml.redistribution import haversine_km

ASSUMED_AVG_SPEED_KMH = 35.0  # rural/semi-urban Indian road network, demo assumption


def _route_distance(stops):
    total = 0.0
    for i in range(len(stops) - 1):
        a, b = stops[i], stops[i + 1]
        total += haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
    return total


def _two_opt(stops):
    """Single pass of 2-opt improvement on a small stop list (demo-scale, so
    this stays cheap rather than iterating to full convergence)."""
    best = stops[:]
    best_dist = _route_distance(best)
    n = len(best)
    for i in range(1, n - 1):
        for j in range(i + 1, n):
            candidate = best[:i] + best[i:j][::-1] + best[j:]
            dist = _route_distance(candidate)
            if dist < best_dist:
                best, best_dist = candidate, dist
    return best, best_dist


def _nearest_neighbor_order(origin, destinations):
    remaining = destinations[:]
    ordered = []
    current = origin
    while remaining:
        nxt = min(remaining, key=lambda d: haversine_km(current["lat"], current["lon"], d["lat"], d["lon"]))
        ordered.append(nxt)
        remaining.remove(nxt)
        current = nxt
    return ordered


def build_routes_from_recommendations(recommendations):
    """
    recommendations: iterable of RedistributionRecommendation-like objects/dicts
    with .source_facility, .destination_facility, .medicine, .recommended_quantity, .urgency

    Returns a list of route dicts ready for OptimizedRoute:
    {origin_facility, stops: [...], total_distance_km, total_eta_hours}
    """
    by_source = {}
    for rec in recommendations:
        by_source.setdefault(rec.source_facility_id, []).append(rec)

    routes = []
    for source_id, recs in by_source.items():
        origin_facility = recs[0].source_facility
        origin = {"lat": origin_facility.latitude, "lon": origin_facility.longitude}

        # collapse multiple medicines going to the same destination into one stop
        stops_by_dest = {}
        for rec in recs:
            dest = rec.destination_facility
            entry = stops_by_dest.setdefault(dest.id, {
                "facility_id": dest.facility_id,
                "name": dest.name,
                "lat": dest.latitude,
                "lon": dest.longitude,
                "medicines": [],
                "urgency": rec.urgency,
            })
            entry["medicines"].append({"medicine": rec.medicine.name, "quantity": rec.recommended_quantity})
            # keep the most urgent label if multiple recs to the same destination differ
            urgency_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            if urgency_rank.get(rec.urgency, 0) > urgency_rank.get(entry["urgency"], 0):
                entry["urgency"] = rec.urgency

        destinations = list(stops_by_dest.values())
        # nearest-neighbor first, then a light 2-opt pass if small enough to be cheap
        ordered = _nearest_neighbor_order(origin, destinations)
        full_path = [origin] + ordered
        if len(full_path) <= 8:
            full_path, total_distance = _two_opt(full_path)
        else:
            total_distance = _route_distance(full_path)

        cumulative_km = 0.0
        stops_out = []
        prev = origin
        for stop in full_path[1:]:
            leg_km = haversine_km(prev["lat"], prev["lon"], stop["lat"], stop["lon"])
            cumulative_km += leg_km
            eta_hours = round(cumulative_km / ASSUMED_AVG_SPEED_KMH, 1)
            stops_out.append({
                "facility_id": stop["facility_id"],
                "name": stop["name"],
                "lat": stop["lat"],
                "lon": stop["lon"],
                "eta_hours": eta_hours,
                "urgency": stop["urgency"],
                "medicines": stop["medicines"],
            })
            prev = stop

        routes.append({
            "origin_facility": origin_facility,
            "stops": stops_out,
            "total_distance_km": round(total_distance, 1),
            "total_eta_hours": round(cumulative_km / ASSUMED_AVG_SPEED_KMH, 1),
        })
    return routes
