# UML Deployment Diagram

The system is deployed as a Docker Compose application with five active containers. The frontend and backend now include user authentication with role-based access control.

```mermaid
flowchart TB
    user[User Browser]

    subgraph docker[Docker Compose Deployment]
        frontend[nginx_frontend\nNginx container\nPort: 80/tcp\nAuth UI + Dashboard]
        backend[fastapi_backend\nFastAPI container\nPort: 8000/tcp\nAuth + REST API + RBAC]
        broker[mqtt_broker\nMosquitto container\nPorts: 1883/tcp, 9001/tcp]
        db[postgres_database\nPostgreSQL container\nPort: 5432/tcp\nUsers + Sensors + Measurements]
        simulator[sensor_simulator\nPython container\nNo external port\nSimulates pressure sensors]
        grafana[grafana\nOptional container\nPort: 3000/tcp]
    end

    user -->|HTTP Login/Dashboard| frontend
    frontend -->|HTTP REST\nJWT Authorization| backend
    simulator -->|MQTT Altitude/Pressure| broker
    broker -->|MQTT subscriptions| backend
    backend -->|PostgreSQL\nAuth + Data| db
    grafana -.->|Optional PostgreSQL queries| db
```

## Communication Summary

- **Browser to frontend**: HTTP with session/JWT persistence
- **Frontend to backend**: HTTP REST with Bearer token authorization
- **Simulator to broker**: MQTT publishing sensor data (pressure, altitude, battery)
- **Broker to backend**: MQTT subscriptions for measurement and sensor status
- **Backend to PostgreSQL**: TCP/IP using PostgreSQL protocol for all user, sensor, and measurement data
- **Frontend authentication**: Login/register screens with role-based dashboard access
- **Optional Grafana**: Can query PostgreSQL for metrics and visualization