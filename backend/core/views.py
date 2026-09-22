from datetime import date

from django.db.models import Count, Avg, Sum, Q
from rest_framework import viewsets, filters
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    Facility, Infrastructure, HMISActivity, Medicine, InventoryHistory,
    Supplier, Order, Shipment, DemandForecast, StockRisk,
    RedistributionRecommendation, OptimizedRoute, EmergencySimulation, FederatedRound,
)
from core.serializers import (
    FacilitySerializer, FacilityListSerializer, MedicineSerializer, InventoryHistorySerializer,
    SupplierSerializer, OrderSerializer, ShipmentSerializer, StockRiskSerializer,
    RedistributionRecommendationSerializer, OptimizedRouteSerializer, FederatedRoundSerializer,
    HMISActivitySerializer,
)
from core.ml.forecasting import forecast_demand
from core.ml.emergency_simulation import run_emergency_simulation
from core.ai.assistant import answer_question
from core.pipeline import run_full_pipeline
from core import data_loader


# ---------------------------------------------------------------------------
# Read-only resource viewsets
# ---------------------------------------------------------------------------

class FacilityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Facility.objects.select_related("infrastructure").all()
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "facility_id", "state", "district"]

    def get_serializer_class(self):
        return FacilitySerializer if self.action == "retrieve" else FacilityListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        state = self.request.query_params.get("state")
        facility_type = self.request.query_params.get("facility_type")
        if state:
            qs = qs.filter(state=state)
        if facility_type:
            qs = qs.filter(facility_type=facility_type)
        return qs


class MedicineViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer


class SupplierViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Order.objects.select_related("facility", "medicine", "supplier").order_by("-created_at")
    serializer_class = OrderSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        facility_id = self.request.query_params.get("facility")
        if facility_id:
            qs = qs.filter(facility_id=facility_id)
        return qs


class ShipmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Shipment.objects.select_related("destination_facility", "source_facility", "medicine").order_by("-created_at")
    serializer_class = ShipmentSerializer


class StockRiskViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockRisk.objects.select_related("facility", "medicine").order_by("-risk_score")
    serializer_class = StockRiskSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        state = self.request.query_params.get("state")
        risk_level = self.request.query_params.get("risk_level")
        facility_id = self.request.query_params.get("facility")
        medicine_id = self.request.query_params.get("medicine")
        if state:
            qs = qs.filter(facility__state=state)
        if risk_level:
            qs = qs.filter(risk_level=risk_level)
        if facility_id:
            qs = qs.filter(facility_id=facility_id)
        if medicine_id:
            qs = qs.filter(medicine_id=medicine_id)
        return qs


class RedistributionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RedistributionRecommendation.objects.select_related(
        "source_facility", "destination_facility", "medicine"
    ).order_by("-computed_at")
    serializer_class = RedistributionRecommendationSerializer


class OptimizedRouteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OptimizedRoute.objects.select_related("origin_facility").order_by("-computed_at")
    serializer_class = OptimizedRouteSerializer


class InventoryHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InventoryHistory.objects.select_related("facility", "medicine").order_by("-date")

    serializer_class = InventoryHistorySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        facility_id = self.request.query_params.get("facility")
        medicine_id = self.request.query_params.get("medicine")
        if facility_id:
            qs = qs.filter(facility_id=facility_id)
        if medicine_id:
            qs = qs.filter(medicine_id=medicine_id)
        return qs[:90]  # cap payload; this is a time series view, not a full dump


class HMISActivityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HMISActivity.objects.select_related("facility").order_by("-date")
    serializer_class = HMISActivitySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        facility_id = self.request.query_params.get("facility")
        if facility_id:
            qs = qs.filter(facility_id=facility_id)
        return qs[:90]


class FederatedRoundViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FederatedRound.objects.all().order_by("-round_number")
    serializer_class = FederatedRoundSerializer


# ---------------------------------------------------------------------------
# Action endpoints
# ---------------------------------------------------------------------------

@api_view(["GET"])
def forecast_view(request):
    """GET /api/forecast/?facility=<id>&medicine=<id>&horizon=14"""
    try:
        facility_id = int(request.query_params["facility"])
        medicine_id = int(request.query_params["medicine"])
    except (KeyError, ValueError):
        return Response({"error": "facility and medicine query params (ids) are required"}, status=400)
    horizon = int(request.query_params.get("horizon", 14))
    forecasts, model_used, is_fallback = forecast_demand(facility_id, medicine_id, horizon, use_ml=True)
    return Response({
        "facility_id": facility_id, "medicine_id": medicine_id, "horizon_days": horizon,
        "model_used": model_used, "is_demo_fallback": is_fallback, "forecast": forecasts,
    })


@api_view(["POST"])
def run_pipeline_view(request):
    """POST /api/pipeline/run/  body: {"horizon_days": 14}  -- recomputes risk/redistribution/routes"""
    horizon_days = int(request.data.get("horizon_days", 14))
    summary = run_full_pipeline(horizon_days=horizon_days)
    return Response(summary)


@api_view(["POST"])
def emergency_simulation_view(request):
    """POST /api/emergency-simulation/  body: {"surge_pct": 30, "scope_state": ""}"""
    surge_pct = float(request.data.get("surge_pct", 30))
    scope_state = request.data.get("scope_state", "") or ""
    result = run_emergency_simulation(surge_pct, scope_state)
    EmergencySimulation.objects.create(
        label=f"+{surge_pct}% footfall surge" + (f" ({scope_state})" if scope_state else ""),
        surge_pct=surge_pct, scope_state=scope_state,
        before_snapshot=result["before"], after_snapshot=result["after"],
    )
    return Response(result)


@api_view(["POST"])
def ai_assistant_view(request):
    """POST /api/ai-assistant/  body: {"question": "..."}"""
    question = request.data.get("question", "").strip()
    if not question:
        return Response({"error": "question is required"}, status=400)
    return Response(answer_question(question))


@api_view(["GET"])
def dataset_status_view(request):
    """GET /api/dataset-status/ -- what real data has been detected vs demo fallback."""
    results = data_loader.load_all()
    summary = {}
    for name, res in results.items():
        if name == "brics":
            summary[name] = {country: r.ok for country, r in res["per_country"].items()}
        else:
            summary[name] = {"ok": res.ok, "reason": res.reason if not res.ok else None}
    return Response(summary)


class NationalDashboardView(APIView):
    """
    GET /api/dashboard/national/
    KPIs + top risks + redistribution + resource utilization for the
    National Admin dashboard's landing view.
    """
    def get(self, request):
        risk_counts = dict(StockRisk.objects.values_list("risk_level").annotate(c=Count("id")))
        top_risks = StockRiskSerializer(
            StockRisk.objects.select_related("facility", "medicine").order_by("-risk_score")[:10], many=True
        ).data
        top_redistribution = RedistributionRecommendationSerializer(
            RedistributionRecommendation.objects.select_related("source_facility", "destination_facility", "medicine")
            .order_by("-computed_at")[:10], many=True
        ).data
        infra = Infrastructure.objects.aggregate(
            total_beds=Sum("total_beds"), occupied_beds=Sum("occupied_beds"),
            doctors_sanctioned=Sum("doctors_sanctioned"), doctors_present=Sum("doctors_present"),
        )
        bed_util = round(100 * infra["occupied_beds"] / infra["total_beds"], 1) if infra["total_beds"] else 0
        by_state = list(
            Facility.objects.values("state")
            .annotate(
                facility_count=Count("id"),
                critical_risk_count=Count("stock_risks", filter=Q(stock_risks__risk_level="critical")),
            ).order_by("state")
        )
        return Response({
            "risk_counts": risk_counts,
            "total_facilities": Facility.objects.count(),
            "bed_utilization_pct": bed_util,
            "doctor_staffing_pct": round(100 * infra["doctors_present"] / infra["doctors_sanctioned"], 1) if infra["doctors_sanctioned"] else 0,
            "top_risks": top_risks,
            "top_redistribution_recommendations": top_redistribution,
            "by_state": by_state,
            "last_computed": StockRisk.objects.order_by("-computed_at").values_list("computed_at", flat=True).first(),
        })


class BricsDashboardView(APIView):
    """
    GET /api/dashboard/brics/
    Federated learning demo panel. ALWAYS clearly labelled synthetic —
    see FederatedRound.is_synthetic_demo and the SKILL note in models.py.
    """
    def get(self, request):
        rounds = FederatedRoundSerializer(FederatedRound.objects.order_by("round_number"), many=True).data
        return Response({
            "rounds": rounds,
            "is_synthetic_demo": True,
            "disclaimer": (
                "This panel demonstrates the federated-learning concept (local country model -> "
                "local update -> federated aggregation -> global model) using synthetic country-level "
                "metrics. No real BRICS partner health data is used or required."
            ),
        })


class RoleDashboardView(APIView):
    """
    GET /api/dashboard/<role>/
    Lightweight role-scoped summaries for Supplier / Dealer / Facility views,
    distinct from the full National Admin dashboard above.
    """
    def get(self, request, role):
        if role == "supplier":
            data = list(
                Supplier.objects.annotate(open_orders=Count("orders", filter=Q(orders__status__in=["pending", "approved"])))
                .values("id", "name", "state", "reliability_score", "avg_lead_time_days", "open_orders")
            )
            return Response({"suppliers": data})

        if role == "dealer":
            data = ShipmentSerializer(
                Shipment.objects.select_related("destination_facility", "source_facility", "medicine")
                .order_by("-created_at")[:30], many=True
            ).data
            return Response({"shipments": data})

        if role == "facility":
            facility_id = request.query_params.get("facility")
            if not facility_id:
                return Response({"error": "facility query param (id) is required for the facility dashboard"}, status=400)
            facility = Facility.objects.select_related("infrastructure").filter(id=facility_id).first()
            if not facility:
                return Response({"error": "facility not found"}, status=404)
            risks = StockRiskSerializer(
                StockRisk.objects.filter(facility=facility).order_by("-risk_score")[:20], many=True
            ).data
            return Response({
                "facility": FacilitySerializer(facility).data,
                "stock_risks": risks,
            })

        return Response({"error": f"unknown role '{role}'"}, status=404)
