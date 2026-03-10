const identity = (value) => JSON.parse(JSON.stringify(value));

export function normalizeMeasurements(measurements = []) {
  return measurements
    .filter((item) => item && typeof item.pressure === 'number' && item.timestamp)
    .map((item) => ({ ...item, timestamp: new Date(item.timestamp).toISOString() }))
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
}

export function limitMeasurements(measurements = [], limit = 25) {
  const normalized = normalizeMeasurements(measurements);
  if (limit <= 0) {
    return normalized;
  }
  return normalized.slice(-limit);
}

export function calculatePressureStats(measurements = []) {
  const normalized = normalizeMeasurements(measurements);
  if (!normalized.length) {
    return {
      latest: null,
      min: null,
      max: null,
      average: null,
      total: 0,
    };
  }

  const pressures = normalized.map((record) => record.pressure);
  const total = normalized.length;
  const sum = pressures.reduce((acc, value) => acc + value, 0);
  return {
    latest: normalized[normalized.length - 1],
    min: Math.min(...pressures),
    max: Math.max(...pressures),
    average: sum / pressures.length,
    total,
  };
}

export function formatPressure(value, fallback = '--') {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return fallback;
  }
  return `${value.toFixed(2)} hPa`;
}

export function formatBattery(value, fallback = '--') {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return fallback;
  }
  return `${Math.round(value * 100)}%`;
}

export function isSensorOnline(sensor, options = {}) {
  const reference = options.now ? new Date(options.now) : new Date();
  const thresholdMinutes = options.thresholdMinutes ?? 7;
  if (!sensor) {
    return false;
  }
  const lastSeen = sensor.last_seen || sensor.lastSeen;
  if (!lastSeen) {
    return false;
  }
  const delta = reference.getTime() - new Date(lastSeen).getTime();
  return delta <= thresholdMinutes * 60 * 1000;
}

export function decorateSensorsWithMeasurements(sensors = [], measurements = [], options = {}) {
  const normalizedMeasurements = normalizeMeasurements(measurements);
  const latestByMac = new Map();
  normalizedMeasurements.forEach((measurement) => {
    latestByMac.set(measurement.mac, measurement);
  });

  return sensors.map((sensor) => {
    const measurement = latestByMac.get(sensor.mac);
    const lastSeen = measurement?.timestamp || sensor.last_seen;
    const annotated = {
      ...sensor,
      last_seen: lastSeen,
      latest_measurement: measurement || null,
      is_online: isSensorOnline(
        { ...sensor, last_seen: lastSeen },
        { thresholdMinutes: options.thresholdMinutes, now: options.now },
      ),
    };
    return annotated;
  });
}

export function mergeMeasurements(current = [], incoming = []) {
  const next = new Map();
  normalizeMeasurements(current).forEach((item) => {
    next.set(item.id ?? `${item.mac}-${item.timestamp}`, item);
  });
  normalizeMeasurements(incoming).forEach((item) => {
    next.set(item.id ?? `${item.mac}-${item.timestamp}`, item);
  });
  return normalizeMeasurements(Array.from(next.values()));
}

export function clone(value) {
  return identity(value);
}
