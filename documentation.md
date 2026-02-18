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

<h3>28.1.2026</h3>
<li>fixed MQTT Client mockup by having it include loop_start</li>
<li>fixed an issue where relative imports (e.g. .database) in the PyTest file would lead to the container raising an error</li>
<li>enhanced mosquitto.conf to explicitly listen on a port</li>
<li>TODO: Deliberation: WebSockets? Logging: Docker Logs (also for everything a user does)</li>

<h3>2026/02/03</h3>
<li>Got some reconsidering done:
<ul>
    <li><b>WebSockets?</b> Definitely; our project would greatly benefit from an up-to-date dashboard in the frontend</li>
    <li><b>Frontend:</b> Martin will assume responsibility for this area.
    <h4>Technology:</h4>
    <ul>
        <li>NGINX</li>
    </ul>
    </li>
    <li><b>Backend:</b> Martin will assume responsibility for this area.
    <h4>Technology:</h4>
    <ul>
        <li>FastAPI</li>
    </ul>
    </li>
    <li><b>Database:</b> Martin will assume responsibility for this area.
    <h4>Technology:</h4>
    <ul>
        <li>SQLModel</li>
    </ul>
    </li>
    <li><b>Simulation:</b> Paolo will assume responsibility for this area.
    <h4>Technology</h4>
    <ul>
        <li>Paho MQTT</li>
    </ul>
    </li>
    <li><b>MQTT:</b> Paolo will assume responsibility for this area.
    </li>
    <h4>Technology:</h4>
    <ul>
        <li>Mosquitto</li>
    </ul>
    <li><b>Testing:</b> Both of us will take care of the testing duties in our respective sections.
    </li>
    <h4>Technology:</h4>
    <ul>
        <li>PyTest</li>
    </ul>
    <li><b>Logging:</b> Both of us will take care of the logging duties in our respective sections.
    </li>
    <h4>Technology:</h4>
    <ul>
        <li>Docker logs</li>
    </ul>
    <li><b>Documentation:</b> Both of us will take care of the documentation duties in our respective sections.
    </li>
    <h4>Technology:</h4>
    <ul>
        <li>Swagger UI (for API endpoint configuration)</li>
        <li>Ruff (to ensure type annotations and the likes)</li>
    </ul>
    <li><b>Security:</b> Both of us will take care of the security duties in our respective sections.
    </li>
    
</ul>
</li>
<li>Branched off into "Martin" and "paolo"</li>
<li><b>Branch Martin:</b> added HTML file for the frontend; adjusted backend's main.py as well as MQTT to use WebSockets and redirect traffic there</li>


<li>2026/02/18, branch Martin</li>
<li>wrote instruction file</li>
<li>moved the frontend HTML files as well as database.py into the correct directory, respectively</li>
