# IoT Pressure Logger Project

## 1. Project Overview

You are tasked with building a complete "IoT Pressure Logger" system from scratch.
The system will simulate distributed sensors that measure atmospheric pressure, collect this data via a messaging system, store it in a database, and present it via a Web Dashboard.

**Technology Stack:**

- **Language**: Python 3.14+
- **Containerization**: Docker & Docker Compose
- **Messaging**: MQTT (Eclipse Mosquitto)
- **Database**: PostgreSQL (with SQLAlchemy/SQLModel)
- **Web Framework**: FastAPI (Backend API)
- **Frontend**: Nginx (serving HTML, CSS, JavaScript)

## 2. Architecture & Containers

You must construct a `docker-compose.yml` environment containing the following five services. You are responsible for configuring their networking and dependencies.

| Service | Container Name | Responsibilities |
|---------|---------------|------------------|
| **Database** | `postgres_database` | Stores sensor metadata, measurements, and logs. Persistent storage via volumes. |
| **Message Broker** | `mqtt_broker` | Acts as the central hub for MQTT messages. Handles topics for sensor status and data. |
| **Simulator** | `sensor_simulator` | A Python service that simulates hardware sensors. It connects to the broker and "publishes" mock data. |
| **Backend** | `fastapi_backend` | The core application. It "subscribes" to the broker to save data and provides a HTTP REST API. |
| **Frontend** | `nginx_frontend` | A web server container (e.g., Nginx) that serves the Dashboard (HTML/JS) to the user. |

### Data Flow

1. **Simulator** -> publishes JSON -> **MQTT Broker** (`sensors/status`, `measurement/data`)
2. **Backend** -> subscribes -> **MQTT Broker**
3. **Backend** -> writes -> **Database**
4. **User** -> requests (HTTP) -> **Frontend** (loads Web App)
5. **Web App (Browser)** -> API Fetch -> **Backend** -> reads -> **Database**

## 3. Work Steps & Detailed Requirements

**Important (process requirement):** Documentation, testing, and logging are not “final steps”. You must work on them continuously while implementing Steps 2–6 (update diagrams when architecture changes, add tests when adding logic/endpoints, and add logging while you code so you can debug inside Docker).

### Step 0: Project Conventions (Required Best Practices)

*Goal: Build the project like a real-world service.*

1. **Configuration via `.env` (Docker Compose)**:
    - Put all configurable values in a `.env` file: DB user/password, ports, broker host/port, log level, etc.
    - Commit a `.env.example` (safe defaults, no secrets) and add `.env` to `.gitignore`.
    - Use `${VARIABLE}` placeholders in `docker-compose.yml` instead of hard-coded values.

2. **Secrets & security basics**:
    - Never commit credentials or API keys.
    - If MQTT is configured with anonymous access for development, clearly document this and keep it **dev-only**.

3. **Docker reliability**:
    - Prefer pinned image tags (avoid `:latest` for reproducibility).
    - Use named volumes for PostgreSQL persistence.
    - Add `restart: unless-stopped` (or similar) to long-running services.
    - Add `healthcheck` for `postgres_database` (and optionally `mqtt_broker`) so you can diagnose startup ordering issues.

4. **Logging as your “runtime debugger”**:
    - Log to `stdout/stderr` only (no local log files inside the container).
    - Verify with `docker compose logs -f fastapi_backend` (and `... sensor_simulator`, `... mqtt_broker`).
    - Use a `LOG_LEVEL` environment variable (`DEBUG/INFO/WARNING/ERROR`).

5. **Database migrations**:
    - Use a migration tool (e.g., Alembic) once your schema stabilizes. Don’t “hand-edit” the database.

6. **Code quality**:
    - Use consistent formatting and linting (e.g., Ruff + Black) and type hints.
    - Keep code modular: separate MQTT handling, DB access, and API routes.

### Step 1: Infrastructure Setup (Docker)

1. Create a project folder structure.
2. Create a `docker-compose.yml` file.
3. **PostgreSQL**: Configure a postgres service with environment variables for user, password, and database name (`pressure_db`). Map port 5432.
4. **Mosquitto**: Configure the Eclipse Mosquitto service. Map port 1883. You may need a simple `mosquitto.conf` allowing anonymous access for development.

### Step 2: The Sensor Simulator

*Goal: Generate traffic for your application.*
You can either use a provided simulator or write a simple script that:
1. Simulates 3 different sensors (with unique MAC addresses).
2. Every 5 minutes: Publishes "Status" (Location, Battery) to `sensors/status`.
3. Every 1 second (when active): Publishes "Measurement" (Pressure) to `measurement/data`.

**Required MQTT Payloads:**

*   **Topic**: `sensors/status`
    ```json
    {
      "mac": "AA:BB:CC:00:11:22",
      "battery": 0.85,
      "latitude": 47.8095,
      "longitude": 13.0550,
      "timestamp": "2023-10-27T10:00:00"
    }
    ```

*   **Topic**: `measurement/data`
    ```json
    {
      "mac": "AA:BB:CC:00:11:22",
      "pressure": 1013.25,
      "timestamp": "2023-10-27T10:00:01"
    }
    ```

### Step 3: Database Design (ORM)

*Goal: Structure your data storage.*
1. Initialize a Python project for `fastapi_backend` with `FastAPI`, `SQLAlchemy` (or SQLModel), and `Pydantic`.
2. Define the Database Models (Recommended Types):
   - **Sensor**: `id` (Integer PK), `mac_address` (String Unique), `name` (String), `latitude` (Float), `longitude` (Float), `battery_level` (Float).
   - **Measurement**: `id` (Integer PK), `sensor_id` (FK -> Sensor), `pressure` (Float), `created_at` (DateTime).
3. Set up the database connection module (Engine, Session) using environment variables from Docker.

**Tip:** Use `hostname="postgres_database"` to connect from your backend container to the database container.

### Step 4: MQTT Collector Service

*Goal: Ingest data into the persistent storage.*
1. Within your FastAPI application, implement a background service (using `lifespan` events) that connects to the MQTT Broker.
2. Subscribe to:
   - `sensors/status`: specific payload handling.
   - `measurement/data`: specific payload handling.
3. **Logic**: When a message arrives:
   - Parse JSON.
   - Find or Create the Sensor in the DB (based on MAC address).
   - Save the Measurement/Status to the DB using a new DB session.

### Step 5: REST API Implementation

*Goal: Expose data to the outside world.*
Implement the following REST endpoints using Pydantic schemas for verification:
- `GET /api/sensors`: List all sensors (include battery/location info).
- `GET /api/sensors/{id}`: Detailed info for one sensor.
- `POST /api/sensors`: Manually add/update a sensor.
- `DELETE /api/sensors/{id}`: Remove a sensor.
- `GET /api/measurements`: Get measurement history (support filtering by `sensor_id`).
- `GET /api/stats`: Return basic statistics (e.g., average pressure).

*Important*: Since your Frontend and Backend are on different origins (ports), you must configure **CORS (Cross-Origin Resource Sharing)** in FastAPI to allow requests from your Frontend container.

### Step 6: Frontend Dashboard

*Goal: Visualize the data in a dedicated container.*

You may choose **one** of the following options:

**Option A: Map Dashboard with Leaflet.js (recommended)**
1. Create a `frontend` directory.
2. **Dashboard Config**:
    - Create an `index.html` with a layout for your Map and Sensor Table.
    - Using **Leaflet.js** (or similar), display a map.
    - Create JavaScript (`app.js`) to fetch the list of sensors from `http://localhost:8000/api/sensors` (Backend URL).
    - Place markers on the map for each sensor using their `latitude`/`longitude`.
    - On marker click, display latest pressure and battery status.
3. **Containerization**:
    - Create a `Dockerfile` in the `frontend` folder using `nginx:alpine`.
    - Copy your HTML/JS/CSS files to `/usr/share/nginx/html`.
4. **Integration**:
    - Add the `nginx_frontend` service to `docker-compose.yml`, mapping it to port `8080` (or similar).
    - Ensure the user can access the map at `http://localhost:8080`.

**Option B: Visualization with Grafana (alternative / optional)**
Grafana can visualize sensor positions and time series data directly from PostgreSQL.
1. Add a `grafana` service to `docker-compose.yml` (port `3000:3000`).
2. Configure a **PostgreSQL datasource** in Grafana pointing to `postgres_database`.
3. Create a DB view or query that returns the latest known status per sensor (e.g., `mac_address`, `latitude`, `longitude`, `battery_level`, `pressure`, `timestamp`).
4. Build dashboards:
    - **Geomap panel**: show sensor markers using `latitude`/`longitude`.
    - **Time series panel**: show pressure over time per sensor.

### Step 7: Documentation (UML & Manual)

*Goal: Professionalize your software delivery.*

**Process note:** Start the documentation early and keep it updated. Don’t wait until “everything works” to write it.

You are required to provide a `README.md` and a `docs/` folder containing the following:

1.  **System Manual**: A short guide on how to start the system using Docker Compose.
2.  **UML Class Diagram**: Visualize your SQLAlchemy models (`Sensor`, `Measurement`, etc.) and their relationships (associations).
3.  **UML Deployment Diagram**: Show the docker containers (`postgres_database`, `mqtt_broker`, `sensor_simulator`, `fastapi_backend`, `nginx_frontend`). If you use Grafana, include `grafana` as an optional container. Add their ports (e.g., 5432, 1883, 8000, 8080, 3000) and how they communicate (protocols like TCP/IP, MQTT, HTTP).
4.  **UML Sequence Diagram**: Illustrate the "Measurement Data Flow":
    *   *Simulator* publishes message -> *Broker* receives -> *Backend* subscribes & processes -> *Database* persists.

*Tool Tip*: You can use PlantUML, Mermaid.js, or Draw.io.

### Step 8: Quality Assurance (Testing & Logging)

*Goal: Ensure reliability and debugging capability.*

Robust software requires automated tests and comprehensive logging.

**Process note:** Testing and logging are done continuously while developing Steps 2–6. Every time you add logic (MQTT parsing, DB writes, API endpoints), you add/adjust tests and logging immediately.

1.  **Logging Strategy**:
    *   Use the standard Python `logging` module. Configure it to output to `stdout` (so Docker logs capture it).
    *   Confirm logs via `docker compose logs -f fastapi_backend` during development; do not rely on `print()`.
    *   **MQTT Collector (backend)**: Log every connection attempt, subscription success, and incoming message metadata (topic + sensor MAC). Log payload parsing failures and DB write failures with stack traces.
    *   **Backend API (FastAPI routes)**: Log request method + path + status code. Log validation errors (422) and unexpected exceptions (500).
    *   **Database layer**: Log connection establishment and transaction rollbacks (on error). Don’t log sensitive credentials.
    *   **Simulator**: Log publish intervals and reconnects (helps debugging if the pipeline is silent).

2.  **Automated Testing (pytest)**:
    *   Create a `tests/` folder.
    *   **Unit Tests**:
        *   Pydantic schema validation for MQTT payloads (valid payload passes, invalid payload fails).
        *   Message handling functions (MQTT payload -> DB operations) using a test database or mocked sessions.
    *   **Integration Tests**:
        *   Use FastAPI's `TestClient` to test your API endpoints.
        *   *Scenario*: `POST /api/sensors` with valid data -> Check if response is 200 OK.
        *   *Scenario*: `GET /api/sensors/{id}` for a non-existent ID -> Check if response is 404 Not Found.

## 4. Helpful Documentation & Resources

To successfully complete this project, you should consult the official documentation. The following links are tailored to the specific tasks in this exercise:

*   **FastAPI Tutorial**: [https://fastapi.tiangolo.com/tutorial/](https://fastapi.tiangolo.com/tutorial/)
    *Recommended read: "First Steps", "Path Operations", and "CORS (Cross-Origin Resource Sharing".*
*   **Docker Compose**: [https://docs.docker.com/compose/getting-started/](https://docs.docker.com/compose/getting-started/)
    *Recommended read: How to define services and environment variables.*
*   **SQLModel (Database)**: [https://sqlmodel.tiangolo.com/](https://sqlmodel.tiangolo.com/)
    *This library combines Pydantic and SQLAlchemy. Read "Interact with the Database" section.*
*   **Leaflet.js (Map)**: [https://leafletjs.com/examples/quick-start/](https://leafletjs.com/examples/quick-start/)
    *Simple guide to initializing a map and adding markers.*
*   **Paho MQTT Python**: [https://pypi.org/project/paho-mqtt/](https://pypi.org/project/paho-mqtt/)
    *Check the "Getting Started" or "Usage" examples.*

*   **Grafana (optional)**: [https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/geomap/](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/geomap/)
    *If you choose Option B in Step 6, use a Geomap panel with latitude/longitude from PostgreSQL.*
