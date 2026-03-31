# main.py
import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header
from sqlalchemy import func
from sqlmodel import Session, select

# Add parent directory to path for imports (useful for local development)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from postgres_database.database import create_db_and_tables, engine, get_session
from fastapi_backend.mqtt_handler import MQTTHandler
from fastapi_backend.models import Measurement, Sensor, User, RegisterRequest, LoginRequest
from fastapi_backend.auth import (
    authenticate_user, register_user, create_access_token, 
    get_user_from_token, ACCESS_TOKEN_EXPIRE_MINUTES
)
from fastapi_backend.role_config import can_access_readings, can_view_sensor

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO") or "INFO",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global MQTT handler instance
mqtt_handler = None


def isoformat_utc(value: datetime | None) -> str | None:
    """Return an ISO8601 string with UTC offset for consistent client parsing"""
    if value is None:
        return None
    dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

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


def extract_token_from_header(authorization: str = Header(None)) -> str:
    """Extract Bearer token from Authorization header"""
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header"
        )
    
    return parts[1]


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
    # Get the running event loop to pass to the MQTT handler
    event_loop = asyncio.get_running_loop()
    mqtt_handler = MQTTHandler(mqtt_broker, mqtt_port, broadcast_callback=manager.broadcast, event_loop=event_loop)
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


# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.post("/api/auth/register")
def register(
    request: RegisterRequest,
    session: Session = Depends(get_session)
):
    """
    Register a new user account
    """
    # Simple validation
    if not request.username or len(request.username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if not request.email or "@" not in request.email:
        raise HTTPException(status_code=400, detail="Invalid email address")
    if not request.password or len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    try:
        user = register_user(session, request.username, request.email, request.password)
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "message": "User registered successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error registering user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error registering user")


@app.post("/api/auth/login")
def login(
    request: LoginRequest,
    session: Session = Depends(get_session)
):
    """
    Login with username and password
    Returns JWT access token
    """
    if not request.username or not request.password:
        raise HTTPException(status_code=400, detail="Username and password required")
    
    try:
        user = authenticate_user(session, request.username, request.password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error during login")


@app.get("/api/auth/me")
def get_current_user_info(
    authorization: str = Header(None),
    session: Session = Depends(get_session)
):
    """Get current user info (requires authentication)"""
    token = extract_token_from_header(authorization)
    user = get_user_from_token(token, session)
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role
    }


@app.get("/api/measurements")
def get_latest_measurements(
    limit: int = 100,
    authorization: str = Header(None),
    session: Session = Depends(get_session)
):
    """Get latest measurements from sensors user can access"""
    try:
        # Get current user
        token = extract_token_from_header(authorization)
        current_user = get_user_from_token(token, session)
        
        statement = select(Measurement).order_by(Measurement.created_at.desc()).limit(limit)
        measurements = session.exec(statement).all()
        
        filtered_measurements = []
        for m in measurements:
            # Only include measurements from sensors the user can read
            if can_access_readings(current_user.role, m.sensor.readings_clearance):
                filtered_measurements.append({
                    "id": m.id,
                    "sensor_id": m.sensor_id,
                    "sensor_name": m.sensor.name if m.sensor else "Unknown",
                    "mac": m.sensor.mac_address if m.sensor else None,
                    "pressure": m.pressure,
                    "timestamp": isoformat_utc(m.created_at)
                })
        
        return filtered_measurements
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving measurements: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
                    "mac": measurement.sensor.mac_address if measurement.sensor else None,
                    "pressure": measurement.pressure,
                    "timestamp": isoformat_utc(measurement.created_at)
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


@app.get("/api/sensors")
def get_sensors(
    authorization: str = Header(None),
    session: Session = Depends(get_session)
):
    """Return sensors filtered by user's display-clearance access level"""
    try:
        # Get current user
        token = extract_token_from_header(authorization)
        current_user = get_user_from_token(token, session)
        
        latest_measurements = (
            select(
                Measurement.sensor_id,
                func.max(Measurement.created_at).label("last_seen")
            )
            .group_by(Measurement.sensor_id)
            .subquery()
        )

        statement = (
            select(Sensor, latest_measurements.c.last_seen)
            .outerjoin(latest_measurements, Sensor.id == latest_measurements.c.sensor_id)
            .order_by(Sensor.id)
        )

        rows = session.exec(statement).all()
        sensors = []
        for sensor, last_seen in rows:
            # Check if user can see this sensor on the map
            if not can_view_sensor(current_user.role, sensor.display_clearance):
                continue
            
            # Check if user can read this sensor's measurements
            can_read = can_access_readings(current_user.role, sensor.readings_clearance)
            
            sensor_data = {
                "id": sensor.id,
                "mac": sensor.mac_address,
                "name": sensor.name,
                "location": f"{sensor.latitude:.4f}, {sensor.longitude:.4f}",
                "latitude": sensor.latitude,
                "longitude": sensor.longitude,
                "altitude": sensor.altitude,
                "battery": sensor.battery_level if can_read else None,
                "last_seen": isoformat_utc(last_seen) if last_seen else None,
                "can_read": can_read
            }
            sensors.append(sensor_data)

        return sensors
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving sensors: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))