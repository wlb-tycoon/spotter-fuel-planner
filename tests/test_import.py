import json
from decimal import Decimal

import pytest
from django.core.management import call_command

from planner.models import Station


@pytest.mark.django_db
def test_import_is_idempotent_and_preserves_price_precision(tmp_path, settings):
    settings.BASE_DIR = tmp_path
    (tmp_path / "data").mkdir()
    (tmp_path / "data/station-coordinates.json").write_text(
        json.dumps(
            {
                "7": {
                    "longitude": -96,
                    "latitude": 32,
                    "source": "https://www.openstreetmap.org/node/1",
                    "confidence": "test",
                }
            }
        )
    )
    (tmp_path / "fuel-prices-for-be-assessment.csv").write_text(
        "OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price\n7,Fuel,Highway,Dallas,TX,1,3.10000001\n7,Fuel,Highway,Dallas,TX,1,3.30000001\n"
    )
    call_command("import_stations")
    call_command("import_stations")
    assert Station.objects.count() == 1
    assert Station.objects.get().price == Decimal("3.20000001")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "bad_data", [{}, [], {"unknown": {}}, {"7": {"longitude": float("nan"), "latitude": 32}}]
)
def test_bad_import_preserves_existing_station(tmp_path, settings, bad_data):
    from django.core.management.base import CommandError

    settings.BASE_DIR = tmp_path
    (tmp_path / "data").mkdir()
    (tmp_path / "data/station-coordinates.json").write_text(json.dumps(bad_data))
    (tmp_path / "fuel-prices-for-be-assessment.csv").write_text(
        "OPIS Truckstop ID,Truckstop Name,Address,City,State,Retail Price\n7,Fuel,Highway,Dallas,TX,3.00\n"
    )
    Station.objects.create(
        opis_id="existing",
        name="Existing",
        address="Street",
        city="Dallas",
        state="TX",
        price=3,
        longitude=-96,
        latitude=32,
        source="test",
        confidence="test",
    )
    with pytest.raises(CommandError):
        call_command("import_stations")
    assert list(Station.objects.values_list("opis_id", flat=True)) == ["existing"]


@pytest.mark.django_db
@pytest.mark.parametrize("price", ["-1", "NaN", "Infinity", "0", "10000"])
def test_invalid_prices_rejected(tmp_path, settings, price):
    from django.core.management.base import CommandError

    settings.BASE_DIR = tmp_path
    (tmp_path / "data").mkdir()
    (tmp_path / "data/station-coordinates.json").write_text(
        json.dumps(
            {"7": {"longitude": -96, "latitude": 32, "source": "test", "confidence": "test"}}
        )
    )
    (tmp_path / "fuel-prices-for-be-assessment.csv").write_text(
        f"OPIS Truckstop ID,Truckstop Name,Address,City,State,Retail Price\n7,Fuel,Highway,Dallas,TX,{price}\n"
    )
    with pytest.raises(CommandError):
        call_command("import_stations")
    assert Station.objects.count() == 0
