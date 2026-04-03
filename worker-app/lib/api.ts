// lib/api.ts
// GigShield API Service — wired to live backend

// Dynamically pull the exact IDs we just tested in the backend
const WORKER_ID = process.env.EXPO_PUBLIC_WORKER_ID;
const POLICY_ID = process.env.EXPO_PUBLIC_POLICY_ID;

// For Expo Go on physical device: use your machine's local IP
const LOCAL_IP = process.env.EXPO_PUBLIC_API_HOST;

export const SERVICES = {
  worker:  `http://${LOCAL_IP}:8001`,
  policy:  `http://${LOCAL_IP}:8002`,
  trigger: `http://${LOCAL_IP}:8003`,
  claims:  `http://${LOCAL_IP}:8004`,
  payment: `http://${LOCAL_IP}:8005`,
  ml:      `http://${LOCAL_IP}:8006`,
};

// ── Helper ────────────────────────────────────────────────────────────────────
async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
  });
  if (!res.ok) throw new Error(`API error ${res.status} at ${url}`);
  return res.json();
}

// ── Worker / Policy ───────────────────────────────────────────────────────────
export async function getWorkerProfile() {
  return apiFetch(`${SERVICES.worker}/api/v1/riders/${WORKER_ID}`);
}

export async function getActivePolicy() {
  const policies: any = await apiFetch(
    `${SERVICES.policy}/api/v1/policies/worker/${WORKER_ID}`
  );
  // sometimes policies is an array or { policies: [] }
  const list = policies.policies || policies || [];
  return Array.isArray(list) ? list.find((p: any) => p.status === "active") ?? null : null;
}

export async function getPremiumBreakdown(policyId = POLICY_ID) {
  return apiFetch(`${SERVICES.policy}/api/v1/policies/${policyId}`);
}

// ── Disruption Monitor (live weather for delhi_rohini) ────────────────────────
export async function getZoneWeather() {
  return apiFetch(`${SERVICES.trigger}/api/v1/trigger/status`);
}

// ── Payouts / Claims ──────────────────────────────────────────────────────────
export const getWorkerClaims = async () => {
  const response = await fetch(`${SERVICES.claims}/api/v1/claims/worker/${WORKER_ID}`);
  const data = await response.json();
  return data.claims || [];
};

export const getWorkerPayments = async () => {
  const response = await fetch(`${SERVICES.payment}/api/v1/payments/worker/${WORKER_ID}`);
  const data = await response.json();
  return data.payments || [];
};

// ── GPS / Sensor Ping (background, silent) ────────────────────────────────────
export async function sendSensorPing(payload: {
  latitude?: number;
  longitude?: number;
  accuracy_meters?: number;
  accelerometer_rms?: number;
  gyroscope_yaw?: number;
  is_mock_location?: boolean;
  is_developer_mode?: boolean;
  gps_cold_start_ms?: number;
  [key: string]: any;
}) {
  return apiFetch(
    `${SERVICES.worker}/api/v1/riders/${WORKER_ID}/gps`,
    { method: "POST", body: JSON.stringify(payload) }
  );
}

export { WORKER_ID, POLICY_ID, LOCAL_IP };
