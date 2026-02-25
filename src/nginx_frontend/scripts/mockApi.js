const SENSOR_BLUEPRINTS = [
  {
    id: 1,
    mac: 'AA:BB:CC:00:11:22',
    name: 'Summit Ridge',
    location: 'Gaisberg Observatory, Salzburg',
    latitude: 47.8009,
    longitude: 13.0867,
    baseline_pressure: 101.32,
    battery: 0.83,
  },
  {
    id: 2,
    mac: 'AA:BB:CC:00:11:33',
    name: 'Lakeside North',
    location: 'Fuschlsee Research Pier',
    latitude: 47.7944,
    longitude: 13.2963,
    baseline_pressure: 100.98,
    battery: 0.74,
  },
  {
    id: 3,
    mac: 'AA:BB:CC:00:11:44',
    name: 'Valley Plains',
    location: 'Enns Test Field',
    latitude: 47.1419,
    longitude: 14.5345,
    baseline_pressure: 101.56,
    battery: 0.68,
  },
];

const deepClone = (value) => JSON.parse(JSON.stringify(value));

const jitter = (value, spread = 0.25) => {
  const delta = (Math.random() - 0.5) * spread;
  return value + delta;
};

const seedMeasurements = (sensors, samples = 60) => {
  const now = Date.now();
  const readings = [];
  for (let step = samples; step > 0; step -= 1) {
    const timestamp = new Date(now - step * 60 * 1000).toISOString();
    sensors.forEach((sensor) => {
      readings.push({
        id: `${sensor.id}-${timestamp}`,
        sensor_id: sensor.id,
        mac: sensor.mac,
        pressure: parseFloat((sensor.baseline_pressure + jitter(0, 0.18)).toFixed(2)),
        timestamp,
      });
    });
  }
  return readings;
};

export function createMockApi(options = {}) {
  const config = {
    latencyMs: options.latencyMs ?? 240,
    streamIntervalMs: options.streamIntervalMs ?? 4500,
    bufferSize: options.bufferSize ?? 240,
  };

  const sensors = SENSOR_BLUEPRINTS.map((sensor) => ({
    ...sensor,
    last_seen: new Date(Date.now() - Math.random() * 5 * 60 * 1000).toISOString(),
  }));

  let measurements = seedMeasurements(sensors, 50);
  let streamHandle = null;

  const withLatency = (payload) =>
    new Promise((resolve) => {
      setTimeout(() => resolve(deepClone(payload)), config.latencyMs + Math.random() * 120);
    });

  const decayBattery = (sensor) => {
    const next = sensor.battery - Math.random() * 0.002;
    sensor.battery = Math.max(0.35, parseFloat(next.toFixed(3)));
  };

  const pushMeasurementFrame = () => {
    const now = new Date();
    const frame = sensors.map((sensor) => {
      const reading = {
        id: `${sensor.id}-${now.getTime()}`,
        sensor_id: sensor.id,
        mac: sensor.mac,
        pressure: parseFloat((sensor.baseline_pressure + jitter(0, 0.22)).toFixed(2)),
        timestamp: now.toISOString(),
      };
      sensor.last_seen = reading.timestamp;
      decayBattery(sensor);
      return reading;
    });
    measurements = measurements.concat(frame).slice(-config.bufferSize);
    return frame;
  };

  const startStream = (cb) => {
    if (!cb) {
      return () => undefined;
    }
    cb(pushMeasurementFrame());
    streamHandle = setInterval(() => {
      cb(pushMeasurementFrame());
    }, config.streamIntervalMs);
    return () => {
      if (streamHandle) {
        clearInterval(streamHandle);
        streamHandle = null;
      }
    };
  };

  return {
    async fetchSensors() {
      return withLatency(sensors);
    },
    async fetchMeasurements() {
      if (!streamHandle) {
        pushMeasurementFrame();
      }
      return withLatency(measurements);
    },
    subscribeRealtime(handler) {
      return startStream(handler);
    },
  };
}
