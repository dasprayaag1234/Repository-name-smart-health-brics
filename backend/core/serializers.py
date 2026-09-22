from rest_framework import serializers

from core.models import (
    Facility, Infrastructure, HMISActivity, Medicine, InventoryHistory,
    Supplier, Order, Shipment, DemandForecast, StockRisk,
    RedistributionRecommendation, OptimizedRoute, EmergencySimulation, FederatedRound,
)


class InfrastructureSerializer(serializers.ModelSerializer):
    bed_utilization_pct = serializers.ReadOnlyField()
    staffing_gap_pct = serializers.ReadOnlyField()

    class Meta:
        model = Infrastructure
        fields = "__all__"


class FacilitySerializer(serializers.ModelSerializer):
    infrastructure = InfrastructureSerializer(read_only=True)

    class Meta:
        model = Facility
        fields = "__all__"


class FacilityListSerializer(serializers.ModelSerializer):
    """Lighter serializer for map/list views with hundreds of facilities."""
    bed_utilization_pct = serializers.FloatField(source="infrastructure.bed_utilization_pct", default=None, read_only=True)

    class Meta:
        model = Facility
        fields = ["id", "facility_id", "name", "facility_type", "state", "district",
                  "latitude", "longitude", "catchment_population", "bed_utilization_pct"]


class HMISActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = HMISActivity
        fields = "__all__"


class MedicineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medicine
        fields = "__all__"


class InventoryHistorySerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)

    class Meta:
        model = InventoryHistory
        fields = "__all__"


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = "__all__"


class OrderSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default=None)

    class Meta:
        model = Order
        fields = "__all__"


class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = "__all__"


class DemandForecastSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemandForecast
        fields = "__all__"


class StockRiskSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    facility_state = serializers.CharField(source="facility.state", read_only=True)
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)

    class Meta:
        model = StockRisk
        fields = "__all__"


class RedistributionRecommendationSerializer(serializers.ModelSerializer):
    source_facility_name = serializers.CharField(source="source_facility.name", read_only=True)
    destination_facility_name = serializers.CharField(source="destination_facility.name", read_only=True)
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)

    class Meta:
        model = RedistributionRecommendation
        fields = "__all__"


class OptimizedRouteSerializer(serializers.ModelSerializer):
    origin_facility_name = serializers.CharField(source="origin_facility.name", read_only=True)

    class Meta:
        model = OptimizedRoute
        fields = "__all__"


class EmergencySimulationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencySimulation
        fields = "__all__"


class FederatedRoundSerializer(serializers.ModelSerializer):
    class Meta:
        model = FederatedRound
        fields = "__all__"
