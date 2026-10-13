import pytest

from planner.geometry import RouteGeometry


def test_route_distance_includes_bend():
    g = RouteGeometry([[-100, 35], [-99, 35], [-99, 36]], 200)
    mile, offset = g.locate(-99, 35)
    assert 80 < mile < 100
    assert offset == pytest.approx(0)
    assert g.locate(-99, 36)[0] == pytest.approx(200)


def test_degenerate_route():
    assert RouteGeometry([[-100, 35], [-100, 35]], 0).locate(-100, 35) == (0, 0)
