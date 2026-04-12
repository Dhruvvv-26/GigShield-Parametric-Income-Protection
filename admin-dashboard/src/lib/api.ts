import type { Claim, PaymentSummary, TriggerStatus, SHAPResult, SHAPInput, Zone, ExclusionReference } from './types'

const W  = import.meta.env.VITE_WORKER_URL  || 'http://localhost:8001'
const PL = import.meta.env.VITE_POLICY_URL  || 'http://localhost:8002'
const TR = import.meta.env.VITE_TRIGGER_URL || 'http://localhost:8003'
const CL = import.meta.env.VITE_CLAIMS_URL  || 'http://localhost:8004'
const PA = import.meta.env.VITE_PAYMENT_URL || 'http://localhost:8005'
const ML = import.meta.env.VITE_ML_URL      || 'http://localhost:8006'

async function get<T>(url: string, fallback: T): Promise<{ data: T; live: boolean }> {
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(4000) })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return { data: await r.json() as T, live: true }
  } catch {
    return { data: fallback, live: false }
  }
}

async function post<T>(url: string, body: unknown, fallback: T): Promise<{ data: T; live: boolean }> {
  try {
    const r = await fetch(url, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body), signal: AbortSignal.timeout(6000),
    })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return { data: await r.json() as T, live: true }
  } catch {
    return { data: fallback, live: false }
  }
}

// ─── Mock Data ────────────────────────────────────────────────────

const MOCK_CLAIMS: Claim[] = [
  {
    claim_id: 'CLM-2026-0041',
    worker_id: '6fc7ae56-8cc2-4d32-b8cf-c21844a177ce',
    rider_name: 'Arjun Kumar',
    zone: 'delhi_rohini',
    event_type: 'aqi',
    metric_value: 452,
    fraud_score: 0.08,
    fraud_flags: [],
    layer_scores: { gps: 0.06, sensor: 0.09, network: 0.11, behavioral: 0.05 },
    status: 'AUTO_APPROVED',
    payout_amount: 350,
    created_at: new Date(Date.now() - 3 * 60000).toISOString(),
    bouncer_passed: true,
  },
  {
    claim_id: 'CLM-2026-0040',
    worker_id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    rider_name: 'Meera Pillai',
    zone: 'delhi_rohini',
    event_type: 'aqi',
    metric_value: 448,
    fraud_score: 0.71,
    fraud_flags: ['GPS_INSTANT_LOCK_184ms', 'LOW_ACCEL_RMS_0.09', 'ZERO_TOWER_HANDOFFS'],
    layer_scores: { gps: 0.84, sensor: 0.78, network: 0.62, behavioral: 0.61 },
    status: 'SOFT_HOLD',
    payout_amount: 175,
    created_at: new Date(Date.now() - 8 * 60000).toISOString(),
    bouncer_passed: true,
  },
  {
    claim_id: 'CLM-2026-0039',
    worker_id: 'f0e1d2c3-b4a5-6789-0123-456789abcdef',
    rider_name: 'Rahul Verma',
    zone: 'delhi_rohini',
    event_type: 'aqi',
    metric_value: 501,
    fraud_score: 0.93,
    fraud_flags: ['MOCK_LOCATION_DETECTED', 'GPS_INSTANT_LOCK_228ms', 'ZERO_TOWER_HANDOFFS', 'BURST_SUBMISSION', 'IP_GPS_DELTA_18km'],
    layer_scores: { gps: 0.96, sensor: 0.91, network: 0.89, behavioral: 0.94 },
    status: 'BLOCKED',
    payout_amount: 0,
    created_at: new Date(Date.now() - 15 * 60000).toISOString(),
    bouncer_passed: false,
  },
  {
    claim_id: 'CLM-2026-0038',
    worker_id: '11223344-5566-7788-99aa-bbccddeeff00',
    rider_name: 'Sunita Yadav',
    zone: 'delhi_dwarka',
    event_type: 'heat',
    metric_value: 44.2,
    fraud_score: 0.19,
    fraud_flags: [],
    layer_scores: { gps: 0.14, sensor: 0.22, network: 0.18, behavioral: 0.20 },
    status: 'AUTO_APPROVED',
    payout_amount: 250,
    created_at: new Date(Date.now() - 22 * 60000).toISOString(),
    bouncer_passed: true,
  },
  {
    claim_id: 'CLM-2026-0037',
    worker_id: 'aabbccdd-eeff-0011-2233-445566778899',
    rider_name: 'Vikram Singh',
    zone: 'mumbai_andheri',
    event_type: 'rain',
    metric_value: 72,
    fraud_score: 0.44,
    fraud_flags: ['ELEVATED_GPS_VARIANCE', 'SLOW_SATELLITE_ACQUIRE'],
    layer_scores: { gps: 0.52, sensor: 0.31, network: 0.41, behavioral: 0.50 },
    status: 'AUTO_APPROVED',
    payout_amount: 380,
    created_at: new Date(Date.now() - 34 * 60000).toISOString(),
    bouncer_passed: true,
  },
]

const MOCK_SUMMARY: PaymentSummary = {
  total_premiums: 1287400,
  total_payouts: 836810,
  loss_ratio: 0.65,
  active_policies: 183,
  claims_pending: 2,
  fraud_blocks_24h: 17,
  auto_approved_24h: 94,
  soft_holds_24h: 5,
  burning_cost_rate: 62.3,
  bcr_status: 'SOLVENT',
  trailing_30d_premiums: 5149600,
  trailing_30d_payouts: 3208180,
  reserve_ratio: 37.7,
}

const MOCK_TRIGGER: TriggerStatus = {
  last_poll: new Date(Date.now() - 90000).toISOString(),
  scheduler_running: true,
  zones_affected: 3,
  active_triggers: [
    { zone: 'delhi_rohini', event_type: 'aqi', metric_value: 452, tier: 2, triggered_at: new Date(Date.now() - 4 * 60000).toISOString() },
    { zone: 'delhi_dwarka', event_type: 'heat', metric_value: 44.2, tier: 1, triggered_at: new Date(Date.now() - 25 * 60000).toISOString() },
    { zone: 'mumbai_andheri', event_type: 'rain', metric_value: 72, tier: 2, triggered_at: new Date(Date.now() - 37 * 60000).toISOString() },
  ],
}

const MOCK_SHAP: SHAPResult = {
  recommended_premium: 127.00,
  confidence: 0.94,
  model_version: 'xgb+lgbm-v2.1',
  shap_breakdown: {
    base_rate: 25.00,
    zone_aqi_risk: 32.50,
    seasonality_month: 14.80,
    vehicle_type_bicycle: 18.90,
    disruption_history_90d: 12.40,
    declared_daily_trips: 10.60,
    avg_daily_earnings: 8.20,
    historical_rain_events: 6.30,
    platform_blinkit_multiplier: 9.60,
    coverage_tier_standard: 15.70,
    monthly_work_days: 4.50,
    new_rider_discount: -16.50,
    zone_clustering_adjustment: -15.00,
  },
}

const MOCK_ZONES: Zone[] = [
  { zone_id: 'delhi_rohini',       city: 'Delhi NCR',  centroid_lat: 28.7300, centroid_lon: 77.1150, active_riders: 47, risk_score: 0.82, trigger_count_30d: 12, last_trigger: 'AQI 452' },
  { zone_id: 'delhi_dwarka',       city: 'Delhi NCR',  centroid_lat: 28.5921, centroid_lon: 77.0460, active_riders: 31, risk_score: 0.68, trigger_count_30d: 8,  last_trigger: 'Heat 44.2°C' },
  { zone_id: 'delhi_connaught',    city: 'Delhi NCR',  centroid_lat: 28.6315, centroid_lon: 77.2167, active_riders: 22, risk_score: 0.54, trigger_count_30d: 5 },
  { zone_id: 'mumbai_andheri',     city: 'Mumbai',     centroid_lat: 19.1136, centroid_lon: 72.8697, active_riders: 39, risk_score: 0.71, trigger_count_30d: 9, last_trigger: 'Rain 72mm' },
  { zone_id: 'mumbai_bandra',      city: 'Mumbai',     centroid_lat: 19.0596, centroid_lon: 72.8295, active_riders: 28, risk_score: 0.60, trigger_count_30d: 6 },
  { zone_id: 'bengaluru_koramangala', city: 'Bengaluru', centroid_lat: 12.9352, centroid_lon: 77.6245, active_riders: 16, risk_score: 0.38, trigger_count_30d: 3 },
]

// ─── Exported API ─────────────────────────────────────────────────

export async function fetchClaims() {
  return get<Claim[]>(`${CL}/api/v1/claims?limit=50`, MOCK_CLAIMS)
}

export async function fetchPaymentSummary() {
  return get<PaymentSummary>(`${PA}/api/v1/payments/summary`, MOCK_SUMMARY)
}

export async function fetchTriggerStatus() {
  return get<TriggerStatus>(`${TR}/api/v1/trigger/status`, MOCK_TRIGGER)
}

export async function calculatePremium(input: SHAPInput) {
  return post<SHAPResult>(`${ML}/api/v1/premium/calculate`, input, MOCK_SHAP)
}

export async function fetchZones() {
  return get<Zone[]>(`${W}/api/v1/zones`, MOCK_ZONES)
}

export async function approveClaim(claimId: string) {
  return post<{ status: string }>(`${CL}/api/v1/claims/admin/review/${claimId}`, { action: 'approve' }, { status: 'approved' })
}

export async function blockClaim(claimId: string) {
  return post<{ status: string }>(`${CL}/api/v1/claims/admin/review/${claimId}`, { action: 'reject' }, { status: 'blocked' })
}

export async function holdClaim(claimId: string, reason?: string) {
  return post<{ status: string }>(`${CL}/api/v1/claims/admin/review/${claimId}`, { action: 'release_hold', reviewer_note: reason }, { status: 'soft_hold' })
}

export async function fetchExclusions() {
  return get<ExclusionReference>(`${PL}/api/v1/policies/exclusions/reference`, {
    exclusions: [
      { code: 'ACT_OF_WAR', label: 'Act of War', description: 'Armed conflict or invasion.' },
      { code: 'PANDEMIC_DECLARED', label: 'WHO Pandemic', description: 'WHO-declared pandemic.' },
      { code: 'TERRORISM', label: 'Terrorism', description: 'Designated terrorist incident.' },
      { code: 'NUCLEAR_EVENT', label: 'Nuclear Event', description: 'Nuclear/radiological contamination.' },
      { code: 'GOVERNMENT_MANDATED_LOCKDOWN_BEYOND_72H', label: 'Extended Lockdown (>72h)', description: 'Government lockdowns >72 hours.' },
    ]
  })
}

export { W, PL, TR, CL, PA, ML }
