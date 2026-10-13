# Five-minute Loom walkthrough

Before recording, start the server, import the Postman collection, and verify the live long-route request succeeds. Keep `.env` closed. Use the actual results rather than promising a particular price or stop count.

- **0:00–0:25** — Introduce yourself: Jeff Lingad. Explain the route/fuel API and the 500-mile, 10-MPG assumptions.
- **0:25–1:00** — Send Dallas → Houston in Postman. Explain that a full initial tank means no purchase for this short trip; gallons consumed remain visible.
- **1:00–2:00** — Send Dallas → Los Angeles. Show route miles, stops, gallons bought, purchase cost, and external-call diagnostics. Open `map_url` in the browser and inspect station markers.
- **2:00–2:25** — Repeat the same route to demonstrate cache hits. Send an invalid starting fuel value to demonstrate validation.
- **2:25–3:35** — Explain `service.py` orchestration, `optimizer.py` next-cheaper-station algorithm, and `routing.py` bounded provider calls/cache. Explain fixed-route optimality and the approximate candidate selection.
- **3:35–4:15** — Show CSV import and coordinate coverage report. Explain median conflicting prices, local city lookup, and unmatched station exclusions.
- **4:15–4:45** — Run tests. Highlight the independent reference solver and actual waypoint-distance verification.
- **4:45–5:00** — Show README setup and GitHub link. Conclude with limitations: static prices, partial matched coverage, and standard driving profile.

Submit the repository URL and Loom URL through Ena's two questions. Check both links from an incognito browser or ensure the recruiter has repository access.
