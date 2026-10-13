"""Exact greedy purchases for a fixed ordered path, continuous fuel, no stop fee."""

from decimal import Decimal

from .errors import PlanError

D = Decimal
CAPACITY = D("50")
MPG = D("10")
EPS = D("0.000001")


def optimize(stations, total_miles, initial_gallons=50):
    end = D(str(total_miles))
    fuel = D(str(initial_gallons))
    last = D(0)
    stops = []
    if not D(0) <= fuel <= CAPACITY:
        raise PlanError("invalid_fuel", "Starting fuel must be between 0 and 50 gallons.")
    ordered = sorted(stations, key=lambda s: float(s["mile"]))
    # Monotonic stack finds the next strictly cheaper station in O(n).
    prices = [D(str(s["price"])) for s in ordered]
    miles = [D(str(s["mile"])) for s in ordered]
    next_cheaper = [None] * len(ordered)
    stack = []
    for i in range(len(ordered) - 1, -1, -1):
        while stack and prices[stack[-1]] >= prices[i]:
            stack.pop()
        if stack:
            next_cheaper[i] = stack[-1]
        stack.append(i)
    for i, station in enumerate(ordered):
        mile = D(str(station["mile"]))
        need = (mile - last) / MPG
        if fuel + EPS < need:
            if fuel + EPS >= (end - last) / MPG:
                break
            raise PlanError(
                "insufficient_station_coverage",
                "No reachable priced station can bridge this route with the available fuel.",
                422,
            )
        fuel = max(D(0), fuel - need)
        last = mile
        price = prices[i]
        target = min(CAPACITY, (end - mile) / MPG)
        cheaper = next_cheaper[i]
        if cheaper is not None and miles[cheaper] - mile <= CAPACITY * MPG:
            target = min(target, (miles[cheaper] - mile) / MPG)
        buy = max(D(0), target - fuel)
        if buy > EPS:
            cost = buy * price
            stops.append(
                {
                    **station,
                    "arrival_fuel_gallons": float(fuel),
                    "gallons_purchased": float(buy),
                    "departure_fuel_gallons": float(fuel + buy),
                    "cost_usd": str(cost.quantize(D("0.01"))),
                }
            )
            fuel += buy
    remaining = (end - last) / MPG
    if fuel + EPS < remaining:
        raise PlanError(
            "insufficient_station_coverage",
            "The destination cannot be reached with the available station coverage.",
            422,
        )
    return {
        "stops": stops,
        "fuel_consumed_gallons": float(end / MPG),
        "fuel_purchased_gallons": sum(s["gallons_purchased"] for s in stops),
        "remaining_fuel_gallons": float(max(D(0), fuel - remaining)),
        "total_fuel_cost_usd": str(
            sum((D(s["cost_usd"]) for s in stops), D(0)).quantize(D("0.01"))
        ),
    }
