import json
import math
import re
import unicodedata
from functools import lru_cache

from django.conf import settings
from shapely.geometry import Point, shape

from .errors import PlanError


@lru_cache(maxsize=1)
def cities():
    path = settings.BASE_DIR / "data/cities.json"
    if not path.exists():
        raise PlanError("data_not_ready", "Run the data preparation commands first.", 503)
    return json.loads(path.read_text())


@lru_cache(maxsize=1)
def boundary():
    p = settings.BASE_DIR / "data/us-boundary.geojson"
    if not p.exists():
        raise PlanError("data_not_ready", "US boundary data is missing.", 503)
    return shape(json.loads(p.read_text())["geometry"])


def resolve(value):
    if isinstance(value, str):
        parts = value.rsplit(",", 1)
        if len(parts) != 2:
            raise PlanError("unknown_location", "Use City, ST format, e.g. Dallas, TX.")
        city = re.sub(
            r"[^a-z0-9]+",
            " ",
            unicodedata.normalize("NFKD", parts[0]).encode("ascii", "ignore").decode().lower(),
        ).strip()
        key = f"{city}, {parts[1].strip().lower()}"
        found = cities().get(key)
        if not found:
            raise PlanError(
                "unknown_location",
                'Use a recognized US city and two-letter state, e.g. Dallas, TX, or {"latitude":32.78,"longitude":-96.8}.',
            )
        return {"label": value, "coordinates": found[:2]}
    if isinstance(value, dict):
        try:
            if isinstance(value.get("latitude"), bool) or isinstance(value.get("longitude"), bool):
                raise ValueError
            lat = float(value["latitude"])
            lon = float(value["longitude"])
        except (KeyError, ValueError, TypeError, OverflowError):
            raise PlanError(
                "invalid_location",
                "Coordinates require numeric latitude and longitude.",
            )
        if not all(math.isfinite(x) for x in (lat, lon)) or not (
            -90 <= lat <= 90 and -180 <= lon <= 180
        ):
            raise PlanError("invalid_location", "Coordinates are out of range.")
        if not boundary().buffer(0.01).covers(Point(lon, lat)):
            raise PlanError("outside_usa", "Both endpoints must be within the USA.")
        return {"label": f"{lat}, {lon}", "coordinates": [lon, lat]}
    raise PlanError("invalid_location", "Provide a US city/state string or a coordinate object.")
