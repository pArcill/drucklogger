# nginx_frontend Explainer

This note focuses specifically on the `src/nginx_frontend` subtree: why every file exists, how assets are served by Nginx, and what the accompanying Vitest specs guarantee.

## Runtime responsibilities

- **Static delivery**: `index.html`, `styles/`, and `scripts/` are copied into `/usr/share/nginx/html` during container startup (see `docker-compose.yml`). Nginx handles routing, while the HTML page bootstraps all UI logic.
- **Mock-by-default data**: The inline script inside `index.html` sets `window.__PRESSURE_USE_MOCK__ = true`, so the dashboard reads from the mock API module until the backend exposes stable endpoints. Toggle it to `false` to hit the FastAPI service via `/api/...`.
- **Leaflet map**: `scripts/app.js` initializes a Leaflet layer, adds sensor markers, and binds popups describing the latest measurements.
- **Live update simulation**: `scripts/mockApi.js` emits deterministic measurement frames so the interface behaves as if MQTT/WebSocket data is flowing, even when only static hosting is available.

## Directory cheat sheet

| Path | What it does |
|------|--------------|
| `index.html` | Semantic layout (hero, stats, map, fleet grid, timeline) plus configuration flags for API base URLs. |
| `styles/main.css` | Defines the typography, color tokens, responsive grids, utility chips, and empty states. |
| `scripts/app.js` | Wires the UI: fetches data (mock or real), renders cards/timeline/map, controls live polling, and updates status badges. |
| `scripts/mockApi.js` | Generates three virtual sensors and rolls synthetic measurements forward so designers can preview the experience offline. |
| `scripts/analytics.js` | Pure helper library that normalizes measurements, computes stats, decorates sensors, and formats values for display. |
| `tests/analytics.test.js` | Vitest suite that locks down the math and data-massaging helpers (detailed below). |
| `package.json` + `vitest.config.js` | Provide the test runner configuration (`vitest run`). |

## Test coverage guide

Every assertion lives in `tests/analytics.test.js` and targets one helper at a time. The following table describes each spec and how it protects the UI logic:

| Describe block / test name | Purpose |
|----------------------------|---------|
| `calculatePressureStats` · `derives range, average, and latest entries` | Ensures the stats card shows accurate min/max/latest/average totals when valid data arrives. |
| `calculatePressureStats` · `handles empty arrays gracefully` | Confirms empty dashboards render placeholders (no NaN) when backends return no measurements. |
| `limitMeasurements` · `returns chronologically sorted slices` | Guarantees the timeline remains chronological even when the backend sends unsorted or over-long payloads. |
| `decorateSensorsWithMeasurements` · `matches sensors with their most recent measurement` | Verifies the fleet grid displays the freshest pressure and online status per sensor. |
| `decorateSensorsWithMeasurements` · `marks sensors as offline when stale` | Confirms stale sensors are labeled offline once their last-seen timestamp exceeds the threshold. |
| `isSensorOnline` · `honors the threshold override` | Tests that health logic respects custom timeouts so operators can tighten or relax the freshness window. |
| `mergeMeasurements` · `deduplicates entries with matching ids` | Protects against duplicate items when realtime pushes overlap with poll responses, keeping charts/timelines clean. |

## How to run the tests

```bash
cd src/nginx_frontend
npm install
npm test
```

Vitest outputs which helper block fails, so regressions in math or sensor status logic are quick to diagnose before touching the UI. Add new specs whenever `scripts/analytics.js` gains a helper or when UI states depend on fresh calculations.
