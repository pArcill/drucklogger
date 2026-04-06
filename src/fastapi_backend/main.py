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
from fastapi_backend.models import Measurement, Sensor, User, RegisterRequest, LoginRequest, CreateSensorRequest
from fastapi_backend.auth import (
    authenticate_user, register_user, create_access_token, 
    get_user_from_token, ACCESS_TOKEN_EXPIRE_MINUTES
)
from fastapi_backend.role_config import can_access_readings, can_view_sensor, ROLE_HIERARCHY

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


@app.get("/api/config/roles")
def get_roles():
    """Get available role hierarchy for access control"""
    return {
        "roles": ROLE_HIERARCHY
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
        logger.info(f"New user registered: {request.username} ({request.email})")
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
        
        logger.info(f"User logged in: {request.username}")
        
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
    try:
        token = extract_token_from_header(authorization)
        user = get_user_from_token(token, session)
        
        logger.debug(f"Current user info requested: {user.username}")
        
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error getting user info")


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
        
        logger.debug(f"User '{current_user.username}' (role={current_user.role}) requested {limit} latest measurements")
        
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
        
        logger.info(f"User '{current_user.username}' accessed {len(filtered_measurements)} measurements (role={current_user.role}, from {len(measurements)} total)")
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
        
        logger.debug(f"User '{current_user.username}' (role={current_user.role}) requested sensor list")
        
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
                logger.debug(f"User '{current_user.username}' cannot view sensor {sensor.mac_address} (display_clearance={sensor.display_clearance})")
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

        logger.info(f"User '{current_user.username}' can access {len(sensors)} sensors (role={current_user.role})")
        return sensors
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving sensors: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sensors")
def create_sensor(
    request: CreateSensorRequest,
    authorization: str = Header(None),
    session: Session = Depends(get_session)
):
    """
    Create a new sensor (either physical or simulator type)
    
    For physical sensors, creates a Sensor record in the database.
    For simulator sensors, additionally creates a SensorSimulator instance.
    """
    try:
        # Get current user (for audit purposes)
        token = extract_token_from_header(authorization)
        current_user = get_user_from_token(token, session)
        
        # Validate input
        if request.sensor_type not in ["physical", "simulator"]:
            raise HTTPException(status_code=400, detail="sensor_type must be 'physical' or 'simulator'")
        
        if not request.mac_address or len(request.mac_address) < 17:
            raise HTTPException(status_code=400, detail="Invalid MAC address (must be in format AA:BB:CC:DD:EE:FF)")
        
        if not request.name or len(request.name) < 1:
            raise HTTPException(status_code=400, detail="Sensor name is required")
        
        if not (-90 <= request.latitude <= 90):
            raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90")
        
        if not (-180 <= request.longitude <= 180):
            raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180")
        
        if not (0 <= request.battery_level <= 1.0):
            raise HTTPException(status_code=400, detail="Battery level must be between 0 and 1.0")
        
        if request.pressure_range_min >= request.pressure_range_max:
            raise HTTPException(status_code=400, detail="Pressure range min must be less than max")
        
        # Check if sensor with this MAC already exists
        existing_sensor = session.exec(
            select(Sensor).where(Sensor.mac_address == request.mac_address)
        ).first()
        
        if existing_sensor:
            raise HTTPException(status_code=400, detail=f"Sensor with MAC address {request.mac_address} already exists")
        
        # Create the sensor record in the database
        sensor = Sensor(
            mac_address=request.mac_address,
            name=request.name,
            sensor_type=request.sensor_type,
            latitude=request.latitude,
            longitude=request.longitude,
            altitude=request.altitude,
            battery_level=request.battery_level,
            display_clearance=request.display_clearance,
            readings_clearance=request.readings_clearance
        )
        
        session.add(sensor)
        session.commit()
        session.refresh(sensor)
        
        logger.info(f"User {current_user.username} created a new {request.sensor_type} sensor: {request.name} ({request.mac_address})")
        
        # If it's a simulator, also write to the config file so sensor_simulator picks it up
        if request.sensor_type == "simulator":
            try:
                import json
                config_path = "/app/simulator_config.json"
                
                # Try alternate paths
                if not os.path.exists(config_path):
                    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "simulator_config.json")
                
                # Load existing config or create new one
                sim_config_data = {"simulators": []}
                if os.path.exists(config_path):
                    try:
                        with open(config_path, 'r') as f:
                            sim_config_data = json.load(f)
                    except Exception as e:
                        logger.warning(f"Could not read simulator config: {e}")
                
                # Add the new simulator
                new_sim = {
                    "name": request.name,
                    "mac": request.mac_address,
                    "latitude": request.latitude,
                    "longitude": request.longitude,
                    "altitude": request.altitude,
                    "battery_level": request.battery_level,
                    "display_clearance": request.display_clearance,
                    "readings_clearance": request.readings_clearance,
                    "expected_range": [request.pressure_range_min, request.pressure_range_max]
                }
                sim_config_data["simulators"].append(new_sim)
                
                # Write back to config file
                with open(config_path, 'w') as f:
                    json.dump(sim_config_data, f, indent=2)
                
                logger.info(f"Added simulator {request.mac_address} to config file at {config_path}")
            except Exception as e:
                logger.warning(f"Failed to write simulator to config file: {e}. Simulator will still be in database.")
        
        return {
            "id": sensor.id,
            "mac": sensor.mac_address,
            "name": sensor.name,
            "sensor_type": request.sensor_type,
            "latitude": sensor.latitude,
            "longitude": sensor.longitude,
            "altitude": sensor.altitude,
            "battery_level": sensor.battery_level,
            "display_clearance": sensor.display_clearance,
            "readings_clearance": sensor.readings_clearance,
            "pressure_range_min": request.pressure_range_min,
            "pressure_range_max": request.pressure_range_max,
            "message": f"{request.sensor_type} sensor created successfully. It will start sending data within 5 seconds."
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error creating sensor: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating sensor: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error creating sensor")


@app.delete("/api/sensors/{sensor_id}")
def delete_sensor(
    sensor_id: int,
    authorization: str = Header(None),
    session: Session = Depends(get_session)
):
    """
    Delete a sensor by ID
    Also removes the sensor from the simulator config file if it's a simulator type
    """
    try:
        # Get current user (for audit purposes)
        token = extract_token_from_header(authorization)
        current_user = get_user_from_token(token, session)
        logger.debug(f"Delete request for sensor {sensor_id} by user {current_user.username}")
        
        # Find the sensor
        try:
            sensor = session.exec(
                select(Sensor).where(Sensor.id == sensor_id)
            ).first()
        except Exception as e:
            logger.error(f"Error querying sensor {sensor_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error querying sensor")
        
        if not sensor:
            logger.debug(f"Sensor {sensor_id} not found")
            raise HTTPException(status_code=404, detail=f"Sensor with ID {sensor_id} not found")
        
        # Store values before deletion (sensor object will be detached after commit)
        try:
            sensor_name = sensor.name
            sensor_mac = sensor.mac_address
            sensor_type = sensor.sensor_type
            logger.debug(f"Stored sensor details: name={sensor_name}, mac={sensor_mac}, type={sensor_type}")
        except Exception as e:
            logger.error(f"Error accessing sensor attributes: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error accessing sensor details")
        
        logger.info(f"User {current_user.username} requested deletion of sensor: {sensor_name} ({sensor_mac})")
        
        # Delete all measurements for this sensor first (to satisfy foreign key constraints)
        try:
            measurements = session.exec(
                select(Measurement).where(Measurement.sensor_id == sensor_id)
            ).all()
            logger.info(f"[DELETE] Found {len(measurements)} measurements to delete for sensor {sensor_id}")
            for measurement in measurements:
                session.delete(measurement)
            
            # Delete the sensor itself
            logger.info(f"[DELETE] About to delete sensor {sensor_id} from session")
            session.delete(sensor)
            
            # Single commit for both measurements and sensor
            logger.info(f"[DELETE] About to COMMIT transaction for sensor {sensor_id}")
            session.commit()
            logger.info(f"[DELETE] COMMIT SUCCESSFUL for sensor {sensor_id} ({sensor_mac})")
            
            # Verify deletion by querying the database
            try:
                verify = session.exec(
                    select(Sensor).where(Sensor.id == sensor_id)
                ).first()
                if verify:
                    logger.error(f"[DELETE] ERROR: Sensor {sensor_id} still exists in database after delete!")
                else:
                    logger.info(f"[DELETE] VERIFIED: Sensor {sensor_id} successfully deleted from database")
                
                # Also verify measurements are gone
                remaining_measurements = session.exec(
                    select(Measurement).where(Measurement.sensor_id == sensor_id)
                ).all()
                if remaining_measurements:
                    logger.error(f"[DELETE] ERROR: {len(remaining_measurements)} measurements still exist for sensor {sensor_id}!")
                else:
                    logger.info(f"[DELETE] VERIFIED: All measurements for sensor {sensor_id} deleted")
            except Exception as e:
                logger.warning(f"[DELETE] Could not verify deletion: {e}")
            
        except Exception as e:
            logger.error(f"[DELETE] Error deleting sensor and measurements: {e}", exc_info=True)
            try:
                session.rollback()
                logger.error(f"[DELETE] Rolled back transaction due to error")
            except:
                pass
            raise HTTPException(status_code=500, detail=f"Error deleting sensor: {str(e)}")
        
        # If it's a simulator, also remove from config file
        if sensor_type == "simulator":
            logger.info(f"[CONFIG] Sensor {sensor_id} is simulator type, attempting config file removal for MAC {sensor_mac}")
            try:
                import json
                config_path = "/app/simulator_config.json"
                logger.debug(f"[CONFIG] Checking primary path: {config_path}")
                
                # Try alternate paths
                if not os.path.exists(config_path):
                    alt_path = os.path.join(os.path.dirname(__file__), "..", "..", "simulator_config.json")
                    logger.info(f"[CONFIG] Primary path not found, trying alternate: {alt_path}")
                    if os.path.exists(alt_path):
                        config_path = alt_path
                        logger.info(f"[CONFIG] Using alternate config path: {config_path}")
                    else:
                        logger.warning(f"[CONFIG] Alternate path also not found")
                
                if os.path.exists(config_path):
                    logger.info(f"[CONFIG] Config file found, reading from {config_path}")
                    try:
                        with open(config_path, 'r') as f:
                            sim_config_data = json.load(f)
                        logger.debug(f"[CONFIG] Successfully loaded JSON, found {len(sim_config_data.get('simulators', []))} simulators")
                        
                        # Remove the simulator with matching MAC
                        if "simulators" in sim_config_data:
                            original_count = len(sim_config_data["simulators"])
                            original_macs = [s.get('mac') for s in sim_config_data['simulators']]
                            logger.info(f"[CONFIG] Current simulators in config: {original_macs}")
                            
                            sim_config_data["simulators"] = [
                                s for s in sim_config_data["simulators"] 
                                if s.get("mac") != sensor_mac
                            ]
                            removed = original_count - len(sim_config_data["simulators"])
                            new_macs = [s.get('mac') for s in sim_config_data['simulators']]
                            
                            logger.info(f"[CONFIG] Removed {removed} simulator(s) with MAC {sensor_mac}")
                            logger.info(f"[CONFIG] Simulators after removal: {new_macs}")
                            
                            # Write back to config file
                            with open(config_path, 'w') as f:
                                json.dump(sim_config_data, f, indent=2)
                            
                            logger.info(f"[CONFIG] Successfully wrote updated config to {config_path}")
                        else:
                            logger.error(f"[CONFIG] ERROR: Config file has no 'simulators' key!")
                    except json.JSONDecodeError as e:
                        logger.error(f"[CONFIG] ERROR: Invalid JSON in simulator config: {e}")
                    except Exception as e:
                        logger.error(f"[CONFIG] ERROR: Could not update simulator config file: {e}", exc_info=True)
                else:
                    logger.error(f"[CONFIG] ERROR: Config file not found at any path - simulator will NOT be removed from config!")
            except Exception as e:
                logger.error(f"[CONFIG] ERROR: Unexpected error processing config file: {e}", exc_info=True)
        else:
            logger.info(f"[CONFIG] Sensor {sensor_id} is not simulator type (type={sensor_type}), skipping config removal")
        
        logger.info(f"Sensor {sensor_name} ({sensor_mac}) deleted successfully by user {current_user.username}")
        
        return {
            "id": sensor_id,
            "name": sensor_name,
            "mac": sensor_mac,
            "message": f"Sensor {sensor_name} deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in delete_sensor: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting sensor: {str(e)}")