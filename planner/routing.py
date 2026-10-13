import hashlib
import json

import requests
from django.conf import settings
from django.core.cache import cache

from .errors import PlanError


class Router:
    def __init__(self):
        self.calls = 0
        self.cache_hits = 0

    def route(self, coordinates):
        key = "route:" + hashlib.sha256(json.dumps(coordinates).encode()).hexdigest()
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
            result = {
                "geometry": feature["geometry"],
                "distance_miles": feature["properties"]["summary"]["distance"] / 1609.344,
                "duration_seconds": feature["properties"]["summary"]["duration"],
                "segments_miles": [
                    s["distance"] / 1609.344 for s in feature["properties"]["segments"]
                ],
            }
        except (KeyError, ValueError, IndexError, TypeError):
            raise PlanError(
                "invalid_provider_response",
                "Routing service returned an invalid response.",
                502,
            )
        cache.set(key, result)
        return result
