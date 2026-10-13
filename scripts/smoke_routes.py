"""Live provider smoke test; requires ORS_API_KEY and imported station data."""

import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from django.test import Client

client = Client()
summaries = []
for start, finish in [
    ("Dallas, TX", "Houston, TX"),
    ("Dallas, TX", "Los Angeles, CA"),
    ("New York, NY", "Los Angeles, CA"),
]:
    before = time.monotonic()
    response = client.post(
        "/api/v1/route-plans/",
        data=json.dumps({"start": start, "finish": finish}),
        content_type="application/json",
    )
    body = response.json()
    summary = {
        "start": start,
        "finish": finish,
        "status": response.status_code,
        "seconds": round(time.monotonic() - before, 2),
    }
    if response.status_code == 201:
        summary.update(
            {
                "distance_miles": round(body["route"]["distance_miles"], 1),
                "cost_usd": body["fuel"]["total_fuel_cost_usd"],
                "stops": len(body["fuel"]["stops"]),
                "diagnostics": body["diagnostics"],
                "map_url": body["map_url"],
            }
        )
        (
            ROOT
            / ".cache"
            / (
                "smoke-"
                + start.split(",")[0].replace(" ", "-")
                + "-"
                + finish.split(",")[0].replace(" ", "-")
                + ".json"
            )
        ).write_text(json.dumps(body))
    else:
        summary["error"] = body
    summaries.append(summary)
    print(summary, flush=True)
(ROOT / "data/smoke-results.json").write_text(json.dumps(summaries, indent=2))
