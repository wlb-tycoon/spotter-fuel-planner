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
