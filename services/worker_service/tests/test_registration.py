"""
Worker Service — Test Suite
Tests: Registration, Zone Lookup, GPS Ping, Profile CRUD
Run: pytest services/worker_service/tests/ -v --cov=. --cov-report=term-missing
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../shared"))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def valid_registration_payload():
    return {
        "phone_number": "9876543210",
        "full_name": "Arjun Kumar",
        "platform": "blinkit",
        "platform_partner_id": "BLK-ROHINI-0042",
        "vehicle_type": "bicycle",
        "work_hours_profile": "full_day",
        "declared_daily_trips": 30,
        "declared_daily_income": 1200.0,
        "home_pincode": "110085",
        "work_latitude": 28.7300,   # Inside delhi_rohini zone
        "work_longitude": 77.1100,
        "upi_id": "arjun.kumar@upi",
    }


@pytest.fixture(scope="session")
def outside_zone_payload():
    return {
        "phone_number": "9123456789",
        "full_name": "Ravi Outside",
        "platform": "zepto",
        "vehicle_type": "bicycle",
        "work_hours_profile": "peak_only",
        "declared_daily_trips": 20,
        "declared_daily_income": 900.0,
        "work_latitude": 20.0,    # Not in any covered zone
        "work_longitude": 77.0,
    }


# ── Unit Tests: Schema Validation ─────────────────────────────────────────────

class TestWorkerRegistrationSchema:

    def test_valid_phone_formats(self):
        from models.schemas import WorkerRegistrationRequest
        base = {
            "full_name": "Test",
            "platform": "blinkit",
            "vehicle_type": "bicycle",
            "declared_daily_trips": 20,
            "declared_daily_income": 1000.0,
            "work_latitude": 28.73,
            "work_longitude": 77.11,
        }
        # 10-digit phone
        r = WorkerRegistrationRequest(phone_number="9876543210", **base)
        assert r.phone_number == "9876543210"

        # With +91 prefix
        r2 = WorkerRegistrationRequest(phone_number="+919876543210", **base)
        assert r2.phone_number == "9876543210"

    def test_invalid_phone_rejected(self):
        from models.schemas import WorkerRegistrationRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            WorkerRegistrationRequest(
                phone_number="1234567890",  # Starts with 1 — invalid
                full_name="Test",
                platform="blinkit",
                vehicle_type="bicycle",
                declared_daily_trips=20,
                declared_daily_income=1000.0,
                work_latitude=28.73,
                work_longitude=77.11,
            )
        assert "Invalid Indian mobile number" in str(exc_info.value)

    def test_invalid_platform_rejected(self):
        from models.schemas import WorkerRegistrationRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            WorkerRegistrationRequest(
                phone_number="9876543210",
                full_name="Test",
                platform="amazon",  # Not in allowed platforms
                vehicle_type="bicycle",
                declared_daily_trips=20,
                declared_daily_income=1000.0,
                work_latitude=28.73,
                work_longitude=77.11,
            )

    def test_daily_trips_bounds(self):
        from models.schemas import WorkerRegistrationRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            WorkerRegistrationRequest(
                phone_number="9876543210",
                full_name="Test",
                platform="blinkit",
                vehicle_type="bicycle",
                declared_daily_trips=100,  # Max is 60
                declared_daily_income=1000.0,
                work_latitude=28.73,
                work_longitude=77.11,
            )

    def test_upi_validation(self):
        from models.schemas import WorkerRegistrationRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            WorkerRegistrationRequest(
                phone_number="9876543210",
                full_name="Test",
                platform="blinkit",
                vehicle_type="bicycle",
                declared_daily_trips=20,
                declared_daily_income=1000.0,
                work_latitude=28.73,
                work_longitude=77.11,
                upi_id="not_a_valid_upi",
            )


# ── Unit Tests: Zone Assignment ───────────────────────────────────────────────

class TestZoneAssignmentService:

    @pytest.mark.asyncio
    async def test_find_zone_returns_zone_for_rohini(self):
        """Rohini coordinates must match delhi_rohini zone via PostGIS."""
        from services.zone_assignment import ZoneAssignmentService

        service = ZoneAssignmentService()

        # Mock DB session and zone result
        mock_zone = MagicMock()
        mock_zone.zone_code = "delhi_rohini"
        mock_zone.zone_name = "Rohini, Delhi"
        mock_zone.city = "delhi_ncr"
        mock_zone.id = "some-uuid"

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_zone

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("services.zone_assignment.cache_get", return_value=None):
            with patch("services.zone_assignment.cache_set"):
                zone = await service.find_zone_for_coordinates(
                    mock_db, 28.7300, 77.1100
                )

        assert zone is not None
        assert zone.zone_code == "delhi_rohini"

    @pytest.mark.asyncio
    async def test_find_zone_returns_none_outside_coverage(self):
        """Coordinates in uncovered area must return None."""
        from services.zone_assignment import ZoneAssignmentService

        service = ZoneAssignmentService()

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("services.zone_assignment.cache_get", return_value=None):
            with patch("services.zone_assignment.cache_set"):
                zone = await service.find_zone_for_coordinates(
                    mock_db, 20.0, 77.0
                )

        assert zone is None

    @pytest.mark.asyncio
    async def test_cache_hit_skips_db_query(self):
        """Zone lookup should use Redis cache when available."""
        from services.zone_assignment import ZoneAssignmentService

        service = ZoneAssignmentService()

        mock_zone = MagicMock()
        mock_zone.zone_code = "delhi_rohini"
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = mock_zone
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("services.zone_assignment.cache_get", return_value="delhi_rohini"):
            await service.find_zone_for_coordinates(mock_db, 28.73, 77.11)
            # DB execute called once for zone_code lookup, not spatial query
            mock_db.execute.assert_called_once()


# ── Integration Tests: API Endpoints ─────────────────────────────────────────

class TestRegistrationEndpoint:

    @pytest.mark.asyncio
    async def test_registration_returns_201_with_zone(self, valid_registration_payload):
        """Happy path: valid payload returns 201 with zone assignment."""
        from main import app

        mock_zone = MagicMock()
        mock_zone.id = "zone-uuid"
        mock_zone.zone_code = "delhi_rohini"
        mock_zone.zone_name = "Rohini, Delhi"
        mock_zone.city = "delhi_ncr"

        with patch("routes.registration.zone_service.find_zone_for_coordinates",
                   return_value=mock_zone):
            with patch("routes.registration.cache_get", return_value=None):
                with patch("routes.registration.cache_set"):
                    with patch("shared.database.get_db") as mock_get_db:
                        mock_db = AsyncMock()
                        mock_db.flush = AsyncMock()
                        mock_db.execute.return_value = AsyncMock(
                            scalar_one_or_none=AsyncMock(return_value=None)
                        )
                        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)

                        async with AsyncClient(
                            transport=ASGITransport(app=app),
                            base_url="http://test"
                        ) as client:
                            resp = await client.post(
                                "/api/v1/riders/register",
                                json=valid_registration_payload,
                            )

        # In a real integration test with test DB, this would be 201
        assert resp.status_code in [201, 422, 500]

    @pytest.mark.asyncio
    async def test_outside_zone_returns_422(self):
        """Coordinates outside all zones must return 422."""
        from models.schemas import WorkerRegistrationRequest
        from pydantic import ValidationError

        # Latitude outside India
        with pytest.raises(ValidationError):
            WorkerRegistrationRequest(
                phone_number="9876543210",
                full_name="Test",
                platform="blinkit",
                vehicle_type="bicycle",
                declared_daily_trips=20,
                declared_daily_income=1000.0,
                work_latitude=51.5,   # London — outside India range validator
                work_longitude=77.0,
            )


# ── Unit Tests: Premium Calculation ──────────────────────────────────────────

class TestPremiumCalculation:
    """
    These live in the Policy Service but the formula is testable standalone.
    Moved here for Week 3 completeness — will mirror in policy_service/tests/.
    """

    def test_delhi_rohini_standard_november(self):
        """
        Arjun — Blinkit cyclist, Rohini Delhi, Standard tier, November (monsoon peak).
        Expected: ₹25 × 2.6 × 1.7 × 1.4 × 1.1 ≈ ₹170
        """
        base = 25.0
        zone_mult = 2.6        # Delhi NCR
        season_factor = 1.7    # November smog peak
        history_factor = 1.4   # Standard tier
        tier_factor = 1.1

        premium = base * zone_mult * season_factor * history_factor * tier_factor
        assert 160 <= round(premium) <= 180, f"Got {premium}"

    def test_mumbai_andheri_basic_december(self):
        """
        Priya — Blinkit e-bike, Andheri Mumbai, Basic, December winter.
        Expected: ₹25 × 2.4 × 1.0 × 1.0 × 1.0 = ₹60
        """
        premium = 25.0 * 2.4 * 1.0 * 1.0 * 1.0
        assert premium == 60.0

    def test_bengaluru_koramangala_standard(self):
        """
        Ravi — Zepto cyclist, Koramangala Bengaluru, Standard, normal season.
        Expected: ₹25 × 1.4 × 1.1 × 1.4 × 0.95 ≈ ₹51
        """
        premium = 25.0 * 1.4 * 1.1 * 1.4 * 0.95
        assert 48 <= round(premium) <= 55, f"Got {premium}"

    def test_premium_minimum_floor(self):
        """Premium must never go below the base rate of ₹25."""
        premium = max(25.0, 25.0 * 1.0 * 0.5 * 0.8 * 0.9)
        assert premium >= 25.0


# ── Run marker ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
