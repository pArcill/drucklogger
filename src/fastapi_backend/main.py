# main.py
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from postgres_database.database import create_db_and_tables, engine
from .mqtt_handler import MQTTHandler
from .models import Measurement

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO") or "INFO",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global MQTT handler instance
mqtt_handler = None

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending WebSocket message: {e}")

manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for startup and shutdown
    """
    global mqtt_handler
    
    # Startup: Create database tables
    logger.info("Starting application...")
    logger.info("Creating database tables...")
    create_db_and_tables()
    
    # Start MQTT handler
    mqtt_broker = os.getenv("MQTT_BROKER", "mqtt_broker")
    mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
    
    logger.info(f"Initializing MQTT handler for {mqtt_broker}:{mqtt_port}")
    mqtt_handler = MQTTHandler(mqtt_broker, mqtt_port, broadcast_callback=manager.broadcast)
    mqtt_handler.start()
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown: cleanup
    logger.info("Shutting down application...")
    if mqtt_handler:
        mqtt_handler.stop()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Sensor Data API",
    description="API for managing sensor data and measurements",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
def read_root():
    """Root endpoint"""
    logger.debug("Root endpoint accessed")
    return {"message": "Sensor Data API is running"}


@app.get("/health")
def health_check():
    """Health check endpoint"""
    logger.debug("Health check endpoint accessed")
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_handler.is_running if mqtt_handler else False
    }


@app.get("/api/measurements")
def get_latest_measurements(limit: int = 100):
    """Get latest measurements from all sensors"""
    try:
        with Session(engine) as session:
            statement = select(Measurement).order_by(Measurement.created_at.desc()).limit(limit)
            measurements = session.exec(statement).all()
            return [
                {
                    "id": m.id,
                    "sensor_id": m.sensor_id,
                    "sensor_name": m.sensor.name if m.sensor else "Unknown",
                    "pressure": m.pressure,
                    "timestamp": m.created_at.isoformat()
                }
                for m in measurements
            ]
    except Exception as e:
        logger.error(f"Error retrieving measurements: {e}", exc_info=True)
        return {"error": str(e)}, 500


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for streaming pressure data
    Clients connect here to receive real-time measurement updates
    """
    await manager.connect(websocket)
    logger.info(f"WebSocket client connected. Total clients: {len(manager.active_connections)}")
    
    try:
        # Send initial measurements
        with Session(engine) as session:
            statement = select(Measurement).order_by(Measurement.created_at.desc()).limit(50)
            recent_measurements = session.exec(statement).all()
            
            for measurement in reversed(recent_measurements):
                await websocket.send_json({
                    "type": "historical",
                    "sensor_id": measurement.sensor_id,
                    "sensor_name": measurement.sensor.name if measurement.sensor else "Unknown",
                    "pressure": measurement.pressure,
                    "timestamp": measurement.created_at.isoformat()
                })
        
        # Keep connection open
        while True:
            await websocket.receive_text()
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(manager.active_connections)}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            manager.disconnect(websocket)
        except:
            pass