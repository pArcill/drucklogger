import json
import os
import sys
from datetime import datetime

import pytest

# Ensure src is on the import path so we can import the simulator module
# __file__ is .../src/test/test_sensor_simulator.py, so going up two levels
# gives us the src directory, which contains the sensor_simulator package.
SRC_PATH = os.path.dirname(os.path.dirname(__file__))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

import sensor_simulator.main as sensor_main

class FakeMqttClient:
    def __init__(self):
        self.connected_to = None
        self.published = []  # list of (topic, payload)
        self.on_connect = None
        self.on_disconnect = None
        self._loop_started = False

    def connect(self, host, port):
        self.connected_to = (host, port)
        # Simulate successful connection callback
        if self.on_connect:
            self.on_connect(self, None, None, 0)

    def publish(self, topic, payload):
        self.published.append((topic, payload))

    def loop_start(self):
        self._loop_started = True

    def loop_stop(self):
        self._loop_started = False

    def disconnect(self):
        pass

def _setup_simulator_with_fake_client(monkeypatch):
    fake_client = FakeMqttClient()

    def fake_client_factory():
        return fake_client

    # Patch the mqtt.Client used inside sensor_main
    monkeypatch.setattr(sensor_main.mqtt, "Client", lambda: fake_client)

    simulator = sensor_main.SensorSimulator(
        mac="AA:BB:CC:00:11:22",
        mqtt_broker="test-broker",
        mqtt_port=1883,
    )

    return simulator, fake_client


def test_send_status_publishes_valid_status(monkeypatch):
    """Ensure status messages publish a single valid payload within expected ranges."""
    simulator, fake_client = _setup_simulator_with_fake_client(monkeypatch)

    simulator.send_status()

    assert len(fake_client.published) == 1
    topic, payload = fake_client.published[0]
    assert topic == "sensors/status"

    data = json.loads(payload)

    # Basic structure and values
    assert data["mac"] == "AA:BB:CC:00:11:22"
    assert 0.2 <= data["battery"] <= 1.0
    assert 47.7995 <= data["latitude"] <= 47.8195
    assert 13.0450 <= data["longitude"] <= 13.0650

    # Timestamp should be valid ISO 8601
    dt = datetime.fromisoformat(data["timestamp"])
    assert isinstance(dt, datetime)


def test_send_status_uses_random_upper_bounds(monkeypatch):
    """Verify patched random.uniform upper bounds propagate into status payload."""
    simulator, fake_client = _setup_simulator_with_fake_client(monkeypatch)

    # Force random.uniform to always return the upper bound
    def fake_uniform(low, high):
        return high

    monkeypatch.setattr(sensor_main.random, "uniform", fake_uniform)

    simulator.send_status()

    assert len(fake_client.published) == 1
    _, payload = fake_client.published[0]
    data = json.loads(payload)

    # With fake_uniform, we know exact values
    assert data["battery"] == pytest.approx(1.0)
    assert data["latitude"] == pytest.approx(47.8095 + 0.01)
    assert data["longitude"] == pytest.approx(13.0550 + 0.01)


def test_send_measurement_publishes_valid_measurement(monkeypatch):
    """Confirm measurement topic receives realistic pressure values and timestamps."""
    simulator, fake_client = _setup_simulator_with_fake_client(monkeypatch)

    simulator.send_measurement()

    assert len(fake_client.published) == 1
    topic, payload = fake_client.published[0]
    assert topic == "measurement/data"

    data = json.loads(payload)

    assert data["mac"] == "AA:BB:CC:00:11:22"
    assert 980.0 <= data["pressure"] <= 1050.0

    dt = datetime.fromisoformat(data["timestamp"])
    assert isinstance(dt, datetime)


def test_sensor_simulator_connects_on_init(monkeypatch):
    """Check __init__ triggers MQTT connection with provided broker coordinates."""
    fake_client = FakeMqttClient()

    monkeypatch.setattr(sensor_main.mqtt, "Client", lambda: fake_client)

    simulator = sensor_main.SensorSimulator(
        mac="AA:BB:CC:00:11:22",
        mqtt_broker="my-broker",
        mqtt_port=1234,
    )

    # Object is used just to ensure __init__ ran
    assert isinstance(simulator, sensor_main.SensorSimulator)
    assert fake_client.connected_to == ("my-broker", 1234)
