from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel, Relationship


class User(SQLModel, table=True):
    """
    Database model for a user account
    """
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=100)
    email: str = Field(unique=True, index=True, max_length=255)
    hashed_password: str
    role: str = Field(default="regular", max_length=50)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = Field(default=True)


class Sensor(SQLModel, table=True):
    """
    Database model for a sensor device
    """
    __tablename__ = "sensors"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    mac_address: str = Field(unique=True, index=True, max_length=17)
    name: str = Field(max_length=100)
    latitude: float
    longitude: float
    altitude: float = Field(default=0.0)  # Meters above sea level
    battery_level: float = Field(ge=0.0, le=1.0)
    display_clearance: str = Field(default="regular", max_length=50)  # Who can see the sensor on map
    readings_clearance: str = Field(default="regular", max_length=50)  # Who can view readings
    
    # Relationship to measurements
    measurements: list["Measurement"] = Relationship(back_populates="sensor")


class Measurement(SQLModel, table=True):
    """
    Database model for pressure measurements from sensors
    """
    __tablename__ = "measurements"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    sensor_id: int = Field(foreign_key="sensors.id")
    pressure: float
    out_of_range: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relationship to sensor
    sensor: Optional[Sensor] = Relationship(back_populates="measurements")


# ============================================================================
# Request/Response Models (not database tables)
# ============================================================================

class RegisterRequest(SQLModel):
    """Request model for user registration"""
    username: str
    email: str
    password: str


class LoginRequest(SQLModel):
    """Request model for user login"""
    username: str
    password: str