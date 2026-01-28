# main.py
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import create_db_and_tables
from .mqtt_handler import MQTTHandler

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO") or "INFO",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global MQTT handler instance
mqtt_handler = None


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
    mqtt_handler = MQTTHandler(mqtt_broker, mqtt_port)
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