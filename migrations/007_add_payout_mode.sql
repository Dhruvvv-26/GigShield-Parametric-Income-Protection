-- ============================================================
-- KavachAI — Migration 007: Add Payout Mode
-- Adds drip-feed payout mode columns to policies and payments.
-- payout_mode: lump_sum (default) or drip_feed
-- ============================================================

-- Add payout mode to policies
ALTER TABLE policies
ADD COLUMN IF NOT EXISTS payout_mode VARCHAR(20) NOT NULL DEFAULT 'lump_sum';

ALTER TABLE policies
ADD COLUMN IF NOT EXISTS drip_interval_hours INTEGER NOT NULL DEFAULT 1;

ALTER TABLE policies
ADD COLUMN IF NOT EXISTS drip_installments INTEGER NOT NULL DEFAULT 7;

-- Constraint: payout_mode must be lump_sum or drip_feed
ALTER TABLE policies
ADD CONSTRAINT chk_payout_mode
CHECK (payout_mode IN ('lump_sum', 'drip_feed'));

-- Add installments tracking to payments
ALTER TABLE payments
ADD COLUMN IF NOT EXISTS installments_disbursed INTEGER NOT NULL DEFAULT 0;

ALTER TABLE payments
ADD COLUMN IF NOT EXISTS payout_mode VARCHAR(20) NOT NULL DEFAULT 'lump_sum';

ALTER TABLE payments
ADD COLUMN IF NOT EXISTS drip_installments INTEGER NOT NULL DEFAULT 1;

ALTER TABLE payments
ADD COLUMN IF NOT EXISTS disbursed_at TIMESTAMPTZ;

-- Index for drip-feed job query
CREATE INDEX IF NOT EXISTS idx_payments_drip_pending
ON payments (payout_mode, status)
WHERE payout_mode = 'drip_feed' AND status != 'completed';
