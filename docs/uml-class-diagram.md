# UML Class Diagram

The backend uses SQLModel models for `Sensor` and `Measurement`. A sensor can have many measurements, while each measurement belongs to exactly one sensor.

```mermaid
classDiagram
    class Sensor {
        +int id
        +str mac_address
        +str name
        +float latitude
        +float longitude
        +float battery_level
    }

    class Measurement {
        +int id
        +int sensor_id
        +float pressure
        +datetime created_at
    }

    Sensor "1" --> "0..*" Measurement : measurements
    Measurement "0..*" --> "1" Sensor : sensor
```

## Relationship Summary

- `Sensor.id` is the primary key of the sensor table.
- `Measurement.sensor_id` is a foreign key to `Sensor.id`.
- The ORM relationship is declared with `Relationship(back_populates=...)` in both models.