from unittest.mock import Mock, patch

import pytest
import requests
from django.core.cache import cache
from django.test import override_settings

from planner.errors import PlanError
from planner.routing import Router


@override_settings(ORS_API_KEY="test-placeholder")
@patch("planner.routing.requests.post")
def test_cache_prevents_duplicate_calls(post):
    cache.clear()
    post.return_value = Mock(ok=True, status_code=200)
    post.return_value.json.return_value = {
        "features": [
            {
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                "properties": {
                    "summary": {"distance": 1609.344, "duration": 100},
                    "segments": [{"distance": 1609.344}],
                },
            }
        ]
    }
    r = Router()
    assert r.route([[0, 0], [1, 1]])["distance_miles"] == 1
    r.route([[0, 0], [1, 1]])
    assert r.calls == 1
    assert r.cache_hits == 1
    assert post.call_count == 1


@override_settings(ORS_API_KEY="test-placeholder")
@patch("planner.routing.requests.post")
@pytest.mark.parametrize(
    "status,code",
    [
        (429, "routing_rate_limited"),
        (401, "routing_authentication_failed"),
        (500, "routing_unavailable"),
    ],
)
def test_provider_errors(post, status, code):
    cache.clear()
    post.return_value = Mock(ok=False, status_code=status)
    with pytest.raises(PlanError) as e:
        Router().route([[0, 0], [2, 2]])
    assert e.value.code == code


@override_settings(ORS_API_KEY="test-placeholder")
@patch("planner.routing.requests.post", side_effect=requests.Timeout)
def test_timeout(post):
    cache.clear()
    with pytest.raises(PlanError) as e:
        Router().route([[0, 0], [3, 3]])
    assert e.value.status == 503


@override_settings(ORS_API_KEY="test-placeholder")
@patch("planner.routing.requests.post")
@pytest.mark.parametrize("bad_value", [-1, float("nan"), float("inf"), True, "100"])
def test_invalid_measurements_not_cached(post, bad_value):
    cache.clear()
    post.return_value = Mock(ok=True, status_code=200)
    post.return_value.json.return_value = {
        "features": [
            {
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                "properties": {
                    "summary": {"distance": bad_value, "duration": 100},
                    "segments": [{"distance": bad_value}],
                },
            }
        ]
    }
    router = Router()
    for _ in range(2):
        with pytest.raises(PlanError) as error:
            router.route([[0, 0], [1, 1]])
        assert error.value.code == "invalid_provider_response"
    assert post.call_count == 2


@override_settings(ORS_API_KEY="test-placeholder")
@patch("planner.routing.requests.post")
@pytest.mark.parametrize(
    "geometry",
    [
        None,
        {"type": "Point", "coordinates": [0, 0]},
        {"type": "LineString", "coordinates": []},
        {"type": "LineString", "coordinates": [[0, 0], [0, 0]]},
        {"type": "LineString", "coordinates": [[0, 0], [float("nan"), 1]]},
    ],
)
def test_invalid_geometry_returns_provider_error(post, geometry):
    cache.clear()
    post.return_value = Mock(ok=True, status_code=200)
    post.return_value.json.return_value = {
        "features": [
            {
                "geometry": geometry,
                "properties": {
                    "summary": {"distance": 100, "duration": 100},
                    "segments": [{"distance": 100}],
                },
            }
        ]
    }
    with pytest.raises(PlanError) as error:
        Router().route([[0, 0], [1, 1]])
    assert error.value.status == 502


@override_settings(ORS_API_KEY="test-placeholder")
@patch("planner.routing.requests.post")
def test_total_uses_sum_of_rounded_legs(post):
    cache.clear()
    post.return_value = Mock(ok=True, status_code=200)
    post.return_value.json.return_value = {
        "features": [
            {
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1], [2, 2]]},
                "properties": {
                    "summary": {"distance": 200.1, "duration": 100},
                    "segments": [{"distance": 100.1}, {"distance": 100.1}],
                },
            }
        ]
    }
    route = Router().route([[0, 0], [1, 1], [2, 2]])
    assert route["distance_miles"] == pytest.approx(sum(route["segments_miles"]))
