import {
  calculatePressureStats,
  decorateSensorsWithMeasurements,
  formatBattery,
  formatPressure,
  mergeMeasurements,
} from './analytics.js';
import { createMockApi } from './mockApi.js';
import { getAuthHeader, isAuthenticated, initAuth, logout, toggleAuthMode, handleAuthSubmit, refreshUserProfile } from './auth.js';

const PRESSURE_SAFE_RANGE = { min: 98, max: 105 }; // hPa boundaries for a healthy reading
const BATTERY_LOW_THRESHOLD = 0.25; // 25%
const BATTERY_CRITICAL_THRESHOLD = 0.12; // 12%

const API_BASE = window.__PRESSURE_API_BASE__ || 'http://localhost:8000/api';
const useMock = window.__PRESSURE_USE_MOCK__ !== false;

const dataSource = useMock ? createMockApi() : createHttpApi(API_BASE);

const state = {
  sensors: [],
  measurements: [],
  livePaused: false,
  unsubscribe: null,
  pollHandle: null,
  profileRefreshHandle: null,
  mapInstance: null,
  markerLayer: null,
  isInitialized: false,
};

const selectors = {
  status: document.getElementById('connectionStatus'),
  lastUpdated: document.getElementById('lastUpdated'),
  refreshButton: document.querySelector('[data-action="refresh"]'),
  liveButton: document.querySelector('[data-action="toggle-live"]'),
  sensorFilter: document.getElementById('sensorFilter'),
  statLatest: document.getElementById('statLatest'),
  statLatestSensor: document.getElementById('statLatestSensor'),
  statAverage: document.getElementById('statAverage'),
  statRange: document.getElementById('statRange'),
  statSensors: document.getElementById('statSensors'),
  statOffline: document.getElementById('statOffline'),
  statTotal: document.getElementById('statTotal'),
  sensorGrid: document.getElementById('sensorGrid'),
  mapContainer: document.getElementById('sensorMap'),
};

function createHttpApi(baseUrl) {
  const normalizedBase = (baseUrl || '').replace(/\/+$/, '');
  const buildPath = (path) => {
    if (!path) {
      return normalizedBase || '/';
    }
    const segment = path.startsWith('/') ? path : `/${path}`;
    return `${normalizedBase}${segment}` || segment;
  };

  const fetchJson = async (path) => {
    const headers = {};
    const authHeader = getAuthHeader();
    if (authHeader) {
      headers['Authorization'] = authHeader;
    }
    
    const response = await fetch(buildPath(path), { headers });
    if (!response.ok) {
      if (response.status === 401) {
        // Token expired or invalid, logout
        window.logout();
        throw new Error('Authentication expired');
      }
      throw new Error(`Request failed: ${response.status}`);
    }
    return response.json();
  };

  const buildWsUrl = () => {
    let origin;
    if (normalizedBase.startsWith('http')) {
      try {
        origin = new URL(normalizedBase).origin;
      } catch (error) {
        console.warn('Falling back to window origin for WebSocket URL', error);
        origin = window.location.origin;
      }
    } else {
      origin = window.location.origin;
    }
    const wsOrigin = origin.startsWith('https') ? origin.replace('https', 'wss') : origin.replace('http', 'ws');
    return `${wsOrigin}/ws`;
  };

  return {
    fetchSensors: () => fetchJson('/sensors'),
    fetchMeasurements: () => fetchJson('/measurements?limit=240'),
    subscribeRealtime(handler) {
      try {
        const socket = new WebSocket(buildWsUrl());
        socket.onmessage = (event) => {
          const payload = JSON.parse(event.data);
          handler(Array.isArray(payload) ? payload : [payload]);
        };
        return () => socket.close();
      } catch (error) {
        console.warn('Realtime socket failed to initialize', error);
        return () => undefined;
      }
    },
  };
}

async function initializeApp() {
  try {
    console.log('Initializing app: bindInteractions');
    bindInteractions();
    state.isInitialized = true;
    
    console.log('Initializing app: initMap');
    initMap();
    
    console.log('Initializing app: refreshUserProfile');
    await refreshUserProfile();
    
    console.log('Initializing app: hydrate');
    await hydrate();
    
    console.log('Initializing app: setupRealtime');
    setupRealtime();
    
    console.log('Initializing app: startPolling');
    startPolling();
    
    console.log('Initializing app: startProfileRefresh');
    startProfileRefresh();
    
    console.log('App initialization complete');
  } catch (error) {
    console.error('App initialization failed:', error);
    state.isInitialized = false;
    throw error;
  }
}

function cleanupApp() {
  try {
    stopRealtime();
  } catch (error) {
    console.warn('Error stopping realtime:', error);
  }
  try {
    stopPolling();
  } catch (error) {
    console.warn('Error stopping polling:', error);
  }
  try {
    stopProfileRefresh();
  } catch (error) {
    console.warn('Error stopping profile refresh:', error);
  }
  
  // Clear state data from previous session
  console.log('cleanupApp: clearing state');
  state.sensors = [];
  state.measurements = [];
  state.livePaused = false;
  state.unsubscribe = null;
  state.pollHandle = null;
  state.profileRefreshHandle = null;
  state.isInitialized = false;
  
  // Clear the sensor grid visual display
  if (selectors.sensorGrid) {
    selectors.sensorGrid.innerHTML = '';
  }
}

async function bootstrap() {
  // Initialize authentication UI
  initAuth();
  
  // Check if user is authenticated
  if (!isAuthenticated()) {
    return;
  }
  
  await initializeApp();
}

function bindInteractions() {
  // Guard against duplicate binding
  if (state.isInitialized) {
    return;
  }
  selectors.refreshButton.addEventListener('click', handleManualRefresh);
  selectors.liveButton.addEventListener('click', toggleLiveMode);
  selectors.sensorFilter.addEventListener('change', renderSensors);
}

async function hydrate() {
  setLoadingState(true);
  try {
    console.log('Hydrate: fetching sensors and measurements');
    const [sensors, measurements] = await Promise.all([
      dataSource.fetchSensors(),
      dataSource.fetchMeasurements(),
    ]);
    console.log('Hydrate: received', sensors.length, 'sensors and', measurements.length, 'measurements');
    state.sensors = sensors;
    state.measurements = mergeMeasurements([], measurements);
    console.log('Hydrate: rendering UI');
    renderAll();
    updateStatus('Synchronized with data source');
  } catch (error) {
    console.error('Failed to hydrate dashboard', error);
    selectors.sensorGrid.innerHTML = '<div class="empty-state">Unable to load data snapshot.</div>';
    updateStatus('Frontend is offline');
  } finally {
    setLoadingState(false);
  }
}

function setupRealtime() {
  stopRealtime();
  if (typeof dataSource.subscribeRealtime !== 'function' || state.livePaused) {
    return;
  }
  state.unsubscribe = dataSource.subscribeRealtime((payload) => {
    if (!Array.isArray(payload) || !payload.length) {
      return;
    }
    state.measurements = mergeMeasurements(state.measurements, payload);
    renderStats();
    renderSensors();
    updateStatus('Live update received');
  });
}

function stopRealtime() {
  if (typeof state.unsubscribe === 'function') {
    state.unsubscribe();
  }
  state.unsubscribe = null;
}

function startPolling() {
  stopPolling();
  state.pollHandle = setInterval(async () => {
    if (state.livePaused) {
      return;
    }
    try {
      const measurements = await dataSource.fetchMeasurements();
      state.measurements = mergeMeasurements(state.measurements, measurements);
      renderStats();
      renderSensors();
      updateStatus('Background poll completed');
    } catch (error) {
      console.warn('Background poll failed', error);
    }
  }, 20000);
}

function stopPolling() {
  if (state.pollHandle) {
    clearInterval(state.pollHandle);
  }
  state.pollHandle = null;
}

function startProfileRefresh() {
  stopProfileRefresh();
  // Refresh user profile every 30 seconds to detect role/permission changes
  state.profileRefreshHandle = setInterval(async () => {
    try {
      await refreshUserProfile();
    } catch (error) {
      console.warn('Profile refresh failed', error);
    }
  }, 30000);
}

function stopProfileRefresh() {
  if (state.profileRefreshHandle) {
    clearInterval(state.profileRefreshHandle);
  }
  state.profileRefreshHandle = null;
}

function toggleLiveMode() {
  state.livePaused = !state.livePaused;
  selectors.liveButton.textContent = state.livePaused ? 'Resume live updates' : 'Pause live updates';
  if (state.livePaused) {
    stopRealtime();
    updateStatus('Live updates paused');
  } else {
    setupRealtime();
    updateStatus('Live updates resumed');
  }
}

async function handleManualRefresh() {
  await hydrate();
}

function setLoadingState(isLoading) {
  selectors.refreshButton.disabled = isLoading;
  selectors.refreshButton.textContent = isLoading ? 'Refreshing…' : 'Manual refresh';
}

function renderStats() {
  const stats = calculatePressureStats(state.measurements);
  selectors.statLatest.textContent = stats.latest ? formatPressure(stats.latest.pressure) : '--';
  selectors.statLatestSensor.textContent = stats.latest ? `Sensor ${stats.latest.mac}` : 'Awaiting feed';
  selectors.statAverage.textContent = stats.average ? formatPressure(stats.average) : '--';
  selectors.statRange.textContent = stats.min && stats.max ? `${formatPressure(stats.min)} · ${formatPressure(stats.max)}` : '--';

  const annotatedSensors = decorateSensorsWithMeasurements(state.sensors, state.measurements);
  const online = annotatedSensors.filter((sensor) => sensor.is_online).length;
  selectors.statSensors.textContent = String(annotatedSensors.length || 0);
  selectors.statOffline.textContent = `${annotatedSensors.length - online} offline`;
  selectors.statTotal.textContent = `${stats.total} measurements`;
}

function renderAll() {
  renderStats();
  renderSensors();
  renderMap();
}

function deriveSensorStatus(sensor) {
  const flags = [];
  const batteryLevel = typeof sensor.battery === 'number' ? sensor.battery : 1;
  const pressure = sensor.latest_measurement?.pressure;

  if (!sensor.is_online) {
    flags.push({ level: 'critical', label: 'Offline' });
  }
  if (batteryLevel <= BATTERY_CRITICAL_THRESHOLD) {
    flags.push({ level: 'critical', label: 'Battery critical' });
  } else if (batteryLevel <= BATTERY_LOW_THRESHOLD) {
    flags.push({ level: 'warning', label: 'Battery low' });
  }

  if (typeof pressure === 'number') {
    //const outOfRange = pressure < PRESSURE_SAFE_RANGE.min || pressure > PRESSURE_SAFE_RANGE.max;
    if (sensor.out_of_range) {
      flags.push({ level: 'warning', label: 'Unusual pressure' });
    }
  }

  const level = flags.some((flag) => flag.level === 'critical')
    ? 'critical'
    : flags.some((flag) => flag.level === 'warning')
      ? 'warning'
      : 'normal';

  const primary = flags.find((flag) => flag.level === 'critical') || flags.find((flag) => flag.level === 'warning');

  return {
    level,
    message: primary ? primary.label : 'Nominal',
    flags,
  };
}

function renderSensors() {
  const container = selectors.sensorGrid;
  if (!state.sensors.length) {
    container.innerHTML = '<div class="empty-state">No sensors available with your access level.</div>';
    return;
  }

  const annotatedSensors = decorateSensorsWithMeasurements(state.sensors, state.measurements);
  const filter = selectors.sensorFilter.value;
  const filtered = annotatedSensors.filter((sensor) => {
    if (filter === 'online') {
      return sensor.is_online;
    }
    if (filter === 'offline') {
      return !sensor.is_online;
    }
    return true;
  });

  if (!filtered.length) {
    container.innerHTML = '<div class="empty-state">No sensors match the selected filter.</div>';
    return;
  }

  container.innerHTML = '';
  filtered.forEach((sensor) => {
    const status = deriveSensorStatus(sensor);
    const canRead = sensor.can_read !== false; // Default to true if not specified (backwards compatibility)
    const pressureDisplay = canRead && sensor.latest_measurement ? formatPressure(sensor.latest_measurement.pressure) : '---';
    const batteryDisplay = canRead ? formatBattery(sensor.battery) : '---';
    const altitudeDisplay = canRead && sensor.altitude ? `${Math.round(sensor.altitude)} m` : '---';
    const detailLine = status.flags.length ? status.flags.map((flag) => flag.label).join(' • ') : 'Operating nominally';
    const card = document.createElement('article');
    card.className = `sensor-card sensor-card--${status.level}`;
    
    const readabilityNotice = !canRead ? '<div style="font-size: 0.8rem; color: var(--color-muted); margin-top: 4px;">⚠ Insufficient clearance for readings</div>' : '';
    
    card.innerHTML = `
      <div class="sensor-card__header">
        <div>
          <div class="sensor-card__title">${sensor.name || sensor.mac}</div>
          <div class="sensor-card__location">${sensor.location || sensor.mac}</div>
        </div>
        <div class="sensor-card__status ${sensor.is_online ? 'sensor-card__status--online' : 'sensor-card__status--offline'}">
          ${sensor.is_online ? 'Online' : 'Offline'}
        </div>
      </div>
      <div class="sensor-card__alert sensor-card__alert--${status.level}">
        ${status.message}
      </div>
      <div class="sensor-card__meta">
        <span>Battery ${batteryDisplay}</span>
        <span>${pressureDisplay}</span>
      </div>
      <div class="battery-bar" aria-hidden="true">
        <div class="battery-bar__value" style="width:${canRead ? Math.round((sensor.battery || 0) * 100) : 0}%"></div>
      </div>
      <div class="sensor-card__meta">
        <span>MAC ${sensor.mac}</span>
        <span>Altitude ${altitudeDisplay}</span>
      </div>
      <div class="sensor-card__meta sensor-card__meta--secondary">
        <span>${detailLine}</span>
        <span>${sensor.last_seen ? relativeTime(sensor.last_seen) : 'n/a'}</span>
      </div>
      ${readabilityNotice}
    `;
    container.appendChild(card);
  });
}

function initMap() {
  if (!window.L) {
    console.warn('Leaflet library not loaded');
    if (selectors.mapContainer) {
      selectors.mapContainer.innerHTML = '<div class="empty-state">Map library failed to load.</div>';
    }
    return;
  }
  if (!selectors.mapContainer) {
    console.warn('Map container not found in DOM');
    return;
  }
  
  // Destroy old map instance if it exists
  if (state.mapInstance) {
    console.log('initMap: destroying old map instance');
    state.mapInstance.remove();
    state.mapInstance = null;
    state.markerLayer = null;
  }
  
  state.mapInstance = L.map('sensorMap', {
    zoomControl: false,
    scrollWheelZoom: false,
    attributionControl: true,
  }).setView([47.5, 13.3], 6);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
  }).addTo(state.mapInstance);

  state.markerLayer = L.layerGroup().addTo(state.mapInstance);
}

function renderMap() {
  if (!state.mapInstance || !state.markerLayer) {
    return;
  }
  state.markerLayer.clearLayers();
  const annotatedSensors = decorateSensorsWithMeasurements(state.sensors, state.measurements);
  const coordinates = [];
  annotatedSensors.forEach((sensor) => {
    if (typeof sensor.latitude !== 'number' || typeof sensor.longitude !== 'number') {
      return;
    }
    const status = deriveSensorStatus(sensor);
    const canRead = sensor.can_read !== false;
    coordinates.push([sensor.latitude, sensor.longitude]);
    
    const pressureInfo = canRead && sensor.latest_measurement 
      ? `<br />${formatPressure(sensor.latest_measurement.pressure)}`
      : '<br /><em style="color: #666;">Readings unavailable</em>';
    const batteryInfo = canRead 
      ? `<br />Battery ${formatBattery(sensor.battery)}`
      : '';
    const altitudeInfo = canRead && sensor.altitude 
      ? `<br />Altitude ${Math.round(sensor.altitude || 0)} m`
      : '';
    
    const marker = L.circleMarker([sensor.latitude, sensor.longitude], {
      radius: 10,
      color: status.level === 'critical' ? '#b91c1c' : status.level === 'warning' ? '#ff9f1c' : '#136f63',
      weight: 2,
      fillOpacity: sensor.is_online ? 0.85 : 0.4,
    });
    marker.bindPopup(
      `<strong>${sensor.name || sensor.mac}</strong>${pressureInfo}${batteryInfo}${altitudeInfo}<br />${sensor.location || ''}`,
    );
    marker.on('mouseover', () => marker.openPopup());
    marker.on('mouseout', () => marker.closePopup());
    marker.addTo(state.markerLayer);
  });

  if (coordinates.length) {
    const bounds = L.latLngBounds(coordinates);
    state.mapInstance.fitBounds(bounds.pad(0.25));
  }
}

function updateStatus(message) {
  const timestamp = new Date();
  if (selectors.status) {
    selectors.status.textContent = `${useMock ? 'Simulated mode' : 'API mode'} · ${message}`;
  }
  if (selectors.lastUpdated) {
    selectors.lastUpdated.textContent = `Last sync ${timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
  }
}

function relativeTime(value) {
  const delta = Date.now() - new Date(value).getTime();
  if (delta < 60 * 1000) {
    return 'moments ago';
  }
  const minutes = Math.round(delta / (60 * 1000));
  if (minutes < 60) {
    return `${minutes} min ago`;
  }
  const hours = Math.round(minutes / 60);
  return `${hours} h ago`;
}

// Make auth functions globally available for inline event handlers
window.logout = logout;
window.toggleAuthMode = toggleAuthMode;
window.handleAuthSubmit = handleAuthSubmit;

// Export functions that analytics.js might need
window.decorateSensorsWithMeasurements = decorateSensorsWithMeasurements;
window.initializeApp = initializeApp;
window.cleanupApp = cleanupApp;

bootstrap();

