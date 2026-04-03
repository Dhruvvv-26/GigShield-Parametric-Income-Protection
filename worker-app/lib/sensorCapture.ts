/**
 * KavachAI Worker App — Sensor Capture SDK
 *
 * Background sensor capture for fraud scoring:
 * - GPS pings (5 pings over 30 seconds)
 * - Accelerometer RMS
 * - Gyroscope yaw rate
 * - Mock location detection
 * - IP-GPS geo delta
 *
 * Triggered silently when FCM "trigger_active" notification arrives.
 * Data is POST'd to Claims Service /api/v1/claims/sensor_data/{rider_id}
 */
import * as Location from 'expo-location';
import { Accelerometer, Gyroscope } from 'expo-sensors';
import * as Device from 'expo-device';
import axios from 'axios';
import api from './api';

interface GpsPing {
  lat: number;
  lng: number;
  accuracy_m: number;
  timestamp: string;
}

interface SensorPayload {
  gps_pings: GpsPing[];
  accelerometer_rms: number;
  gyroscope_yaw_rate: number;
  is_mock_location: boolean;
  is_developer_mode: boolean;
  gps_cold_start_ms: number;
  ip_address: string | null;
  ip_geo_lat: number | null;
  ip_geo_lng: number | null;
}

/**
 * Capture sensor data over a 30-second window and submit to backend.
 * This runs silently in background — the rider sees only the payout notification.
 */
export async function captureSensorData(workerId: string): Promise<void> {
  console.log('[SensorSDK] Starting sensor capture for worker', workerId.substring(0, 8));

  try {
    // Request location permissions
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== 'granted') {
      console.log('[SensorSDK] Location permission not granted, submitting partial data');
      await submitPartialData(workerId);
      return;
    }

    // Parallel capture of all sensor data
    const [gpsPings, accelData, gyroData, ipGeo, mockCheck] = await Promise.allSettled([
      captureGpsPings(),
      captureAccelerometer(),
      captureGyroscope(),
      captureIpGeo(),
      detectMockLocation(),
    ]);

    const payload: SensorPayload = {
      gps_pings: gpsPings.status === 'fulfilled' ? gpsPings.value.pings : [],
      gps_cold_start_ms: gpsPings.status === 'fulfilled' ? gpsPings.value.coldStart : 30000,
      accelerometer_rms: accelData.status === 'fulfilled' ? accelData.value : 0,
      gyroscope_yaw_rate: gyroData.status === 'fulfilled' ? gyroData.value : 0,
      is_mock_location: mockCheck.status === 'fulfilled' ? mockCheck.value.isMock : false,
      is_developer_mode: mockCheck.status === 'fulfilled' ? mockCheck.value.isDevMode : false,
      ip_address: ipGeo.status === 'fulfilled' ? ipGeo.value.ip : null,
      ip_geo_lat: ipGeo.status === 'fulfilled' ? ipGeo.value.lat : null,
      ip_geo_lng: ipGeo.status === 'fulfilled' ? ipGeo.value.lng : null,
    };

    // Submit to Claims Service
    await api.claims.post(`/api/v1/claims/sensor_data/${workerId}`, payload);
    console.log('[SensorSDK] Sensor data submitted successfully');

  } catch (error) {
    console.error('[SensorSDK] Error during sensor capture:', error);
  }
}

/**
 * Capture 5 GPS pings over 30 seconds (one every 6 seconds).
 */
async function captureGpsPings(): Promise<{ pings: GpsPing[]; coldStart: number }> {
  const pings: GpsPing[] = [];
  let coldStart = 30000;

  for (let i = 0; i < 5; i++) {
    try {
      const startLock = Date.now();
      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });
      if (i === 0) {
        coldStart = Date.now() - startLock;
      }

      pings.push({
        lat: location.coords.latitude,
        lng: location.coords.longitude,
        accuracy_m: location.coords.accuracy || 0,
        timestamp: new Date(location.timestamp).toISOString(),
      });

      if (i < 4) {
        await sleep(6000); // 6 seconds between pings
      }
    } catch (e) {
      console.log(`[SensorSDK] GPS ping ${i + 1} failed:`, e);
    }
  }

  return { pings, coldStart };
}

/**
 * Capture accelerometer RMS over 30-second window.
 * RMS = sqrt(mean(x² + y² + z²))
 */
async function captureAccelerometer(): Promise<number> {
  return new Promise((resolve) => {
    const samples: number[] = [];

    Accelerometer.setUpdateInterval(200); // 5 Hz
    const subscription = Accelerometer.addListener(({ x, y, z }) => {
      samples.push(Math.sqrt(x * x + y * y + z * z));
    });

    // Collect for 10 seconds (we don't need the full 30s)
    setTimeout(() => {
      subscription.remove();
      if (samples.length === 0) {
        resolve(0);
        return;
      }
      const mean = samples.reduce((a, b) => a + b, 0) / samples.length;
      resolve(parseFloat(mean.toFixed(3)));
    }, 10000);
  });
}

/**
 * Capture gyroscope mean yaw rate over 10-second window.
 */
async function captureGyroscope(): Promise<number> {
  return new Promise((resolve) => {
    const yawRates: number[] = [];

    Gyroscope.setUpdateInterval(200); // 5 Hz
    const subscription = Gyroscope.addListener(({ z }) => {
      yawRates.push(Math.abs(z)); // z-axis = yaw
    });

    setTimeout(() => {
      subscription.remove();
      if (yawRates.length === 0) {
        resolve(0);
        return;
      }
      const mean = yawRates.reduce((a, b) => a + b, 0) / yawRates.length;
      resolve(parseFloat(mean.toFixed(4)));
    }, 10000);
  });
}

/**
 * Get IP-based geolocation for network-GPS consistency check.
 * Uses ip-api.com (free, 1000 req/day limit).
 */
async function captureIpGeo(): Promise<{ ip: string; lat: number; lng: number }> {
  try {
    const response = await axios.get('http://ip-api.com/json/?fields=query,lat,lon', {
      timeout: 5000,
    });
    return {
      ip: response.data.query,
      lat: response.data.lat,
      lng: response.data.lon,
    };
  } catch {
    return { ip: '', lat: 0, lng: 0 };
  }
}

/**
 * Detect if mock location or developer mode is enabled.
 */
async function detectMockLocation(): Promise<{ isMock: boolean; isDevMode: boolean }> {
  const isRealDevice = Device.isDevice;

  // On emulators / non-real-devices, flag as potential mock
  const isMock = !isRealDevice;

  // Check for developer mode (Android specific)
  // expo-device doesn't expose dev mode directly, but non-device = suspect
  const isDevMode = !isRealDevice;

  return { isMock, isDevMode };
}

/**
 * Submit partial data when full sensor capture isn't possible.
 */
async function submitPartialData(workerId: string): Promise<void> {
  const payload: SensorPayload = {
    gps_pings: [],
    gps_cold_start_ms: 30000,
    accelerometer_rms: 0,
    gyroscope_yaw_rate: 0,
    is_mock_location: !Device.isDevice,
    is_developer_mode: !Device.isDevice,
    ip_address: null,
    ip_geo_lat: null,
    ip_geo_lng: null,
  };

  try {
    await api.claims.post(`/api/v1/claims/sensor_data/${workerId}`, payload);
    console.log('[SensorSDK] Partial sensor data submitted');
  } catch (error) {
    console.error('[SensorSDK] Failed to submit partial data:', error);
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
