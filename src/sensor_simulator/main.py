from dataclasses import dataclass, asdict
from datetime import datetime

import json
import logging
import logging.handlers
import os
import random
import time
import math
import paho.mqtt.client as mqtt
import sys
import traceback

"""
A sensor simulator sending simulated sensor data

Authors: Martin Koeck, Paolo Arcilla
Date:	2026/01/21
"""

# Configure logging
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# main logger
log_path = os.path.join(LOG_DIR, "pressure_logger.log")
logging.basicConfig(
	level=os.getenv("LOG_LEVEL", "INFO"),
	format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
	handlers=[
		logging.StreamHandler(),
		logging.handlers.WatchedFileHandler(log_path)
	]
)
logger = logging.getLogger(__name__)


# crash logger
def handle_crash(exc_type, exc_value, exc_tb):
    # Skip KeyboardInterrupt (Ctrl+C) — not a real crash
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Option 1 (recommended - cleanest):
    crash_dir = os.path.abspath(os.path.join(LOG_DIR, "..", "crashlogs"))


    os.makedirs(crash_dir, exist_ok=True)

    crash_filename = f"crash_{timestamp}.log"
    crash_path = os.path.join(crash_dir, crash_filename)

    # Create a dedicated crash logger
    crash_logger = logging.getLogger("crash")
    crash_logger.setLevel(logging.DEBUG)

    # Remove any old handlers to avoid duplicates
    for handler in crash_logger.handlers[:]:
        crash_logger.removeHandler(handler)

    crash_handler = logging.FileHandler(crash_path, mode='w', encoding='utf-8')
    crash_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"
    ))
    crash_logger.addHandler(crash_handler)

    # Log the crash
    crash_logger.critical("=== UNHANDLED EXCEPTION - APPLICATION CRASHED ===")
    crash_logger.critical("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))

    # Also inform the main logger
    logger.critical("Application crashed! Full crash report written to: %s", crash_path)

    crash_handler.flush()
    crash_handler.close()

    # Optional: re-raise so Docker sees the container as crashed
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = handle_crash


if os.getenv("SIMULATE_CRASH", "0") == "1":
    logger.error("Simulating a crash for testing...")
    raise RuntimeError("Intentional crash for crash-logging test\nAdjust sensor_simulator's environment variable SIMULATE_CRASH in docker-compose.yml to circumvent this.")


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
		self.mqtt_broker = mqtt_broker
		self.mqtt_port = mqtt_port
		self.client = mqtt.Client()
		self.client.on_connect = self._on_connect
		self.client.on_disconnect = self._on_disconnect
		self._connect_with_retry()
		self.client.loop_start()
		# likelihood modifier used by _maybe_decrease_battery; smaller means
		# slower accumulation of probability.  A realistic value might be
		# ~0.005 so that it takes dozens of messages before drain becomes
		# likely.  This is tunable for different sensor characteristics.
		self.battery_decrease_likelihood_modifier = 0.005
		self.messages_sent_since_last_battery_decrease = 0
		self.battery = random.uniform(0.2, 1.0)
		self.latitude = 47.8095 + random.uniform(-0.01, 0.01)
		self.longitude = 13.0550 + random.uniform(-0.01, 0.01)

		self.expected_range = [980.0, 1050.0]

	def _connect_with_retry(self, max_retries=10, initial_delay=1):
		"""Connect to MQTT broker with exponential backoff retry"""
		delay = initial_delay
		for attempt in range(max_retries):
			try:
				logger.info(f"Connecting sensor {self.mac} to MQTT broker {self.mqtt_broker}:{self.mqtt_port} (attempt {attempt + 1}/{max_retries})")
				self.client.connect(self.mqtt_broker, self.mqtt_port)
				logger.info(f"Sensor {self.mac} connection initiated successfully")
				return
			except ConnectionRefusedError:
				if attempt < max_retries - 1:
					logger.warning(f"Connection refused for sensor {self.mac}, retrying in {delay}s...")
					time.sleep(delay)
					delay = min(delay * 2, 30)  # Exponential backoff, max 30s
				else:
					logger.error(f"Failed to connect sensor {self.mac} after {max_retries} attempts")
					raise
			except Exception as e:
				logger.error(f"Unexpected error connecting sensor {self.mac}: {e}")
				raise

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
		if self.battery <= 0:
			logger.debug(f"Battery of sensor {self.mac} is dead, cannot send status")
			return
		status = SensorStatus(
			mac=self.mac,
			battery=self.battery,
			latitude=self.latitude,
			longitude=self.longitude,
			timestamp=datetime.now().isoformat()
		)
		self.client.publish("sensors/status", json.dumps(asdict(status)))
		logger.info(f"Sensor {self.mac} sent status: battery={status.battery:.2f}, location=({status.latitude:.4f}, {status.longitude:.4f})")
		# battery usage may happen on either status or measurement send
		self._maybe_decrease_battery()
			

	def send_measurement(self):
		"""
		Sends simulated measurement data
		"""
		# do not send if battery is dead
		if self.battery <= 0:
			logger.debug(f"Battery of sensor {self.mac} is dead; cannot send measurement")
			return
		# sample pressure from normal distribution centered on range midpoint
		mean = sum(self.expected_range) / 2
		std_dev = (self.expected_range[1] - self.expected_range[0]) / 4
		pressure = random.gauss(mean, std_dev)
		is_in_range = self.expected_range[0] <= pressure <= self.expected_range[1]
		measurement = MeasurementData(
			mac=self.mac,
			pressure=pressure,
			timestamp=datetime.now().isoformat()
		)
		# include out-of-range indicator in the published message
		measurement_dict = asdict(measurement)
		measurement_dict['out_of_range'] = not is_in_range
		self.client.publish("measurement/data", json.dumps(measurement_dict))
		logger.debug(f"Sensor {self.mac} sent measurement: {measurement.pressure:.2f} hPa (in_range={is_in_range})")
		# possibility of draining battery on each packet
		self._maybe_decrease_battery()
	
	def disconnect(self):
		"""Disconnect from MQTT broker"""
		logger.info(f"Disconnecting sensor {self.mac}")
		self.client.loop_stop()
		self.client.disconnect()

	def _maybe_decrease_battery(self, amount: float = 0.01):
		"""Decide whether to lower battery based on message count.

		Probability starts near zero and asymptotically approaches 1 as
		`messages_sent_since_last_battery_decrease` grows.  After a drop we
		reset the counter.  This gives a realistic feeling of occasional
		battery use without a decrement on every transmission.
		"""
		# increment before computing probability so first call has nonzero chance
		self.messages_sent_since_last_battery_decrease += 1
		# Use an exponential CDF: p = 1 - exp(-lambda * n)
		lam = self.battery_decrease_likelihood_modifier
		p = 1 - math.exp(-lam * self.messages_sent_since_last_battery_decrease)
		if random.random() < p:
			old = self.battery
			self.battery = max(0, self.battery - amount)
			logger.debug(f"Battery drain triggered for sensor {self.mac}: {old:.3f} -> {self.battery:.3f}")
			self.messages_sent_since_last_battery_decrease = 0

def main():
	# Get configuration from environment
	mqtt_broker = os.getenv("MQTT_BROKER", "mqtt_broker")
	mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
	
	# Create three sensors with different MAC addresses
	sensors: list[SensorSimulator] = [
		SensorSimulator("AA:BB:CC:00:11:22", mqtt_broker, mqtt_port),
		SensorSimulator("AA:BB:CC:00:11:23", mqtt_broker, mqtt_port),
		SensorSimulator("AA:BB:CC:00:11:24", mqtt_broker, mqtt_port),
	]
	
	logger.info(f"Started {len(sensors)} sensor simulators")
	
	# Send initial status for all sensors
	logger.info("Sending initial status updates...")
	for sensor in sensors:
		sensor.send_status()
	
	try:
		measurement_counter = 0
		while True:
			# Send measurements every second
			for sensor in sensors:
				sensor.send_measurement()
			measurement_counter += 1
			
			# Send status every 10 seconds
			# This may be a bit unrealistic, but I thought a shorter time might be better for
			# testing and observation purposes.
			if measurement_counter % 10 == 0:
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