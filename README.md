# IoT Pressure Logger

IoT Pressure Logger is a Docker-based system that simulates pressure sensors, publishes telemetry over MQTT, stores measurements in PostgreSQL, exposes data through FastAPI, and serves a dashboard through Nginx.

## Components

- `postgres_database`: PostgreSQL persistence for sensors and measurements
- `mqtt_broker`: Eclipse Mosquitto broker for sensor status and measurement topics
- `sensor_simulator`: Python simulator that publishes sensor status and pressure data
- `fastapi_backend`: FastAPI application that subscribes to MQTT and exposes HTTP/WebSocket endpoints
- `nginx_frontend`: Static dashboard served by Nginx with Leaflet-based map visualization

## Quick Start

1. Create a local environment file.

	PowerShell:
	```powershell
	Copy-Item .env.example .env
	```

	Bash:
	```bash
	cp .env.example .env
	```

2. Adjust values in `.env` if you want different ports or credentials.

3. Start the stack.

	```bash
	docker compose up -d --build
	```

4. Open the services.

- Frontend: `http://localhost:80`
- Backend API docs: `http://localhost:8000/docs`
- Backend health endpoint: `http://localhost:8000/health`
- MQTT TCP broker: `localhost:1883`

If you change the port variables in `.env`, use those values instead of the defaults above.

## Data Flow

1. `sensor_simulator` publishes JSON messages to `sensors/status` and `measurement/data`.
2. `mqtt_broker` forwards those MQTT messages.
3. `fastapi_backend` subscribes to both topics, parses the payloads, and writes them into PostgreSQL.
4. `nginx_frontend` serves the dashboard to the browser.
5. The browser fetches sensor and measurement data from the FastAPI API.

## Repository Documentation

- [docs/system-manual.md](docs/system-manual.md)
- [docs/uml-class-diagram.md](docs/uml-class-diagram.md)
- [docs/uml-deployment-diagram.md](docs/uml-deployment-diagram.md)
- [docs/uml-sequence-diagram.md](docs/uml-sequence-diagram.md)

## Main API Endpoints

- `GET /`
- `GET /health`
- `GET /api/sensors`
- `GET /api/measurements`
- `GET /ws`

## Notes

- The MQTT broker is configured with anonymous access in `mosquitto.conf`. This is suitable for development only.
- Container ports are driven by `.env.example` and referenced in `docker-compose.yml`.
- The frontend currently supports mock mode and real API mode.