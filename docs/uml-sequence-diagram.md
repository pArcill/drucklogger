# UML Sequence Diagrams

## 1. User Authentication Flow

```mermaid
sequenceDiagram
    participant Browser
    participant Frontend as nginx_frontend
    participant Backend as fastapi_backend
    participant DB as postgres_database

    Browser->>Frontend: Enter username, email, password
    Browser->>Frontend: Click "Register" or "Login"
    
    alt Registration
        Frontend->>Backend: POST /api/auth/register (JSON)
        Backend->>DB: Check if user exists
        Backend->>DB: Hash password + create User row
        DB-->>Backend: Return new user object
        Backend-->>Frontend: 200 OK + user info
    else Login
        Frontend->>Backend: POST /api/auth/login (JSON)
        Backend->>DB: Query User by username
        Backend->>Backend: Verify password hash
        Backend->>Backend: Generate JWT token
        Backend-->>Frontend: 200 OK + access_token
    end
    
    Frontend->>Frontend: Store token in localStorage
    Frontend->>Browser: Render dashboard screen
```

## 2. Measurement Data Flow

This sequence describes the measurement data flow from simulated device publishing through persistence in the database.

```mermaid
sequenceDiagram
    participant Simulator as sensor_simulator
    participant Broker as mqtt_broker
    participant Backend as fastapi_backend
    participant DB as postgres_database

    Simulator->>Broker: Publish measurement/data JSON
    Note over Simulator,Broker: Topic: measurement/data
    Note over Simulator,Broker: Contains: mac_address, pressure, altitude, battery
    Broker-->>Backend: Deliver subscribed MQTT message
    Backend->>Backend: Parse JSON payload
    Backend->>Backend: Resolve sensor by MAC address
    Backend->>DB: Insert Measurement row
    DB-->>Backend: Commit successful
    Backend->>Backend: Update sensor altitude, battery
```

## 3. Dashboard Data Access (Role-Based Filtering)

```mermaid
sequenceDiagram
    participant Browser
    participant Frontend as nginx_frontend
    participant Backend as fastapi_backend
    participant DB as postgres_database

    Browser->>Frontend: Request sensor list
    Frontend->>Backend: GET /api/sensors + Authorization header
    Backend->>Backend: Extract token from header
    Backend->>Backend: Decode JWT + get user role
    Backend->>DB: Query all sensors
    Backend->>Backend: Filter sensors by display_clearance
    Backend->>Backend: For each sensor, add can_read flag
    Backend-->>Frontend: 200 OK + filtered sensors
    Frontend->>Browser: Display sensors user can access
    Note over Frontend,Browser: Show "⚠ Insufficient clearance" for restricted sensors
```

## Included Processing Steps

**Authentication**:
- User submits registration or login form with JSON body (no python-multipart required)
- Backend validates credentials and generates JWT token
- Token is returned and stored in browser localStorage
- Token is included in Authorization header for subsequent requests

**Measurement Flow**:
- Simulator publishes pressure, altitude, and battery level via MQTT
- Backend receives MQTT messages and resolves sensor by MAC address
- Measurements are persisted with timestamp
- Sensor altitude and battery level are updated in real-time

**Dashboard Access**:
- User JWT token determines their role (guest, regular, elevated, full_clearance, top_secret)
- Sensors have two independent clearance levels: display_clearance and readings_clearance
- Backend filters sensors based on user role vs. sensor display_clearance
- Measurements are only visible if user role exceeds readings_clearance
- Frontend UI shows "---" for data the user cannot access