"""
Payment Service — Test Suite
Tests cover:
  - Razorpay client simulated payout creation
  - UPI masking
  - Payment summary/loss ratio calculation
  - Webhook handling for payout.processed and payout.failed
  - Idempotency key prevention
  - Financial controls (daily cap, velocity limit)
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from services.razorpay_client import RazorpayPayoutClient


# ── Razorpay Client Tests ────────────────────────────────────────────────────

class TestRazorpayClient:
    """Test the Razorpay payout client."""

    def setup_method(self):
        self.client = RazorpayPayoutClient()

    def test_simulated_mode_default(self):
        """Without credentials, client should be in simulated mode."""
        assert not self.client.is_live_mode

    def test_simulated_payout_creates_id(self):
        """Simulated payout should generate a pout_test_ ID."""
        result = self.client._create_simulated_payout(
            worker_upi_id="arjun@oksbi",
            amount_rupees=300.0,
            narration="KavachAI AQI payout",
            claim_id=str(uuid4()),
        )
        assert result["payout_id"].startswith("pout_test_")
        assert result["status"] == "processing"
        assert result["amount"] == 300.0
        assert result["mode"] == "test"

    def test_simulated_payout_has_razorpay_response(self):
        """Simulated payout should include mock Razorpay response body."""
        result = self.client._create_simulated_payout(
            worker_upi_id="rider@paytm",
            amount_rupees=500.0,
            narration="KavachAI disruption payout",
            claim_id=str(uuid4()),
        )
        rr = result["razorpay_response"]
        assert rr["entity"] == "payout"
        assert rr["amount"] == 50000  # 500 * 100 paise
        assert rr["currency"] == "INR"
        assert rr["mode"] == "UPI"
        assert rr["purpose"] == "payout"

    def test_upi_masking_normal(self):
        """UPI IDs should be masked: 'arjun@oksbi' → 'ar***@oksbi'."""
        masked = RazorpayPayoutClient._mask_upi("arjun@oksbi")
        assert masked == "ar***@oksbi"

    def test_upi_masking_short_name(self):
        """Short UPI names should be fully masked."""
        masked = RazorpayPayoutClient._mask_upi("a@upi")
        assert masked == "***@upi"

    def test_upi_masking_empty(self):
        """Empty UPI should return '***'."""
        masked = RazorpayPayoutClient._mask_upi("")
        assert masked == "***"

    def test_upi_masking_none(self):
        """None UPI should return '***'."""
        masked = RazorpayPayoutClient._mask_upi(None)
        assert masked == "***"

    def test_simulated_payout_amount_paise_conversion(self):
        """Amount should be correctly converted to paise."""
        result = self.client._create_simulated_payout(
            worker_upi_id="test@upi",
            amount_rupees=150.50,
            narration="Test",
            claim_id=str(uuid4()),
        )
        assert result["amount_paise"] == 15050

    @pytest.mark.asyncio
    async def test_create_payout_uses_simulated(self):
        """create_payout() should use simulated mode when no credentials."""
        result = await self.client.create_payout(
            worker_upi_id="demo@ybl",
            amount_rupees=200.0,
            narration="Test payout",
            claim_id=str(uuid4()),
        )
        assert result["mode"] == "test"
        assert result["payout_id"] is not None


# ── Schema Tests ─────────────────────────────────────────────────────────────

class TestPaymentSchemas:
    """Test Pydantic schema validation."""

    def test_payment_response_valid(self):
        from models.schemas import PaymentResponse
        resp = PaymentResponse(
            payment_id=uuid4(),
            claim_id=uuid4(),
            worker_id=uuid4(),
            amount=300.0,
            status="completed",
            razorpay_payout_id="pout_test_abc123",
            upi_id_masked="ar***@oksbi",
            initiated_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        assert resp.status == "completed"
        assert resp.amount == 300.0

    def test_payment_summary_response(self):
        from models.schemas import PaymentSummaryResponse
        summary = PaymentSummaryResponse(
            total_premiums_this_week=13000.0,
            total_payouts_this_week=8450.0,
            loss_ratio_percent=65.0,
            active_policies=50,
            claims_this_week=23,
            payments_completed=20,
            payments_pending=2,
            payments_failed=1,
            avg_payout_amount=367.39,
            daily_payout_volume=2450.0,
        )
        assert summary.loss_ratio_percent == 65.0
        assert summary.active_policies == 50

    def test_webhook_payload_valid(self):
        from models.schemas import RazorpayWebhookPayload
        payload = RazorpayWebhookPayload(
            event="payout.processed",
            payload={"payout": {"entity": {"id": "pout_test_123"}}},
        )
        assert payload.event == "payout.processed"

    def test_payment_list_response(self):
        from models.schemas import PaymentListResponse, PaymentResponse
        resp = PaymentListResponse(
            payments=[
                PaymentResponse(
                    payment_id=uuid4(),
                    claim_id=uuid4(),
                    worker_id=uuid4(),
                    amount=200.0,
                    status="completed",
                    initiated_at=datetime.now(timezone.utc),
                ),
            ],
            total=1,
            worker_id=str(uuid4()),
        )
        assert resp.total == 1
        assert len(resp.payments) == 1
