-- ============================================================
-- KavachAI — Migration 006: Add Policy Exclusions
-- Adds force majeure exclusion JSONB column to policies table.
-- Exclusion types: ACT_OF_WAR, PANDEMIC_DECLARED, TERRORISM,
--                  NUCLEAR_EVENT, GOVERNMENT_MANDATED_LOCKDOWN_BEYOND_72H
-- ============================================================

-- Add exclusions JSONB column with default force majeure exclusions
ALTER TABLE policies
ADD COLUMN IF NOT EXISTS exclusions JSONB NOT NULL DEFAULT '[
    "ACT_OF_WAR",
    "PANDEMIC_DECLARED",
    "TERRORISM",
    "NUCLEAR_EVENT",
    "GOVERNMENT_MANDATED_LOCKDOWN_BEYOND_72H"
]'::jsonb;

-- GIN index for efficient JSONB containment queries (admin dashboard filters)
CREATE INDEX IF NOT EXISTS idx_policies_exclusions
ON policies USING GIN (exclusions);

-- Constraint: ensure exclusions is always a JSON array
ALTER TABLE policies
ADD CONSTRAINT chk_exclusions_is_array
CHECK (jsonb_typeof(exclusions) = 'array');
