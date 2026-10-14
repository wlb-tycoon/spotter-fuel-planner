import hashlib
import json
import math

import requests
from django.conf import settings
from django.core.cache import cache

from .errors import PlanError


class Router:
    def __init__(self):
        self.calls = 0
        self.cache_hits = 0

    def route(self, coordinates):
        key = "route:v3:" + hashlib.sha256(json.dumps(coordinates).encode()).hexdigest()
        cached = cache.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        if not settings.ORS_API_KEY:
            raise PlanError("routing_not_configured", "Set ORS_API_KEY in .env.", 503)
        self.calls += 1
        try:
            response = requests.post(
                "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
                headers={"Authorization": settings.ORS_API_KEY},
                json={"coordinates": coordinates, "instructions": True},
                timeout=(5, 35),
            )
        except requests.RequestException:
            raise PlanError(
                "routing_unavailable", "Routing service unavailable; please retry.", 503
            )
        if response.status_code == 429:
            raise PlanError(
                "routing_rate_limited",
                "Routing provider quota reached; retry later.",
                503,
            )
        if response.status_code in (401, 403):
            raise PlanError(
                "routing_authentication_failed",
                "Routing provider rejected the configured API key.",
                503,
            )
        if response.status_code >= 500:
            raise PlanError(
                "routing_unavailable", "Routing provider is temporarily unavailable.", 503
            )
        if not response.ok:
            raise PlanError(
                "route_unavailable",
                "No route could be calculated within the provider limits.",
                422,
            )
        try:
            feature = response.json()["features"][0]
            segments = feature["properties"]["segments"]
            if len(segments) != len(coordinates) - 1:
                raise ValueError("Unexpected route segment count")
            geometry = feature["geometry"]
            points = geometry["coordinates"]
            if geometry["type"] != "LineString" or not isinstance(points, list) or len(points) < 2:
                raise ValueError("Invalid route geometry")
            for point in points:
                if not isinstance(point, list) or len(point) < 2:
                    raise ValueError("Invalid coordinate")
                lon, lat = point[:2]
                if any(type(v) not in (int, float) or not math.isfinite(v) for v in (lon, lat)):
                    raise ValueError("Invalid coordinate value")
                if not -180 <= lon <= 180 or not -90 <= lat <= 90:
                    raise ValueError("Coordinate out of range")
            distance = feature["properties"]["summary"]["distance"]
            duration = feature["properties"]["summary"]["duration"]
            leg_distances = [segment["distance"] for segment in segments]
            for value in [distance, duration, *leg_distances]:
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                    raise ValueError("Invalid route measurement")
            # Provider distances are rounded to tenths of a metre per segment.
            if abs(sum(leg_distances) - distance) > max(1, len(segments) * 0.1):
                raise ValueError("Inconsistent route distances")
            if distance > 0 and all(point[:2] == points[0][:2] for point in points):
                raise ValueError("Degenerate route geometry")
            distance = sum(leg_distances)
            result = {
                "geometry": geometry,
                "distance_miles": distance / 1609.344,
                "duration_seconds": duration,
                "segments_miles": [distance / 1609.344 for distance in leg_distances],
            }
        except (KeyError, ValueError, IndexError, TypeError, OverflowError):
            raise PlanError(
                "invalid_provider_response",
                "Routing service returned an invalid response.",
                502,
            )
        cache.set(key, result)
        return result
