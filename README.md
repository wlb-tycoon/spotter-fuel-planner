# Spotter fuel route planner

Django API and interactive map for US driving trips. Uses the supplied fuel-price CSV, a 50-gallon tank, 500-mile maximum range, and 10 US MPG. Built by Jeff Lingad for the Spotter backend assessment.

## Run locally

Python 3.12+ is required. On Debian/Ubuntu, install `python3-venv` if virtual-environment creation reports that ensurepip is missing.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-lock.txt
cp .env.example .env
# Set ORS_API_KEY in .env using your free openrouteservice account.
python manage.py migrate
python manage.py import_stations
python manage.py runserver
```

Open http://127.0.0.1:8000/ or import `docs/Spotter.postman_collection.json` into Postman. Never commit `.env`. Prepared coordinate and city data are included; no bulk geocoding is needed to start the app.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/route-plans/ \
  -H 'Content-Type: application/json' \
  -d '{"start":"Dallas, TX","finish":"Los Angeles, CA","initial_fuel_gallons":50}'
```

Locations accept `City, ST` strings or `{"latitude":32.7767,"longitude":-96.797}`. City/state lookup is local and deterministic; arbitrary street addresses are not supported. Starting fuel defaults to 50 gallons and must be 0–50. Coordinates are checked against a US boundary with a small tolerance for coastline generalization. Non-contiguous US endpoints are accepted, but a provider route or usable station coverage may not exist.

## Response

`POST /api/v1/route-plans/` returns HTTP 201 with:

- `id`, `start`, `finish`, and `map_url`.
- `route`: GeoJSON geometry, miles, duration, and leg distances.
- `fuel`: ordered purchases, gallons consumed/purchased/remaining, and `total_fuel_cost_usd`.
- `vehicle`, `assumptions`, `warnings`, and performance/call-count `diagnostics`.

`GET /api/v1/health/` returns the imported station count. `GET /maps/<id>/` renders a saved route. JSON errors use `{"error":{"code":"...","message":"..."}}` with 400 for input validation, 415 for content type, 422 for infeasible routes, and 502/503 for provider failures. Missing maps return 404.

## Algorithm and cost accounting

The optimizer minimizes purchases for a **fixed ordered path** with continuous fuel quantities, no stop fee, and constant MPG. At each station, buy enough to reach the next cheaper station within range; if none exists, buy up to tank capacity or the fuel needed to finish. A monotonic stack finds next-cheaper stations in O(n) after sorting. Equal-price purchases are deferred when the next stop remains reachable, avoiding redundant top-ups and excessive route waypoints. Existing fuel is carried forward. Fuel never exceeds 50 gallons and an unreachable leg produces an error.

A full initial tank is assumed because the assignment does not specify starting fuel. **Total cost is money purchased during the trip, excluding the cost of pre-existing fuel.** A trip under 500 miles may therefore cost $0 in new purchases while still consuming fuel. Cost is computed using Decimal. Displayed station purchases are rounded to cents, and the total equals the sum of those displayed charges.

The station-selection step is approximate: eligible POIs within a 3-mile corridor are projected onto the initial route. Purchases are selected using these distances, then a second directions request routes through the selected station coordinates. Purchases and feasibility are recomputed using the returned road distances. If an actual leg is infeasible, the API returns 422; it does not silently return an impossible plan or exhaust the provider budget searching alternatives. Visited waypoints can remain on the final route even when recomputation removes their purchase.

This is **not a proof of minimum cost over all possible road routes or station subsets**. Final purchases are optimized for the selected path; station selection, POI entrances, routing snaps, partial coverage, and road detours limit the claim. The routing profile is `driving-car`; commercial truck restrictions are outside the assessment model.

## Data preparation and provenance

The source CSV has 8,151 observations and 6,738 distinct IDs. It has no coordinates and includes Canadian stations. US records are retained. Original CSV rows are preserved, and prices are the median of observations for an ID: there are no timestamps or fuel-grade labels to justify choosing a latest observation. Prices are assumed USD per US gallon.

`data/station-coordinates.json` contains matched OSM fuel POIs and official Pilot/Flying J locations with source URLs and match reasons. Exact official store-number/state matches take precedence over OSM name matches. GeoNames city coordinates narrow candidate searches; **they are never used as station coordinates**. Matching uses store numbers, distinctive names, or an unambiguous brand near the listed city. These are automated matches, not a guarantee of manual verification. Explicit store-number, state, and country conflicts are rejected before fuzzy matching. Unresolved/ambiguous records are excluded. See `data/import-report.json` for coverage and exclusions.

Rebuild sources only when necessary:

```bash
python scripts/download_station_sources.py
python scripts/download_pilot_locations.py
python scripts/prepare_data.py
python manage.py import_stations
```

Overpass availability is variable; cached source downloads are ignored by Git. Enrichment is offline and independent of route requests. Prepared data changes require restarting the app to refresh in-memory city data.

Data attribution and licensing:

- Fuel prices: supplied assessment CSV; no claim of live pricing or a redistribution license beyond the assessment.
- Station coordinates: © OpenStreetMap contributors, ODbL; https://www.openstreetmap.org/copyright. The derived coordinate database is provided under ODbL. Original OSM element URLs are included.
- Pilot/Flying J coordinates: official public locator and Download All Locations data, https://locations.pilotflyingj.com/search. Only matching location coordinates are retained; supplied CSV prices remain authoritative.
- City gazetteer: GeoNames, CC BY 4.0; https://www.geonames.org/ and https://download.geonames.org/export/dump/.
- US boundary: Natural Earth public-domain map data; https://www.naturalearthdata.com/.
- Routing: openrouteservice / HeiGIT, based on OpenStreetMap.
- Map display: Leaflet and attributed OSM tiles. Browser tile requests are separate from backend routing requests.

## Performance and call budget

A new route normally makes **one routing call**, or **two with fuel stops**. Endpoint resolution and station lookup make no network requests. Routing responses are cached in-process for one hour; repeat routes reuse them. A bounded timeout is used and no automatic network retries are made. Free account quotas still apply.

Station latitude/longitude indexes narrow the candidate set before geometric filtering. SQLite keeps setup simple for the assessment; PostgreSQL/PostGIS and shared caching are natural extensions for multiple workers. Maps are saved in SQLite. The assessment app has no authentication or rate limiting and should not be exposed as a public production service without those controls. Provider secrets remain server-side.

## Included data coverage and live examples

The prepared snapshot contains **1,376 of 6,626 US station IDs (20.8%)**, including **594 exact official Pilot/Flying J store-number/state matches**. The remaining matches use OSM store numbers, distinctive names, or an unambiguous nearby brand. All 5,250 unresolved US IDs are listed in the import report; the app does not invent coordinates or promise coverage for every US route. This partial dataset is a material limitation of the submission.

Live checks with a full starting tank:

| Trip | Routed miles | Fuel purchases | Stops | Routing calls |
|---|---:|---:|---:|---:|
| Dallas → Houston | 240.2 | $0.00 | 0 | 1 |
| Dallas → Los Angeles | 1,446.1 | $295.64 | 5 | 2 |
| New York → Los Angeles | 2,810.9 | $770.20 | 12 | 2 |

These are observed outputs, not guarantees; provider routes can change. The cost excludes pre-existing fuel. See `data/smoke-results.json` and `data/benchmark-results.json` for measured results.

## Verification

```bash
python manage.py check
pytest -q
python scripts/smoke_routes.py  # optional live calls; requires key and imported data
```

Tests include fuel conservation, range limits, cost decisions, 100 randomized comparisons to an independent dynamic-programming oracle, provider errors/cache behavior, input validation, map responses, and revalidation with actual road legs. `data/smoke-results.json` records the latest live run when present.

See `docs/DEMO.md` for the five-minute Loom outline. Submit GitHub and Loom links through Ena's questions. A deployed site is not required by the email.
