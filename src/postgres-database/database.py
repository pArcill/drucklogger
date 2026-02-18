# database.py
from sqlmodel import create_engine, SQLModel, Session
import os

# Use DATABASE_URL if provided, otherwise construct from individual env vars
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{os.getenv('DB_USER', 'admin')}:"
    f"{os.getenv('DB_PASSWORD', 'changeme')}@"
    f"{os.getenv('DB_HOST', 'localhost')}:"
    f"{os.getenv('DB_PORT', '5432')}/"
    f"{os.getenv('DB_NAME', 'sensor_db')}"
)

engine = create_engine(DATABASE_URL, echo=True)


def create_db_and_tables():
    """
    Create all database tables
    """
    from .models import Sensor, Measurement  # Import here to ensure models are registered
    SQLModel.metadata.create_all(engine)


def get_session():
    """
    Dependency for getting database sessions
    """
    with Session(engine) as session:
        yield session