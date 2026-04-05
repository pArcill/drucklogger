FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir paho-mqtt==1.6.1 sqlmodel==0.0.14 psycopg2-binary==2.9.9

# Copy all source files (sensor_simulator will be able to import postgres_database and fastapi_backend)
COPY . /app/src/

CMD ["python", "/app/src/sensor_simulator/main.py"]