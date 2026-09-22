from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Facility, Infrastructure


class Command(BaseCommand):
    help = "Import facility capacity, latest bed status and latest staff attendance."

    def handle(self, *args, **options):
        base = Path(settings.DATASETS_DIR)

        capacity_path = base / "infrastructure" / "facility_capacity.csv"
        attendance_path = base / "infrastructure" / "staff_attendance.csv"
        beds_path = base / "infrastructure" / "daily_bed_status.csv"

        for path in [capacity_path, attendance_path, beds_path]:
            if not path.exists():
                raise FileNotFoundError(f"Dataset not found: {path}")

        self.stdout.write("Reading infrastructure datasets...")

        capacity = pd.read_csv(
            capacity_path,
            dtype={"facility_id": str},
        )

        attendance = pd.read_csv(
            attendance_path,
            dtype={"facility_id": str},
        )

        beds = pd.read_csv(
            beds_path,
            dtype={"facility_id": str},
        )

        # Normalize IDs.
        capacity["facility_id"] = capacity["facility_id"].astype(str)
        attendance["facility_id"] = attendance["facility_id"].astype(str)
        beds["facility_id"] = beds["facility_id"].astype(str)

        # Keep the latest attendance record for each facility.
        attendance["date"] = pd.to_datetime(
            attendance["date"],
            errors="coerce",
        )

        latest_attendance = (
            attendance
            .dropna(subset=["date"])
            .sort_values("date")
            .drop_duplicates("facility_id", keep="last")
        )

        # Keep the latest available bed-status record for each facility.
        beds["date"] = pd.to_datetime(
            beds["date"],
            errors="coerce",
        )

        latest_beds = (
            beds
            .dropna(subset=["date"])
            .sort_values("date")
            .drop_duplicates("facility_id", keep="last")
        )

        attendance_map = {
            str(row.facility_id): row
            for row in latest_attendance.itertuples(index=False)
        }

        beds_map = {
            str(row.facility_id): row
            for row in latest_beds.itertuples(index=False)
        }

        facility_map = {
            obj.facility_id: obj
            for obj in Facility.objects.all()
        }

        missing_capacity_facilities = (
            set(facility_map) - set(capacity["facility_id"])
        )

        if missing_capacity_facilities:
            raise ValueError(
                f"{len(missing_capacity_facilities)} database facilities "
                "are missing from facility_capacity.csv"
            )

        infrastructure_objects = []

        for row in capacity.itertuples(index=False):
            facility_id = str(row.facility_id)
            facility = facility_map.get(facility_id)

            # Only import facilities already present in our operational DB.
            if not facility:
                continue

            bed_row = beds_map.get(facility_id)
            attendance_row = attendance_map.get(facility_id)

            beds_total = int(
                0 if pd.isna(row.beds_total) else row.beds_total
            )

            # Use the latest observed occupied-bed count.
            if bed_row is not None:
                occupied_beds = int(
                    0
                    if pd.isna(bed_row.beds_occupied)
                    else bed_row.beds_occupied
                )
            else:
                # The four missing facilities are SHCs with zero beds.
                if beds_total != 0:
                    raise ValueError(
                        f"No bed-status record for {facility_id}, "
                        f"but capacity says beds_total={beds_total}"
                    )
                occupied_beds = 0

            doctors_sanctioned = int(
                0
                if pd.isna(row.doctors_sanctioned)
                else row.doctors_sanctioned
            )

            nurses_sanctioned = int(
                0
                if pd.isna(row.nurses_sanctioned)
                else row.nurses_sanctioned
            )

            specialists_sanctioned = int(
                0
                if pd.isna(row.specialists_sanctioned)
                else row.specialists_sanctioned
            )

            # Use latest attendance as the "present" value.
            doctors_present = 0
            nurses_present = 0
            specialists_present = 0

            if attendance_row is not None:
                doctors_present = int(
                    0
                    if pd.isna(attendance_row.doctors_present)
                    else attendance_row.doctors_present
                )
                nurses_present = int(
                    0
                    if pd.isna(attendance_row.nurses_present)
                    else attendance_row.nurses_present
                )
                specialists_present = int(
                    0
                    if pd.isna(attendance_row.specialists_present)
                    else attendance_row.specialists_present
                )

            infrastructure_objects.append(
                Infrastructure(
                    facility=facility,
                    total_beds=beds_total,
                    occupied_beds=occupied_beds,
                    doctors_sanctioned=doctors_sanctioned,
                    doctors_present=doctors_present,
                    nurses_sanctioned=nurses_sanctioned,
                    nurses_present=nurses_present,
                    specialists_sanctioned=specialists_sanctioned,
                    specialists_present=specialists_present,
                    # These fields are not supplied by these datasets.
                    has_cold_storage=False,
                    has_ambulance=False,
                )
            )

        with transaction.atomic():
            Infrastructure.objects.all().delete()

            Infrastructure.objects.bulk_create(
                infrastructure_objects,
                batch_size=1000,
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Infrastructure data imported successfully."
            )
        )
        self.stdout.write(
            f"Infrastructure records: {Infrastructure.objects.count()}"
        )

        self.stdout.write(
            f"Latest staff attendance date: "
            f"{latest_attendance['date'].max().date()}"
        )

        self.stdout.write(
            f"Latest bed-status date: "
            f"{latest_beds['date'].max().date()}"
        )