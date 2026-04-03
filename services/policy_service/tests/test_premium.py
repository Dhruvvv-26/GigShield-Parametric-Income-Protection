"""
Policy Service — Test Suite
Tests: Premium calculation engine, policy creation, renewal logic.
Run: pytest services/policy_service/tests/ -v --cov=. --cov-report=term-missing
"""
import pytest
from datetime import datetime, timezone

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../shared"))


# ── Premium Engine Tests ──────────────────────────────────────────────────────

class TestPremiumEngine:

    @pytest.fixture
    def engine(self):
        from services.premium_engine import PremiumCalculationEngine
        return PremiumCalculationEngine()

    def test_delhi_rohini_standard_november(self, engine):
        """Arjun — Blinkit cyclist, Rohini Delhi, Standard, November."""
        result = engine.calculate(
            zone_code="delhi_rohini",
            coverage_tier="standard",
            vehicle_type="bicycle",
            declared_daily_trips=30,
            declared_daily_income=1200.0,
            work_hours_profile="full_day",
            calculation_date=datetime(2026, 11, 15, tzinfo=timezone.utc),
        )
        # Expected: 25 × 2.6 × 1.7 × 1.4 × 1.4 × 1.0 ≈ ₹214
        assert 150 <= result["final_premium"] <= 250
        assert result["city"] == "delhi_ncr"
        assert result["coverage_tier"] == "standard"
        assert result["max_payout_per_event"] == 400.0

    def test_mumbai_andheri_basic_december(self, engine):
        """Priya — Blinkit e-bike, Andheri Mumbai, Basic, December."""
        result = engine.calculate(
            zone_code="mumbai_andheri_west",
            coverage_tier="basic",
            vehicle_type="e_bike",
            declared_daily_trips=20,
            declared_daily_income=1000.0,
            work_hours_profile="full_day",
            calculation_date=datetime(2026, 12, 1, tzinfo=timezone.utc),
        )
        assert result["final_premium"] >= 25.0   # Never below base rate
        assert result["city"] == "mumbai"
        assert result["max_payout_per_event"] == 200.0

    def test_bengaluru_koramangala_premium(self, engine):
        """Premium tier gives highest payout cap."""
        result = engine.calculate(
            zone_code="bengaluru_koramangala",
            coverage_tier="premium",
            vehicle_type="motorcycle",
            declared_daily_trips=15,
            declared_daily_income=1400.0,
            work_hours_profile="peak_only",
            calculation_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert result["max_payout_per_event"] == 700.0
        assert result["max_payout_per_week"] == 1400.0
        assert result["final_premium"] >= 25.0

    def test_premium_floor_enforced(self, engine):
        """Premium must never go below ₹25 base rate regardless of factors."""
        result = engine.calculate(
            zone_code="bengaluru_koramangala",
            coverage_tier="basic",
            vehicle_type="bicycle",
            declared_daily_trips=1,
            declared_daily_income=100.0,
            work_hours_profile="morning_only",
            calculation_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        assert result["final_premium"] >= 25.0

    def test_breakdown_components_sum_to_final(self, engine):
        """Breakdown attribution should be internally consistent."""
        result = engine.calculate(
            zone_code="delhi_rohini",
            coverage_tier="standard",
            vehicle_type="bicycle",
            declared_daily_trips=30,
            declared_daily_income=1200.0,
            work_hours_profile="full_day",
        )
        bd = result["breakdown"]
        assert bd["base_rate"] == 25.0
        assert bd["zone_multiplier"] == 2.6      # Delhi NCR
        assert bd["final_premium"] == result["final_premium"]

    def test_all_zones_produce_valid_premium(self, engine):
        """Every zone in the system must produce a valid premium."""
        from services.premium_engine import ZONE_CITY_MAP
        for zone_code in ZONE_CITY_MAP.keys():
            result = engine.calculate(
                zone_code=zone_code,
                coverage_tier="standard",
                vehicle_type="bicycle",
                declared_daily_trips=25,
                declared_daily_income=1000.0,
                work_hours_profile="full_day",
            )
            assert result["final_premium"] >= 25.0, f"Failed for {zone_code}"
            assert result["city"] in [
                "delhi_ncr", "mumbai", "bengaluru", "hyderabad", "pune", "kolkata"
            ]

    def test_higher_risk_city_has_higher_premium(self, engine):
        """Delhi NCR premium must exceed Bengaluru for same tier/vehicle."""
        delhi = engine.calculate(
            zone_code="delhi_rohini",
            coverage_tier="standard",
            vehicle_type="bicycle",
            declared_daily_trips=28,
            declared_daily_income=1200.0,
            work_hours_profile="full_day",
            calculation_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        blr = engine.calculate(
            zone_code="bengaluru_koramangala",
            coverage_tier="standard",
            vehicle_type="bicycle",
            declared_daily_trips=28,
            declared_daily_income=1200.0,
            work_hours_profile="full_day",
            calculation_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        assert delhi["final_premium"] > blr["final_premium"], (
            f"Delhi ({delhi['final_premium']}) should exceed Bengaluru ({blr['final_premium']})"
        )

    def test_monsoon_peak_higher_than_winter(self, engine):
        """July (monsoon peak) must produce higher premium than February (mild)."""
        july = engine.calculate(
            zone_code="mumbai_kurla",
            coverage_tier="standard",
            vehicle_type="bicycle",
            declared_daily_trips=25,
            declared_daily_income=1100.0,
            work_hours_profile="full_day",
            calculation_date=datetime(2026, 7, 15, tzinfo=timezone.utc),
        )
        feb = engine.calculate(
            zone_code="mumbai_kurla",
            coverage_tier="standard",
            vehicle_type="bicycle",
            declared_daily_trips=25,
            declared_daily_income=1100.0,
            work_hours_profile="full_day",
            calculation_date=datetime(2026, 2, 15, tzinfo=timezone.utc),
        )
        assert july["final_premium"] > feb["final_premium"]

    def test_premium_tier_ordering(self, engine):
        """Premium tier > Standard tier > Basic tier for same zone."""
        kwargs = dict(
            zone_code="delhi_rohini",
            vehicle_type="bicycle",
            declared_daily_trips=30,
            declared_daily_income=1200.0,
            work_hours_profile="full_day",
        )
        basic    = engine.calculate(coverage_tier="basic",    **kwargs)
        standard = engine.calculate(coverage_tier="standard", **kwargs)
        premium  = engine.calculate(coverage_tier="premium",  **kwargs)

        assert basic["final_premium"] < standard["final_premium"]
        assert standard["final_premium"] < premium["final_premium"]


# ── Tier Config Tests ─────────────────────────────────────────────────────────

class TestTierConfig:

    def test_all_tiers_have_required_keys(self):
        from services.premium_engine import TIER_CONFIG
        required_keys = {"factor", "max_payout_per_event", "max_payout_per_week"}
        for tier, config in TIER_CONFIG.items():
            assert required_keys.issubset(config.keys()), f"Tier {tier} missing keys"

    def test_payout_caps_are_financially_sound(self):
        """Weekly payout cap should be 2× per-event cap."""
        from services.premium_engine import TIER_CONFIG
        for tier, config in TIER_CONFIG.items():
            assert config["max_payout_per_week"] == 2 * config["max_payout_per_event"], \
                f"Tier {tier}: weekly cap should be 2× event cap"


# ── Seasonal Factor Tests ─────────────────────────────────────────────────────

class TestSeasonalFactors:

    def test_all_months_have_factor(self):
        from services.premium_engine import MONTHLY_SEASON_FACTORS
        assert len(MONTHLY_SEASON_FACTORS) == 12

    def test_november_is_highest_for_delhi_context(self):
        """November is AQI peak — should be highest or tied highest factor."""
        from services.premium_engine import MONTHLY_SEASON_FACTORS
        nov_factor = MONTHLY_SEASON_FACTORS[11]
        max_factor = max(MONTHLY_SEASON_FACTORS.values())
        assert nov_factor == max_factor, "November should be peak season factor"

    def test_all_factors_above_one(self):
        """Seasonal factor must always be ≥ 1.0 (never reduces base premium)."""
        from services.premium_engine import MONTHLY_SEASON_FACTORS
        for month, factor in MONTHLY_SEASON_FACTORS.items():
            assert factor >= 1.0, f"Month {month} has factor below 1.0: {factor}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
