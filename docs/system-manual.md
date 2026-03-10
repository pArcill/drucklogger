# System Manual

## Purpose

This guide explains how to start the IoT Pressure Logger system with Docker Compose and verify that the main services are running.

## Prerequisites

- Docker Desktop or Docker Engine with Docker Compose support
- A local copy of this repository

## Environment Setup

1. Create `.env` from the example file.

   PowerShell:
   ```powershell
   Copy-Item .env.example .env
   ```

   Bash:
   ```bash
   cp .env.example .env
   ```

2. Review the values in `.env`.

Important variables:

- `API_PORT`: external FastAPI port, default `8000`
- `NGINX_PORT`: external frontend port, default `80`
- `POSTGRES_PORT`: external PostgreSQL port, default `5432`
- `MQTT_TCP_PORT`: external MQTT port, default `1883`
- `MQTT_WS_PORT`: external MQTT WebSocket port, default `9001`

## Start The System

Run the stack from the repository root:

```bash
docker compose up -d --build
```

This starts:

- `postgres_database`
- `mqtt_broker`
- `sensor_simulator`
- `fastapi_backend`
- `nginx_frontend`

## Check Service Status

```bash
docker compose ps
```

To inspect logs:

```bash
docker compose logs -f fastapi_backend
docker compose logs -f sensor_simulator
docker compose logs -f mqtt_broker
```

## Access The Application

- Frontend dashboard: `http://localhost:80`
- FastAPI Swagger UI: `http://localhost:8000/docs`
- FastAPI health check: `http://localhost:8000/health`

If you changed the values in `.env`, replace the ports above with your configured values.

## Stop The System

```bash
docker compose down
```

To also remove named volumes:

```bash
docker compose down -v
```

## Troubleshooting

- If the backend cannot connect to PostgreSQL, check that `postgres_database` is healthy with `docker compose ps`.
- If no live data appears, inspect `sensor_simulator` and `mqtt_broker` logs.
- If the frontend loads but shows no data, check the browser network tab and confirm `fastapi_backend` is reachable on `API_PORT`.
- MQTT anonymous access is enabled in `mosquitto.conf`; keep that configuration for development only.