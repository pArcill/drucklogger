# UML Class Diagram

The backend uses SQLModel models for user authentication, sensor management, and measurement storage. Users have roles that determine what sensors and measurements they can access based on clearance levels.

```mermaid
classDiagram
    class User {
        +int id
        +str username
        +str email
        +str hashed_password
        +str role
        +datetime created_at
        +bool is_active
    }

    class Sensor {
        +int id
        +str mac_address
        +str name
        +float latitude
        +float longitude
        +float altitude
        +float battery_level
        +str display_clearance
        +str readings_clearance
    }

    class Measurement {
        +int id
        +int sensor_id
        +float pressure
        +bool out_of_range
        +datetime created_at
    }

    Sensor "1" --> "0..*" Measurement : measurements
    Measurement "0..*" --> "1" Sensor : sensor
```

## Relationship Summary

- `User.id` is the primary key of the users table. Users are authenticated via username/password.
- `Sensor.id` is the primary key of the sensors table.
- `Measurement.sensor_id` is a foreign key to `Sensor.id`.
- Each sensor has two clearance fields:
  - `display_clearance`: Controls visibility in the dashboard map and sensor list
  - `readings_clearance`: Controls access to measurement data (pressure values, battery level, altitude)
- User roles determine access levels: `guest` → `regular` → `elevated` → `full_clearance` → `top_secret`
- The ORM relationships are declared with `Relationship(back_populates=...)` in both models.