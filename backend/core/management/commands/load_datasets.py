"""
Imports real datasets from datasets/ into the database, using data_loader.py
for validation. Anything missing/invalid is skipped and reported — this
command never crashes because a file is absent; that's what the demo data
generator is for.

Usage: python manage.py load_datasets
"""
import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction

from core import data_loader
from core.models import (
    Facility, Infrastructure, HMISActivity, Medicine, InventoryHistory,
    Supplier, Order, Shipment,
)


class Command(BaseCommand):
    help = "Import real CSV datasets from datasets/ into the database (skips anything missing/invalid)."

    @transaction.atomic
    def handle(self, *args, **opts):
        results = data_loader.load_all()
        self.stdout.write(data_loader.summarize(results))
        self.stdout.write("")

        if results["facilities"].ok:
            self._load_facilities(results["facilities"].df)
        if results["medicines"].ok:
            self._load_medicines(results["medicines"].df)
        if results["infrastructure"].ok:
            self._load_infrastructure(results["infrastructure"].df)
        if results["hmis"].ok:
            self._load_hmis(results["hmis"].df)
        if results["inventory"].ok:
            self._load_inventory(results["inventory"].df)
        if results["suppliers"].ok:
            self._load_suppliers(results["suppliers"].df)
        if results["orders"].ok:
            self._load_orders(results["orders"].df)
        if results["shipments"].ok:
            self._load_shipments(results["shipments"].df)

        real_count = sum(1 for k, r in results.items() if k != "brics" and r.ok)
        self.stdout.write(self.style.SUCCESS(
            f"\nImported {real_count} real dataset(s). Run `python manage.py run_pipeline` next "
            f"to (re)compute forecasts/risk/redistribution/routes from this data. "
            f"Any dataset not found above is still running on demo data."
        ))

    def _load_facilities(self, df):
        objs = []
        for _, row in df.iterrows():
            objs.append(Facility(
                facility_id=str(row["facility_id"]), name=row["name"], facility_type=row["facility_type"],
                state=row["state"], district=row["district"],
                latitude=float(row["latitude"]), longitude=float(row["longitude"]),
                catchment_population=int(row.get("catchment_population", 0) or 0),
                is_demo_data=False,
            ))
        Facility.objects.filter(is_demo_data=False).delete()
        Facility.objects.bulk_create(objs, batch_size=1000, ignore_conflicts=True)
        self.stdout.write(f"  facilities: imported {len(objs)} rows")

    def _load_medicines(self, df):
        objs = []
        for _, row in df.iterrows():
            objs.append(Medicine(
                medicine_id=str(row["medicine_id"]), name=row["name"],
                category=row.get("category", "general") or "general",
                unit=row.get("unit", "units") or "units",
                is_temperature_sensitive=bool(row.get("is_temperature_sensitive", False)),
                avg_lead_time_days=int(row.get("avg_lead_time_days", 7) or 7),
            ))
        Medicine.objects.bulk_create(objs, batch_size=500, ignore_conflicts=True)
        self.stdout.write(f"  medicines: imported {len(objs)} rows")

    def _load_infrastructure(self, df):
        fac_map = {f.facility_id: f for f in Facility.objects.all()}
        objs = []
        for _, row in df.iterrows():
            facility = fac_map.get(str(row["facility_id"]))
            if not facility:
                continue
            objs.append(Infrastructure(
                facility=facility,
                total_beds=int(row["total_beds"]), occupied_beds=int(row["occupied_beds"]),
                doctors_sanctioned=int(row["doctors_sanctioned"]), doctors_present=int(row["doctors_present"]),
                nurses_sanctioned=int(row["nurses_sanctioned"]), nurses_present=int(row["nurses_present"]),
                specialists_sanctioned=int(row.get("specialists_sanctioned", 0) or 0),
                specialists_present=int(row.get("specialists_present", 0) or 0),
                has_cold_storage=bool(row.get("has_cold_storage", False)),
                has_ambulance=bool(row.get("has_ambulance", False)),
            ))
        Infrastructure.objects.filter(facility__in=[o.facility for o in objs]).delete()
        Infrastructure.objects.bulk_create(objs, batch_size=1000)
        self.stdout.write(f"  infrastructure: imported {len(objs)} rows")

    def _load_hmis(self, df):
        fac_map = {f.facility_id: f for f in Facility.objects.all()}
        objs = []
        for _, row in df.iterrows():
            facility = fac_map.get(str(row["facility_id"]))
            if not facility:
                continue
            objs.append(HMISActivity(
                facility=facility, date=pd.to_datetime(row["date"]).date(),
                opd_footfall=int(row["opd_footfall"]),
                ipd_admissions=int(row.get("ipd_admissions", 0) or 0),
                deliveries=int(row.get("deliveries", 0) or 0),
                emergency_cases=int(row.get("emergency_cases", 0) or 0),
            ))
        HMISActivity.objects.bulk_create(objs, batch_size=5000, ignore_conflicts=True)
        self.stdout.write(f"  hmis: imported {len(objs)} rows")

    def _load_inventory(self, df):
        fac_map = {f.facility_id: f for f in Facility.objects.all()}
        med_map = {m.medicine_id: m for m in Medicine.objects.all()}
        objs = []
        for _, row in df.iterrows():
            facility = fac_map.get(str(row["facility_id"]))
            medicine = med_map.get(str(row["medicine_id"]))
            if not facility or not medicine:
                continue
            objs.append(InventoryHistory(
                facility=facility, medicine=medicine, date=pd.to_datetime(row["date"]).date(),
                opening_stock=int(row.get("opening_stock", 0) or 0),
                consumed=int(row.get("consumed", 0) or 0),
                received=int(row.get("received", 0) or 0),
                closing_stock=int(row["closing_stock"]),
                reorder_level=int(row.get("reorder_level", 0) or 0),
                safety_stock=int(row.get("safety_stock", 0) or 0),
            ))
        InventoryHistory.objects.bulk_create(objs, batch_size=5000, ignore_conflicts=True)
        self.stdout.write(f"  inventory: imported {len(objs)} rows")

    def _load_suppliers(self, df):
        objs = []
        for _, row in df.iterrows():
            objs.append(Supplier(
                supplier_id=str(row["supplier_id"]), name=row["name"], state=row["state"],
                reliability_score=float(row.get("reliability_score", 0.9) or 0.9),
                avg_lead_time_days=int(row.get("avg_lead_time_days", 7) or 7),
            ))
        Supplier.objects.bulk_create(objs, batch_size=500, ignore_conflicts=True)
        self.stdout.write(f"  suppliers: imported {len(objs)} rows")

    def _load_orders(self, df):
        fac_map = {f.facility_id: f for f in Facility.objects.all()}
        med_map = {m.medicine_id: m for m in Medicine.objects.all()}
        sup_map = {s.supplier_id: s for s in Supplier.objects.all()}
        objs = []
        for _, row in df.iterrows():
            facility = fac_map.get(str(row["facility_id"]))
            medicine = med_map.get(str(row["medicine_id"]))
            if not facility or not medicine:
                continue
            objs.append(Order(
                order_id=str(row["order_id"]), facility=facility, medicine=medicine,
                supplier=sup_map.get(str(row.get("supplier_id", ""))),
                quantity=int(row["quantity"]), status=row.get("status", "pending"),
                expected_delivery=pd.to_datetime(row["expected_delivery"]).date() if row.get("expected_delivery") else None,
            ))
        Order.objects.bulk_create(objs, batch_size=1000, ignore_conflicts=True)
        self.stdout.write(f"  orders: imported {len(objs)} rows")

    def _load_shipments(self, df):
        fac_map = {f.facility_id: f for f in Facility.objects.all()}
        med_map = {m.medicine_id: m for m in Medicine.objects.all()}
        order_map = {o.order_id: o for o in Order.objects.all()}
        objs = []
        for _, row in df.iterrows():
            dest = fac_map.get(str(row["destination_facility_id"]))
            medicine = med_map.get(str(row["medicine_id"]))
            if not dest or not medicine:
                continue
            objs.append(Shipment(
                shipment_id=str(row["shipment_id"]),
                order=order_map.get(str(row.get("order_id", ""))),
                source_facility=fac_map.get(str(row.get("source_facility_id", ""))),
                destination_facility=dest, medicine=medicine, quantity=int(row["quantity"]),
                distance_km=float(row["distance_km"]) if row.get("distance_km") else None,
                eta_hours=float(row["eta_hours"]) if row.get("eta_hours") else None,
                status=row.get("status", "planned"), urgency=row.get("urgency", "medium"),
            ))
        Shipment.objects.bulk_create(objs, batch_size=1000, ignore_conflicts=True)
        self.stdout.write(f"  shipments: imported {len(objs)} rows")
