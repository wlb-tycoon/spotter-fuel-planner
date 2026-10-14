import random
from decimal import Decimal

import pytest

from planner.errors import PlanError
from planner.optimizer import optimize


def station(mile, price):
    return {"mile": mile, "price": str(price), "station_id": str(mile)}


def test_short_trip():
    r = optimize([], 200)
    assert r["total_fuel_cost_usd"] == "0.00"
    assert r["remaining_fuel_gallons"] == 30


def test_boundary():
    assert optimize([], 500)["remaining_fuel_gallons"] == 0
    with pytest.raises(PlanError):
        optimize([], 500.01)


def test_cheaper_next_station_partial_purchase():
    r = optimize([station(100, 5), station(300, 2)], 700, 10)
    assert [s["gallons_purchased"] for s in r["stops"]] == [20, 40]
    assert r["total_fuel_cost_usd"] == "180.00"


def test_unreachable():
    with pytest.raises(PlanError):
        optimize([station(501, 1)], 700)


def test_expensive_later_station():
    r = optimize([station(100, 2), station(400, 5)], 700, 10)
    assert [s["gallons_purchased"] for s in r["stops"]] == [50, 10]
    assert r["remaining_fuel_gallons"] == 0


def test_multiple_stops_conservation():
    r = optimize([station(400, 3), station(800, 2), station(1200, 4)], 1500)
    assert r["remaining_fuel_gallons"] == pytest.approx(50 + r["fuel_purchased_gallons"] - 150)
    assert all(0 <= s["departure_fuel_gallons"] <= 50 for s in r["stops"])


def oracle(stations, total, initial):
    # Independent dynamic program: whole gallon purchases, distances divisible by 10.
    states = {initial: 0}
    previous = 0
    for s in stations + [{"mile": total, "price": 0}]:
        need = (s["mile"] - previous) // 10
        arrivals = {f - need: c for f, c in states.items() if f >= need}
        if s["mile"] == total:
            return min(arrivals.values()) if arrivals else None
        states = {}
        for f, c in arrivals.items():
            for buy in range(51 - f):
                states[f + buy] = min(states.get(f + buy, float("inf")), c + buy * s["price"])
        previous = s["mile"]
    return None


def test_matches_reference_solver():
    rng = random.Random(17)
    for _ in range(100):
        miles = sorted(rng.sample(range(1, 140), 8))
        total = 1500
        initial = rng.randrange(10, 51)
        ss = [{"mile": m * 10, "price": rng.randrange(2, 7)} for m in miles]
        expected = oracle(ss, total, initial)
        if expected is None:
            with pytest.raises(PlanError):
                optimize(ss, total, initial)
        else:
            assert Decimal(optimize(ss, total, initial)["total_fuel_cost_usd"]) == expected


def test_equal_price_topups_do_not_exceed_waypoint_limit():
    result = optimize([station(mile, 3) for mile in range(50, 3000, 50)], 3000)
    assert len(result["stops"]) == 5
    assert result["total_fuel_cost_usd"] == "750.00"
    assert result["fuel_purchased_gallons"] == 250
    previous_mile = 0
    fuel = 50
    for stop in result["stops"]:
        fuel -= (stop["mile"] - previous_mile) / 10
        assert fuel >= 0
        assert stop["arrival_fuel_gallons"] == pytest.approx(fuel)
        fuel += stop["gallons_purchased"]
        assert fuel <= 50
        assert stop["departure_fuel_gallons"] == pytest.approx(fuel)
        previous_mile = stop["mile"]
    assert fuel - (3000 - previous_mile) / 10 == pytest.approx(0)
