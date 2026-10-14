import pytest

from planner.errors import PlanError
from planner.locations import resolve


@pytest.mark.parametrize(
    "value",
    [
        {"latitude": 91, "longitude": 0},
        {"latitude": True, "longitude": 0},
        {"latitude": "nan", "longitude": 0},
        [],
        None,
    ],
)
def test_bad_coordinates(value):
    with pytest.raises(PlanError):
        resolve(value)


def test_non_us():
    with pytest.raises(PlanError) as e:
        resolve({"latitude": 51.5, "longitude": -0.12})
    assert e.value.code == "outside_usa"


def test_huge_coordinate_is_rejected():
    with pytest.raises(PlanError) as error:
        resolve({"latitude": 10**400, "longitude": 0})
    assert error.value.code == "invalid_location"
