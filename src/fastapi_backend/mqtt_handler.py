# mqtt_handler.py
import asyncio
import json
import logging
import os
import threading
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from sqlmodel import Session, select

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from postgres_database.database import engine
from .models import Sensor, Measurement

# Configure logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


class MQTTHandler:
    """
    Handles MQTT connections and message processing for sensor data
    """
    def __init__(self, broker: str, port: int, broadcast_callback=None):
        self.broker = broker
        self.port = port
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.is_running = False
        self._thread = None
        self.broadcast_callback = broadcast_callback
        
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
            # Subscribe to topics
            client.subscribe("sensors/status")
            client.subscribe("measurement/data")
            logger.info("Subscribed to topics: sensors/status, measurement/data")
        else:
            logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker. Return code: {rc}")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """Callback when a message is received"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            logger.debug(f"Received message on topic '{topic}': {payload}")
            
            # Parse JSON payload
            data = json.loads(payload)
            
            if topic == "sensors/status":
                self._handle_sensor_status(data)
            elif topic == "measurement/data":
                self._handle_measurement_data(data)
            else:
                logger.warning(f"Received message on unknown topic: {topic}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON payload: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
    
    def _handle_sensor_status(self, data: dict):
        """
        Handle sensor status updates
        Creates or updates sensor information in the database
        """
        try:
            mac = data.get("mac")
            battery = data.get("battery")
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            timestamp = data.get("timestamp")
            
            if not mac:
                logger.error("Sensor status missing MAC address")
                return
            
            logger.info(f"Processing status update for sensor {mac}")
            
            with Session(engine) as session:
                # Find or create sensor
                statement = select(Sensor).where(Sensor.mac_address == mac)
                sensor = session.exec(statement).first()
                
                if sensor:
                    # Update existing sensor
                    if battery is not None:
                        sensor.battery_level = battery
                    if latitude is not None:
                        sensor.latitude = latitude
                    if longitude is not None:
                        sensor.longitude = longitude
                    logger.info(f"Updated sensor {mac} - Battery: {battery}, Location: ({latitude}, {longitude})")
                else:
                    # Create new sensor
                    sensor = Sensor(
                        mac_address=mac,
                        name=f"Sensor {mac}",
                        battery_level=battery if battery is not None else 1.0,
                        latitude=latitude if latitude is not None else 0.0,
                        longitude=longitude if longitude is not None else 0.0
                    )
                    session.add(sensor)
                    logger.info(f"Created new sensor {mac}")
                
                session.commit()
                logger.debug(f"Successfully saved sensor status for {mac}")
                
        except Exception as e:
            logger.error(f"Error handling sensor status: {e}", exc_info=True)
    
    def _handle_measurement_data(self, data: dict):
        """
        Handle measurement data
        Creates sensor if needed and saves measurement to database
        """
        try:
            mac = data.get("mac")
            pressure = data.get("pressure")
            timestamp_str = data.get("timestamp")
            
            if not mac or pressure is None:
                logger.error("Measurement data missing MAC address or pressure")
                return
            
            logger.info(f"Processing measurement for sensor {mac}: {pressure} hPa")
            
            with Session(engine) as session:
                # Find or create sensor
                statement = select(Sensor).where(Sensor.mac_address == mac)
                sensor = session.exec(statement).first()
                
                if not sensor:
                    # Create sensor if it doesn't exist
                    sensor = Sensor(
                        mac_address=mac,
                        name=f"Sensor {mac}",
                        battery_level=1.0,
                        latitude=0.0,
                        longitude=0.0
                    )
                    session.add(sensor)
                    session.commit()
                    session.refresh(sensor)
                    logger.info(f"Created new sensor {mac} from measurement data")
                
                # Create measurement
                measurement = Measurement(
                    sensor_id=sensor.id,
                    pressure=pressure,
                    created_at=datetime.now(timezone.utc)
                )
                session.add(measurement)
                session.commit()
                logger.debug(f"Saved measurement: sensor_id={sensor.id}, pressure={pressure}")
                
                # Broadcast to WebSocket clients
                if self.broadcast_callback:
                    broadcast_data = {
                        "type": "measurement",
                        "sensor_id": sensor.id,
                        "mac_address": sensor.mac_address,
                        "sensor_name": sensor.name,
                        "pressure": pressure,
                        "timestamp": measurement.created_at.isoformat()
                    }
                    asyncio.create_task(self.broadcast_callback(broadcast_data))
                
        except Exception as e:
            logger.error(f"Error handling measurement data: {e}", exc_info=True)
    
    def start(self):
        """Start the MQTT client in a background thread"""
        if self.is_running:
            logger.warning("MQTT handler already running")
            return
        
        try:
            logger.info(f"Connecting to MQTT broker at {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, keepalive=60)
            self.is_running = True
            
            # Start the network loop in a background thread
            self._thread = threading.Thread(target=self.client.loop_forever, daemon=True)
            self._thread.start()
            logger.info("MQTT client started in background thread")
            
        except Exception as e:
            logger.error(f"Failed to start MQTT client: {e}", exc_info=True)
            raise
    
    def stop(self):
        """Stop the MQTT client"""
        if not self.is_running:
            return
        
        logger.info("Stopping MQTT client...")
        self.is_running = False
        self.client.disconnect()
        self.client.loop_stop()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        
        logger.info("MQTT client stopped")
