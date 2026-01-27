from dataclasses import dataclass, asdict
from datetime import datetime

import json
import logging
import os
import random
import time
import paho.mqtt.client as mqtt

"""
A sensor simulator sending simulated sensor data

Authors: Martin Koeck, Paolo Arcilla
Date:	2026/01/21
"""

# Configure logging
logging.basicConfig(
	level=os.getenv("LOG_LEVEL", "INFO"),
	format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

"""
Topic: sensors/status
{
  "mac": "AA:BB:CC:00:11:22",
  "battery": 0.85,
  "latitude": 47.8095,
  "longitude": 13.0550,
  "timestamp": "2023-10-27T10:00:00"
}

Topic: measurement/data
{
  "mac": "AA:BB:CC:00:11:22",
  "pressure": 1013.25,
  "timestamp": "2023-10-27T10:00:01" # ISO 8601 format
}
"""


@dataclass
class SensorStatus:
	"""
	Class to convey status data as sent by a SensorSimulator object

	Attributes:
		mac(str): The physical address of the sensor
		battery(float): The current battery levels with 1.0 = 100%
		latitude(float): The latitude of the sensor's coordinates at time of transmission
		longitude(float): The longitude of the sensor's coordinates at time of transmission
		timestamp(str): Time of transmission
	"""
	mac: str
	battery: float
	latitude: float
	longitude: float
	timestamp: str

@dataclass
class MeasurementData:
	""""""
	mac: str
	pressure: float
	timestamp: str

class SensorSimulator:
	"""
	Class for simulating a sensor with the ability to publish its status or readings
	"""
	def __init__(self, mac: str, mqtt_broker: str, mqtt_port: int):
		self.mac = mac
		self.client = mqtt.Client()
		self.client.on_connect = self._on_connect
		self.client.on_disconnect = self._on_disconnect
		logger.info(f"Connecting sensor {mac} to MQTT broker {mqtt_broker}:{mqtt_port}")
		self.client.connect(mqtt_broker, mqtt_port)
		self.client.loop_start()

	def _on_connect(self, client, userdata, flags, rc):
		"""Callback when connected to MQTT broker"""
		if rc == 0:
			logger.info(f"Sensor {self.mac} connected to MQTT broker")
		else:
			logger.error(f"Sensor {self.mac} failed to connect. Return code: {rc}")

	def _on_disconnect(self, client, userdata, rc):
		"""Callback when disconnected from MQTT broker"""
		if rc != 0:
			logger.warning(f"Sensor {self.mac} unexpected disconnect. Return code: {rc}")

	def send_status(self):
		"""
		Sends simulated sensor status
		"""
		status = SensorStatus(
			mac=self.mac,
			battery=random.uniform(0.2, 1.0),
			latitude=47.8095 + random.uniform(-0.01, 0.01),
			longitude=13.0550 + random.uniform(-0.01, 0.01),
			timestamp=datetime.now().isoformat()
		)
		self.client.publish("sensors/status", json.dumps(asdict(status)))
		logger.info(f"Sensor {self.mac} sent status: battery={status.battery:.2f}, location=({status.latitude:.4f}, {status.longitude:.4f})")

	def send_measurement(self):
		"""
		Sends simulated measurement data
		"""
		measurement = MeasurementData(
			mac=self.mac,
			pressure=random.uniform(980.0, 1050.0),
			timestamp=datetime.now().isoformat()
		)
		self.client.publish("measurement/data", json.dumps(asdict(measurement)))
		logger.debug(f"Sensor {self.mac} sent measurement: {measurement.pressure:.2f} hPa")
	
	def disconnect(self):
		"""Disconnect from MQTT broker"""
		logger.info(f"Disconnecting sensor {self.mac}")
		self.client.loop_stop()
		self.client.disconnect()

def main():
	# Get configuration from environment
	mqtt_broker = os.getenv("MQTT_BROKER", "mqtt_broker")
	mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
	
	# Create three sensors with different MAC addresses
	sensors = [
		SensorSimulator("AA:BB:CC:00:11:22", mqtt_broker, mqtt_port),
		SensorSimulator("AA:BB:CC:00:11:23", mqtt_broker, mqtt_port),
		SensorSimulator("AA:BB:CC:00:11:24", mqtt_broker, mqtt_port),
	]
	
	logger.info(f"Started {len(sensors)} sensor simulators")
	
	# Wait for connections to establish
	time.sleep(2)
	
	try:
		measurement_counter = 0
		while True:
			# Send measurements every second
			for sensor in sensors:
				sensor.send_measurement()
			measurement_counter += 1
			
			# Send status every 5 minutes (300 seconds)
			if measurement_counter % 300 == 0:
				for sensor in sensors:
					sensor.send_status()
				logger.info("Status update sent for all sensors")
			
			time.sleep(1)
	
	except KeyboardInterrupt:
		logger.info("Shutting down sensor simulators...")
	except Exception as e:
		logger.error(f"Error in sensor simulator: {e}", exc_info=True)
	finally:
		for sensor in sensors:
			sensor.disconnect()
		logger.info("All sensors disconnected")

if __name__ == "__main__":
	main()