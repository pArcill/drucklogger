<h2>Approach</h2>
After brief consideration, we concluded that since the tasks mostly build up on each other, it would be counterproductive to divide the workload. Instead, we will work through them sequentially together.

<h3>2026/01/20</h3>
<li>Set up project structure</li>
<li>Config files (docker-compose.yml, mosquitto.conf, .env, .env.example)</li>
<li>For formatting and linting: Ruff + Black</li>

<h3>2026/01/21</h3>
<li>Wrote Dockerfiles for sensor_simulator and fastapi_backend</li>
<li>Got to work on sensor_simulator's main.py</li>

<h3>2026/01/27</h3>
<li>Set up a UV virtual environment</li>
<li>Had Git Copilot write up a number of PyTest testcases (located in a subdirectory of src for easier accessibility and to prevent accidental packaging)</li>
<li>Began work on backend; we decided on SQLModel
    <ul>
    <li>Wrote a requirements file for the backend (src/fastapi_backend/requirements.txt)</li>
    <li>Created the file src/fastapi_backend/models.py to define the database entities</li>
    <li>Filled in the blanks in src/fastapi_backend/Dockerfile (which is to say, the entire thing)</li>
    <li>Implemented PyTests for the backend</li>
    </ul>
</li>
<li>Updated docker-compose.yml to use environment variables rather than hardcoded values, they're configurable in .env.example</li>
<li>Added the file src/nginx.conf for the containers to actually work</li>
<li>Began work on the background service for the MQTT Broker</li>
<li>TODO: solve sensor simulator error</li>