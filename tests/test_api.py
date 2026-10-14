import json
from unittest.mock import patch

import pytest

from planner.models import RoutePlan

pytestmark = pytest.mark.django_db


def test_invalid_json(client):
    assert (
        client.post("/api/v1/route-plans/", data="{", content_type="application/json").status_code
        == 400
    )


def test_method(client):
    assert client.get("/api/v1/route-plans/").status_code == 405


def test_content_type(client):
    assert (
        client.post("/api/v1/route-plans/", data="hello", content_type="text/plain").status_code
        == 415
    )


def test_home(client):
    assert client.get("/").status_code == 200


def test_health(client):
    assert client.get("/api/v1/health/").json()["priced_stations"] == 0


def location(v):
    return {"label": v, "coordinates": [-96, 32] if v == "A" else [-95, 32]}


@patch("planner.service.resolve", side_effect=location)
@patch("planner.service.Router.route")
def test_short_route(route, resolve, client):
    route.return_value = {
        "geometry": {"type": "LineString", "coordinates": [[-96, 32], [-95, 32]]},
        "distance_miles": 100,
        "duration_seconds": 6000,
        "segments_miles": [100],
    }
    r = client.post(
        "/api/v1/route-plans/",
        data=json.dumps({"start": "A", "finish": "B"}),
        content_type="application/json",
    )
    assert r.status_code == 201
    body = r.json()
    assert body["fuel"]["total_fuel_cost_usd"] == "0.00"
    assert client.get("/maps/" + body["id"] + "/").status_code == 200
    assert RoutePlan.objects.count() == 1


@patch("planner.service.resolve", side_effect=location)
@pytest.mark.parametrize("fuel", [-1, 51, "NaN", True, None])
def test_bad_fuel(resolve, client, fuel):
    r = client.post(
        "/api/v1/route-plans/",
        data=json.dumps({"start": "A", "finish": "B", "initial_fuel_gallons": fuel}),
        content_type="application/json",
    )
    assert r.status_code == 400


@patch("planner.service.resolve", side_effect=location)
@patch("planner.service.candidates")
@patch("planner.service.Router.route")
def test_refueling_uses_actual_waypoint_distances(route, candidates, resolve, client):
    def geometry(distance, segments):
        return {
            "geometry": {"type": "LineString", "coordinates": [[-96, 32], [-95, 32]]},
            "distance_miles": distance,
            "duration_seconds": 1000,
            "segments_miles": segments,
        }

    route.side_effect = [geometry(700, [700]), geometry(710, [400, 310])]
    candidates.return_value = [
        {
            "mile": 395,
            "price": "3",
            "station_id": "1",
            "coordinates": [-95.5, 32],
            "name": "Fuel",
        }
    ]
    r = client.post(
        "/api/v1/route-plans/",
        data=json.dumps({"start": "A", "finish": "B"}),
        content_type="application/json",
    )
    assert r.status_code == 201
    body = r.json()
    assert body["fuel"]["total_fuel_cost_usd"] == "63.00"
    assert body["fuel"]["stops"][0]["mile"] == 400
    assert body["diagnostics"]["station_legs_routed"] is True
    assert route.call_count == 2


@patch("planner.service.resolve", side_effect=location)
@patch("planner.service.candidates")
@patch("planner.service.Router.route")
def test_unreachable_actual_leg_is_rejected(route, candidates, resolve, client):
    def geometry(distance, segments):
        return {
            "geometry": {"type": "LineString", "coordinates": [[-96, 32], [-95, 32]]},
            "distance_miles": distance,
            "duration_seconds": 1000,
            "segments_miles": segments,
        }

    route.side_effect = [geometry(700, [700]), geometry(720, [510, 210])]
    candidates.return_value = [
        {"mile": 490, "price": "3", "station_id": "1", "coordinates": [-95.5, 32]}
    ]
    r = client.post(
        "/api/v1/route-plans/",
        data=json.dumps({"start": "A", "finish": "B"}),
        content_type="application/json",
    )
    assert r.status_code == 422
    assert RoutePlan.objects.count() == 0


def test_large_body_uses_json_error(client, settings):
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 100
    response = client.post("/api/v1/route-plans/", data=" " * 200, content_type="application/json")
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "body_too_large"


def test_deeply_nested_json_is_rejected(client):
    response = client.post(
        "/api/v1/route-plans/", data="[" * 2000 + "0" + "]" * 2000, content_type="application/json"
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] in {"invalid_json", "invalid_body"}


@patch("planner.views.json.loads", side_effect=RecursionError)
def test_parser_recursion_error_returns_json(loads, client):
    response = client.post("/api/v1/route-plans/", data="[]", content_type="application/json")
    assert response.status_code == 400
    assert b"invalid_json" in response.content


@patch("planner.service.Router.route")
def test_identical_endpoints_require_no_provider(route, client):
    response = client.post(
        "/api/v1/route-plans/",
        data=json.dumps({"start": "Dallas, TX", "finish": "Dallas, TX", "initial_fuel_gallons": 0}),
        content_type="application/json",
    )
    assert response.status_code == 201
    assert response.json()["route"]["distance_miles"] == 0
    assert response.json()["fuel"]["total_fuel_cost_usd"] == "0.00"
    route.assert_not_called()


def test_map_escapes_untrusted_labels(client):
    label = "</script><script>alert(1)</script>"
    record = RoutePlan.objects.create(
        result={"start": {"label": label}, "finish": {"label": "End"}, "fuel": {"stops": []}}
    )
    response = client.get(f"/maps/{record.id}/")
    assert response.status_code == 200
    assert label.encode() not in response.content
    assert b"\\u003C/script\\u003E" in response.content
