import time
from decimal import Decimal, InvalidOperation

from .errors import PlanError
from .geometry import RouteGeometry
from .locations import resolve
from .models import RoutePlan, Station
from .optimizer import optimize
from .routing import Router


def candidates(route):
    coords = route["geometry"]["coordinates"]
    geometry = RouteGeometry(coords, route["distance_miles"])
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    rows = Station.objects.filter(
        longitude__gte=min(lons) - 0.15,
        longitude__lte=max(lons) + 0.15,
        latitude__gte=min(lats) - 0.1,
        latitude__lte=max(lats) + 0.1,
    )
    result = []
    for s in rows:
        mile, offset = geometry.locate(s.longitude, s.latitude)
        if offset > 3:
            continue
        result.append(
            {
                "station_id": s.opis_id,
                "name": s.name,
                "address": s.address,
                "city": s.city,
                "state": s.state,
                "price": str(s.price),
                "coordinates": [s.longitude, s.latitude],
                "mile": mile,
                "route_offset_miles": round(offset, 3),
                "coordinate_source": s.source,
                "coordinate_confidence": s.confidence,
            }
        )
    return sorted(result, key=lambda s: (s["mile"], Decimal(s["price"]), s["station_id"]))


def plan(payload):
    started = time.monotonic()
    if not isinstance(payload, dict):
        raise PlanError("invalid_body", "Request body must be an object.")
    unknown = set(payload) - {"start", "finish", "initial_fuel_gallons"}
    if unknown:
        raise PlanError("unknown_fields", "Unknown fields: " + ", ".join(sorted(unknown)))
    start = resolve(payload.get("start"))
    finish = resolve(payload.get("finish"))
    try:
        initial = Decimal(str(payload.get("initial_fuel_gallons", 50)))
        if not initial.is_finite() or not 0 <= initial <= 50:
            raise ValueError
    except (InvalidOperation, ValueError):
        raise PlanError("invalid_fuel", "Starting fuel must be between 0 and 50 gallons.")
    router = Router()
    if start["coordinates"] == finish["coordinates"]:
        route = {
            "geometry": {
                "type": "LineString",
                "coordinates": [start["coordinates"], finish["coordinates"]],
            },
            "distance_miles": 0,
            "duration_seconds": 0,
            "segments_miles": [0],
        }
        choices = []
    else:
        route = router.route([start["coordinates"], finish["coordinates"]])
        choices = candidates(route)
    solution = optimize(choices, route["distance_miles"], initial)
    base_distance = route["distance_miles"]
    verified = False
    # One additional directions request visits selected station waypoints and validates actual leg lengths.
    if solution["stops"]:
        selected = solution["stops"]
        if len(selected) > 48:
            raise PlanError("too_many_stops", "Route exceeds the provider waypoint limit.", 422)
        route = router.route(
            [start["coordinates"]] + [s["coordinates"] for s in selected] + [finish["coordinates"]]
        )
        mile = 0
        fixed = []
        for s, distance in zip(selected, route["segments_miles"]):
            mile += distance
            fixed.append({**s, "mile": mile})
        solution = optimize(fixed, route["distance_miles"], initial)
        verified = True
        # Retain traversed waypoints even if a recomputed purchase is zero.
        visited = [{"station_id": s["station_id"], "coordinates": s["coordinates"]} for s in fixed]
    else:
        visited = []
    result = {
        "start": start,
        "finish": finish,
        "route": route,
        "fuel": solution,
        "vehicle": {
            "range_miles": 500,
            "mpg": 10,
            "tank_capacity_gallons": 50,
            "initial_fuel_gallons": float(initial),
        },
        "visited_station_waypoints": visited,
        "assumptions": {
            "currency": "USD",
            "price_unit": "USD per US gallon",
            "initial_fuel_cost": "Excluded; total_fuel_cost_usd is purchases during this trip.",
            "price_policy": "Median of supplied rows for each station ID; conflicting observations have no timestamps.",
            "optimization_scope": "Greedy optimal purchases for the fixed ordered path. Station selection uses an approximate route corridor; no global road-network optimum is claimed.",
            "station_access": "Selected station coordinates are routed as waypoints. Road snapping and entrance accuracy depend on the provider.",
            "profile": "driving-car; truck height/weight restrictions are not modeled.",
        },
        "diagnostics": {
            "candidate_stations": len(choices),
            "external_routing_calls": router.calls,
            "routing_cache_hits": router.cache_hits,
            "station_legs_routed": verified,
            "base_route_miles": base_distance,
            "elapsed_ms": round((time.monotonic() - started) * 1000),
        },
        "warnings": [
            "Only automatically matched CSV stations are eligible; matches are not all manually verified, and unmatched stations may contain cheaper alternatives."
        ],
    }
    record = RoutePlan.objects.create(result=result)
    return record
