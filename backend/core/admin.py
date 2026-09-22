from django.contrib import admin

from core.models import (
    Facility, Infrastructure, HMISActivity, Medicine, InventoryHistory,
    Supplier, Order, Shipment, DemandForecast, StockRisk,
    RedistributionRecommendation, OptimizedRoute, EmergencySimulation, FederatedRound,
)

admin.site.register(Facility)
admin.site.register(Infrastructure)
admin.site.register(HMISActivity)
admin.site.register(Medicine)
admin.site.register(InventoryHistory)
admin.site.register(Supplier)
admin.site.register(Order)
admin.site.register(Shipment)
admin.site.register(DemandForecast)
admin.site.register(StockRisk)
admin.site.register(RedistributionRecommendation)
admin.site.register(OptimizedRoute)
admin.site.register(EmergencySimulation)
admin.site.register(FederatedRound)
