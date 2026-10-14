import csv
import json
import math
import statistics
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from planner.models import Station

US_STATES = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
)


class Command(BaseCommand):
    help = "Validate and import matched station coordinates and CSV prices; safe to repeat."

    def handle(self, *args, **options):
        path = settings.BASE_DIR / "data/station-coordinates.json"
        try:
            matches = json.loads(path.read_text())
            if not isinstance(matches, dict) or not matches:
                raise ValueError("Coordinate data must be a nonempty station mapping")
            groups = {}
            with (settings.BASE_DIR / "fuel-prices-for-be-assessment.csv").open(newline="") as f:
                reader = csv.DictReader(f)
                required = {
                    "OPIS Truckstop ID",
                    "Truckstop Name",
                    "Address",
                    "City",
                    "State",
                    "Retail Price",
                }
                if not required.issubset(reader.fieldnames or []):
                    raise ValueError("CSV is missing required columns")
                for row in reader:
                    groups.setdefault(row["OPIS Truckstop ID"], []).append(row)
            prepared = []
            for key, geo in matches.items():
                if key not in groups:
                    raise ValueError(f"Station {key} is absent from the CSV")
                rows = groups[key]
                r = rows[0]
                if any(row["State"] != r["State"] for row in rows) or r["State"] not in US_STATES:
                    raise ValueError(f"Station {key} has an invalid or conflicting US state")
                prices = [Decimal(row["Retail Price"]) for row in rows]
                if any(not price.is_finite() or price <= 0 or price >= 10000 for price in prices):
                    raise ValueError(f"Station {key} has an invalid retail price")
                price = statistics.median(prices).quantize(Decimal("0.00000001"))
                lon, lat = geo["longitude"], geo["latitude"]
                if any(
                    type(value) not in (int, float) or not math.isfinite(value)
                    for value in (lon, lat)
                ):
                    raise ValueError(f"Station {key} has invalid coordinates")
                if not -180 <= lon <= 180 or not -90 <= lat <= 90:
                    raise ValueError(f"Station {key} coordinates are out of range")
                values = {
                    "name": r["Truckstop Name"],
                    "address": r["Address"],
                    "city": r["City"],
                    "state": r["State"],
                    "price": price,
                    "longitude": lon,
                    "latitude": lat,
                    "source": geo["source"],
                    "confidence": geo["confidence"],
                }
                Station(opis_id=key, **values).full_clean(
                    validate_unique=False, validate_constraints=False
                )
                prepared.append((key, values))
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            InvalidOperation,
            OverflowError,
            ValidationError,
        ) as error:
            raise CommandError(
                f"Station import rejected; existing data was preserved: {error}"
            ) from error
        # Validate the complete input before replacing any existing station records.
        with transaction.atomic():
            for key, values in prepared:
                Station.objects.update_or_create(opis_id=key, defaults=values)
            Station.objects.exclude(opis_id__in=matches).delete()
        self.stdout.write(self.style.SUCCESS(f"Imported {len(prepared)} priced stations."))
