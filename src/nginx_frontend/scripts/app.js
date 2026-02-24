import {
  calculatePressureStats,
  decorateSensorsWithMeasurements,
  formatBattery,
  formatPressure,
  limitMeasurements,
  mergeMeasurements,
} from './analytics.js';
import { createMockApi } from './mockApi.js';

const API_BASE = window.__PRESSURE_API_BASE__ || 'http://localhost:8000/api';
const useMock = window.__PRESSURE_USE_MOCK__ !== false;

const dataSource = useMock ? createMockApi() : createHttpApi(API_BASE);

const state = {
  sensors: [],
  measurements: [],
  livePaused: false,
  unsubscribe: null,
  pollHandle: null,
  mapInstance: null,
  markerLayer: null,
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
  measurementFeed: document.getElementById('measurementFeed'),
  mapContainer: document.getElementById('sensorMap'),
};

function createHttpApi(baseUrl) {
  const fetchJson = async (path) => {
    const response = await fetch(`${baseUrl}${path}`);
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }
    return response.json();
  };

  const buildWsUrl = () => {
    const url = new URL(baseUrl);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${url.origin}/ws/measurements`;
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

async function bootstrap() {
  bindInteractions();
  initMap();
  await hydrate();
  setupRealtime();
  startPolling();
}

function bindInteractions() {
  selectors.refreshButton.addEventListener('click', handleManualRefresh);
  selectors.liveButton.addEventListener('click', toggleLiveMode);
  selectors.sensorFilter.addEventListener('change', renderSensors);
}

async function hydrate() {
  setLoadingState(true);
  try {
    const [sensors, measurements] = await Promise.all([
      dataSource.fetchSensors(),
      dataSource.fetchMeasurements(),
    ]);
    state.sensors = sensors;
    state.measurements = mergeMeasurements([], measurements);
    renderAll();
    updateStatus('Synchronized with data source');
  } catch (error) {
    console.error('Failed to hydrate dashboard', error);
    selectors.sensorGrid.innerHTML = '<div class="empty-state">Unable to load data snapshot.</div>';
    selectors.measurementFeed.innerHTML = '<li class="empty-state">Realtime feed unavailable.</li>';
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
    renderTimeline();
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
      renderTimeline();
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

function renderAll() {
  renderStats();
  renderTimeline();
  renderSensors();
  renderMap();
}

function renderStats() {
  const stats = calculatePressureStats(state.measurements);
  selectors.statLatest.textContent = stats.latest ? formatPressure(stats.latest.pressure) : '--';
  selectors.statLatestSensor.textContent = stats.latest
    ? `Sensor ${stats.latest.mac}`
    : 'Awaiting feed';
  selectors.statAverage.textContent = stats.average ? formatPressure(stats.average) : '--';
  selectors.statRange.textContent = stats.min && stats.max ? `${formatPressure(stats.min)} · ${formatPressure(stats.max)}` : '--';

  const annotatedSensors = decorateSensorsWithMeasurements(state.sensors, state.measurements);
  const online = annotatedSensors.filter((sensor) => sensor.is_online).length;
  selectors.statSensors.textContent = String(annotatedSensors.length || 0);
  selectors.statOffline.textContent = `${annotatedSensors.length - online} offline`;
  selectors.statTotal.textContent = `${stats.total} measurements`;
}

function renderSensors() {
  const container = selectors.sensorGrid;
  if (!state.sensors.length) {
    container.innerHTML = '<div class="empty-state">No sensors defined yet.</div>';
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
    const card = document.createElement('article');
    card.className = 'sensor-card';
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
      <div class="sensor-card__meta">
        <span>Battery ${formatBattery(sensor.battery)}</span>
        <span>${sensor.latest_measurement ? formatPressure(sensor.latest_measurement.pressure) : '--'}</span>
      </div>
      <div class="battery-bar" aria-hidden="true">
        <div class="battery-bar__value" style="width:${Math.round((sensor.battery || 0) * 100)}%"></div>
      </div>
      <div class="sensor-card__meta">
        <span>MAC ${sensor.mac}</span>
        <span>${sensor.last_seen ? relativeTime(sensor.last_seen) : 'n/a'}</span>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderTimeline() {
  const feed = selectors.measurementFeed;
  const latest = limitMeasurements(state.measurements, 20).reverse();
  if (!latest.length) {
    feed.innerHTML = '<li class="empty-state">Waiting for telemetry…</li>';
    return;
  }
  feed.innerHTML = '';
  latest.forEach((entry) => {
    const item = document.createElement('li');
    item.className = 'timeline__item';
    item.innerHTML = `
      <div>
        <div class="timeline__pressure">${formatPressure(entry.pressure)}</div>
        <div class="timeline__meta">Sensor ${entry.mac}</div>
      </div>
      <div class="timeline__meta">${new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</div>
    `;
    feed.appendChild(item);
  });
}

function initMap() {
  if (!window.L || !selectors.mapContainer) {
    selectors.mapContainer.innerHTML = '<div class="empty-state">Map library failed to load.</div>';
    return;
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
  annotatedSensors.forEach((sensor) => {
    if (typeof sensor.latitude !== 'number' || typeof sensor.longitude !== 'number') {
      return;
    }
    const marker = L.circleMarker([sensor.latitude, sensor.longitude], {
      radius: 10,
      color: sensor.is_online ? '#136f63' : '#94a3b8',
      weight: 2,
      fillOpacity: sensor.is_online ? 0.85 : 0.4,
    });
    marker.bindPopup(
      `<strong>${sensor.name || sensor.mac}</strong><br />${formatPressure(sensor.latest_measurement?.pressure)}<br />Battery ${formatBattery(sensor.battery)}<br />${sensor.location || ''}`,
    );
    marker.addTo(state.markerLayer);
  });
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

bootstrap();
