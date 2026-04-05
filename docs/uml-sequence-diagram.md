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

## 4. Sensor Creation Flow

This sequence describes creating a new sensor from the dashboard, supporting both physical and simulator types.

```mermaid
sequenceDiagram
    participant Browser
    participant Frontend as nginx_frontend
    participant Backend as fastapi_backend
    participant DB as postgres_database
    participant ConfigFile as simulator_config.json
    participant Simulator as sensor_simulator

    Browser->>Frontend: Click "Add sensor" button
    Frontend->>Browser: Show sensor creation modal
    Browser->>Frontend: Fill form + select type
    Browser->>Frontend: Click "Create"
    
    Frontend->>Backend: POST /api/sensors + sensor data
    Backend->>Backend: Validate MAC, coordinates, battery
    Backend->>DB: Insert new Sensor record
    DB-->>Backend: Return sensor with ID
    
    alt Sensor Type: Simulator
        Backend->>ConfigFile: Read simulator_config.json
        Backend->>ConfigFile: Append new simulator config
        ConfigFile-->>Backend: File updated
        Backend-->>Frontend: 200 OK + "will start sending data soon"
        
        Simulator->>ConfigFile: Poll for new simulators (every 5s)
        ConfigFile-->>Simulator: New simulator config detected
        Simulator->>Simulator: Instantiate SensorSimulator
        Simulator->>Simulator: Schedule measurement/status publishing
        
        Simulator->>Broker: Publish sensors/status message
        Simulator->>Broker: Publish measurement/data (every 1s)
        Broker-->>Backend: MQTT messages received
        Backend->>DB: Create/update measurements
    else Sensor Type: Physical
        Backend-->>Frontend: 200 OK + "awaiting MQTT messages"
        Note over Backend,Frontend: Physical sensor must publish MQTT messages
        Simulator->>Broker: (external device publishes)
        Broker-->>Backend: MQTT messages received
        Backend->>DB: Create/update measurements
    end
    
    Frontend->>Frontend: Close modal + refresh sensor list
    Frontend->>Browser: Display new sensor in grid
    Browser->>Browser: Render real-time updates via WebSocket
```

## 5. Simulator Configuration Update

The sensor_simulator service periodically checks for new simulator configurations and starts them automatically.

```mermaid
sequenceDiagram
    participant ConfigFile as simulator_config.json
    participant Simulator as sensor_simulator
    participant MQTT as mqtt_broker
    participant Backend as fastapi_backend

    loop Every 5 seconds
        Simulator->>ConfigFile: Read simulator_config.json
        ConfigFile-->>Simulator: Configuration data
        Simulator->>Simulator: Check for new MAC addresses
        
        alt New simulator found
            Simulator->>Simulator: Create SensorSimulator instance
            Simulator->>Simulator: Set location, battery, range from config
            Simulator->>MQTT: Connect to broker (if needed)
            
            loop Every 1 second
                Simulator->>MQTT: Publish measurement/data
                MQTT-->>Backend: Forward to subscribed client
            end
            
            loop Every 10 seconds
                Simulator->>MQTT: Publish sensors/status
                MQTT-->>Backend: Forward to subscribed client
            end
            
            Simulator->>Simulator: Simulate battery drain
        else No new simulators
            Note over Simulator: Continue with existing simulators
        end
    end
```

## Processing Details

**Sensor Creation**:
- Form validates: MAC address format, coordinate ranges (-90/+90, -180/+180), battery 0-100%, pressure min < max
- User must have authentication token (Bearer token in Authorization header)
- Simulator sensors are added to both database and JSON config file
- Physical sensors only added to database (assume external MQTT publisher)
- Clearance levels determine who can see/read the sensor

**Simulator Auto-Start**:
- sensor_simulator service runs in loop checking config file every 5 seconds
- No container restart required - new simulators detected and started automatically
- Configuration includes: MAC, location, altitude, battery level, expected pressure range
- Simulator generates realistic pressure measurements following a normal distribution
- Battery drains slowly with each transmitted message

**Message Publishing**:
- Measurements (measurement/data): Once per second, contains pressure value
- Status (sensors/status): Every 10 seconds, contains battery level and location
- Both include MAC address for identification and clearance levels for access control