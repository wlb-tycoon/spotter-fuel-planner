"""Locate stations along a route, preserving cumulative great-circle distances."""

import bisect
import math
from itertools import accumulate

from shapely.geometry import LineString, Point


def haversine(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 3958.7613 * 2 * math.asin(min(1, math.sqrt(h)))


class RouteGeometry:
    def __init__(self, coordinates, road_miles):
        self.road_miles = road_miles
        meanlat = sum(c[1] for c in coordinates) / len(coordinates)
        self.xscale = 69.172 * math.cos(math.radians(meanlat))
        self.yscale = 69.0
        points = [(c[0] * self.xscale, c[1] * self.yscale) for c in coordinates]
        self.line = LineString(points)
        self.projected = [0, *accumulate(math.dist(a, b) for a, b in zip(points, points[1:]))]
        self.actual = [
            0,
            *accumulate(haversine(a, b) for a, b in zip(coordinates, coordinates[1:])),
        ]

    def locate(self, longitude, latitude):
        point = Point(longitude * self.xscale, latitude * self.yscale)
        position = self.line.project(point)
        offset = self.line.distance(point)
        if not self.actual[-1]:
            return 0, offset
        i = min(bisect.bisect_right(self.projected, position) - 1, len(self.projected) - 2)
        segment = self.projected[i + 1] - self.projected[i]
        fraction = (position - self.projected[i]) / segment if segment else 0
        distance = self.actual[i] + fraction * (self.actual[i + 1] - self.actual[i])
        return distance / self.actual[-1] * self.road_miles, offset
