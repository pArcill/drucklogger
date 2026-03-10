# UML Deployment Diagram

The system is deployed as a Docker Compose application with five active containers. Grafana is not currently part of the stack, but it is shown as an optional extension because it is allowed by the assignment.

```mermaid
flowchart TB
    user[User Browser]

    subgraph docker[Docker Compose Deployment]
        frontend[nginx_frontend\nNginx container\nPort: 80/tcp]
        backend[fastapi_backend\nFastAPI container\nPort: 8000/tcp]
        broker[mqtt_broker\nMosquitto container\nPorts: 1883/tcp, 9001/tcp]
        db[postgres_database\nPostgreSQL container\nPort: 5432/tcp]
        simulator[sensor_simulator\nPython container\nNo external port]
        grafana[grafana\nOptional container\nPort: 3000/tcp]
    end

    user -->|HTTP| frontend
    frontend -->|HTTP REST| backend
    simulator -->|MQTT| broker
    broker -->|MQTT subscriptions| backend
    backend -->|PostgreSQL TCP/IP| db
    grafana -.->|Optional PostgreSQL queries| db
```

## Communication Summary

- Browser to frontend: HTTP
- Frontend to backend: HTTP REST
- Simulator to broker: MQTT
- Broker to backend: MQTT subscriptions
- Backend to PostgreSQL: TCP/IP using PostgreSQL protocol
- Optional Grafana to PostgreSQL: TCP/IP using PostgreSQL protocol