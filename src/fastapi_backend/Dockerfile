FROM python:3.12-slim

WORKDIR /app

# Copy requirements first for better caching
COPY fastapi_backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy both fastapi_backend and postgres_database packages
COPY fastapi_backend ./fastapi_backend/
COPY postgres_database ./postgres_database/

# Create __init__.py files to make directories into packages
RUN touch __init__.py && touch fastapi_backend/__init__.py && touch postgres_database/__init__.py

# Set PYTHONPATH so Python can find all packages
ENV PYTHONPATH=/app

CMD ["uvicorn", "fastapi_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]