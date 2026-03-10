# UML Sequence Diagram

This sequence describes the required measurement data flow from simulated device publishing through persistence in the database.

```mermaid
sequenceDiagram
    participant Simulator as sensor_simulator
    participant Broker as mqtt_broker
    participant Backend as fastapi_backend
    participant DB as postgres_database

    Simulator->>Broker: Publish measurement/data JSON
    Note over Simulator,Broker: Topic: measurement/data
    Broker-->>Backend: Deliver subscribed MQTT message
    Backend->>Backend: Parse JSON payload
    Backend->>Backend: Resolve sensor by MAC address
    Backend->>DB: Insert Measurement row
    DB-->>Backend: Commit successful
```

## Included Processing Steps

- The simulator emits a pressure value and timestamp.
- The broker receives and forwards the MQTT message.
- The backend subscriber parses the payload and resolves the owning sensor.
- The backend stores the measurement persistently in PostgreSQL.