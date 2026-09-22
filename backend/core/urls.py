from django.urls import path, include
from rest_framework.routers import DefaultRouter

from core import views

router = DefaultRouter()
router.register("facilities", views.FacilityViewSet, basename="facility")
router.register("medicines", views.MedicineViewSet, basename="medicine")
router.register("suppliers", views.SupplierViewSet, basename="supplier")
router.register("orders", views.OrderViewSet, basename="order")
router.register("shipments", views.ShipmentViewSet, basename="shipment")
router.register("stock-risks", views.StockRiskViewSet, basename="stockrisk")
router.register("redistribution", views.RedistributionViewSet, basename="redistribution")
router.register("routes", views.OptimizedRouteViewSet, basename="route")
router.register("inventory-history", views.InventoryHistoryViewSet, basename="inventoryhistory")
router.register("hmis", views.HMISActivityViewSet, basename="hmis")
router.register("federated-rounds", views.FederatedRoundViewSet, basename="federatedround")

urlpatterns = [
    path("", include(router.urls)),
    path("forecast/", views.forecast_view, name="forecast"),
    path("pipeline/run/", views.run_pipeline_view, name="run-pipeline"),
    path("emergency-simulation/", views.emergency_simulation_view, name="emergency-simulation"),
    path("ai-assistant/", views.ai_assistant_view, name="ai-assistant"),
    path("dataset-status/", views.dataset_status_view, name="dataset-status"),
    path("dashboard/national/", views.NationalDashboardView.as_view(), name="dashboard-national"),
    path("dashboard/brics/", views.BricsDashboardView.as_view(), name="dashboard-brics"),
    path("dashboard/<str:role>/", views.RoleDashboardView.as_view(), name="dashboard-role"),
]
