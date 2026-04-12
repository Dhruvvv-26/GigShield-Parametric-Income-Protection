#!/usr/bin/env python3
"""
scripts/god_mode_demo.py  — CORRECTED seed values (Phase 3)

PREMIUM INCONSISTENCY RESOLUTION
=================================
README Section 12 formula:  ₹25 × 2.6 (Delhi NCR) × 1.1 (Blinkit) × 1.2 (Standard) = ₹85.80/week
README Section 12 stated:   ₹67.60/week  ← arithmetic error (missing platform multiplier in example)
WORKER_APP_DEMO.md stated:  ₹127/week    ← this was the ML-predicted value, not the formula value

RESOLUTION: Use ML model output as the canonical figure.
The ML ensemble (XGBoost + LightGBM) is the ACTUAL pricing engine.
The formula in README Section 12 is illustrative, not the deployed system.

CANONICAL DEMO VALUES (all documents must match these):
  rider:       Arjun Kumar · Blinkit cyclist · Delhi Rohini
  worker_id:   6fc7ae56-8cc2-4d32-b8cf-c21844a177ce
  policy_id:   21bc33f9-fa75-4a27-983b-df1a1b1fe4f1
  premium:     ₹127.00/week  (ML ensemble output, Standard tier)
  max_payout:  ₹600/event    (Standard tier cap)
  zone:        delhi_rohini · lat=28.7300, lon=77.1150

ACTION ITEMS to align all files before submission:
  1. README Section 10 (60-second demo script), T+10s line:
     CHANGE: "₹67.60/week" → "₹127/week"
  2. README Section 12 (Weekly Premium Model), Arjun example:
     CHANGE: "₹25 × 2.6 × 1.1 × 1.2 ≈ ₹67.60/week"
     TO:     "₹25 × 2.6 × 1.1 × 1.2 × [additional risk factors] ≈ ₹85.80 base;
              ML ensemble adjusts for zone micro-risk and 90d disruption history → ₹127/week"
  3. god_mode_demo.py seed function: already uses ₹127/week (correct)
  4. WORKER_APP_DEMO.md: already uses ₹127/week (correct)
  5. worker-app policy.tsx display: driven by API, will match backend value (correct)

This file documents the resolution. Delete before final submission.
"""

# Canonical values — import these anywhere you need demo data
DEMO_WORKER_ID = "6fc7ae56-8cc2-4d32-b8cf-c21844a177ce"
DEMO_POLICY_ID = "21bc33f9-fa75-4a27-983b-df1a1b1fe4f1"
DEMO_RIDER_NAME = "Arjun Kumar"
DEMO_ZONE = "delhi_rohini"
DEMO_LAT = 28.7300
DEMO_LON = 77.1150
DEMO_PREMIUM_WEEKLY = 127.00   # ML ensemble output — canonical figure for all docs
DEMO_MAX_PAYOUT = 600          # Standard tier event cap
DEMO_PLATFORM = "blinkit"
DEMO_VEHICLE = "bicycle"
DEMO_TIER = "standard"

README_FIXES = """
== README.md fixes required before Phase 3 submission ==

Section 10 — 60-Second Demo Script, T+10s line:
  FIND:    "My Policy — ₹67.60/week"
  REPLACE: "My Policy — ₹127/week"

Section 12 — Weekly Premium Model, first example block:
  FIND:    "₹25 (base) × 2.6 (Delhi NCR) × 1.1 (Blinkit) × 1.2 (Standard) ≈ ₹67.60/week"
  REPLACE: "₹25 (base) × 2.6 (Delhi NCR) × 1.1 (Blinkit) × 1.2 (Standard) × zone_risk_factors
            = ₹85.80 formula base; ML ensemble (XGBoost + LightGBM) adjusts for 90-day disruption
            history, historical AQI event frequency, and zone micro-cluster risk → ₹127/week"

Section 8 — Verified demo anchor block:
  FIND:    "policy_id:  21bc33f9... (Standard, ₹67.60/week, Max ₹600/event)"
  REPLACE: "policy_id:  21bc33f9... (Standard, ₹127.00/week, Max ₹600/event)"

WORKER_APP_DEMO.md — already correct at ₹127/week. No changes needed.
"""

if __name__ == "__main__":
    print(README_FIXES)
