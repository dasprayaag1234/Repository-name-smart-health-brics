"""
Core data models for the Smart Health & Supply Chain Resilience platform.

These map directly onto the datasets/ CSV structure (see datasets/dataset_config.json).
Every model can be populated either from real CSVs the user drops into datasets/, or
from the demo/synthetic data generator (core/management/commands/generate_demo_data.py)
so the whole pipeline runs before real data exists.
"""
from django.db import models


class Facility(models.Model):
    FACILITY_TYPES = [
        ("PHC", "Primary Health Centre"),
        ("CHC", "Community Health Centre"),
        ("SHC", "Sub Health Centre"),
        ("DH", "District Hospital"),
    ]

    facility_id = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)
    facility_type = models.CharField(max_length=8, choices=FACILITY_TYPES)
    state = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    catchment_population = models.IntegerField(default=0)
    is_demo_data = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["state", "district"])]
        ordering = ["facility_id"]

    def __str__(self):
        return f"{self.name} ({self.facility_id})"


class Infrastructure(models.Model):
    facility = models.OneToOneField(Facility, on_delete=models.CASCADE, related_name="infrastructure")
    total_beds = models.IntegerField(default=0)
    occupied_beds = models.IntegerField(default=0)
    doctors_sanctioned = models.IntegerField(default=0)
    doctors_present = models.IntegerField(default=0)
    nurses_sanctioned = models.IntegerField(default=0)
    nurses_present = models.IntegerField(default=0)
    specialists_sanctioned = models.IntegerField(default=0)
    specialists_present = models.IntegerField(default=0)
    has_cold_storage = models.BooleanField(default=False)
    has_ambulance = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def bed_utilization_pct(self):
        return round(100 * self.occupied_beds / self.total_beds, 1) if self.total_beds else 0.0

    @property
    def staffing_gap_pct(self):
        sanctioned = self.doctors_sanctioned + self.nurses_sanctioned + self.specialists_sanctioned
        present = self.doctors_present + self.nurses_present + self.specialists_present
        if not sanctioned:
            return 0.0
        return round(100 * (sanctioned - present) / sanctioned, 1)


class HMISActivity(models.Model):
    """Daily patient footfall / activity records, used as a demand driver."""
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="hmis_records")
    date = models.DateField()
    opd_footfall = models.IntegerField(default=0)
    ipd_admissions = models.IntegerField(default=0)
    deliveries = models.IntegerField(default=0)
    emergency_cases = models.IntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["facility", "date"])]
        ordering = ["date"]


class Medicine(models.Model):
    CATEGORY_CHOICES = [
        ("essential", "WHO Essential Medicine"),
        ("emergency", "Emergency/Critical"),
        ("chronic", "Chronic Disease"),
        ("maternal", "Maternal & Child Health"),
        ("general", "General"),
    ]
    medicine_id = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="general")
    unit = models.CharField(max_length=20, default="units")
    is_temperature_sensitive = models.BooleanField(default=False)
    avg_lead_time_days = models.IntegerField(default=7)

    def __str__(self):
        return self.name


class InventoryHistory(models.Model):
    """Daily stock snapshot per facility per medicine — the core time series for forecasting."""
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="inventory_records")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="inventory_records")
    date = models.DateField()
    opening_stock = models.IntegerField(default=0)
    consumed = models.IntegerField(default=0)
    received = models.IntegerField(default=0)
    closing_stock = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=0)
    safety_stock = models.IntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["facility", "medicine", "date"])]
        ordering = ["date"]


class Supplier(models.Model):
    supplier_id = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)
    state = models.CharField(max_length=100)
    reliability_score = models.FloatField(default=0.9)  # 0-1, on-time delivery rate
    avg_lead_time_days = models.IntegerField(default=7)

    def __str__(self):
        return self.name


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]
    order_id = models.CharField(max_length=32, unique=True)
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="orders")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="orders")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, related_name="orders")
    quantity = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    expected_delivery = models.DateField(null=True, blank=True)
    reasoning = models.TextField(blank=True, default="")  # why this qty was recommended


class Shipment(models.Model):
    shipment_id = models.CharField(max_length=32, unique=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="shipments", null=True, blank=True)
    source_facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="outgoing_shipments", null=True, blank=True)
    destination_facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="incoming_shipments")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="shipments")
    quantity = models.IntegerField()
    distance_km = models.FloatField(null=True, blank=True)
    eta_hours = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, default="planned")
    urgency = models.CharField(max_length=10, default="medium")  # low/medium/high/critical
    created_at = models.DateTimeField(auto_now_add=True)


class DemandForecast(models.Model):
    """ML-generated forecast, cached per facility/medicine/horizon."""
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="forecasts")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="forecasts")
    generated_at = models.DateTimeField(auto_now_add=True)
    horizon_days = models.IntegerField(default=14)  # 7 / 14 / 30
    daily_forecast = models.JSONField(default=list)  # [{date, predicted_demand, lower, upper}, ...]
    model_used = models.CharField(max_length=50, default="xgboost")
    is_demo_fallback = models.BooleanField(default=False)

    class Meta:
        ordering = ["-generated_at"]


class StockRisk(models.Model):
    RISK_LEVELS = [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")]
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="stock_risks")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="stock_risks")
    computed_at = models.DateTimeField(auto_now_add=True)
    current_stock = models.IntegerField()
    forecasted_demand_period = models.FloatField()
    incoming_supply = models.IntegerField(default=0)
    projected_stock = models.FloatField()
    days_of_stock = models.FloatField()
    expected_stockout_date = models.DateField(null=True, blank=True)
    shortage_quantity = models.FloatField(default=0)
    risk_score = models.FloatField()  # 0-100
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS)
    explanation = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-risk_score"]


class RedistributionRecommendation(models.Model):
    computed_at = models.DateTimeField(auto_now_add=True)
    source_facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="redistribution_sources")
    destination_facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="redistribution_destinations")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="redistribution_recs")
    recommended_quantity = models.IntegerField()
    urgency = models.CharField(max_length=10, default="medium")
    reason = models.TextField(blank=True, default="")
    distance_km = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, default="recommended")  # recommended/approved/rejected/completed

    class Meta:
        ordering = ["-computed_at"]


class OptimizedRoute(models.Model):
    """A sequenced set of stops for one vehicle covering one or more redistribution transfers."""
    computed_at = models.DateTimeField(auto_now_add=True)
    origin_facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="routes_originating")
    stops = models.JSONField(default=list)  # [{facility_id, name, lat, lon, eta_hours, medicines:[...]}]
    total_distance_km = models.FloatField(default=0)
    total_eta_hours = models.FloatField(default=0)
    is_demo_abstraction = models.BooleanField(
        default=True,
        help_text="True unless a real routing/traffic API is wired in — always surfaced in the UI."
    )


class EmergencySimulation(models.Model):
    """Stores a footfall-surge what-if scenario and its before/after recalculation."""
    created_at = models.DateTimeField(auto_now_add=True)
    label = models.CharField(max_length=255, default="Surge scenario")
    surge_pct = models.FloatField(default=30.0)
    scope_state = models.CharField(max_length=100, blank=True, default="")  # "" = national
    before_snapshot = models.JSONField(default=dict)
    after_snapshot = models.JSONField(default=dict)


class FederatedRound(models.Model):
    """One round of the BRICS federated-learning demo: local updates -> aggregated global model."""
    created_at = models.DateTimeField(auto_now_add=True)
    round_number = models.IntegerField()
    country_updates = models.JSONField(default=list)  # [{country, local_metric, sample_size, delta}, ...]
    global_metric = models.JSONField(default=dict)  # aggregated result
    is_synthetic_demo = models.BooleanField(default=True)

    class Meta:
        ordering = ["-round_number"]
