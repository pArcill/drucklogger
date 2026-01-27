# Environment Configuration

This project uses environment variables for configuration. Follow these steps to set up your environment:

## Setup Instructions

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit the `.env` file** with your actual credentials:
   - Replace `your_secure_password_here` with strong passwords
   - Adjust ports if needed
   - Modify database names and users as required

3. **Important:** Never commit the `.env` file to version control. It's already listed in `.gitignore`.

## Environment Variables

### Database Configuration
- `POSTGRES_USER`: PostgreSQL admin username
- `POSTGRES_PASSWORD`: PostgreSQL admin password
- `POSTGRES_DB`: Database name

### Database Connection (FastAPI Backend)
- `DB_USER`: Database user for the application
- `DB_PASSWORD`: Database password for the application
- `DB_HOST`: Database host (default: `postgres_database` in Docker)
- `DB_PORT`: Database port (default: `5432`)
- `DB_NAME`: Database name

### MQTT Broker
- `MQTT_BROKER`: MQTT broker hostname (default: `mqtt_broker` in Docker)
- `MQTT_PORT`: MQTT broker internal port (default: `1883`)

### Ports (External)
- `API_PORT`: FastAPI backend external port (default: `8000`)
- `NGINX_PORT`: Nginx frontend external port (default: `80`)
- `POSTGRES_PORT`: PostgreSQL external port (default: `5432`)
- `MQTT_TCP_PORT`: MQTT TCP external port (default: `1883`)
- `MQTT_WS_PORT`: MQTT WebSocket external port (default: `9001`)

## Usage

Once configured, start the services with:
```bash
docker-compose up -d
```

Docker Compose will automatically load variables from the `.env` file.
