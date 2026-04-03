"""
Payment Service — Razorpay Client
Phase 2: Test mode with simulated payouts (generates realistic payout IDs).
Phase 3: Switch to real Razorpay Payout API with live credentials.

Test mode behavior:
- Generates payout IDs in format: pout_test_{uuid8}
- Simulates UPI payout flow: PENDING → PROCESSING → COMPLETED
- No actual API calls — all payouts are simulated locally
- When RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are provided, switches to real API
"""
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RazorpayPayoutClient:
    """
    Razorpay Payout API client.
    In test mode (no real keys), simulates payouts locally.
    With real test keys, calls the actual Razorpay test sandbox.
    """

    BASE_URL = "https://api.razorpay.com/v1"

    def __init__(self):
        self._key_id = getattr(settings, "razorpay_key_id", "")
        self._key_secret = getattr(settings, "razorpay_key_secret", "")
        self._is_live = bool(
            self._key_id and self._key_secret
            and not self._key_id.startswith("demo")
            and not self._key_id.startswith("rzp_test_")
        )

    @property
    def is_live_mode(self) -> bool:
        return self._is_live

    async def create_payout(
        self,
        worker_upi_id: str,
        amount_rupees: float,
        narration: str,
        claim_id: str,
        worker_name: str = "GigShield Worker",
    ) -> dict:
        """
        Create a UPI payout to the worker.
        Returns: {
            "payout_id": str,
            "status": str,  # "processing" or "queued"
            "amount": float,
            "upi_id": str,
            "mode": "test" | "live",
        }
        """
        if self._is_live:
            return await self._create_live_payout(
                worker_upi_id, amount_rupees, narration, claim_id, worker_name
            )
        else:
            return self._create_simulated_payout(
                worker_upi_id, amount_rupees, narration, claim_id
            )

    def _create_simulated_payout(
        self,
        worker_upi_id: str,
        amount_rupees: float,
        narration: str,
        claim_id: str,
    ) -> dict:
        """Simulated payout for development/testing without Razorpay credentials."""
        payout_id = f"pout_test_{uuid.uuid4().hex[:12]}"
        amount_paise = int(amount_rupees * 100)

        logger.info(
            "Simulated Razorpay payout created",
            extra={
                "payout_id": payout_id,
                "amount_rupees": amount_rupees,
                "upi_id": self._mask_upi(worker_upi_id),
                "claim_id": claim_id,
            },
        )

        return {
            "payout_id": payout_id,
            "status": "processing",
            "amount": amount_rupees,
            "amount_paise": amount_paise,
            "upi_id": worker_upi_id,
            "upi_id_masked": self._mask_upi(worker_upi_id),
            "mode": "test",
            "narration": narration,
            "razorpay_response": {
                "id": payout_id,
                "entity": "payout",
                "fund_account_id": f"fa_test_{uuid.uuid4().hex[:8]}",
                "amount": amount_paise,
                "currency": "INR",
                "notes": {"claim_id": claim_id},
                "fees": 0,
                "tax": 0,
                "status": "processing",
                "utr": f"UTR{uuid.uuid4().hex[:10].upper()}",
                "mode": "UPI",
                "purpose": "payout",
                "created_at": int(datetime.now(timezone.utc).timestamp()),
            },
        }

    async def _create_live_payout(
        self,
        worker_upi_id: str,
        amount_rupees: float,
        narration: str,
        claim_id: str,
        worker_name: str,
    ) -> dict:
        """Create a real Razorpay test-mode payout via API."""
        amount_paise = int(amount_rupees * 100)

        # Step 1: Create contact
        async with httpx.AsyncClient(
            auth=(self._key_id, self._key_secret),
            timeout=30.0,
        ) as client:
            # Create fund account with UPI
            contact_payload = {
                "name": worker_name,
                "type": "customer",
                "notes": {"claim_id": claim_id, "source": "gigshield"},
            }
            contact_resp = await client.post(
                f"{self.BASE_URL}/contacts", json=contact_payload
            )

            if contact_resp.status_code != 200:
                logger.error(f"Razorpay contact creation failed: {contact_resp.text}")
                return {
                    "payout_id": None,
                    "status": "failed",
                    "error": contact_resp.text,
                    "mode": "live",
                }

            contact_id = contact_resp.json()["id"]

            # Create fund account
            fund_payload = {
                "contact_id": contact_id,
                "account_type": "vpa",
                "vpa": {"address": worker_upi_id},
            }
            fund_resp = await client.post(
                f"{self.BASE_URL}/fund_accounts", json=fund_payload
            )

            if fund_resp.status_code != 200:
                logger.error(f"Razorpay fund account creation failed: {fund_resp.text}")
                return {
                    "payout_id": None,
                    "status": "failed",
                    "error": fund_resp.text,
                    "mode": "live",
                }

            fund_account_id = fund_resp.json()["id"]

            # Create payout
            payout_payload = {
                "account_number": getattr(settings, "razorpay_account_number", "2323230085726431"),
                "fund_account_id": fund_account_id,
                "amount": amount_paise,
                "currency": "INR",
                "mode": "UPI",
                "purpose": "payout",
                "queue_if_low_balance": True,
                "reference_id": claim_id,
                "narration": narration[:30],  # Razorpay max 30 chars
                "notes": {"claim_id": claim_id, "source": "gigshield"},
            }
            payout_resp = await client.post(
                f"{self.BASE_URL}/payouts", json=payout_payload
            )

            if payout_resp.status_code in (200, 201):
                payout_data = payout_resp.json()
                return {
                    "payout_id": payout_data["id"],
                    "status": payout_data.get("status", "processing"),
                    "amount": amount_rupees,
                    "amount_paise": amount_paise,
                    "upi_id": worker_upi_id,
                    "upi_id_masked": self._mask_upi(worker_upi_id),
                    "mode": "live",
                    "razorpay_response": payout_data,
                }
            else:
                logger.error(f"Razorpay payout creation failed: {payout_resp.text}")
                return {
                    "payout_id": None,
                    "status": "failed",
                    "error": payout_resp.text,
                    "mode": "live",
                }

    @staticmethod
    def _mask_upi(upi_id: str) -> str:
        """Mask UPI ID for display: 'arjun@oksbi' → 'ar***@oksbi'"""
        if not upi_id:
            return "***"
        parts = upi_id.split("@")
        if len(parts) == 2:
            name = parts[0]
            masked = name[:2] + "***" if len(name) > 2 else "***"
            return f"{masked}@{parts[1]}"
        return "***"

    async def verify_webhook_signature(
        self,
        body: bytes,
        signature: str,
        webhook_secret: str,
    ) -> bool:
        """Verify Razorpay webhook signature using HMAC-SHA256."""
        import hmac
        expected = hmac.new(
            webhook_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
