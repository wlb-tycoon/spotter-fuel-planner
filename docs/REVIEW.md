# Assessment code review

The review checked the API, provider adapter, fuel optimizer, route geometry, station matching/import, scripts, templates, and submission documentation against the assessment email.

## Corrections

- Reject malformed route geometry, nonfinite/negative measurements, inconsistent leg totals, and unexpected leg counts before caching provider results. Use the sum of validated leg distances for fuel accounting.
- Return JSON errors for oversized bodies, parser recursion failures, and coordinate numeric overflow.
- Validate complete station imports before modifying the database. Empty mappings, missing station IDs, invalid prices/coordinates, and conflicting states preserve existing data.
- Reject explicit store-number/state/country conflicts during coordinate matching. Removed two incorrect station matches; the rebuilt snapshot contains 1,376 stations, including 594 official store-number/state matches.
- Finish preparation before replacing prepared data files; failed or empty preparations preserve existing outputs.
- Defer equal-price purchases when the next stop is safely reachable. This avoids excessive small top-ups and unnecessary routing waypoints without changing the fixed-path fuel objective.
- Make live smoke checks usable on a fresh checkout and exit unsuccessfully when a request fails. Keep end-to-end benchmark timing distinct from internal planning time.

## Verification evidence

| Area | Evidence |
|---|---|
| Fuel optimality and range | Reference dynamic-programming solver comparisons, capacity/conservation tests, exact-range and unreachable cases, equal-price consolidation regression |
| Input/provider failures | Malformed JSON, oversized requests, numeric overflow, malformed geometry, invalid distances, timeout, authentication/quota failures, cache tests |
| Data handling | Import idempotency and precision, preservation on invalid imports/preparation, identity-conflict regressions; real snapshot reimport succeeded |
| Geometry and map output | Curved/degenerate geometry tests, actual waypoint-distance revalidation, map rendering and script-injection escaping tests; unchanged Leaflet UI was previously verified in-browser |
| Call budget and performance | Live smoke records in `data/smoke-results.json`; cold/warm measurements in `data/benchmark-results.json` |
| Build and schema | 71 passing tests; Ruff checks; Django system checks; no missing migrations; clean diff whitespace check |
| Submission consistency | README coverage and example results updated; Postman collection and Loom outline checked against the API |

The three live routes passed after the corrections. The two long routes used two provider calls each; the repeated benchmark used none.

## Remaining documented limitations

The available snapshot covers 1,376 of 6,626 US station IDs. Matching outside official store-number records remains heuristic. Candidate selection uses an approximate corridor; the optimizer is exact for a fixed ordered path, not every possible road route or station subset. A selected path that fails actual-road range validation returns 422. Prices are a supplied snapshot, conflicting observations use a median, starting fuel defaults to a full tank, and initial fuel cost is excluded. The standard driving profile does not model commercial truck restrictions. The local assessment server is not a hardened public production deployment.

These limitations remain explicit in the README and API. Passing checks support the reviewed behavior; they do not prove that no undiscovered defect exists.
