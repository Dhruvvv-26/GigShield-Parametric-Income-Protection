-- ============================================================
-- KavachAI — Migration 008: Add Worker Phone Number
-- Adds phone_number column for WhatsApp (Twilio) notifications.
-- ============================================================

ALTER TABLE workers
ADD COLUMN IF NOT EXISTS phone_number VARCHAR(15);

-- Index for phone number lookups (WhatsApp dispatch)
CREATE INDEX IF NOT EXISTS idx_workers_phone
ON workers (phone_number)
WHERE phone_number IS NOT NULL;
