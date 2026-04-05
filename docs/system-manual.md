# System Manual

## Purpose

This guide explains how to start the IoT Pressure Logger system with Docker Compose, manage user accounts and permissions, and verify that the main services are running.

## Prerequisites

- Docker Desktop or Docker Engine with Docker Compose support
- A local copy of this repository
- Basic knowledge of UNIX/PowerShell command line

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
- `SECRET_KEY`: JWT secret for authentication (set a strong random value in production)
- `TOKEN_EXPIRE_MINUTES`: JWT token expiration time, default `1440` (24 hours)

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

or consult the locally created logs/pressure_logger.log file, as well as any system failures documented inside the crashlogs folder.

## Access The Application

- Frontend dashboard: `http://localhost:80`
- FastAPI Swagger UI: `http://localhost:8000/docs`
- FastAPI health check: `http://localhost:8000/health`

If you changed the values in `.env`, replace the ports above with your configured values.

---

# Authentication Guide

## Login and Registration

When you first visit the application at `http://localhost:80`, you will see a login/register screen.

### Register a New Account

1. Click the **"Don't have an account? Register here"** link
2. Enter a **username** (minimum 3 characters)
3. Enter an **email** address (must contain @)
4. Enter a **password** (minimum 6 characters)
5. Click **Register**

New accounts are created with the **`regular`** role by default.

### Login to an Existing Account

1. Enter your **username**
2. Enter your **password**
3. Click **Login**

The system will generate a JWT token valid for 24 hours (configurable via `TOKEN_EXPIRE_MINUTES`).

### Logout

Click the **Logout** button in the top-right corner of the dashboard to clear your session.

---

# Sensor Management

## Overview

The system supports two types of sensors:

1. **Physical Sensors** - Real hardware devices that connect via MQTT
2. **Simulator Sensors** - Software-based virtual sensors that generate simulated pressure data

New sensors can be created directly from the dashboard without requiring container restarts or manual configuration.

## Creating a New Sensor

### From the Dashboard

1. Click the **"Add sensor"** button in the toolbar (top-right area of the Sensor Fleet section)
2. A modal form will appear with the following fields:

#### Basic Information
- **Sensor Name**: A descriptive name for the sensor (e.g., "Pressure Gauge A")
- **MAC Address**: Unique MAC address in format `AA:BB:CC:DD:EE:FF`

#### Location & Environment
- **Latitude**: Geographic latitude (-90 to 90 degrees)
- **Longitude**: Geographic longitude (-180 to 180 degrees)
- **Altitude**: Height above sea level in meters

#### Measurement Configuration
- **Battery Level**: Initial battery percentage (0-100%)
- **Pressure Range - Minimum**: Minimum expected pressure (hPa)
- **Pressure Range - Maximum**: Maximum expected pressure (hPa)

#### Access Control
- **Sensor Type**: Choose **Simulator** or **Physical**
- **Display Clearance**: Who can see this sensor on the map
- **Readings Clearance**: Who can view this sensor's measurements

### Sensor Type: Physical

Physical sensors are real devices that transmit data via MQTT protocol.

- **Configuration**: MAC address and location are required
- **Data Transmission**: Sensor must be configured to send MQTT messages to the broker
- **Topics**:
  - Status updates: `sensors/status` (battery, location)
  - Measurements: `measurement/data` (pressure readings)
- **Message Properties**:
  - `mac`: MAC address matching the registered sensor
  - `display_clearance`: Access level (extracted from database)
  - `readings_clearance`: Access level (extracted from database)

**Example MQTT Status Message:**
```json
{
  "mac": "AA:BB:CC:00:11:22",
  "battery": 0.85,
  "latitude": 47.8095,
  "longitude": 13.0550,
  "altitude": 500.0,
  "display_clearance": "regular",
  "readings_clearance": "regular",
  "timestamp": "2026-04-05T10:23:45+00:00"
}
```

### Sensor Type: Simulator

Simulator sensors are virtual sensors that automatically generate realistic pressure data. They start sending data within 5 seconds of creation.

- **Configuration**: All fields are required (no defaults)
- **Data Transmission**: Automatic - starts immediately after creation
- **Auto-start**: Simulator reads from `/app/simulator_config.json` every 5 seconds
- **Data Points**:
  - Measurements: Every 1 second (on `measurement/data` topic)
  - Status updates: Every 10 seconds (on `sensors/status` topic)
  - Battery drain: Realistic battery consumption over time

**Simulator Configuration Details:**

When a simulator is created:
1. A record is added to the PostgreSQL database
2. Configuration is appended to `simulator_config.json`
3. The sensor_simulator service detects the new entry
4. Simulator instance starts and begins sending data

The configuration file (`simulator_config.json`) has this structure:
```json
{
  "simulators": [
    {
      "mac": "AA:BB:CC:00:11:22",
      "latitude": 47.8095,
      "longitude": 13.0550,
      "altitude": 500.0,
      "battery_level": 0.95,
      "display_clearance": "regular",
      "readings_clearance": "regular",
      "expected_range": [980.0, 1050.0]
    }
  ]
}
```

## Real-Time Data Updates

The dashboard displays real-time sensor data via WebSocket connection:

- **Connection**: Automatic connection established on dashboard load
- **Update Rate**: Measurements displayed as they arrive (typically ~1 per second)
- **Historical Data**: Last 50 measurements loaded on initial connection
- **Battery**: Updates every 10 seconds when sensor sends status
- **Location**: Static after sensor creation (can be updated via database)

## Simulator vs Physical - Comparison

| Feature           | Physical          | Simulator        |
| --------------- | --------------- | -------------- |
| Setup Required  | Hardware device | None - auto-start |
| Default Data    | Depends on device | Realistic pressure curve |
| Battery Updates | From device     | Automatic drain |
| Start Delay     | Depends on device | 5 seconds max  |
| Testing         | Requires hardware | Immediate      |
| Configuration   | Via device      | Via form/JSON  |

## Accessing Sensor Data

Once a sensor is created:

1. **On Map**: Visible to users with role ≥ `display_clearance`
2. **Measurements**: Accessible to users with role ≥ `readings_clearance`
3. **Hiding Data**: If user lacks `readings_clearance`, fields show "⚠ Insufficient clearance for readings"
4. **Filtering**: The API automatically filters by user permissions

---

# Account Permissions and Role Hierarchy

## Overview

The system implements a hierarchical role-based access control (RBAC) system. Each user has a **role** that determines what sensors and measurements they can view. Each sensor has two independent **clearance levels** that control who can see and access that sensor's data.

## Role Hierarchy

Roles are ranked from lowest to highest privilege:

1. **`guest`** - Lowest privilege (reserved for unauthenticated access)
2. **`regular`** - Default role for new users
3. **`elevated`** - Enhanced access for trusted operators
4. **`full_clearance`** - Administrative-level access
5. **`top_secret`** - Highest privilege (restricted data)

**Key principle**: A user with a higher role can access ALL data that users of lower roles can access.

### Example Role Access Chain

- A user with role **`elevated`** can access data restricted to `regular` or `elevated` clearance
- A user with role **`full_clearance`** can access data from `guest`, `regular`, `elevated`, and `full_clearance` sensors
- A user with role **`top_secret`** can access ALL sensors

## Sensor Clearance Levels

Each sensor has two clearance attributes:

### 1. `display_clearance`

Controls **visibility** of the sensor on the dashboard map and sensor list.

- Only users with a role ≥ the sensor's `display_clearance` will see the sensor at all
- Default: `regular` (all logged-in users can see)
- If a user lacks `display_clearance`, the sensor is completely hidden from their view

### 2. `readings_clearance`

Controls **access to sensor data** (pressure measurements, battery level, altitude).

- Even if a user can see a sensor, they may not be able to read its measurements
- Users lacking `readings_clearance` will see "---" for data fields
- Default: `regular` (all logged-in users can read)
- Shows a warning: ⚠ **Insufficient clearance for readings**

### Example Configuration

A sensor with:
- `display_clearance = "elevated"`
- `readings_clearance = "full_clearance"`

Visibility matrix:

| User Role        | See Sensor? | Read Data? |
| --------------- | ----------- | ---------- |
| guest           | ❌ No      | ❌ No     |
| regular         | ❌ No      | ❌ No     |
| elevated        | ✅ Yes     | ❌ No (insufficient clearance) |
| full_clearance  | ✅ Yes     | ✅ Yes    |
| top_secret      | ✅ Yes     | ✅ Yes    |

---

# Managing Account Permissions

## Changing User Roles

**Current limitation**: Role assignment requires direct database modification.

### Via Database (PostgreSQL)

1. Connect to the PostgreSQL container:

   ```bash
   docker exec -it postgres_database psql -U admin -d sensor_db
   ```

2. View all users:

   ```sql
   SELECT id, username, em ail, role FROM users;
   ```

3. Update a user's role:

   ```sql
   UPDATE users SET role = 'elevated' WHERE username = 'john';
   ```

4. Commit and exit:

   ```sql
   \q
   ```

### Via pgAdmin (Optional)

If you have pgAdmin running, you can:

1. Navigate to the PostgreSQL connection
2. Open the `users` table in the `pressure_db` database
3. Edit the `role` column for any user
4. Save changes

## Modifying Sensor Clearance

Sensors start with both `display_clearance` and `readings_clearance` set to `regular`.

### Via Database (PostgreSQL)

1. Connect to the database (as above):

   ```bash
   docker exec -it drucklogger-postgres_database-1 psql -U admin -d pressure_db
   ```

2. View all sensors with their clearance levels:

   ```sql
   SELECT id, name, mac_address, display_clearance, readings_clearance FROM sensors;
   ```

3. Update a sensor's clearance:

   ```sql
   UPDATE sensors 
   SET display_clearance = 'elevated', readings_clearance = 'full_clearance'
   WHERE name = 'Sensor A';
   ```

4. Verify the change:

   ```sql
   SELECT * FROM sensors WHERE name = 'Sensor A';
   ```

### Clearance Configuration Examples

**Public sensor** (everyone can see and read):
```sql
UPDATE sensors 
SET display_clearance = 'guest', readings_clearance = 'guest'
WHERE name = 'Public Sensor';
```

**Restricted visibility** (only elevated+ can see it exists):
```sql
UPDATE sensors 
SET display_clearance = 'elevated', readings_clearance = 'regular'
WHERE name = 'Internal Sensor';
```

**Top-secret sensor** (only top_secret role can access):
```sql
UPDATE sensors 
SET display_clearance = 'top_secret', readings_clearance = 'top_secret'
WHERE name = 'Classified Sensor';
```

---

## Principal: Calculating Average Pressure

When a user views average pressure statistics:

- Only measurements from sensors where the user has `readings_clearance` are included
- Measurements the user cannot access are excluded from the calculation
- Users with higher roles see more complete averages

---

# Troubleshooting

## Authentication Issues

### "Invalid username or password"

- Verify the username and password are correct
- Check that the user account was successfully registered
- Ensure the database is running: `docker compose ps` should show `postgres_database` as healthy

### "User account is inactive"

- The user's `is_active` field is set to `false` in the database
- Re-enable the user:

  ```bash
  docker exec -it drucklogger-postgres_database-1 psql -U admin -d pressure_db
  UPDATE users SET is_active = true WHERE username = 'john';
  \q
  ```

## Permission Issues

### "⚠ Insufficient clearance for readings" on all sensors

- Your user role is lower than the sensors' `readings_clearance` level
- Ask an administrator to adjust sensor clearance or upgrade your role
- Check your role: `SELECT role FROM users WHERE username = '<your_username>';`

### Sensors disappearing after update

- You may have updated a sensor's `display_clearance` to a level higher than your role
- Have an administrator adjust the sensor's clearance level for visibility
- Check sensor clearance: `SELECT name, display_clearance FROM sensors;`

## Service Connection Issues

- If the backend cannot connect to PostgreSQL, check that `postgres_database` is healthy with `docker compose ps`.
- If no live data appears, inspect `sensor_simulator` and `mqtt_broker` logs.
- If the frontend loads but shows no data, check the browser network tab and confirm `fastapi_backend` is reachable on `API_PORT`.
- MQTT anonymous access is enabled in `mosquitto.conf`; keep that configuration for development only.

## Sensor Creation Issues

### Simulator not sending data after creation

**Symptoms**: Newly created simulator appears in sensor list but shows "---" for measurements

**Diagnosis**:
1. Check if simulator is running: `docker compose logs sensor_simulator --tail=50`
2. Look for message: `Loaded simulator <MAC> from config file`
3. Verify JSON config file exists: `docker compose exec sensor_simulator cat /app/simulator_config.json | head -20`

**Solutions**:
- Wait up to 5 seconds - sensor_simulator checks config every 5 seconds
- Verify simulator config file has correct JSON structure - must include all fields
- Check MQTT broker is running: `docker compose logs mqtt_broker --tail=20`
- Restart sensor_simulator: `docker compose restart sensor_simulator`

### Simulator shows 0% battery immediately

- Simulators initialize with realistic random battery (20-100%)
- If showing 0%, simulator may not have sent status yet (wait 10 seconds)
- Check logs: `docker compose logs sensor_simulator | grep "battery"`

## Simulator Configuration Issues

### simulator_config.json is empty or malformed

The configuration file is located at `./simulator_config.json` in the project root.

**To reset to default simulators**:
```json
{
  "simulators": [
    {
      "mac": "AA:BB:CC:00:11:22",
      "latitude": 47.8095,
      "longitude": 13.0550,
      "altitude": 500.0,
      "battery_level": 0.95,
      "display_clearance": "regular",
      "readings_clearance": "regular",
      "expected_range": [980.0, 1050.0]
    }
  ]
}
```

**To manually add a simulator** (without using the form):
1. Edit `simulator_config.json` locally
2. Add entry to `simulators` array
3. Wait 5 seconds or restart container: `docker compose restart sensor_simulator`
4. New simulator should appear on dashboard within 5 seconds

### Simulators offline but no error in logs

**Possible causes**:
- Configuration file not accessible to sensor_simulator container
- MQTT broker connection refused
- Database modules import error (check logs for "Database modules not available")

**Solutions**:
- Verify volume mount in docker-compose.yml includes `simulator_config.json`
- Check MQTT broker health: `docker compose logs mqtt_broker | grep -i error`
- Restart entire stack: `docker compose down && docker compose up -d --build`

## Data Display Issues

### WebSocket connection failing

- Check browser console: F12 → Console tab
- Verify `fastapi_backend` is running: `docker compose ps | grep fastapi`
- Check for CORS issues in browser dev tools
- Restart frontend connection: Refresh browser page

### Measurements not updating in real-time

- WebSocket may have disconnected - refresh page
- Check that `sensor_simulator` and `mqtt_broker` are running
- Verify `fastapi_backend` can connect to MQTT broker: `docker compose logs fastapi_backend | grep mqtt`

## Stop The System

```bash
docker compose down
```

To also remove named volumes:

```bash
docker compose down -v
```

---

# Security Notes

- Change `SECRET_KEY` in `.env` to a strong random value in production
- Use HTTPS in production (configure reverse proxy with SSL certificates)
- Never commit `.env` with real secrets to version control
- Use environment-specific `.env` files for development, staging, and production
- Rotate tokens regularly by restarting the application or setting shorter `TOKEN_EXPIRE_MINUTES`
- Regularly audit the `users` table for inactive or suspicious accounts