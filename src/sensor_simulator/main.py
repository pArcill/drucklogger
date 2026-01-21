from dataclasses import dataclass, asdict
from datetime import datetime

import json
import random
import time
import paho.mqtt.client as mqtt

"""
A sensor simulator sending simulated sensor data

Authors: Martin Koeck, Paolo Arcilla
Date:	2026/01/21
"""

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
		self.client.connect(mqtt_broker, mqtt_port)

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

def main():
	pass

if __name__ == "__main__":
	main()