from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    Facility,
    Medicine,
    InventoryHistory,
    HMISActivity,
    StockRisk,
    RedistributionRecommendation,
    OptimizedRoute,
)


class Command(BaseCommand):
    help = "Replace demo core data with real dataset-backed facility, medicine, inventory and HMIS data."

    BATCH_SIZE = 5000

    def handle(self, *args, **options):
        base = Path(settings.DATASETS_DIR)

        facility_path = base / "facilities" / "facility_master_full.csv"
        medicine_path = base / "medicines" / "medicine_master.csv"
        inventory_path = base / "inventory" / "inventory_history.csv"
        hmis_path = base / "hmis" / "facility_daily_activity.csv"

        for path in [facility_path, medicine_path, inventory_path, hmis_path]:
            if not path.exists():
                raise FileNotFoundError(f"Dataset not found: {path}")

        self.stdout.write("Reading operational facility IDs...")

        inventory_ids = set(
            pd.read_csv(
                inventory_path,
                usecols=["facility_id"],
                dtype={"facility_id": str},
            )["facility_id"].dropna().astype(str).unique()
        )

        hmis_ids = set(
            pd.read_csv(
                hmis_path,
                usecols=["facility_id"],
                dtype={"facility_id": str},
            )["facility_id"].dropna().astype(str).unique()
        )

        operational_facility_ids = inventory_ids | hmis_ids

        self.stdout.write(
            f"Operational facilities referenced by inventory/HMIS: "
            f"{len(operational_facility_ids)}"
        )

        self.stdout.write("Loading facility master subset...")

        facilities_df = pd.read_csv(
            facility_path,
            dtype={"facility_id": str},
        )

        facilities_df["facility_id"] = facilities_df["facility_id"].astype(str)

        facilities_df = facilities_df[
            facilities_df["facility_id"].isin(operational_facility_ids)
        ].copy()

        missing_facilities = (
            operational_facility_ids
            - set(facilities_df["facility_id"].astype(str))
        )

        if missing_facilities:
            raise ValueError(
                f"{len(missing_facilities)} operational facility IDs "
                f"were not found in facility_master_full.csv"
            )

        facilities_df["latitude"] = pd.to_numeric(
            facilities_df["latitude"], errors="coerce"
        ).fillna(0.0)

        facilities_df["longitude"] = pd.to_numeric(
            facilities_df["longitude"], errors="coerce"
        ).fillna(0.0)

        self.stdout.write(f"Facilities to import: {len(facilities_df)}")

        self.stdout.write("Loading medicines...")

        medicines_df = pd.read_csv(
            medicine_path,
            dtype={"medicine_id": str},
        )

        medicines_df["medicine_id"] = medicines_df["medicine_id"].astype(str)

        self.stdout.write(f"Medicines to import: {len(medicines_df)}")

        with transaction.atomic():
            self.stdout.write("Removing existing pipeline/core demo records...")

            StockRisk.objects.all().delete()
            RedistributionRecommendation.objects.all().delete()
            OptimizedRoute.objects.all().delete()
            InventoryHistory.objects.all().delete()
            HMISActivity.objects.all().delete()

            # The current local database contains only generated demo
            # facilities. Remove those before inserting the real subset.
            Facility.objects.filter(is_demo_data=True).delete()

            # Medicine has no is_demo_data field, and the current database
            # medicines were created by generate_demo_data, so replace them.
            Medicine.objects.all().delete()

            self.stdout.write("Importing facilities...")

            facility_objects = [
                Facility(
                    facility_id=str(row.facility_id),
                    name=str(row.name),
                    facility_type=str(row.facility_type),
                    state=str(row.state),
                    district=str(row.district),
                    latitude=float(row.latitude),
                    longitude=float(row.longitude),
                    catchment_population=0,
                    is_demo_data=False,
                )
                for row in facilities_df.itertuples(index=False)
            ]

            Facility.objects.bulk_create(
                facility_objects,
                batch_size=self.BATCH_SIZE,
            )

            facility_map = {
                obj.facility_id: obj
                for obj in Facility.objects.filter(
                    facility_id__in=operational_facility_ids
                )
            }

            self.stdout.write("Importing medicines...")

            medicine_objects = [
                Medicine(
                    medicine_id=str(row.medicine_id),
                    name=str(row.medicine_name),
                    category=str(row.medicine_category),
                    unit=str(row.unit),
                    # These fields do not exist in the source dataset.
                    # Keep Django model defaults rather than inventing values.
                    is_temperature_sensitive=False,
                    avg_lead_time_days=7,
                )
                for row in medicines_df.itertuples(index=False)
            ]

            Medicine.objects.bulk_create(
                medicine_objects,
                batch_size=self.BATCH_SIZE,
            )

            medicine_map = {
                obj.medicine_id: obj
                for obj in Medicine.objects.all()
            }

            self.stdout.write("Importing inventory history...")

            inventory_count = 0

            for chunk in pd.read_csv(
                inventory_path,
                chunksize=self.BATCH_SIZE,
                dtype={
                    "facility_id": str,
                    "medicine_id": str,
                },
            ):
                chunk["date"] = pd.to_datetime(
                    chunk["date"], errors="coerce"
                )

                chunk = chunk.dropna(subset=["date"])

                objects = []

                for row in chunk.itertuples(index=False):
                    facility = facility_map.get(str(row.facility_id))
                    medicine = medicine_map.get(str(row.medicine_id))

                    if not facility or not medicine:
                        continue

                    objects.append(
                        InventoryHistory(
                            facility=facility,
                            medicine=medicine,
                            date=row.date.date(),
                            opening_stock=int(
                                0 if pd.isna(row.opening_stock)
                                else row.opening_stock
                            ),
                            consumed=int(
                                0 if pd.isna(row.consumed_quantity)
                                else row.consumed_quantity
                            ),
                            received=int(
                                0 if pd.isna(row.received_quantity)
                                else row.received_quantity
                            ),
                            closing_stock=int(
                                0 if pd.isna(row.closing_stock)
                                else row.closing_stock
                            ),
                            # Not present in the source dataset.
                            reorder_level=0,
                            safety_stock=0,
                        )
                    )

                if objects:
                    InventoryHistory.objects.bulk_create(
                        objects,
                        batch_size=self.BATCH_SIZE,
                    )
                    inventory_count += len(objects)

                    self.stdout.write(
                        f"  Imported inventory records: {inventory_count}"
                    )

            self.stdout.write("Importing HMIS activity...")

            hmis_count = 0

            for chunk in pd.read_csv(
                hmis_path,
                chunksize=self.BATCH_SIZE,
                dtype={"facility_id": str},
            ):
                chunk["date"] = pd.to_datetime(
                    chunk["date"], errors="coerce"
                )

                chunk = chunk.dropna(subset=["date"])

                objects = []

                for row in chunk.itertuples(index=False):
                    facility = facility_map.get(str(row.facility_id))

                    if not facility:
                        continue

                    objects.append(
                        HMISActivity(
                            facility=facility,
                            date=row.date.date(),
                            opd_footfall=int(
                                0 if pd.isna(row.opd_visits)
                                else row.opd_visits
                            ),
                            ipd_admissions=int(
                                0 if pd.isna(row.ipd_admissions)
                                else row.ipd_admissions
                            ),
                            deliveries=int(
                                0 if pd.isna(row.institutional_deliveries)
                                else row.institutional_deliveries
                            ),
                            emergency_cases=int(
                                0 if pd.isna(row.emergency_visits)
                                else row.emergency_visits
                            ),
                        )
                    )

                if objects:
                    HMISActivity.objects.bulk_create(
                        objects,
                        batch_size=self.BATCH_SIZE,
                    )
                    hmis_count += len(objects)

                    self.stdout.write(
                        f"  Imported HMIS records: {hmis_count}"
                    )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Real core datasets imported successfully."
            )
        )
        self.stdout.write(
            f"Facilities: {Facility.objects.count()}"
        )
        self.stdout.write(
            f"Medicines: {Medicine.objects.count()}"
        )
        self.stdout.write(
            f"Inventory records: {InventoryHistory.objects.count()}"
        )
        self.stdout.write(
            f"HMIS records: {HMISActivity.objects.count()}"
        )