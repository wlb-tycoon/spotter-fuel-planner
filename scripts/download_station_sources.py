"""One-time public source download; never called by the route API.
Uses small resumable bounding-box queries to avoid nationwide Overpass timeouts.
"""

import argparse
import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
CACHE.mkdir(exist_ok=True)


def tile(bounds):
    south, west, north, east = bounds
    name = f"{south}_{west}_{north}_{east}"
    out = CACHE / f"osm-fuel-{name}.json"
    if out.exists():
        return
    q = f"[out:json][timeout:45];nwr[amenity=fuel]({south},{west},{north},{east});out center tags;"
    for host in [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    ]:
        try:
            req = urllib.request.Request(
                host,
                data=urllib.parse.urlencode({"data": q}).encode(),
                headers={"User-Agent": "SpotterAssessment/1.0 (offline station enrichment)"},
            )
            with urllib.request.urlopen(req, timeout=65) as response:
                data = json.load(response)
            if data.get("remark"):
                raise RuntimeError(data["remark"])
            out.write_text(json.dumps(data))
            print(name, len(data["elements"]), flush=True)
            return
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise SystemExit(
                    "Overpass rate limited the download. Retain cache and retry later."
                ) from e
            print(name, type(e).__name__, str(e), flush=True)
        except (OSError, ValueError, RuntimeError) as e:
            print(name, type(e).__name__, str(e), flush=True)
    print("FAILED", name, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--regional",
        action="store_true",
        help="Also fetch all fuel POIs in regional batches (slower).",
    )
    options = parser.parse_args()
    output = CACHE / "osm-fuel-exact-brands.json"
    if not output.exists():
        brands = [
            "Love's",
            "Love's Travel Stops",
            "Pilot",
            "Flying J",
            "TA",
            "Petro",
            "Kwik Trip",
            "Kwik Star",
            "Sapp Bros.",
            "TravelCenters of America",
            "Road Ranger",
        ]
        query = (
            "[out:json][timeout:90];("
            + "".join(
                'nwr["amenity"="fuel"]["brand"=' + json.dumps(brand) + "];" for brand in brands
            )
            + ");out center tags;"
        )
        request = urllib.request.Request(
            "https://overpass-api.de/api/interpreter",
            data=urllib.parse.urlencode({"data": query}).encode(),
            headers={"User-Agent": "SpotterAssessment/1.0"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.load(response)
        if data.get("remark"):
            raise RuntimeError(data["remark"])
        output.write_text(json.dumps(data))
        print("Major-chain POIs:", len(data["elements"]))
    if options.regional:
        boxes = [
            (south, west, min(south + 5, 49.4), min(west + 10, -66))
            for south in [25, 30, 35, 40, 45]
            for west in [-125, -115, -105, -95, -85, -75]
        ]
        for bounds in boxes:
            tile(bounds)
    p = CACHE / "US.zip"
    if not p.exists():
        tmp = p.with_suffix(".download")
        urllib.request.urlretrieve("https://download.geonames.org/export/dump/US.zip", tmp)
        tmp.replace(p)
    boundary = ROOT / "data/us-boundary.geojson"
    if not boundary.exists():
        data = json.load(
            urllib.request.urlopen(
                "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson",
                timeout=60,
            )
        )
        boundary.write_text(
            json.dumps(next(x for x in data["features"] if x["properties"].get("ADM0_A3") == "USA"))
        )


if __name__ == "__main__":
    main()
