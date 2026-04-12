/**
 * KavachAI Worker App — Production API Client
 *
 * All service URLs are driven by EXPO_PUBLIC_* environment variables.
 * For tunnel access (loca.lt), set EXPO_PUBLIC_TUNNEL_CLAIMS / _POLICY.
 * For direct LAN access, set EXPO_PUBLIC_CLAIMS_SERVICE etc.
 */

// ── Service URLs sourced from env vars ─────────────────────────────────────

const API_HOST = process.env.EXPO_PUBLIC_API_HOST ?? "localhost";

export const WORKER_ID =
  process.env.EXPO_PUBLIC_WORKER_ID ?? "fffafc0b-7c28-42e8-ae34-020f51acf148";

export const SERVICES = {
  worker:  process.env.EXPO_PUBLIC_WORKER_SERVICE  ?? `http://${API_HOST}:8001`,
  policy:  process.env.EXPO_PUBLIC_TUNNEL_POLICY   ?? process.env.EXPO_PUBLIC_POLICY_SERVICE  ?? `http://${API_HOST}:8002`,
  trigger: process.env.EXPO_PUBLIC_TRIGGER_SERVICE  ?? `http://${API_HOST}:8003`,
  claims:  process.env.EXPO_PUBLIC_TUNNEL_CLAIMS   ?? process.env.EXPO_PUBLIC_CLAIMS_SERVICE  ?? `http://${API_HOST}:8004`,
  payment: process.env.EXPO_PUBLIC_PAYMENT_SERVICE  ?? `http://${API_HOST}:8005`,
  ml:      process.env.EXPO_PUBLIC_ML_SERVICE       ?? `http://${API_HOST}:8006`,
};

// ── Common headers (bypass-tunnel-reminder for loca.lt tunnels) ────────────

const HEADERS: Record<string, string> = {
  "bypass-tunnel-reminder": "true",
  "Content-Type": "application/json",
};

// ── Helper ─────────────────────────────────────────────────────────────────

async function apiFetch<T>(url: string, init?: RequestInit): Promise<T | null> {
  try {
    const response = await fetch(url, {
      ...init,
      headers: { ...HEADERS, ...(init?.headers ?? {}) },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (e) {
    console.error(`❌ API Error [${url}]:`, e);
    return null;
  }
}

// ── Public API functions ───────────────────────────────────────────────────

export const getWorkerProfile = async () => {
  console.log("📡 [PROD] Fetching Worker Profile...");
  return apiFetch(`${SERVICES.worker}/api/v1/workers/${WORKER_ID}`);
};

export const getActivePolicy = async () => {
  console.log("📡 [PROD] Fetching Policy...");
  const data = await apiFetch<{ policies: any[]; active_count: number }>(
    `${SERVICES.policy}/api/v1/policies/worker/${WORKER_ID}`
  );
  if (!data?.policies?.length) return null;
  // Pick the first active policy, or fall back to the most recent one
  const policy =
    data.policies.find((p: any) => p.status === "active") || data.policies[0];
  // Normalize field names for the frontend screens
  return {
    ...policy,
    tier: policy.coverage_tier,
    premium_amount: policy.weekly_premium,
    max_payout_amount: policy.max_payout_per_event,
    end_date: policy.coverage_end,
    start_date: policy.coverage_start,
  };
};

export const getWorkerClaims = async () => {
  console.log("📡 [PROD] Fetching Claims...");
  const data = await apiFetch<{ claims: any[] }>(
    `${SERVICES.claims}/api/v1/claims/worker/${WORKER_ID}`
  );
  return data?.claims ?? [];
};

export const getZoneWeather = async () => {
  console.log("📡 [PROD] Fetching Zone Weather / Triggers...");
  return apiFetch(`${SERVICES.trigger}/api/v1/trigger/status`);
};

export const getWorkerPayments = async () => {
  console.log("📡 [PROD] Fetching Payments...");
  const data = await apiFetch<{ payments: any[] }>(
    `${SERVICES.payment}/api/v1/payments/worker/${WORKER_ID}`
  );
  return data?.payments ?? [];
};

export const sendSensorPing = async (sensorData: Record<string, any>) => {
  console.log("📡 [PROD] Sending Sensor Ping...");
  return apiFetch(
    `${SERVICES.claims}/api/v1/claims/sensor_data/${WORKER_ID}`,
    { method: "POST", body: JSON.stringify(sensorData) }
  );
};

// ── Phase 3 additions ──────────────────────────────────────────────────────

export const fetchPolicyExclusions = async () => {
  console.log("📡 [PROD] Fetching Force Majeure Exclusions...");
  return apiFetch<{ exclusions: Array<{ code: string; label: string; description: string }> }>(
    `${SERVICES.policy}/api/v1/policies/exclusions/reference`
  );
};

export const fetchPaymentSummaryPublic = async () => {
  console.log("📡 [PROD] Fetching Payment Summary (BCR)...");
  return apiFetch<{
    total_premiums_this_week: number;
    total_payouts_this_week: number;
    loss_ratio_percent: number;
    burning_cost_rate: number;
    bcr_status: string;
    reserve_ratio: number;
  }>(`${SERVICES.payment}/api/v1/payments/summary`);
};
