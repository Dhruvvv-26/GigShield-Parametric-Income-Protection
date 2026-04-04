-- ============================================================
-- KavachAI — Database Schema
-- Migration 01: Core tables
-- Run once at container startup via docker-entrypoint-initdb.d
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── ENUM TYPES ────────────────────────────────────────────────────────────────

CREATE TYPE vehicle_type AS ENUM ('bicycle', 'e_bike', 'motorcycle', 'scooter');
CREATE TYPE platform_type AS ENUM ('blinkit', 'zepto', 'dunzo', 'swiggy_instamart');
CREATE TYPE work_hours_profile AS ENUM ('full_day', 'peak_only', 'morning_only', 'evening_only');
CREATE TYPE coverage_tier AS ENUM ('basic', 'standard', 'premium');
CREATE TYPE policy_status AS ENUM ('active', 'expired', 'cancelled', 'pending_payment');
CREATE TYPE claim_status AS ENUM ('pending', 'auto_approved', 'soft_hold', 'blocked', 'completed', 'rejected');
CREATE TYPE trigger_event_type AS ENUM ('aqi', 'heavy_rain', 'extreme_heat', 'cyclone', 'curfew', 'flood_alert');
CREATE TYPE trigger_tier AS ENUM ('tier1', 'tier2', 'tier3');
CREATE TYPE payout_status AS ENUM ('pending', 'processing', 'completed', 'failed', 'refunded');
CREATE TYPE kyc_status AS ENUM ('pending', 'verified', 'rejected');

-- ── ZONES TABLE (populated by migration 02) ───────────────────────────────────

CREATE TABLE zones (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_code       VARCHAR(50) UNIQUE NOT NULL,     -- e.g. 'delhi_rohini'
    zone_name       VARCHAR(100) NOT NULL,           -- e.g. 'Rohini, Delhi'
    city            VARCHAR(50) NOT NULL,            -- e.g. 'delhi_ncr'
    geohash         VARCHAR(12),                     -- GeoHash precision 6
    boundary        GEOMETRY(POLYGON, 4326) NOT NULL,  -- PostGIS polygon
    risk_multiplier NUMERIC(4,2) NOT NULL DEFAULT 1.0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_zones_city ON zones(city);
CREATE INDEX idx_zones_boundary ON zones USING GIST(boundary);
CREATE INDEX idx_zones_geohash ON zones(geohash);

-- ── WORKERS TABLE ─────────────────────────────────────────────────────────────

CREATE TABLE workers (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_hash              VARCHAR(128) UNIQUE NOT NULL,  -- bcrypt hash
    phone_last4             VARCHAR(4),                    -- for display only
    platform                platform_type NOT NULL,
    platform_partner_id     VARCHAR(100),                  -- Blinkit/Zepto fleet ID
    full_name               VARCHAR(100) NOT NULL,
    vehicle_type            vehicle_type NOT NULL,
    work_hours_profile      work_hours_profile NOT NULL DEFAULT 'full_day',
    declared_daily_trips    INTEGER NOT NULL CHECK (declared_daily_trips BETWEEN 1 AND 60),
    declared_daily_income   NUMERIC(8,2) NOT NULL,         -- ₹ self-reported
    home_pincode            VARCHAR(10),
    kyc_status              kyc_status NOT NULL DEFAULT 'pending',
    device_fingerprint      VARCHAR(128),                  -- SHA-256 of device params
    upi_id                  TEXT,                          -- Fernet encrypted
    work_location           GEOMETRY(POINT, 4326),         -- Last known GPS
    zone_id                 UUID REFERENCES zones(id),
    primary_zone_id         UUID REFERENCES zones(id),
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_workers_zone ON workers(zone_id);
CREATE INDEX idx_workers_platform ON workers(platform);
CREATE INDEX idx_workers_work_location ON workers USING GIST(work_location);
CREATE INDEX idx_workers_phone_hash ON workers(phone_hash);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER workers_updated_at
    BEFORE UPDATE ON workers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── GPS PINGS TABLE ───────────────────────────────────────────────────────────

CREATE TABLE gps_pings (
    id          BIGSERIAL PRIMARY KEY,
    worker_id   UUID NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
    location    GEOMETRY(POINT, 4326) NOT NULL,
    accuracy_m  NUMERIC(8,2),           -- OS-reported accuracy in metres
    speed_kmh   NUMERIC(6,2),           -- Computed velocity
    altitude_m  NUMERIC(8,2),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_gps_pings_worker ON gps_pings(worker_id, recorded_at DESC);
CREATE INDEX idx_gps_pings_location ON gps_pings USING GIST(location);

-- Partition hint: In production, partition by recorded_at (monthly).

-- ── POLICIES TABLE ────────────────────────────────────────────────────────────

CREATE TABLE policies (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    worker_id           UUID NOT NULL REFERENCES workers(id) ON DELETE RESTRICT,
    zone_id             UUID NOT NULL REFERENCES zones(id),
    coverage_tier       coverage_tier NOT NULL DEFAULT 'standard',
    status              policy_status NOT NULL DEFAULT 'pending_payment',
    weekly_premium      NUMERIC(8,2) NOT NULL,     -- ₹
    max_payout_per_event NUMERIC(8,2) NOT NULL,    -- ₹
    max_payout_per_week NUMERIC(8,2) NOT NULL,     -- ₹
    coverage_start      TIMESTAMPTZ,               -- Set when payment confirmed
    coverage_end        TIMESTAMPTZ,               -- coverage_start + 7 days
    razorpay_payment_id VARCHAR(100),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT no_overlapping_policies UNIQUE (worker_id, coverage_start, coverage_end)
);

CREATE INDEX idx_policies_worker ON policies(worker_id);
CREATE INDEX idx_policies_zone ON policies(zone_id);
CREATE INDEX idx_policies_status ON policies(status);
CREATE INDEX idx_policies_active ON policies(worker_id, status)
    WHERE status = 'active';

CREATE TRIGGER policies_updated_at
    BEFORE UPDATE ON policies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── TRIGGER EVENTS TABLE ─────────────────────────────────────────────────────

CREATE TABLE trigger_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    zone_id         UUID NOT NULL REFERENCES zones(id),
    event_type      trigger_event_type NOT NULL,
    tier            trigger_tier NOT NULL,
    metric_value    NUMERIC(10,2) NOT NULL,         -- AQI reading / mm rainfall / °C
    metric_unit     VARCHAR(20) NOT NULL,            -- 'aqi' / 'mm' / 'celsius'
    data_source     VARCHAR(50) NOT NULL,            -- 'openweathermap' / 'cpcb' / 'test'
    raw_payload     JSONB,                           -- Full API response for audit
    is_sustained    BOOLEAN NOT NULL DEFAULT FALSE,  -- Has threshold held for min duration
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sustained_since TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX idx_trigger_events_zone ON trigger_events(zone_id, detected_at DESC);
CREATE INDEX idx_trigger_events_type ON trigger_events(event_type);
CREATE INDEX idx_trigger_events_active ON trigger_events(zone_id)
    WHERE resolved_at IS NULL;

-- ── CLAIMS TABLE ──────────────────────────────────────────────────────────────

CREATE TABLE claims (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_id           UUID NOT NULL REFERENCES policies(id),
    worker_id           UUID NOT NULL REFERENCES workers(id),
    trigger_event_id    UUID NOT NULL REFERENCES trigger_events(id),
    status              claim_status NOT NULL DEFAULT 'pending',
    payout_amount       NUMERIC(8,2) NOT NULL,
    fraud_score         NUMERIC(5,4),               -- 0.0000 – 1.0000
    fraud_flags         JSONB DEFAULT '[]',          -- Array of flag codes
    worker_gps_at_claim GEOMETRY(POINT, 4326),
    sensor_data         JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at         TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    CONSTRAINT one_claim_per_policy_event UNIQUE (policy_id, trigger_event_id)
);

CREATE INDEX idx_claims_worker ON claims(worker_id, created_at DESC);
CREATE INDEX idx_claims_status ON claims(status);
CREATE INDEX idx_claims_trigger ON claims(trigger_event_id);

-- ── PAYMENTS TABLE ────────────────────────────────────────────────────────────

CREATE TABLE payments (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    claim_id            UUID NOT NULL REFERENCES claims(id),
    worker_id           UUID NOT NULL REFERENCES workers(id),
    amount              NUMERIC(8,2) NOT NULL,
    status              payout_status NOT NULL DEFAULT 'pending',
    razorpay_payout_id  VARCHAR(100),
    upi_id_masked       VARCHAR(50),                -- Masked for display
    initiated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    failed_at           TIMESTAMPTZ,
    failure_reason      TEXT,
    retry_count         SMALLINT NOT NULL DEFAULT 0
);

CREATE INDEX idx_payments_claim ON payments(claim_id);
CREATE INDEX idx_payments_worker ON payments(worker_id, initiated_at DESC);
CREATE INDEX idx_payments_status ON payments(status);

-- Append-only audit log — no UPDATE/DELETE allowed
CREATE TABLE payment_audit_log (
    id          BIGSERIAL PRIMARY KEY,
    payment_id  UUID NOT NULL REFERENCES payments(id),
    old_status  payout_status,
    new_status  payout_status NOT NULL,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    changed_by  VARCHAR(50) NOT NULL,   -- service name
    note        TEXT
);

-- Enforce append-only
CREATE RULE payment_audit_no_update AS ON UPDATE TO payment_audit_log DO INSTEAD NOTHING;
CREATE RULE payment_audit_no_delete AS ON DELETE TO payment_audit_log DO INSTEAD NOTHING;

-- ── PREMIUM CALCULATION LOG ───────────────────────────────────────────────────

CREATE TABLE premium_calculations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    worker_id       UUID NOT NULL REFERENCES workers(id),
    zone_id         UUID NOT NULL REFERENCES zones(id),
    coverage_tier   coverage_tier NOT NULL,
    base_rate       NUMERIC(8,2) NOT NULL,
    zone_multiplier NUMERIC(5,3) NOT NULL,
    season_factor   NUMERIC(5,3) NOT NULL,
    history_factor  NUMERIC(5,3) NOT NULL,
    tier_factor     NUMERIC(5,3) NOT NULL,
    final_premium   NUMERIC(8,2) NOT NULL,
    calculation_method VARCHAR(20) NOT NULL DEFAULT 'rule_based', -- 'rule_based' / 'xgboost'
    shap_values     JSONB,          -- Phase 3: SHAP waterfall data
    calculated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_premium_calc_worker ON premium_calculations(worker_id, calculated_at DESC);
