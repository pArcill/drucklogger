import { describe, expect, it } from 'vitest';
import {
  calculatePressureStats,
  decorateSensorsWithMeasurements,
  isSensorOnline,
  limitMeasurements,
  mergeMeasurements,
} from '../scripts/analytics.js';

const sampleMeasurements = [
  { id: 1, mac: 'AA', pressure: 101.1, timestamp: '2024-03-01T10:00:00Z' },
  { id: 2, mac: 'AA', pressure: 101.3, timestamp: '2024-03-01T10:05:00Z' },
  { id: 3, mac: 'BB', pressure: 100.9, timestamp: '2024-03-01T10:07:00Z' },
];

describe('calculatePressureStats', () => {
  it('derives range, average, and latest entries', () => {
    const stats = calculatePressureStats(sampleMeasurements);
    expect(stats.latest.mac).toBe('BB');
    expect(stats.min).toBeCloseTo(100.9);
    expect(stats.max).toBeCloseTo(101.3);
    expect(stats.average).toBeCloseTo((101.1 + 101.3 + 100.9) / 3);
    expect(stats.total).toBe(3);
  });

  it('handles empty arrays gracefully', () => {
    const stats = calculatePressureStats();
    expect(stats.latest).toBeNull();
    expect(stats.total).toBe(0);
    expect(stats.average).toBeNull();
  });
});

describe('limitMeasurements', () => {
  it('returns chronologically sorted slices', () => {
    const limited = limitMeasurements(sampleMeasurements, 2);
    expect(limited).toHaveLength(2);
    expect(limited[0].mac).toBe('AA');
    expect(limited[1].mac).toBe('BB');
  });
});

describe('decorateSensorsWithMeasurements', () => {
  const sensors = [
    { id: 1, mac: 'AA', last_seen: '2024-03-01T10:03:00Z', battery: 0.8 },
    { id: 2, mac: 'BB', last_seen: '2024-03-01T09:59:00Z', battery: 0.6 },
  ];

  it('matches sensors with their most recent measurement', () => {
    const annotated = decorateSensorsWithMeasurements(sensors, sampleMeasurements, {
      now: new Date('2024-03-01T10:08:00Z'),
    });
    const first = annotated.find((sensor) => sensor.mac === 'AA');
    expect(first.latest_measurement.pressure).toBeCloseTo(101.3);
    expect(first.is_online).toBe(true);
  });

  it('marks sensors as offline when stale', () => {
    const annotated = decorateSensorsWithMeasurements(sensors, sampleMeasurements, {
      now: new Date('2024-03-01T10:40:00Z'),
    });
    const second = annotated.find((sensor) => sensor.mac === 'BB');
    expect(second.is_online).toBe(false);
  });
});

describe('isSensorOnline', () => {
  it('honors the threshold override', () => {
    const sensor = { last_seen: '2024-03-01T10:00:00Z' };
    const now = new Date('2024-03-01T10:20:00Z');
    expect(isSensorOnline(sensor, { now, thresholdMinutes: 15 })).toBe(false);
    expect(isSensorOnline(sensor, { now, thresholdMinutes: 25 })).toBe(true);
  });
});

describe('mergeMeasurements', () => {
  it('deduplicates entries with matching ids', () => {
    const current = [
      { id: 'AA-1', mac: 'AA', pressure: 101, timestamp: '2024-03-01T10:00:00Z' },
      { id: 'BB-1', mac: 'BB', pressure: 100.8, timestamp: '2024-03-01T10:01:00Z' },
    ];
    const incoming = [
      { id: 'AA-1', mac: 'AA', pressure: 101.5, timestamp: '2024-03-01T10:00:00Z' },
      { id: 'CC-1', mac: 'CC', pressure: 100.4, timestamp: '2024-03-01T10:02:00Z' },
    ];
    const merged = mergeMeasurements(current, incoming);
    expect(merged).toHaveLength(3);
    const aa = merged.find((item) => item.mac === 'AA');
    expect(aa.pressure).toBeCloseTo(101.5);
  });
});
