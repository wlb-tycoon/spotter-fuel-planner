"""Download the same public records offered by Pilot's Download All Locations.
The official locator requests its search URL with Accept: application/json.
Only use these records to locate matching CSV store IDs, never to replace prices.
"""

import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"


def main():
    CACHE.mkdir(exist_ok=True)
    rows = []
    for offset in range(0, 5000, 50):
        path = CACHE / f"pilot-page-{offset}.json"
        if path.exists():
            response = json.loads(path.read_text())
        else:
            request = urllib.request.Request(
                f"https://locations.pilotflyingj.com/search?per=50&offset={offset}",
                headers={"Accept": "application/json", "User-Agent": "SpotterAssessment/1.0"},
            )
            with urllib.request.urlopen(request, timeout=60) as connection:
                response = json.load(connection)
            path.write_text(json.dumps(response))
            time.sleep(1)
        entities = response["response"]["entities"]
        rows.extend(entities)
        print(f"{len(rows)}/{response['response']['count']}", flush=True)
        if len(rows) >= response["response"]["count"] or not entities:
            break
    (CACHE / "pilot-locations.json").write_text(json.dumps(rows))


if __name__ == "__main__":
    main()
