from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel, Relationship


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
    battery_level: float = Field(ge=0.0, le=1.0)
    
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relationship to sensor
    sensor: Optional[Sensor] = Relationship(back_populates="measurements")