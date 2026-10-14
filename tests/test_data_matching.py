import pytest

from scripts.prepare_data import identifiers_agree, store_numbers


@pytest.mark.parametrize(
    "tags",
    [
        {"name": "Littlefield Express #5"},
        {"name": "Littlefield Express", "ref": "5"},
        {"name": "Littlefield Express #2", "ref": "5"},
        {"addr:state": "OK"},
        {"addr:country": "CA"},
    ],
)
def test_conflicting_identity_is_rejected(tags):
    assert not identifiers_agree({"Truckstop Name": "LITTLEFIELD EXPRESS #2", "State": "AR"}, tags)


def test_zero_padded_identifier_matches():
    assert identifiers_agree({"Truckstop Name": "PILOT #002", "State": "AR"}, {"ref": "2"})
    assert store_numbers({"name": "Pilot #002", "ref": "0002"}) == {2}


def test_highway_number_is_not_store_number():
    assert store_numbers({"name": "Pilot I-80 Travel Center"}) == set()


def test_missing_identity_allows_name_matching():
    assert identifiers_agree({"Truckstop Name": "PILOT #2", "State": "AR"}, {"name": "Pilot"})


@pytest.mark.parametrize("source", ['{"elements": []}', "{invalid json"])
def test_failed_preparation_preserves_all_outputs(tmp_path, monkeypatch, source):
    import json
    import zipfile

    from scripts import prepare_data

    monkeypatch.setattr(prepare_data, "ROOT", tmp_path)
    (tmp_path / ".cache").mkdir()
    (tmp_path / "data").mkdir()
    with zipfile.ZipFile(tmp_path / ".cache/US.zip", "w") as archive:
        archive.writestr("US.txt", "")
    (tmp_path / ".cache/osm-fuel-test.json").write_text(source)
    (tmp_path / "fuel-prices-for-be-assessment.csv").write_text("OPIS Truckstop ID,State\n")
    names = ["cities.json", "station-coordinates.json", "import-report.json"]
    for name in names:
        (tmp_path / "data" / name).write_text("previous data")
    with pytest.raises((SystemExit, json.JSONDecodeError)):
        prepare_data.main()
    assert all((tmp_path / "data" / name).read_text() == "previous data" for name in names)
