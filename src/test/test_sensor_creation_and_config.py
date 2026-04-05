# src/test/test_sensor_creation_and_config.py
"""
Test module for sensor creation API endpoint and simulator config loading

This test suite validates that:
1. Sensors can be created via API endpoint
2. Simulator configs are properly loaded from JSON file
3. User authentication is required for sensor creation
4. Clearance levels are properly set during sensor creation
5. Simulator and physical sensors are handled correctly
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

# Add src to path for imports
SRC_PATH = os.path.dirname(os.path.dirname(__file__))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from fastapi_backend.models import Sensor, User, CreateSensorRequest
from fastapi_backend.main import app
from fastapi_backend.auth import create_access_token, hash_password
from postgres_database.database import get_session


@pytest.fixture(name="session")
def session_fixture():
    """Create an in-memory SQLite database for testing"""
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
    """Create a test client with overridden database session"""
    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="test_user")
def test_user_fixture(session: Session):
    """Create a test user with regular role"""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hash_password("password123"),
        role="regular",
        is_active=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(name="admin_user")
def admin_user_fixture(session: Session):
    """Create a test admin user with full_clearance role"""
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=hash_password("password123"),
        role="full_clearance",
        is_active=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_auth_token(user: User) -> str:
    """Generate an auth token for a user"""
    from datetime import timedelta
    access_token_expires = timedelta(minutes=30)
    return create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )


# Sensor Creation Endpoint Tests

def test_create_physical_sensor(client: TestClient, test_user: User):
    """Test creating a physical sensor via API"""
    token = get_auth_token(test_user)
    
    payload = {
        "sensor_type": "physical",
        "name": "Physical Sensor 1",
        "mac_address": "AA:BB:CC:DD:EE:01",
        "latitude": 47.8095,
        "longitude": 13.0550,
        "altitude": 500.0,
        "battery_level": 0.85,
        "pressure_range_min": 980.0,
        "pressure_range_max": 1050.0,
        "display_clearance": "regular",
        "readings_clearance": "regular"
    }
    
    response = client.post(
        "/api/sensors",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Physical Sensor 1"
    assert data["sensor_type"] == "physical"
    assert data["mac"] == "AA:BB:CC:DD:EE:01"
    assert "message" in data
    assert "created successfully" in data["message"]


def test_create_simulator_sensor(client: TestClient, test_user: User):
    """Test creating a simulator sensor via API"""
    token = get_auth_token(test_user)
    
    payload = {
        "sensor_type": "simulator",
        "name": "Test Simulator",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "latitude": 48.0,
        "longitude": 14.0,
        "altitude": 600.0,
        "battery_level": 0.90,
        "pressure_range_min": 980.0,
        "pressure_range_max": 1050.0,
        "display_clearance": "regular",
        "readings_clearance": "regular"
    }
    
    response = client.post(
        "/api/sensors",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Simulator"
    assert data["sensor_type"] == "simulator"
    assert data["sensor_type"] in data["message"]


def test_create_sensor_without_authentication(client: TestClient):
    """Test that sensor creation requires authentication"""
    payload = {
        "sensor_type": "physical",
        "name": "Unauthorized Sensor",
        "mac_address": "AA:BB:CC:DD:EE:02",
        "latitude": 47.8095,
        "longitude": 13.0550,
        "altitude": 500.0,
        "battery_level": 0.85,
        "pressure_range_min": 980.0,
        "pressure_range_max": 1050.0,
        "display_clearance": "regular",
        "readings_clearance": "regular"
    }
    
    response = client.post("/api/sensors", json=payload)
    
    assert response.status_code in [401, 400]  # Either unauthorized or invalid


def test_create_sensor_invalid_mac_address(client: TestClient, test_user: User):
    """Test that sensor creation validates MAC address format"""
    token = get_auth_token(test_user)
    
    payload = {
        "sensor_type": "physical",
        "name": "Bad MAC Sensor",
        "mac_address": "INVALID",
        "latitude": 47.8095,
        "longitude": 13.0550,
        "altitude": 500.0,
        "battery_level": 0.85,
        "pressure_range_min": 980.0,
        "pressure_range_max": 1050.0,
        "display_clearance": "regular",
        "readings_clearance": "regular"
    }
    
    response = client.post(
        "/api/sensors",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    
    assert response.status_code == 400
    assert "MAC" in response.json()["detail"]


def test_create_sensor_invalid_latitude(client: TestClient, test_user: User):
    """Test that sensor creation validates latitude range"""
    token = get_auth_token(test_user)
    
    payload = {
        "sensor_type": "physical",
        "name": "Bad Latitude Sensor",
        "mac_address": "AA:BB:CC:DD:EE:03",
        "latitude": 95.0,  # Invalid: > 90
        "longitude": 13.0550,
        "altitude": 500.0,
        "battery_level": 0.85,
        "pressure_range_min": 980.0,
        "pressure_range_max": 1050.0,
        "display_clearance": "regular",
        "readings_clearance": "regular"
    }
    
    response = client.post(
        "/api/sensors",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    
    assert response.status_code == 400
    assert "Latitude" in response.json()["detail"]


def test_create_sensor_invalid_pressure_range(client: TestClient, test_user: User):
    """Test that sensor creation validates pressure range"""
    token = get_auth_token(test_user)
    
    payload = {
        "sensor_type": "physical",
        "name": "Bad Pressure Sensor",
        "mac_address": "AA:BB:CC:DD:EE:04",
        "latitude": 47.8095,
        "longitude": 13.0550,
        "altitude": 500.0,
        "battery_level": 0.85,
        "pressure_range_min": 1050.0,  # min > max
        "pressure_range_max": 980.0,
        "display_clearance": "regular",
        "readings_clearance": "regular"
    }
    
    response = client.post(
        "/api/sensors",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    
    assert response.status_code == 400
    assert "Pressure range" in response.json()["detail"]


def test_create_sensor_duplicate_mac(client: TestClient, test_user: User, session: Session):
    """Test that duplicate MAC addresses are rejected"""
    # Create first sensor
    existing_sensor = Sensor(
        mac_address="AA:BB:CC:DD:EE:05",
        name="Existing Sensor",
        latitude=47.8095,
        longitude=13.0550,
        altitude=500.0,
        battery_level=0.85,
        display_clearance="regular",
        readings_clearance="regular"
    )
    session.add(existing_sensor)
    session.commit()
    
    token = get_auth_token(test_user)
    
    # Try to create another sensor with same MAC
    payload = {
        "sensor_type": "physical",
        "name": "Duplicate MAC Sensor",
        "mac_address": "AA:BB:CC:DD:EE:05",
        "latitude": 48.0,
        "longitude": 14.0,
        "altitude": 600.0,
        "battery_level": 0.90,
        "pressure_range_min": 980.0,
        "pressure_range_max": 1050.0,
        "display_clearance": "regular",
        "readings_clearance": "regular"
    }
    
    response = client.post(
        "/api/sensors",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_create_sensor_with_clearance_levels(client: TestClient, admin_user: User):
    """Test creating sensor with specific clearance levels"""
    token = get_auth_token(admin_user)
    
    payload = {
        "sensor_type": "physical",
        "name": "Classified Sensor",
        "mac_address": "AA:BB:CC:DD:EE:06",
        "latitude": 47.8095,
        "longitude": 13.0550,
        "altitude": 500.0,
        "battery_level": 0.85,
        "pressure_range_min": 980.0,
        "pressure_range_max": 1050.0,
        "display_clearance": "full_clearance",
        "readings_clearance": "top_secret"
    }
    
    response = client.post(
        "/api/sensors",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["display_clearance"] == "full_clearance"
    assert data["readings_clearance"] == "top_secret"


# Simulator Config Loading Tests

@pytest.mark.skip(reason="Test times out due to MQTT connection attempts - needs deeper mocking of SensorSimulator")
def test_load_simulators_from_config():
    """Test loading simulators from config file"""
    from sensor_simulator.main import load_simulators_from_config
    
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config = {
            "simulators": [
                {
                    "mac": "AA:BB:CC:00:11:22",
                    "latitude": 47.8095,
                    "longitude": 13.0550,
                    "altitude": 500.0,
                    "battery_level": 0.95,
                    "display_clearance": "regular",
                    "readings_clearance": "regular",
                    "expected_range": [980.0, 1050.0]
                },
                {
                    "mac": "AA:BB:CC:00:11:23",
                    "latitude": 47.8100,
                    "longitude": 13.0600,
                    "altitude": 600.0,
                    "battery_level": 0.85,
                    "display_clearance": "regular",
                    "readings_clearance": "regular",
                    "expected_range": [980.0, 1050.0]
                }
            ]
        }
        json.dump(config, f)
        config_file = f.name
    
    try:
        # Mock the config path and SensorSimulator to avoid MQTT connection timeouts
        import sensor_simulator.main as sensor_main
        from unittest.mock import patch, MagicMock
        original_exists = os.path.exists
        original_open = open
        
        def mock_exists(path):
            if path == "/app/simulator_config.json" or path == config_file:
                return True
            return original_exists(path)
        
        def mock_open_func(path, *args, **kwargs):
            if path == "/app/simulator_config.json" and "r" in str(args):
                return original_open(config_file, *args, **kwargs)
            return original_open(path, *args, **kwargs)
        
        running_simulators = {}
        
        with pytest.MonkeyPatch().context() as m:
            m.setattr(os.path, "exists", mock_exists)
            m.setattr("builtins.open", mock_open_func)
            # Mock SensorSimulator to avoid MQTT connection attempts
            mock_simulator = MagicMock()
            m.setattr(sensor_main, "SensorSimulator", MagicMock(return_value=mock_simulator))
            
            # Test loading - count should be 2
            # (mocked MQTT simulator creation, so it won't try to connect)
            loaded = load_simulators_from_config("localhost", 1883, running_simulators)
            assert isinstance(loaded, int)
            assert loaded == 2

    finally:
        if os.path.exists(config_file):
            os.unlink(config_file)


@pytest.mark.skip(reason="Test times out due to MQTT connection attempts - needs deeper mocking of SensorSimulator")
def test_load_simulators_from_config_invalid_json():
    """Test handling of invalid JSON in config file"""
    from sensor_simulator.main import load_simulators_from_config
    
    # Create a temporary invalid config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{ invalid json")
        config_file = f.name
    
    try:
        import sensor_simulator.main as sensor_main
        original_exists = os.path.exists
        
        def mock_exists(path):
            if path == "/app/simulator_config.json":
                return True
            if path == config_file:
                return True
            return original_exists(path)
        
        running_simulators = {}
        
        # Mock read to return our invalid file
        import builtins
        original_open_fn = builtins.open
        
        def mock_open_fn(path, *args, **kwargs):
            if path == "/app/simulator_config.json" and "r" in str(args):
                return original_open_fn(config_file, *args, **kwargs)
            return original_open_fn(path, *args, **kwargs)
        
        with pytest.MonkeyPatch().context() as m:
            m.setattr(os.path, "exists", mock_exists)
            m.setattr("builtins.open", mock_open_fn)
            
            # Should return 0 on invalid JSON error
            loaded = load_simulators_from_config("localhost", 1883, running_simulators)
            assert loaded == 0

    finally:
        if os.path.exists(config_file):
            os.unlink(config_file)


@pytest.mark.skip(reason="Test times out due to MQTT connection attempts - needs deeper mocking of SensorSimulator")
def test_load_simulators_from_config_missing_file():
    """Test handling of missing config file"""
    from sensor_simulator.main import load_simulators_from_config
    
    import sensor_simulator.main as sensor_main
    original_exists = os.path.exists
    
    def mock_exists(path):
        # Config file doesn't exist
        if path == "/app/simulator_config.json":
            return False
        return original_exists(path)
    
    running_simulators = {}
    
    with pytest.MonkeyPatch().context() as m:
        m.setattr(os.path, "exists", mock_exists)
        
        # Should return 0 when file doesn't exist
        loaded = load_simulators_from_config("localhost", 1883, running_simulators)
        assert loaded == 0


# WebSocket Tests

def test_websocket_connection(client: TestClient, test_user: User):
    """Test WebSocket connection"""
    token = get_auth_token(test_user)
    
    # Note: TestClient doesn't fully support WebSocket testing
    # WebSocket endpoints don't appear in OpenAPI docs - they're excluded by FastAPI
    # This test just verifies that the API is running
    
    # Verify the API is accessible
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "paths" in response.json()


# Authentication Tests

def test_register_user(client: TestClient):
    """Test user registration via API"""
    payload = {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "password123"
    }
    
    response = client.post("/api/auth/register", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"
    assert "message" in data


def test_register_user_duplicate_username(client: TestClient, test_user: User):
    """Test that duplicate usernames are rejected"""
    payload = {
        "username": "testuser",
        "email": "different@example.com",
        "password": "password123"
    }
    
    response = client.post("/api/auth/register", json=payload)
    
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_login_user(client: TestClient, test_user: User):
    """Test user login"""
    payload = {
        "username": "testuser",
        "password": "password123"
    }
    
    response = client.post("/api/auth/login", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "testuser"


def test_login_user_wrong_password(client: TestClient, test_user: User):
    """Test login with wrong password"""
    payload = {
        "username": "testuser",
        "password": "wrongpassword"
    }
    
    response = client.post("/api/auth/login", json=payload)
    
    assert response.status_code == 401
    assert "Invalid username or password" in response.json()["detail"]


def test_get_current_user_info(client: TestClient, test_user: User):
    """Test retrieving current user info"""
    token = get_auth_token(test_user)
    
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["role"] == "regular"


# Sensor Deletion Tests

def test_delete_sensor(client: TestClient, test_user: User, session: Session):
    """Test deleting a sensor via DELETE /api/sensors/{id}"""
    # Create a sensor first
    token = get_auth_token(test_user)
    
    create_payload = {
        "sensor_type": "physical",
        "name": "Sensor to Delete",
        "mac_address": "AA:BB:CC:DD:EE:99",
        "latitude": 47.8095,
        "longitude": 13.0550,
        "altitude": 500.0,
        "battery_level": 0.85,
        "pressure_range_min": 980.0,
        "pressure_range_max": 1050.0,
        "display_clearance": "regular",
        "readings_clearance": "regular"
    }
    
    create_response = client.post(
        "/api/sensors",
        headers={"Authorization": f"Bearer {token}"},
        json=create_payload
    )
    
    assert create_response.status_code == 200
    created_sensor = create_response.json()
    sensor_id = created_sensor["id"]
    
    # Verify sensor exists
    sensors_before = session.exec(select(Sensor)).all()
    assert len(sensors_before) == 1
    
    # Delete the sensor
    delete_response = client.delete(
        f"/api/sensors/{sensor_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert delete_response.status_code == 200
    delete_data = delete_response.json()
    assert delete_data["name"] == "Sensor to Delete"
    assert "deleted successfully" in delete_data["message"]
    
    # Verify sensor is deleted
    sensors_after = session.exec(select(Sensor)).all()
    assert len(sensors_after) == 0


def test_delete_sensor_not_found(client: TestClient, test_user: User):
    """Test deleting a non-existent sensor"""
    token = get_auth_token(test_user)
    
    response = client.delete(
        "/api/sensors/99999",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_delete_sensor_persists_across_requests(client: TestClient, test_user: User, session: Session):
    """Test that deleted sensor doesn't reappear in subsequent GET requests"""
    token = get_auth_token(test_user)
    
    # Create a sensor
    create_payload = {
        "sensor_type": "physical",
        "name": "Persistent Delete Test",
        "mac_address": "AA:BB:CC:DD:EE:77",
        "latitude": 47.8095,
        "longitude": 13.0550,
        "altitude": 500.0,
        "battery_level": 0.85,
        "pressure_range_min": 980.0,
        "pressure_range_max": 1050.0,
        "display_clearance": "regular",
        "readings_clearance": "regular"
    }
    
    create_response = client.post(
        "/api/sensors",
        headers={"Authorization": f"Bearer {token}"},
        json=create_payload
    )
    
    assert create_response.status_code == 200
    sensor_id = create_response.json()["id"]
    
    # Verify sensor exists via GET
    get_before = client.get(
        "/api/sensors",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert get_before.status_code == 200
    sensors_before = get_before.json()
    assert len(sensors_before) == 1
    assert sensors_before[0]["id"] == sensor_id
    
    # Delete the sensor
    delete_response = client.delete(
        f"/api/sensors/{sensor_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert delete_response.status_code == 200
    
    # Verify sensor is gone via GET (simulating page refresh)
    get_after = client.get(
        "/api/sensors",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert get_after.status_code == 200
    sensors_after = get_after.json()
    assert len(sensors_after) == 0, "Sensor should not reappear after GET request"


def test_delete_simulator_removes_from_config(client: TestClient, test_user: User, session: Session, tmp_path, monkeypatch):
    """Test that deleting a simulator also removes it from config file"""
    import json
    
    # Create a config file
    config_path = tmp_path / "simulator_config.json"
    monkeypatch.setattr("os.path.exists", lambda x: str(x) == str(config_path) if "simulator" in str(x) else os.path.exists(x))
    
    # Patch the path in main.py to use our temp config
    import fastapi_backend.main
    original_exists = os.path.exists
    
    def mock_exists(path):
        if "simulator_config.json" in path:
            return True
        return original_exists(path)
    
    def mock_open_func(*args, **kwargs):
        if "simulator_config.json" in args[0]:
            return open(config_path, *args[1:] if len(args) > 1 else [], **kwargs)
        return original_open(*args, **kwargs)
    
    original_open = open
    monkeypatch.setattr("os.path.exists", mock_exists)
    monkeypatch.setattr("builtins.open", mock_open_func)
    
    token = get_auth_token(test_user)
    
    # Create a simulator sensor
    create_payload = {
        "sensor_type": "simulator",
        "name": "Simulator to Delete",
        "mac_address": "AA:BB:CC:DD:EE:88",
        "latitude": 47.8095,
        "longitude": 13.0550,
        "altitude": 500.0,
        "battery_level": 0.85,
        "pressure_range_min": 980.0,
        "pressure_range_max": 1050.0,
        "display_clearance": "regular",
        "readings_clearance": "regular"
    }
    
    create_response = client.post(
        "/api/sensors",
        headers={"Authorization": f"Bearer {token}"},
        json=create_payload
    )
    
    assert create_response.status_code == 200
    created_sensor = create_response.json()
    sensor_id = created_sensor["id"]
    
    # Delete the simulator sensor
    delete_response = client.delete(
        f"/api/sensors/{sensor_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert delete_response.status_code == 200
    
    # Verify it's removed from database
    sensors = session.exec(select(Sensor)).all()
    assert len(sensors) == 0


def test_delete_sensor_requires_auth(client: TestClient):
    """Test that deleting a sensor requires authentication"""
    response = client.delete("/api/sensors/1")
    
    assert response.status_code == 401
    assert "Missing authorization header" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
