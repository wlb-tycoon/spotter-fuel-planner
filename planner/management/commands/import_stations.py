import csv
import json
import statistics
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from planner.models import Station


class Command(BaseCommand):
    help = "Import matched station coordinates and CSV prices; safe to repeat."

    def handle(self, *args, **options):
        path = settings.BASE_DIR / "data/station-coordinates.json"
        if not path.exists():
            raise CommandError("Run scripts/prepare_data.py first.")
        matches = json.loads(path.read_text())
        groups = {}
        with (settings.BASE_DIR / "fuel-prices-for-be-assessment.csv").open(newline="") as f:
            for r in csv.DictReader(f):
                groups.setdefault(r["OPIS Truckstop ID"], []).append(r)
        with transaction.atomic():
            for key, geo in matches.items():
                rows = groups[key]
                r = rows[0]
                price = statistics.median(Decimal(x["Retail Price"]) for x in rows)
                Station.objects.update_or_create(
                    opis_id=key,
                    defaults={
                        "name": r["Truckstop Name"],
                        "address": r["Address"],
                        "city": r["City"],
                        "state": r["State"],
                        "price": price,
                        "longitude": geo["longitude"],
                        "latitude": geo["latitude"],
                        "source": geo["source"],
                        "confidence": geo["confidence"],
                    },
                )
            Station.objects.exclude(opis_id__in=matches).delete()
        self.stdout.write(self.style.SUCCESS(f"Imported {len(matches)} priced stations."))
