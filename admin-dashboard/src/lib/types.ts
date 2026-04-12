export interface Claim {
  claim_id: string
  worker_id: string
  rider_name: string
  zone: string
  event_type: 'aqi' | 'rain' | 'heat' | 'cyclone' | 'bandh'
  metric_value: number
  fraud_score: number
  fraud_flags: string[]
  layer_scores: {
    gps: number
    sensor: number
    network: number
    behavioral: number
  }
  status: 'AUTO_APPROVED' | 'SOFT_HOLD' | 'BLOCKED' | 'PENDING'
  payout_amount: number
  created_at: string
  bouncer_passed?: boolean
}

export interface PaymentSummary {
  total_premiums: number
  total_payouts: number
  loss_ratio: number
  active_policies: number
  claims_pending: number
  fraud_blocks_24h: number
  auto_approved_24h: number
  soft_holds_24h: number
  // BCR fields — Phase 3
  burning_cost_rate: number
  bcr_status: 'SOLVENT' | 'WATCH' | 'CRITICAL'
  trailing_30d_premiums: number
  trailing_30d_payouts: number
  reserve_ratio: number
}

export interface TriggerStatus {
  last_poll: string
  active_triggers: ActiveTrigger[]
  zones_affected: number
  scheduler_running: boolean
}

export interface ActiveTrigger {
  zone: string
  event_type: string
  metric_value: number
  tier: 1 | 2 | 3
  triggered_at: string
}

export interface SHAPResult {
  recommended_premium: number
  shap_breakdown: Record<string, number>
  model_version: string
  confidence: number
}

export interface SHAPInput {
  city: string
  vehicle_type: string
  coverage_tier: string
  month: number
  historical_aqi_events_12m: number
  historical_rain_events_12m: number
  disruption_history_90d: number
  declared_daily_trips: number
  avg_daily_earnings: number
  monthly_work_days: number
}

export interface Zone {
  zone_id: string
  city: string
  centroid_lat: number
  centroid_lon: number
  active_riders: number
  risk_score: number
  last_trigger?: string
  trigger_count_30d: number
}

export interface Exclusion {
  code: string
  label: string
  description: string
}

export interface ExclusionReference {
  exclusions: Exclusion[]
}
