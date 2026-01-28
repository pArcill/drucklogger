FROM python:3.12-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire fastapi_backend package
COPY . ./fastapi_backend/

# Create an empty __init__.py in parent if needed
RUN touch __init__.py

# Set PYTHONPATH so Python can find the fastapi_backend package
ENV PYTHONPATH=/app

CMD ["uvicorn", "fastapi_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]