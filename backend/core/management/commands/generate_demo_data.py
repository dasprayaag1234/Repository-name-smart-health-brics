"""
Generates clearly-labelled synthetic data across every model so the full
pipeline (forecast -> risk -> procurement -> redistribution -> routing ->
simulation -> Gemini -> BRICS panel) works end-to-end before real datasets
are dropped into datasets/.

Usage: python manage.py generate_demo_data [--flush]
"""
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    Facility, Infrastructure, HMISActivity, Medicine, InventoryHistory,
    Supplier, Order, Shipment, FederatedRound,
)

STATES_DISTRICTS = {
    "Odisha": ["Khordha", "Cuttack", "Puri", "Ganjam", "Sundargarh"],
    "Uttar Pradesh": ["Lucknow", "Kanpur Nagar", "Varanasi", "Agra", "Prayagraj"],
    "Kerala": ["Ernakulam", "Thiruvananthapuram", "Kozhikode", "Kottayam", "Thrissur"],
    "Bihar": ["Patna", "Gaya", "Muzaffarpur", "Bhagalpur", "Darbhanga"],
    "Karnataka": ["Bengaluru Urban", "Mysuru", "Belagavi", "Dakshina Kannada", "Kalaburagi"],
    "Assam": ["Kamrup", "Cachar", "Dibrugarh", "Jorhat", "Nagaon"],
}

# Rough state centroid coords for scattering facility lat/lon
STATE_CENTROIDS = {
    "Odisha": (20.5, 84.9), "Uttar Pradesh": (26.8, 80.9), "Kerala": (10.5, 76.3),
    "Bihar": (25.6, 85.6), "Karnataka": (14.9, 75.6), "Assam": (26.4, 92.9),
}

FACILITY_TYPES = ["PHC", "PHC", "PHC", "CHC", "SHC", "DH"]  # weighted toward PHC

MEDICINES = [
    ("Paracetamol 500mg", "essential", False),
    ("ORS Sachets", "essential", False),
    ("Amoxicillin 250mg", "essential", False),
    ("Insulin (vial)", "chronic", True),
    ("Iron Folic Acid Tablets", "maternal", False),
    ("Oxytocin Injection", "maternal", True),
    ("Anti-Snake Venom", "emergency", True),
    ("Measles Vaccine", "essential", True),
    ("ORS + Zinc Combo", "essential", False),
    ("Metformin 500mg", "chronic", False),
    ("Amlodipine 5mg", "chronic", False),
    ("Ceftriaxone Injection", "emergency", True),
    ("BCG Vaccine", "essential", True),
    ("Diazepam Injection", "emergency", False),
    ("Albendazole Tablets", "general", False),
]

BRICS_COUNTRIES = ["india", "brazil", "russia", "china", "south_africa"]


class Command(BaseCommand):
    help = "Generate labelled synthetic demo data across the whole schema."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete existing data first")
        parser.add_argument("--facilities-per-district", type=int, default=8)
        parser.add_argument("--history-days", type=int, default=30)

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["flush"]:
            self.stdout.write("Flushing existing data...")
            for model in [Shipment, Order, InventoryHistory, HMISActivity, Infrastructure, Facility, Medicine, Supplier, FederatedRound]:
                model.objects.all().delete()

        random.seed(42)
        facilities = self._make_facilities(opts["facilities_per_district"])
        self._make_infrastructure(facilities)
        medicines = self._make_medicines()
        self._make_hmis(facilities, opts["history_days"])
        self._make_inventory(facilities, medicines, opts["history_days"])
        suppliers = self._make_suppliers()
        self._make_orders_and_shipments(facilities, medicines, suppliers)
        self._make_federated_rounds()

        self.stdout.write(self.style.SUCCESS(
            f"Demo data generated: {len(facilities)} facilities, {len(medicines)} medicines, "
            f"{opts['history_days']} days of HMIS/inventory history. All flagged is_demo_data=True."
        ))

    def _make_facilities(self, per_district):
        objs = []
        fid = 1
        for state, districts in STATES_DISTRICTS.items():
            clat, clon = STATE_CENTROIDS[state]
            for district in districts:
                for _ in range(per_district):
                    ftype = random.choice(FACILITY_TYPES)
                    objs.append(Facility(
                        facility_id=f"FAC{fid:05d}",
                        name=f"{ftype} {district} #{fid}",
                        facility_type=ftype,
                        state=state,
                        district=district,
                        latitude=clat + random.uniform(-1.2, 1.2),
                        longitude=clon + random.uniform(-1.2, 1.2),
                        catchment_population=random.randint(5000, 80000),
                        is_demo_data=True,
                    ))
                    fid += 1
        Facility.objects.bulk_create(objs, batch_size=1000)
        return list(Facility.objects.all())

    def _make_infrastructure(self, facilities):
        objs = []
        for f in facilities:
            beds = {"PHC": 10, "SHC": 4, "CHC": 30, "DH": 120}[f.facility_type]
            beds = max(2, int(beds * random.uniform(0.6, 1.3)))
            doc_sanctioned = max(1, beds // 8)
            nurse_sanctioned = max(2, beds // 3)
            spec_sanctioned = 0 if f.facility_type in ("PHC", "SHC") else max(1, beds // 15)
            objs.append(Infrastructure(
                facility=f,
                total_beds=beds,
                occupied_beds=int(beds * random.uniform(0.3, 0.95)),
                doctors_sanctioned=doc_sanctioned,
                doctors_present=max(0, doc_sanctioned - random.choice([0, 0, 0, 1, 1, 2])),
                nurses_sanctioned=nurse_sanctioned,
                nurses_present=max(0, nurse_sanctioned - random.choice([0, 0, 1, 1, 2])),
                specialists_sanctioned=spec_sanctioned,
                specialists_present=max(0, spec_sanctioned - random.choice([0, 0, 1])) if spec_sanctioned else 0,
                has_cold_storage=random.random() > 0.35,
                has_ambulance=random.random() > 0.25,
            ))
        Infrastructure.objects.bulk_create(objs, batch_size=1000)

    def _make_medicines(self):
        objs = []
        for i, (name, cat, temp_sensitive) in enumerate(MEDICINES, start=1):
            objs.append(Medicine(
                medicine_id=f"MED{i:04d}",
                name=name,
                category=cat,
                unit="units",
                is_temperature_sensitive=temp_sensitive,
                avg_lead_time_days=random.choice([5, 7, 10, 14]),
            ))
        Medicine.objects.bulk_create(objs, batch_size=200)
        return list(Medicine.objects.all())

    def _make_hmis(self, facilities, days):
        objs = []
        start = date.today() - timedelta(days=days)
        for f in facilities:
            base = max(5, f.catchment_population // 1000)
            for d in range(days):
                day = start + timedelta(days=d)
                weekday_factor = 0.6 if day.weekday() == 6 else 1.0  # lower on Sundays
                footfall = max(0, int(random.gauss(base, base * 0.25) * weekday_factor))
                objs.append(HMISActivity(
                    facility=f, date=day,
                    opd_footfall=footfall,
                    ipd_admissions=int(footfall * random.uniform(0.02, 0.08)),
                    deliveries=int(footfall * random.uniform(0.0, 0.01)) if f.facility_type in ("CHC", "DH") else 0,
                    emergency_cases=int(footfall * random.uniform(0.01, 0.05)),
                ))
        HMISActivity.objects.bulk_create(objs, batch_size=5000)

    def _make_inventory(self, facilities, medicines, days):
        """
        Simulates a running stock ledger per facility/medicine with a
        deliberate mix: ~65% healthy, ~20% low, ~15% trending toward
        critical, so risk scoring and redistribution have something to find.
        """
        start = date.today() - timedelta(days=days)
        objs = []
        for f in facilities:
            # not every facility stocks every medicine — pick a realistic subset
            n_meds = random.randint(6, len(medicines))
            stocked = random.sample(medicines, n_meds)
            for m in stocked:
                profile = random.choices(["healthy", "low", "critical"], weights=[65, 20, 15])[0]
                base_daily_use = max(1, int(random.gauss(8, 4)))
                stock = {
                    "healthy": random.randint(base_daily_use * 25, base_daily_use * 45),
                    "low": random.randint(base_daily_use * 8, base_daily_use * 15),
                    "critical": random.randint(0, base_daily_use * 4),
                }[profile]
                reorder = base_daily_use * 10
                safety = base_daily_use * 5
                for d in range(days):
                    day = start + timedelta(days=d)
                    consumed = max(0, int(random.gauss(base_daily_use, base_daily_use * 0.3)))
                    received = 0
                    # periodic resupply for healthy/low profiles only, so critical stays critical
                    if profile != "critical" and d % random.choice([10, 14, 18]) == 0 and d > 0:
                        received = base_daily_use * random.randint(15, 30)
                    opening = stock
                    stock = max(0, stock - consumed + received)
                    objs.append(InventoryHistory(
                        facility=f, medicine=m, date=day,
                        opening_stock=opening, consumed=consumed, received=received,
                        closing_stock=stock, reorder_level=reorder, safety_stock=safety,
                    ))
        InventoryHistory.objects.bulk_create(objs, batch_size=5000)

    def _make_suppliers(self):
        names = ["National Medical Stores", "State Pharma Corp", "Regional Health Logistics",
                 "Central Drug Distributors", "MedSupply Federation"]
        objs = []
        for i, name in enumerate(names, start=1):
            objs.append(Supplier(
                supplier_id=f"SUP{i:03d}", name=name,
                state=random.choice(list(STATES_DISTRICTS.keys())),
                reliability_score=round(random.uniform(0.75, 0.98), 2),
                avg_lead_time_days=random.choice([4, 6, 8, 10]),
            ))
        Supplier.objects.bulk_create(objs)
        return list(Supplier.objects.all())

    def _make_orders_and_shipments(self, facilities, medicines, suppliers):
        orders = []
        sample_facilities = random.sample(facilities, min(60, len(facilities)))
        for i, f in enumerate(sample_facilities, start=1):
            m = random.choice(medicines)
            orders.append(Order(
                order_id=f"ORD{i:05d}", facility=f, medicine=m,
                supplier=random.choice(suppliers),
                quantity=random.randint(50, 500),
                status=random.choice(["pending", "approved", "shipped", "delivered"]),
                expected_delivery=date.today() + timedelta(days=random.randint(1, 14)),
                reasoning="Auto-generated demo order (no real procurement data yet).",
            ))
        Order.objects.bulk_create(orders)

    def _make_federated_rounds(self):
        """Synthetic BRICS federated-learning rounds — see FederatedRound.is_synthetic_demo."""
        objs = []
        base_error = {"india": 18.0, "brazil": 21.0, "russia": 19.5, "china": 16.0, "south_africa": 23.0}
        for round_num in range(1, 4):
            updates = []
            for country in BRICS_COUNTRIES:
                improvement = round_num * random.uniform(0.8, 1.6)
                local_error = max(6.0, base_error[country] - improvement + random.uniform(-0.5, 0.5))
                updates.append({
                    "country": country,
                    "local_forecast_error_pct": round(local_error, 2),
                    "sample_size": random.randint(2000, 9000),
                    "delta_vs_previous_round": round(-improvement, 2),
                })
            global_error = round(sum(u["local_forecast_error_pct"] * u["sample_size"] for u in updates) /
                                  sum(u["sample_size"] for u in updates), 2)
            objs.append(FederatedRound(
                round_number=round_num,
                country_updates=updates,
                global_metric={"aggregated_forecast_error_pct": global_error, "method": "sample-weighted average (FedAvg-style, synthetic demo)"},
                is_synthetic_demo=True,
            ))
        FederatedRound.objects.bulk_create(objs)
