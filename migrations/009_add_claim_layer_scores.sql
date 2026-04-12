-- ============================================================
-- KavachAI — Migration 009: Add Claim Layer Scores
-- Adds per-layer fraud score breakdown columns to claims table.
-- Used by the admin dashboard fraud queue to show the
-- contribution of each detection layer.
-- ============================================================

ALTER TABLE claims
ADD COLUMN IF NOT EXISTS gps_score NUMERIC(5,4);

ALTER TABLE claims
ADD COLUMN IF NOT EXISTS sensor_score NUMERIC(5,4);

ALTER TABLE claims
ADD COLUMN IF NOT EXISTS network_score NUMERIC(5,4);

ALTER TABLE claims
ADD COLUMN IF NOT EXISTS behavioral_score NUMERIC(5,4);

-- Selfie URL for dual-selfie check
ALTER TABLE claims
ADD COLUMN IF NOT EXISTS selfie_url TEXT;

-- Reviewer note for admin audit trail
ALTER TABLE claims
ADD COLUMN IF NOT EXISTS reviewer_note TEXT;
