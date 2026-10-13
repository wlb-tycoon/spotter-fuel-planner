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
