"""Match supplied stations to OSM POIs. City coordinates only narrow the search;
only actual OSM fuel POI coordinates are exported as station locations."""

import collections
import csv
import difflib
import json
import math
import pathlib
import re
import unicodedata
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATES = set(
    [
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
        "DC",
    ]
)


def norm(s):
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower(),
    ).strip()


def brand(s):
    s = norm(s)
    for words, name in [
        ("flying j", "flyingj"),
        ("pilot", "pilot"),
        ("love", "loves"),
        ("loves", "loves"),
        ("petro", "petro"),
        ("travelcenters", "ta"),
        ("ta ", "ta"),
        ("circle k", "circlek"),
        ("kwik trip", "kwiktrip"),
        ("kwik star", "kwikstar"),
        ("speedway", "speedway"),
        ("casey", "caseys"),
        ("caseys", "caseys"),
        ("quiktrip", "quiktrip"),
        ("sapp", "sapp"),
        ("ambest", "ambest"),
    ]:
        if re.search(r"\b" + re.escape(words.strip()) + r"\b", s):
            return name
    return None


def main():
    if (
        not list((ROOT / ".cache").glob("osm-fuel-*.json"))
        and not (ROOT / ".cache/pilot-locations.json").exists()
    ):
        raise SystemExit(
            "No downloaded station sources. Existing prepared data was left unchanged."
        )
    cities = {}
    with zipfile.ZipFile(ROOT / ".cache/US.zip") as z:
        for raw in z.open("US.txt"):
            x = raw.decode().rstrip("\n").split("\t")
            if len(x) < 19 or x[6] != "P" or x[7].endswith("H") or x[10] not in STATES:
                continue
            record = [float(x[5]), float(x[4]), int(x[14] or 0)]
            for n in {x[1], x[2], *x[3].split(",")}:
                if n:
                    key = f"{norm(n)}, {x[10].lower()}"
                    if key not in cities or cities[key][2] < record[2]:
                        cities[key] = record
    (ROOT / "data/cities.json").write_text(
        json.dumps(cities, sort_keys=True, separators=(",", ":"))
    )
    elements = {}
    for path in (ROOT / ".cache").glob("osm-fuel-*.json"):
        for e in json.loads(path.read_text()).get("elements", []):
            elements[(e["type"], e["id"])] = e
    grid = collections.defaultdict(list)
    for e in elements.values():
        t = e.get("tags", {})
        p = e.get("center", e)
        if "lon" not in p:
            continue
        e["lon"], e["lat"] = p["lon"], p["lat"]
        e["label"] = " ".join(t.get(k, "") for k in ["name", "brand", "operator"])
        e["brand"] = brand(e["label"])
        grid[(int(e["lon"] * 4), int(e["lat"] * 4))].append(e)
    groups = collections.defaultdict(list)
    with (ROOT / "fuel-prices-for-be-assessment.csv").open(newline="") as f:
        for r in csv.DictReader(f):
            groups[r["OPIS Truckstop ID"]].append(r)
    matches = {}
    unmatched = []
    eligible = 0
    for key, rows in groups.items():
        r = rows[0]
        if r["State"] not in STATES:
            continue
        eligible += 1
        city = cities.get(f"{norm(r['City'])}, {r['State'].lower()}")
        if not city:
            unmatched.append({"station_id": key, "reason": "city_not_resolved"})
            continue
        lon, lat = city[:2]
        near = []
        b = brand(r["Truckstop Name"])
        num = re.search(r"#\s*(\d+)", r["Truckstop Name"])
        for gx in range(int(lon * 4) - 2, int(lon * 4) + 3):
            for gy in range(int(lat * 4) - 2, int(lat * 4) + 3):
                for e in grid[(gx, gy)]:
                    dist = math.hypot(
                        (e["lon"] - lon) * 69 * math.cos(math.radians(lat)),
                        (e["lat"] - lat) * 69,
                    )
                    if dist > 18:
                        continue
                    t = e["tags"]
                    score = 0
                    reason = ""
                    names = [norm(t.get("name", "")), norm(t.get("brand", ""))]
                    target = norm(re.sub(r"#\s*\d+", "", r["Truckstop Name"]))
                    sim = max(
                        (difflib.SequenceMatcher(None, target, n).ratio() for n in names if n),
                        default=0,
                    )
                    if b and b == e["brand"]:
                        if num and (
                            num.group(1) == t.get("ref")
                            or re.search(
                                r"(?:#|\b)0*" + re.escape(num.group(1)) + r"\b",
                                t.get("name", ""),
                            )
                        ):
                            score = 100
                            reason = "brand_and_store_number"
                        elif dist < 6 or norm(t.get("addr:city", "")) == norm(r["City"]):
                            score = 70
                            reason = "unique_brand_near_city"
                    if sim >= 0.88 and dist < 10 and score < 85:
                        score = 85
                        reason = "distinctive_name_near_city"
                    if score:
                        near.append((score, dist, e, reason))
        near.sort(key=lambda x: (-x[0], x[1]))
        # Deduplicate node/way representations of the same POI within 150 m.
        unique = []
        for item in near:
            if not any(
                math.hypot(
                    (item[2]["lon"] - v[2]["lon"]) * 55,
                    (item[2]["lat"] - v[2]["lat"]) * 69,
                )
                < 0.1
                for v in unique
            ):
                unique.append(item)
        if not unique or (len(unique) > 1 and unique[0][0] == unique[1][0]):
            unmatched.append({"station_id": key, "reason": "ambiguous_or_no_match"})
            continue
        score, dist, e, reason = unique[0]
        matches[key] = {
            "longitude": e["lon"],
            "latitude": e["lat"],
            "source": f"https://www.openstreetmap.org/{e['type']}/{e['id']}",
            "confidence": reason,
        }
    # Prefer an exact chain store-number + state match from the official locator.
    pilot_path = ROOT / ".cache/pilot-locations.json"
    if pilot_path.exists():
        official = {}
        for entity in json.loads(pilot_path.read_text()):
            profile = entity["profile"]
            number = str(profile.get("c_externalStoreNumber", "")).lstrip("0")
            address = profile.get("address", {})
            if address.get("countryCode") == "US":
                official[(number, address.get("region"))] = profile
        for key, rows in groups.items():
            row = rows[0]
            if brand(row["Truckstop Name"]) not in {"pilot", "flyingj"}:
                continue
            number = re.search(r"#\s*(\d+)", row["Truckstop Name"])
            if not number:
                continue
            profile = official.get((number.group(1).lstrip("0"), row["State"]))
            if not profile:
                continue
            coordinate = profile.get("routableCoordinate") or profile.get("yextDisplayCoordinate")
            if not coordinate:
                continue
            city = cities.get(f"{norm(row['City'])}, {row['State'].lower()}")
            if (
                city
                and math.hypot(
                    (coordinate["long"] - city[0]) * 55, (coordinate["lat"] - city[1]) * 69
                )
                > 25
            ):
                continue
            matches[key] = {
                "longitude": coordinate["long"],
                "latitude": coordinate["lat"],
                "source": profile["c_pagesURL"],
                "confidence": "official_store_number_state",
            }
        unmatched = [row for row in unmatched if row["station_id"] not in matches]
    (ROOT / "data/station-coordinates.json").write_text(
        json.dumps(matches, indent=2, sort_keys=True)
    )
    report = {
        "csv_rows": sum(map(len, groups.values())),
        "unique_ids": len(groups),
        "eligible_us_ids": eligible,
        "matched_stations": len(matches),
        "unmatched_us_stations": len(unmatched),
        "osm_pois": len(elements),
        "price_policy": "Median of all source observations per station ID",
        "match_methods": dict(collections.Counter(x["confidence"] for x in matches.values())),
        "unmatched": unmatched,
    }
    (ROOT / "data/import-report.json").write_text(json.dumps(report, indent=2))
    print({k: v for k, v in report.items() if k != "unmatched"})


if __name__ == "__main__":
    main()
