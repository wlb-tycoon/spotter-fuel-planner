"""Measure cold and warm end-to-end requests against the real routing provider."""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.core.cache import cache  # noqa: E402
from django.test import Client  # noqa: E402

cache.clear()
client = Client()
results = []
for mode in ("cold", "warm"):
    started = time.perf_counter()
    response = client.post(
        "/api/v1/route-plans/",
        data=json.dumps({"start": "Dallas, TX", "finish": "Los Angeles, CA"}),
        content_type="application/json",
    )
    data = response.json()
    result = {
        "mode": mode,
        "status": response.status_code,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
    }
    if response.status_code != 201:
        raise SystemExit(data)
    result.update(data["diagnostics"])
    results.append(result)
    print(result, flush=True)
assert results[1]["external_routing_calls"] == 0
(ROOT / "data/benchmark-results.json").write_text(json.dumps(results, indent=2))
