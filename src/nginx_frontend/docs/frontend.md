# Frontend Implementation Guide

## Overview
The `src/nginx_frontend` directory hosts the pressure dashboard that Nginx serves inside its container. The UI is intentionally API-agnostic: it hydrates from a mock data source today and can switch to the FastAPI backend without structural changes. The layout emphasizes three pillars:

1. **Operational awareness** – hero, stat cards, and badges surface the current fleet state.
2. **Spatial context** – Leaflet renders markers for each sensor.
3. **Temporal insight** – a rolling measurement timeline mirrors the expected API payloads.

## File map

| Path | Purpose |
|------|---------|
| `index.html` | Semantic layout plus configuration knobs (`__PRESSURE_API_BASE__`, `__PRESSURE_USE_MOCK__`). |
| `styles/main.css` | Visual system (Space Grotesk, warm gradients, responsive grids). |
| `scripts/app.js` | DOM orchestration, map rendering, mock/real data glue. |
| `scripts/mockApi.js` | Deterministic mock sensors + realtime simulation used until the backend is ready. |
| `scripts/analytics.js` | Pure helpers that calculate stats (unit-tested with Vitest). |
| `tests/analytics.test.js` | Covers the analytics helpers to guarantee deterministic math. |
| `package.json` | Test runner configuration (`vitest`). |

## Mock vs. real data

- Mock mode is enabled by default via `window.__PRESSURE_USE_MOCK__ = true` (see the inline script in `index.html`).
- Once the FastAPI endpoints are stable, set `__PRESSURE_USE_MOCK__ = false` or remove the override entirely.
- The frontend expects:
  - `GET /api/sensors` → array with `id`, `mac`, `latitude`, `longitude`, `battery`, `last_seen`.
  - `GET /api/measurements?limit=240` → array of `{id, mac, pressure, timestamp}`.
  - Optional websocket at `/ws/measurements` that emits either individual measurements or batched arrays.
- If realtime transport differs (e.g., MQTT over WebSockets, SSE), adapt `createHttpApi()` inside `scripts/app.js` but retain the same handler signature (`Array<Measurement>`).

## Testing workflow

1. `cd src/nginx_frontend`
2. `npm install`
3. `npm test`

The Vitest suite focuses on data-layer invariants (statistics, sorting, deduplication, sensor health rules). Extend the suite whenever analytics helpers change or new UI states depend on deterministic math.

## Maintaining the UI

- **Design tokens** live in `:root` inside `styles/main.css`. Update those variables rather than scattering new hex values.
- **Map interactions**: markers come from `decorateSensorsWithMeasurements`. When adding sensor properties (e.g., altitude), enrich that helper first.
- **Accessibility**: every panel declares `aria-label`s and announcements (`aria-live`). Preserve them when restructuring.
- **Performance**: the dashboard avoids frameworks, so keep JavaScript modular and idempotent. Prefer pure helpers in `analytics.js` for anything testable.
- **Docker image**: the Nginx container only needs the static assets. During image build copy `index.html`, `styles`, `scripts`, and `tests` (tests may be skipped for the runtime image, but keep them in the repo).

## Future contributors checklist

- [ ] Update `mockApi.js` whenever the backend schema changes so designers can still prototype.
- [ ] Expand Vitest coverage for each new analytics helper or rendering branch.
- [ ] Document new controls/shortcuts directly in this file to keep onboarding quick.
- [ ] Run `npm test` before opening a PR; attach screenshots of the refreshed UI when styles change.
- [ ] Coordinate with the backend team before flipping `__PRESSURE_USE_MOCK__` to ensure CORS and auth headers are aligned.
