from django.core.management.base import BaseCommand

from core.pipeline import run_full_pipeline


class Command(BaseCommand):
    help = "Run the forecast -> risk -> redistribution -> routing pipeline and persist results."

    def add_arguments(self, parser):
        parser.add_argument("--horizon-days", type=int, default=14)

    def handle(self, *args, **opts):
        self.stdout.write("Running pipeline (this scores every facility/medicine pair — may take a minute)...")
        summary = run_full_pipeline(horizon_days=opts["horizon_days"])
        for k, v in summary.items():
            self.stdout.write(f"  {k}: {v}")
        self.stdout.write(self.style.SUCCESS("Pipeline complete."))
