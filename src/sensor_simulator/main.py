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

# Try to import database modules, but don't fail if not available
# (sensor_simulator may run standalone without database access)
DATABASE_AVAILABLE = False
engine = None
Session = None
Sensor = None

try:
	sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
	from postgres_database.database import engine, create_db_and_tables
	from fastapi_backend.models import Sensor
	from sqlmodel import Session, select
	DATABASE_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as e:
	import traceback
	# Print to stderr so it appears in logs
	print(f"WARNING: Database modules not available: {e}", file=sys.stderr)
	print(traceback.format_exc(), file=sys.stderr)



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

# Log database availability
if DATABASE_AVAILABLE:
	logger.info("Database modules available - will load simulators from database")
else:
	logger.warning("Database modules not available - will use hardcoded sensors only")


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
		altitude(float): The altitude of the sensor in meters above sea level
		display_clearance(str): Clearance level for viewing sensor on map
		readings_clearance(str): Clearance level for viewing sensor readings
		timestamp(str): Time of transmission
	"""
	mac: str
	battery: float
	latitude: float
	longitude: float
	altitude: float
	display_clearance: str
	readings_clearance: str
	timestamp: str

@dataclass
class MeasurementData:
	"""
	Class to convey measurement data as sent by a SensorSimulator object

	Attributes:
		mac(str): The physical address of the sensor
		pressure(float): The measured pressure value in hPa
		display_clearance(str): Clearance level for viewing sensor on map
		readings_clearance(str): Clearance level for viewing sensor readings
		timestamp(str): Time of measurement
	"""
	mac: str
	pressure: float
	display_clearance: str
	readings_clearance: str
	timestamp: str

class SensorSimulator:
	"""
	Class for simulating a sensor with the ability to publish its status or readings
	"""
	def __init__(self, mac: str, mqtt_broker: str, mqtt_port: int, display_clearance = "regular", readings_clearance = "regular"):
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
		self.altitude = random.uniform(200.0, 1500.0)  # Meters above sea level
		self.display_clearance: str = display_clearance  # Who can see the sensor on map
		self.readings_clearance: str = readings_clearance  # Who can view readings

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
			altitude=self.altitude,
			display_clearance=self.display_clearance,
			readings_clearance=self.readings_clearance,
			timestamp=datetime.now().isoformat()
		)
		self.client.publish("sensors/status", json.dumps(asdict(status)))
		logger.info(f"Sensor {self.mac} sent status: battery={status.battery:.2f}, location=({status.latitude:.4f}, {status.longitude:.4f}), altitude={status.altitude:.1f}m")
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
			display_clearance=self.display_clearance,
			readings_clearance=self.readings_clearance,
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

def load_simulators_from_db(mqtt_broker, mqtt_port, running_simulators):
	"""Load simulator sensors from the database"""
	try:
		with Session(engine) as session:
			# Query for all sensors with type "simulator"
			simulators = session.exec(select(Sensor).where(Sensor.sensor_type == "simulator")).all()
			loaded_count = 0
			
			for sensor in simulators:
				if sensor.mac_address in running_simulators:
					continue
				
				try:
					simulator = SensorSimulator(
						mac=sensor.mac_address,
						mqtt_broker=mqtt_broker,
						mqtt_port=mqtt_port,
						display_clearance=sensor.display_clearance,
						readings_clearance=sensor.readings_clearance
					)
					simulator.latitude = sensor.latitude
					simulator.longitude = sensor.longitude
					simulator.altitude = sensor.altitude
					simulator.battery = sensor.battery_level
					
					running_simulators[sensor.mac_address] = simulator
					logger.info(f"Loaded simulator {sensor.mac_address} from database")
					loaded_count += 1
				except Exception as e:
					logger.error(f"Failed to create simulator for {sensor.mac_address}: {e}")
			
			return loaded_count
	except Exception as e:
		logger.error(f"Error loading simulators from database: {e}")
		return 0

def load_simulators_from_config(mqtt_broker, mqtt_port, running_simulators):
	"""Load simulator configurations from JSON file"""
	config_path = "/app/simulator_config.json"
	
	# Try alternate paths if the standard one doesn't exist
	if not os.path.exists(config_path):
		config_path = "simulator_config.json"
	if not os.path.exists(config_path):
		config_path = "../simulator_config.json"
	if not os.path.exists(config_path):
		logger.warning(f"No simulator config file found at {config_path}")
		return 0
	
	try:
		with open(config_path, 'r') as f:
			config_data = json.load(f)
		
		simulators_config = config_data.get("simulators", [])
		loaded_count = 0
		
		for sim_config in simulators_config:
			mac = sim_config.get("mac")
			if not mac or mac in running_simulators:
				continue
			
			try:
				simulator = SensorSimulator(
					mac=mac,
					mqtt_broker=mqtt_broker,
					mqtt_port=mqtt_port,
					display_clearance=sim_config.get("display_clearance", "regular"),
					readings_clearance=sim_config.get("readings_clearance", "regular")
				)
				simulator.latitude = sim_config.get("latitude", 47.0)
				simulator.longitude = sim_config.get("longitude", 13.0)
				simulator.altitude = sim_config.get("altitude", 0.0)
				simulator.battery = sim_config.get("battery_level", 1.0)
				simulator.expected_range = sim_config.get("expected_range", [980.0, 1050.0])
				
				running_simulators[mac] = simulator
				logger.info(f"Loaded simulator {mac} from config file")
				loaded_count += 1
			except Exception as e:
				logger.error(f"Failed to create simulator for {mac}: {e}")
		
		return loaded_count
	except Exception as e:
		logger.error(f"Error loading simulator config: {e}")
		return 0

def sync_config_simulators_to_database(running_simulators):
	"""Sync running simulators from config file to database so they appear in the UI"""
	if not DATABASE_AVAILABLE:
		return 0
	
	try:
		with Session(engine) as session:
			synced_count = 0
			
			for mac, simulator in running_simulators.items():
				# Check if sensor exists in database
				existing = session.exec(
					select(Sensor).where(Sensor.mac_address == mac)
				).first()
				
				if not existing:
					# Create sensor record for this simulator
					sensor = Sensor(
						mac_address=mac,
						name=f"Simulator {mac}",
						sensor_type="simulator",
						latitude=simulator.latitude,
						longitude=simulator.longitude,
						altitude=simulator.altitude,
						battery_level=simulator.battery,
						display_clearance=simulator.display_clearance,
						readings_clearance=simulator.readings_clearance
					)
					session.add(sensor)
					synced_count += 1
					logger.info(f"Synced simulator {mac} to database (was in config file)")
			
			if synced_count > 0:
				session.commit()
				logger.info(f"Synced {synced_count} simulator(s) from config to database")
			
			return synced_count
	except Exception as e:
		logger.error(f"Error syncing config simulators to database: {e}")
		return 0

def remove_deleted_simulators(running_simulators):
	"""Remove simulators for sensors that have been deleted from the database"""
	if not DATABASE_AVAILABLE:
		return 0
	
	try:
		with Session(engine) as session:
			# Get all simulator sensors currently in database
			active_simulators = session.exec(select(Sensor).where(Sensor.sensor_type == "simulator")).all()
			active_macs = {sensor.mac_address for sensor in active_simulators}
			
			# Find simulators that are no longer in database
			running_macs = set(running_simulators.keys())
			deleted_macs = running_macs - active_macs
			
			removed_count = 0
			for mac in deleted_macs:
				try:
					simulator = running_simulators[mac]
					simulator.disconnect()
					del running_simulators[mac]
					logger.info(f"Removed simulator {mac} (sensor was deleted from database)")
					removed_count += 1
				except Exception as e:
					logger.error(f"Error removing simulator {mac}: {e}")
			
			return removed_count
	except Exception as e:
		logger.error(f"Error checking for deleted simulators: {e}")
		return 0

def main():
	"""
	Main sensor simulator loop.
	Loads simulator sensors from the config file or database and runs them continuously.
	Falls back to hardcoded sensors if no sensors are found.
	"""
	# Initialize database if available
	if DATABASE_AVAILABLE:
		try:
			create_db_and_tables()
			logger.info("Database initialized")
		except Exception as e:
			logger.warning(f"Could not initialize database: {e}. Will use config file or hardcoded sensors.")
	
	mqtt_broker = os.getenv("MQTT_BROKER", "mqtt_broker")
	mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
	
	# Dictionary to track running simulator instances by MAC address
	running_simulators: dict[str, SensorSimulator] = {}
	last_db_check = 0
	db_check_interval = 5  # Check for new simulators every 5 seconds
	
	# Try to load simulators from config file first
	logger.info("Attempting to load simulators from config file...")
	loaded = load_simulators_from_config(mqtt_broker, mqtt_port, running_simulators)
	
	# If database is available and no config file simulators, try database
	if loaded == 0 and DATABASE_AVAILABLE:
		logger.info("No simulators in config file. Attempting to load from database...")
		loaded = load_simulators_from_db(mqtt_broker, mqtt_port, running_simulators)
	
	# Log the result
	if loaded == 0:
		logger.warning("No simulators found in config file or database. Running without simulators.")
		logger.warning("Please add simulators via the API or provide a simulator_config.json file.")
	else:
		logger.info(f"Started {len(running_simulators)} simulator(s) from config file or database")
	
	# Sync config file simulators to database so they appear in UI
	if DATABASE_AVAILABLE and running_simulators:
		synced = sync_config_simulators_to_database(running_simulators)
		if synced > 0:
			logger.info(f"Synced {synced} simulator(s) to database on startup")
	
	# Send initial status for all sensors
	logger.info("Sending initial status updates...")
	for simulator in running_simulators.values():
		try:
			simulator.send_status()
		except Exception as e:
			logger.error(f"Error sending initial status for {simulator.mac}: {e}")
	
	try:
		measurement_counter = 0
		while True:
			# Periodically check for new/deleted simulators (every 5 seconds)
			now = time.time()
			if now - last_db_check >= db_check_interval:
				# Check for and remove deleted simulators first
				if DATABASE_AVAILABLE:
					removed = remove_deleted_simulators(running_simulators)
					if removed > 0:
						logger.info(f"Removed {removed} simulator(s) that were deleted from database")
				
				# Load new simulators from both config file and database
				newly_loaded_macs = []
				
				# Always check config file for new entries
				initial_count = len(running_simulators)
				load_simulators_from_config(mqtt_broker, mqtt_port, running_simulators)
				config_newly_loaded = len(running_simulators) - initial_count
				if config_newly_loaded > 0:
					logger.info(f"Loaded {config_newly_loaded} new simulator(s) from config file")
					newly_loaded_macs.extend(list(running_simulators.keys())[-config_newly_loaded:])
					# Sync newly loaded config simulators to database
					synced = sync_config_simulators_to_database(running_simulators)
					if synced > 0:
						logger.info(f"Synced {synced} new simulator(s) to database")
				
				# Also check database if available
				if DATABASE_AVAILABLE:
					initial_count = len(running_simulators)
					load_simulators_from_db(mqtt_broker, mqtt_port, running_simulators)
					db_newly_loaded = len(running_simulators) - initial_count
					if db_newly_loaded > 0:
						logger.info(f"Loaded {db_newly_loaded} new simulator(s) from database")
						newly_loaded_macs.extend(list(running_simulators.keys())[-db_newly_loaded:])
				
				# Send initial status for newly loaded sensors
				for mac in newly_loaded_macs:
					try:
						if mac in running_simulators:
							running_simulators[mac].send_status()
					except Exception as e:
						logger.error(f"Error sending status for new simulator {mac}: {e}")
				last_db_check = now
			
			# Send measurements for all running simulators
			for simulator in running_simulators.values():
				try:
					simulator.send_measurement()
				except Exception as e:
					logger.error(f"Error sending measurement for {simulator.mac}: {e}")
			
			measurement_counter += 1
			
			# Send status every 10 seconds
			if measurement_counter % 10 == 0:
				for simulator in running_simulators.values():
					try:
						simulator.send_status()
					except Exception as e:
						logger.error(f"Error sending status for {simulator.mac}: {e}")
				logger.debug(f"Status update sent for {len(running_simulators)} simulator(s)")
			
			time.sleep(1)
	
	except KeyboardInterrupt:
		logger.info("Shutting down sensor simulators...")
	except Exception as e:
		logger.error(f"Error in sensor simulator main loop: {e}", exc_info=True)
	finally:
		for simulator in running_simulators.values():
			try:
				simulator.disconnect()
			except Exception as e:
				logger.error(f"Error disconnecting simulator {simulator.mac}: {e}")
		logger.info("All sensors disconnected")

if __name__ == "__main__":
	main()