# src/test/test_fastapi_backend.py
import os
import sys
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Add src to path for imports
SRC_PATH = os.path.dirname(os.path.dirname(__file__))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from fastapi_backend.models import Sensor, Measurement
from fastapi_backend.main import app
from postgres_database.database import get_session


@pytest.fixture(name="session")
def session_fixture():
    """
    Create an in-memory SQLite database for testing
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """
    Create a test client with overridden database session
    """
    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# Model Tests

def test_sensor_model_creation():
    """Test creating a Sensor model instance"""
    sensor = Sensor(
        mac_address="AA:BB:CC:00:11:22",
        name="Test Sensor",
        latitude=47.8095,
        longitude=13.0550,
        battery_level=0.85
    )
    
    assert sensor.mac_address == "AA:BB:CC:00:11:22"
    assert sensor.name == "Test Sensor"
    assert sensor.latitude == 47.8095
    assert sensor.longitude == 13.0550
    assert sensor.battery_level == 0.85


def test_sensor_battery_level_validation():
    """Test that battery_level is constrained between 0 and 1"""
    # Valid battery level
    sensor = Sensor(
        mac_address="AA:BB:CC:00:11:22",
        name="Test Sensor",
        latitude=47.8095,
        longitude=13.0550,
        battery_level=0.5
    )
    assert sensor.battery_level == 0.5
    
    # Edge cases
    sensor_min = Sensor(
        mac_address="AA:BB:CC:00:11:23",
        name="Min Battery",
        latitude=47.8095,
        longitude=13.0550,
        battery_level=0.0
    )
    assert sensor_min.battery_level == 0.0
    
    sensor_max = Sensor(
        mac_address="AA:BB:CC:00:11:24",
        name="Max Battery",
        latitude=47.8095,
        longitude=13.0550,
        battery_level=1.0
    )
    assert sensor_max.battery_level == 1.0


def test_measurement_model_creation():
    """Test creating a Measurement model instance"""
    now = datetime.now(timezone.utc)
    measurement = Measurement(
        sensor_id=1,
        pressure=1013.25,
        created_at=now
    )
    
    assert measurement.sensor_id == 1
    assert measurement.pressure == 1013.25
    assert measurement.created_at == now


def test_measurement_default_timestamp():
    """Test that Measurement gets a default timestamp"""
    measurement = Measurement(
        sensor_id=1,
        pressure=1013.25
    )
    
    assert measurement.created_at is not None
    assert isinstance(measurement.created_at, datetime)
    # Check it's recent (within last 5 seconds)
    time_diff = datetime.now(timezone.utc) - measurement.created_at
    assert time_diff.total_seconds() < 5


# Database Tests

def test_create_sensor_in_db(session: Session):
    """Test creating a sensor in the database"""
    sensor = Sensor(
        mac_address="AA:BB:CC:00:11:22",
        name="DB Test Sensor",
        latitude=47.8095,
        longitude=13.0550,
        battery_level=0.75
    )
    
    session.add(sensor)
    session.commit()
    session.refresh(sensor)
    
    assert sensor.id is not None
    assert sensor.mac_address == "AA:BB:CC:00:11:22"


def test_sensor_mac_address_unique_constraint(session: Session):
    """Test that mac_address must be unique"""
    sensor1 = Sensor(
        mac_address="AA:BB:CC:00:11:22",
        name="Sensor 1",
        latitude=47.8095,
        longitude=13.0550,
        battery_level=0.75
    )
    session.add(sensor1)
    session.commit()
    
    # Try to add another sensor with same MAC
    sensor2 = Sensor(
        mac_address="AA:BB:CC:00:11:22",
        name="Sensor 2",
        latitude=47.8095,
        longitude=13.0550,
        battery_level=0.85
    )
    session.add(sensor2)
    
    with pytest.raises(Exception):  # Should raise IntegrityError
        session.commit()


def test_create_measurement_with_sensor_relationship(session: Session):
    """Test creating a measurement linked to a sensor"""
    # Create sensor first
    sensor = Sensor(
        mac_address="AA:BB:CC:00:11:22",
        name="Test Sensor",
        latitude=47.8095,
        longitude=13.0550,
        battery_level=0.85
    )
    session.add(sensor)
    session.commit()
    session.refresh(sensor)
    
    # Create measurement
    measurement = Measurement(
        sensor_id=sensor.id,
        pressure=1013.25
    )
    session.add(measurement)
    session.commit()
    session.refresh(measurement)
    
    assert measurement.id is not None
    assert measurement.sensor_id == sensor.id
    assert measurement.sensor.mac_address == "AA:BB:CC:00:11:22"


def test_sensor_measurements_relationship(session: Session):
    """Test that sensor.measurements relationship works"""
    # Create sensor
    sensor = Sensor(
        mac_address="AA:BB:CC:00:11:22",
        name="Test Sensor",
        latitude=47.8095,
        longitude=13.0550,
        battery_level=0.85
    )
    session.add(sensor)
    session.commit()
    session.refresh(sensor)
    
    # Add multiple measurements
    measurement1 = Measurement(sensor_id=sensor.id, pressure=1010.0)
    measurement2 = Measurement(sensor_id=sensor.id, pressure=1015.0)
    measurement3 = Measurement(sensor_id=sensor.id, pressure=1020.0)
    
    session.add_all([measurement1, measurement2, measurement3])
    session.commit()
    
    # Refresh sensor to load relationships
    session.refresh(sensor)
    
    assert len(sensor.measurements) == 3
    pressures = [m.pressure for m in sensor.measurements]
    assert 1010.0 in pressures
    assert 1015.0 in pressures
    assert 1020.0 in pressures


# API Endpoint Tests

def test_read_root(client: TestClient):
    """Test the root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Sensor Data API is running"}


def test_health_check(client: TestClient):
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert ('status', 'healthy') in response.json().items()


def test_handle_sensor_status_broadcast_and_db(session: Session):
    """Ensure MQTTHandler creates/updates sensor and sends a status message via callback"""
    import asyncio
    from fastapi_backend.mqtt_handler import MQTTHandler
    from postgres_database import database as dbmod
    import fastapi_backend.mqtt_handler as mh

    # point handler and database module at our in-memory test engine
    dbmod.engine = session.bind
    mh.engine = session.bind

    received = []
    async def fake_broadcast(msg):
        # simply append; run_coroutine_threadsafe will schedule it
        received.append(msg)

    # create and set an event loop for run_coroutine_threadsafe to use
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    handler = MQTTHandler("test-broker", 1883, broadcast_callback=fake_broadcast, event_loop=loop)

    # prepare status payload
    payload = {
        "mac": "AA:BB:CC:00:11:22",
        "battery": 0.42,
        "latitude": 47.0,
        "longitude": 8.0,
        "timestamp": "2026-03-03T12:00:00Z"
    }

    # call the handler directly; it will commit using the patched engine
    handler._handle_sensor_status(payload)

    # confirm the sensor was inserted in the database
    from fastapi_backend.models import Sensor
    from sqlmodel import select
    with session:
        sensor = session.exec(select(Sensor).where(Sensor.mac_address == payload["mac"])) .first()
        assert sensor is not None
        assert sensor.battery_level == pytest.approx(0.42)
        assert sensor.latitude == pytest.approx(47.0)
        assert sensor.longitude == pytest.approx(8.0)

    # the broadcast callback is scheduled asynchronously; give the loop a moment
    # retrieving the result of run_coroutine_threadsafe will block until completion.
    # Since we don't have a handle to the future, we can simply allow the event loop
    # to cycle by running a no-op coroutine.
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.sleep(0))

    assert len(received) == 1
    status_msg = received[0]
    assert status_msg["type"] == "status"
    assert status_msg["sensor_name"] == sensor.name
    assert status_msg["battery"] == pytest.approx(0.42)
    assert status_msg["sensor_id"] == sensor.id


def test_api_has_openapi_docs(client: TestClient):
    """Test that OpenAPI documentation is available"""
    response = client.get("/docs")
    assert response.status_code == 200
    
    response = client.get("/openapi.json")
    assert response.status_code == 200
    openapi_schema = response.json()
    assert openapi_schema["info"]["title"] == "Sensor Data API"
    assert openapi_schema["info"]["version"] == "1.0.0"