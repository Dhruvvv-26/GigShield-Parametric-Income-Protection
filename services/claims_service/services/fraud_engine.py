"""
GigShield Fraud Detection Engine — Phase 3: ML + Rule-Based Hybrid

This module implements the 4-layer adversarial defense engine.
When trained ML models (IsolationForest + GradientBoosting) are available,
they are used for scoring. Otherwise, falls back to deterministic
rule-based scoring.

ML Models:
  - IsolationForest: unsupervised anomaly detection (trained on legitimate-only)
  - GradientBoosting: supervised fraud classifier
  - Combined: 40% IsoForest + 60% GradientBoosting

Fallback: Rule-based thresholds (Phase 2 implementation retained).
"""
import logging
import math
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

import httpx
import numpy as np
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.claim import GpsPing, Worker

logger = logging.getLogger(__name__)

# ── IPinfo.io for server-side IP geolocation ──────────────────────────────────
IPINFO_TOKEN = os.environ.get("IPINFO_TOKEN", "")

# ── ML Model Loading (graceful fallback) ─────────────────────────────────────
_ml_models = {
    "iso_forest": None,
    "gb_fraud": None,
    "scaler": None,
    "meta": None,
}
_ML_AVAILABLE = False

try:
    import joblib
    MODEL_DIR = os.environ.get("ML_MODEL_DIR", "/app/models")
    _model_files = {
        "iso_forest": os.path.join(MODEL_DIR, "iso_forest.pkl"),
        "gb_fraud": os.path.join(MODEL_DIR, "gb_fraud.pkl"),
        "scaler": os.path.join(MODEL_DIR, "fraud_scaler.pkl"),
        "meta": os.path.join(MODEL_DIR, "fraud_meta.pkl"),
    }
    if all(os.path.exists(p) for p in _model_files.values()):
        for key, path in _model_files.items():
            _ml_models[key] = joblib.load(path)
        _ML_AVAILABLE = True
        logger.info("ML fraud models loaded successfully — using ML scoring")
    else:
        missing = [k for k, p in _model_files.items() if not os.path.exists(p)]
        logger.warning(f"ML model files missing ({missing}) — using rule-based fallback")
except ImportError:
    logger.warning("joblib not available — using rule-based fraud scoring")
except Exception as e:
    logger.warning(f"Failed to load ML fraud models: {e} — using rule-based fallback")

# ── Weights ──────────────────────────────────────────────────────────────────

GPS_WEIGHT     = 0.30
SENSOR_WEIGHT  = 0.25
NETWORK_WEIGHT = 0.25
BEHAVIOR_WEIGHT = 0.20

# ── Thresholds ───────────────────────────────────────────────────────────────

GPS_VARIANCE_THRESHOLD_M = 500    # > 500m variance across pings → suspicious
GPS_ACCURACY_THRESHOLD_M = 100    # > 100m accuracy radius → suspicious
ACCEL_RMS_STATIONARY = 0.5        # < 0.5 m/s² RMS → stationary (suspicious during work hours)
ACCEL_RMS_CYCLING = 3.0           # > 3.0 m/s² RMS → cycling (normal)
GYRO_YAW_THRESHOLD = 0.1          # < 0.1 rad/s → not moving (suspicious)
IP_GPS_DELTA_KM = 50              # > 50km delta → mismatched
ZONE_RESIDENCY_DAYS = 7           # Must have at least 7 days of zone residency history


class FraudScoringEngine:
    """
    PHASE 2: Rule-based deterministic fraud detection engine.

    Computes a composite fraud score (0.0–1.0) from four sub-scores:
      - GPS physics plausibility (weight: 0.30)
      - Device sensor validation (weight: 0.25)
      - Network-GPS geo consistency (weight: 0.25)
      - Behavioral pattern analysis (weight: 0.20)

    Each sub-score uses hardcoded thresholds and deterministic logic.
    No ML model is loaded. No .pkl file is referenced. All scoring
    is fully explainable.

    PHASE 3 UPGRADE PATH (Week 5):
      - Replace _compute_gps_physics_score → Isolation Forest anomaly detector
      - Replace _compute_device_sensor_score → GradientBoosting feature input
      - Replace _compute_network_geo_score → GradientBoosting feature input
      - Replace _compute_behavioral_score → NetworkX Louvain graph scorer
      - Function signatures and return types remain identical (drop-in swap)
    """

    async def score_claim(
        self,
        db: AsyncSession,
        worker_id: UUID,
        zone_id: UUID,
        sensor_data: Optional[dict] = None,
        client_ip: Optional[str] = None,
    ) -> dict:
        """
        Compute fraud score for a claim.

        Phase 3: Uses ML ensemble (IsoForest + GradientBoosting) when models
        are available. Falls back to rule-based deterministic scoring.

        Returns: {
            "total_score": float,
            "gps_physics_score": float,
            "device_sensor_score": float,
            "network_geo_score": float,
            "behavioral_score": float,
            "flags": list[str],
            "decision": str  # "approved" | "soft_hold" | "blocked"
        }
        """
        sensor = sensor_data or {}
        flags = []

        # ── Server-side IP geolocation (IPinfo.io) ────────────────────────
        ip_result = await self._resolve_ip_geolocation(client_ip, sensor, flags)

        # ── Layer 5 Zero-Trust: Biometric Geo Lock ────────────────────────────────
        camera_lat = sensor.get("camera_gps_lat")
        camera_lng = sensor.get("camera_gps_lng")
        ip_lat = ip_result.get("ip_lat")
        ip_lng = ip_result.get("ip_lng")
        
        if camera_lat is not None and ip_lat is not None:
            camera_ip_delta = self._haversine_km(camera_lat, camera_lng, ip_lat, ip_lng)
            if camera_ip_delta > 50.0:  # 50km divergence tolerance for IP geo accuracy
                flags.append(f"CAMERA_IP_MISMATCH_{camera_ip_delta:.0f}km")
                logger.warning(f"Geo Lock failed: Camera {camera_lat},{camera_lng} vs IP {ip_lat},{ip_lng} (Delta: {camera_ip_delta:.1f}km)")

        # ── Try ML scoring first ─────────────────────────────────────────
        if _ML_AVAILABLE:
            try:
                ml_result = self._ml_score_claim(sensor, flags, ip_result)
                # Still run rule-based sub-scores for explainability breakdown
                gps_score = await self._compute_gps_physics_score(db, worker_id, sensor, [])
                sensor_score = self._compute_device_sensor_score(sensor, [])
                network_score = self._compute_network_geo_score(sensor, [])
                behavioral_score = await self._compute_behavioral_score(db, worker_id, zone_id, sensor, [])

                result = {
                    "total_score": ml_result["total_score"],
                    "gps_physics_score": round(gps_score, 4),
                    "device_sensor_score": round(sensor_score, 4),
                    "network_geo_score": round(network_score, 4),
                    "behavioral_score": round(behavioral_score, 4),
                    "iso_forest_score": ml_result.get("iso_forest_score", 0.0),
                    "gb_score": ml_result.get("gb_score", 0.0),
                    "flags": flags,
                    "decision": ml_result["decision"],
                    "scoring_method": "ml_ensemble",
                }

                logger.info(
                    f"Fraud score computed (ML) | worker={worker_id} | score={ml_result['total_score']:.4f} | decision={ml_result['decision']}"
                )

                # Vuln A Fail-Closed: If IP geo was unavailable, override to soft_hold
                if ip_result.get("geo_unavailable") and result["decision"] == "approved":
                    result["decision"] = "soft_hold"
                    flags.append("FAIL_CLOSED_GEO_UNAVAILABLE")
                    logger.warning(f"Fail-Closed override: {worker_id} held for review — IP geolocation was unavailable")

                return result

            except Exception as e:
                logger.warning(f"ML scoring failed, falling back to rules: {e}")

        # ── Rule-based fallback ──────────────────────────────────────────
        # Inject server-resolved IP data into sensor for _compute_network_geo_score
        sensor["_server_ip_delta_km"] = ip_result.get("delta_km")
        sensor["_server_vpn_detected"] = ip_result.get("vpn", False)

        gps_score = await self._compute_gps_physics_score(
            db, worker_id, sensor, flags
        )
        sensor_score = self._compute_device_sensor_score(sensor, flags)
        network_score = self._compute_network_geo_score(sensor, flags)
        behavioral_score = await self._compute_behavioral_score(
            db, worker_id, zone_id, sensor, flags
        )

        total_score = round(
            GPS_WEIGHT * gps_score
            + SENSOR_WEIGHT * sensor_score
            + NETWORK_WEIGHT * network_score
            + BEHAVIOR_WEIGHT * behavioral_score,
            4,
        )
        total_score = max(0.0, min(1.0, total_score))

        if total_score >= 0.85:
            decision = "blocked"
        elif total_score >= 0.65:
            decision = "soft_hold"
        else:
            decision = "approved"

        result = {
            "total_score": total_score,
            "gps_physics_score": round(gps_score, 4),
            "device_sensor_score": round(sensor_score, 4),
            "network_geo_score": round(network_score, 4),
            "behavioral_score": round(behavioral_score, 4),
            "flags": flags,
            "decision": decision,
            "scoring_method": "rule_based",
        }

        logger.info(
            f"Fraud score computed (rules) | worker={worker_id} | score={total_score:.4f} | decision={decision}"
        )

        # Vuln A Fail-Closed: If IP geo was unavailable, override to soft_hold
        if ip_result.get("geo_unavailable") and result["decision"] == "approved":
            result["decision"] = "soft_hold"
            flags.append("FAIL_CLOSED_GEO_UNAVAILABLE")
            logger.warning(f"Fail-Closed override: {worker_id} held for review — IP geolocation was unavailable")

        return result

    def _ml_score_claim(self, sensor: dict, flags: list, ip_result: dict) -> dict:
        """Score using trained ML models (IsoForest + GradientBoosting)."""
        meta = _ml_models["meta"]
        feature_cols = meta["feature_columns"]

        # Extract features from sensor data matching training columns
        gps_pings = sensor.get("gps_pings", [])

        # GPS variance from pings
        if gps_pings and len(gps_pings) >= 2:
            lats = [p.get("lat", 0) for p in gps_pings]
            lngs = [p.get("lng", 0) for p in gps_pings]
            lat_var = max(lats) - min(lats)
            lng_var = max(lngs) - min(lngs)
            gps_variance = math.sqrt((lat_var * 111000) ** 2 + (lng_var * 111000) ** 2) / 1000.0
            accuracies = [p.get("accuracy_m", 10) for p in gps_pings if p.get("accuracy_m")]
            gps_accuracy = sum(accuracies) / len(accuracies) if accuracies else 10.0
        else:
            gps_variance = sensor.get("gps_variance_sigma", 5.0)
            gps_accuracy = sensor.get("gps_accuracy_m", 10.0)

        now = datetime.now(timezone.utc)
        month = now.month

        # Use SERVER-RESOLVED IP-GPS delta, not client-provided
        ip_gps_delta = ip_result.get("delta_km", 1.0)

        feature_map = {
            "gps_variance_sigma": gps_variance,
            "gps_accuracy_m": gps_accuracy,
            "gps_cold_start_ms": sensor.get("gps_cold_start_ms", 30000),
            "accel_rms": sensor.get("accelerometer_rms", 1.5),
            "gyro_yaw_mismatch_deg": sensor.get("gyroscope_yaw_rate", 5.0) * 57.2958,  # rad/s → deg
            "mock_location_enabled": int(sensor.get("is_mock_location", False)),
            "ip_gps_delta_km": ip_gps_delta,
            "tower_handoffs_30min": sensor.get("tower_handoffs_30min", 4),
            "zone_resident_t_minus_30": int(sensor.get("zone_resident_t_minus_30", True)),
            "claims_in_window_same_zone": sensor.get("claims_in_window_same_zone", 5),
            "month": month,
            "is_monsoon": int(month in [6, 7, 8, 9]),
        }

        X = np.array([[feature_map.get(col, 0) for col in feature_cols]], dtype=float)

        # Isolation Forest scoring
        X_scaled = _ml_models["scaler"].transform(X)
        iso_raw = float(-_ml_models["iso_forest"].score_samples(X_scaled)[0])
        iso_min = meta.get("iso_score_min", 0)
        iso_max = meta.get("iso_score_max", 1)
        iso_score = max(0.0, min(1.0, (iso_raw - iso_min) / (iso_max - iso_min + 1e-8)))

        # GradientBoosting scoring
        gb_score = float(_ml_models["gb_fraud"].predict_proba(X)[:, 1][0])

        # Combined: 40% IsoForest + 60% GB
        combined = round(0.40 * iso_score + 0.60 * gb_score, 4)

        # Generate flags
        if sensor.get("is_mock_location"):
            flags.append("MOCK_LOCATION_DETECTED")
        if feature_map["gps_cold_start_ms"] < 500:
            flags.append(f"GPS_INSTANT_LOCK_{feature_map['gps_cold_start_ms']}ms")
        if gps_variance < 0.001:
            flags.append(f"GPS_ZERO_VARIANCE_{gps_variance:.6f}")
        if feature_map["accel_rms"] < 0.1:
            flags.append(f"DEVICE_STATIONARY_ACCEL_{feature_map['accel_rms']:.3f}")
        if ip_gps_delta > 5.0:
            flags.append(f"IP_GPS_MISMATCH_{ip_gps_delta:.1f}km")
        if feature_map["claims_in_window_same_zone"] > 50:
            flags.append(f"COORDINATED_BURST_{feature_map['claims_in_window_same_zone']}")

        if combined >= 0.85:
            decision = "blocked"
        elif combined >= 0.65:
            decision = "soft_hold"
        else:
            decision = "approved"

        return {
            "total_score": combined,
            "iso_forest_score": round(iso_score, 4),
            "gb_score": round(gb_score, 4),
            "decision": decision,
        }

    async def _resolve_ip_geolocation(
        self,
        client_ip: Optional[str],
        sensor: dict,
        flags: list,
    ) -> dict:
        """
        Server-side IP geolocation via IPinfo.io.

        SECURITY: This uses the raw client IP extracted from the FastAPI
        Request object (request.client.host), NOT from the sensor payload.
        A spoofed device cannot fake this — the IP comes from the TCP
        connection itself.

        Returns: {
            "ip": str,
            "ip_lat": float | None,
            "ip_lng": float | None,
            "delta_km": float,
            "city": str,
            "region": str,
            "vpn": bool,
        }
        """
        result = {
            "ip": client_ip or "unknown",
            "ip_lat": None,
            "ip_lng": None,
            "delta_km": 1.0,  # Default: low delta (benefit of doubt)
            "city": "",
            "region": "",
            "vpn": False,
            "geo_unavailable": False,  # Vuln A: Fail-Closed tracking flag
        }

        if not client_ip or client_ip in ("127.0.0.1", "::1", "testclient"):
            logger.debug("IP geolocation skipped — localhost/test client")
            return result

        try:
            url = f"https://ipinfo.io/{client_ip}/json"
            params = {}
            if IPINFO_TOKEN:
                params["token"] = IPINFO_TOKEN

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            # Parse location "lat,lng" string
            loc = data.get("loc", "")
            if loc and "," in loc:
                parts = loc.split(",")
                result["ip_lat"] = float(parts[0])
                result["ip_lng"] = float(parts[1])

            result["city"] = data.get("city", "")
            result["region"] = data.get("region", "")

            # VPN / proxy detection
            privacy = data.get("privacy", {})
            if isinstance(privacy, dict):
                is_vpn = privacy.get("vpn", False)
                is_proxy = privacy.get("proxy", False)
                if is_vpn or is_proxy:
                    result["vpn"] = True
                    flags.append("VPN_DETECTED")
                    logger.info(f"VPN/proxy detected for IP {client_ip}")

            # Calculate Haversine distance between IP geo and first GPS ping
            gps_pings = sensor.get("gps_pings", [])
            if result["ip_lat"] is not None and gps_pings:
                gps_lat = gps_pings[0].get("lat", 0)
                gps_lng = gps_pings[0].get("lng", 0)
                delta_km = self._haversine_km(
                    result["ip_lat"], result["ip_lng"],
                    gps_lat, gps_lng,
                )
                result["delta_km"] = round(delta_km, 2)

            logger.debug(
                f"IPinfo resolved | ip={client_ip} | city={result['city']} "
                f"| lat={result['ip_lat']} | lng={result['ip_lng']} "
                f"| delta_km={result['delta_km']}"
            )

        except httpx.HTTPStatusError as e:
            logger.warning(f"IPinfo API error (HTTP {e.response.status_code}): {e}")
            result["geo_unavailable"] = True
            flags.append("NETWORK_GEO_UNAVAILABLE")
        except httpx.RequestError as e:
            logger.warning(f"IPinfo request failed: {e}")
            result["geo_unavailable"] = True
            flags.append("NETWORK_GEO_UNAVAILABLE")
        except Exception as e:
            logger.warning(f"IPinfo geolocation failed: {e}")
            result["geo_unavailable"] = True
            flags.append("NETWORK_GEO_UNAVAILABLE")

        return result

    async def _compute_gps_physics_score(
        self,
        db: AsyncSession,
        worker_id: UUID,
        sensor: dict,
        flags: list,
    ) -> float:
        """
        GPS physics plausibility check.
        Phase 2: Rule-based. Phase 3: Replaced by Isolation Forest anomaly detector.

        Checks:
          (1) Mock location flag (hard stop → 1.0)
          (2) Developer mode flag
          (3) GPS pings variance from sensor data
          (4) GPS accuracy radius
          (5) Historical GPS ping frequency (DB fallback)
          (6) GPS cold start time (< 2s = suspicious, mock GPS has instant lock)
        """
        score = 0.0

        # Check mock location flag — hard stop
        if sensor.get("is_mock_location"):
            flags.append("MOCK_LOCATION_DETECTED")
            return 1.0  # Instant max score

        if sensor.get("is_developer_mode"):
            flags.append("DEVELOPER_MODE_ENABLED")
            score += 0.3

        # Check GPS cold start time
        cold_start_ms = sensor.get("gps_cold_start_ms")
        if cold_start_ms is not None:
            if cold_start_ms < 2000:
                flags.append(f"GPS_INSTANT_LOCK_{cold_start_ms}ms")
                score += 0.3
            elif cold_start_ms < 5000:
                score += 0.1

        # Check GPS pings from sensor data
        gps_pings = sensor.get("gps_pings", [])
        if gps_pings and len(gps_pings) >= 2:
            lats = [p.get("lat", 0) for p in gps_pings]
            lngs = [p.get("lng", 0) for p in gps_pings]
            lat_var = max(lats) - min(lats)
            lng_var = max(lngs) - min(lngs)

            # Convert to approximate meters (1 degree ≈ 111km at equator)
            variance_m = math.sqrt(
                (lat_var * 111000) ** 2 + (lng_var * 111000) ** 2
            )

            if variance_m < 0.5:
                # Near-zero variance — physically impossible without spoofing
                flags.append(f"GPS_ZERO_VARIANCE_{variance_m:.3f}m")
                score += 0.6
            elif variance_m > GPS_VARIANCE_THRESHOLD_M:
                flags.append(f"GPS_HIGH_VARIANCE_{variance_m:.0f}m")
                score += 0.5

            # Check accuracy
            accuracies = [p.get("accuracy_m", 0) for p in gps_pings if p.get("accuracy_m")]
            if accuracies:
                avg_accuracy = sum(accuracies) / len(accuracies)
                if avg_accuracy < 1.0:
                    # Sub-meter accuracy is suspicious (real GPS ≈ 5-15m)
                    flags.append(f"GPS_UNREALISTIC_ACCURACY_{avg_accuracy:.1f}m")
                    score += 0.3
                elif avg_accuracy > GPS_ACCURACY_THRESHOLD_M:
                    flags.append(f"GPS_LOW_ACCURACY_{avg_accuracy:.0f}m")
                    score += 0.3
        else:
            # No sensor GPS data — check DB for recent pings
            cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
            result = await db.execute(
                select(func.count(GpsPing.id)).where(
                    GpsPing.worker_id == worker_id,
                    GpsPing.recorded_at >= cutoff,
                )
            )
            recent_pings = result.scalar() or 0
            if recent_pings < 3:
                flags.append("INSUFFICIENT_GPS_HISTORY")
                score += 0.2

        return min(1.0, score)

    def _compute_device_sensor_score(
        self,
        sensor: dict,
        flags: list,
    ) -> float:
        """
        Device sensor plausibility check.
        Phase 2: Rule-based. Phase 3: Replaced by GradientBoosting feature input.

        Checks accelerometer RMS and gyroscope yaw rate.
        A delivery rider should show movement signatures during work hours.
        """
        score = 0.0

        accel_rms = sensor.get("accelerometer_rms")
        gyro_yaw = sensor.get("gyroscope_yaw_rate")

        if accel_rms is not None:
            if accel_rms < 0.1:
                # Near-zero — only gravitational DC component (sitting at home)
                flags.append(f"DEVICE_STATIONARY_ACCEL_{accel_rms:.3f}")
                score += 0.8
            elif accel_rms < ACCEL_RMS_STATIONARY:
                flags.append(f"DEVICE_LOW_ACCEL_{accel_rms:.2f}")
                score += 0.5
            elif accel_rms > ACCEL_RMS_CYCLING:
                # Normal cycling movement
                score += 0.0
            else:
                # Ambiguous zone
                score += 0.1
        else:
            # No accelerometer data — slight penalty
            score += 0.15

        if gyro_yaw is not None:
            if gyro_yaw < 0.02:
                # Near-zero rotation — device is completely stationary
                flags.append(f"DEVICE_NO_ROTATION_{gyro_yaw:.3f}")
                score += 0.4
            elif gyro_yaw < GYRO_YAW_THRESHOLD:
                flags.append("DEVICE_LOW_ROTATION")
                score += 0.2
        else:
            score += 0.05

        return min(1.0, score)

    def _compute_network_geo_score(
        self,
        sensor: dict,
        flags: list,
    ) -> float:
        """
        Network-GPS geo consistency check.
        Phase 2: Rule-based. Phase 3: Replaced by GradientBoosting feature input.

        Compares IP-based geolocation with GPS coordinates.
        """
        score = 0.0

        # ── IP-GPS delta: use server-resolved IPinfo.io data ──────────────
        # The ip_result was already computed in score_claim() via
        # _resolve_ip_geolocation() using the raw TCP client IP.
        # We access it through the sensor dict where score_claim injects it.
        ip_delta_km = sensor.get("_server_ip_delta_km")

        if ip_delta_km is not None:
            if ip_delta_km > IP_GPS_DELTA_KM:
                flags.append(f"IP_GPS_MISMATCH_{ip_delta_km:.0f}km")
                score += 0.9
            elif ip_delta_km > 5:
                flags.append(f"IP_GPS_DELTA_{ip_delta_km:.1f}km")
                score += 0.5
            elif ip_delta_km > 2:
                score += 0.2
        else:
            # No IP geo data — minimal penalty
            score += 0.1

        # Check if VPN was detected by IPinfo.io
        if sensor.get("_server_vpn_detected"):
            flags.append("VPN_DETECTED")
            score += 0.4

        # Check tower handoffs
        tower_handoffs = sensor.get("tower_handoffs_30min")
        if tower_handoffs is not None:
            if tower_handoffs == 0:
                flags.append("ZERO_TOWER_HANDOFFS")
                score += 0.3
            elif tower_handoffs < 2:
                score += 0.1

        return min(1.0, score)

    async def _compute_behavioral_score(
        self,
        db: AsyncSession,
        worker_id: UUID,
        zone_id: UUID,
        sensor: dict,
        flags: list,
    ) -> float:
        """
        Behavioral analysis.
        Phase 2: Rule-based. Phase 3: Replaced by NetworkX Louvain graph scorer.

        Checks:
          (1) Zone residency — was the worker in the zone before the trigger?
          (2) Claim frequency — too many claims in short timeframe?
          (3) Coordinated burst — abnormal same-zone claims (from sensor payload)
        """
        score = 0.0

        # Check pre-event zone residency from sensor payload
        zone_resident = sensor.get("zone_resident_t_minus_30")
        if zone_resident is False:
            flags.append("NOT_ZONE_RESIDENT_BEFORE_TRIGGER")
            score += 0.3

        # Check coordinated burst from sensor payload
        claims_in_window = sensor.get("claims_in_window_same_zone")
        if claims_in_window is not None:
            if claims_in_window > 100:
                flags.append(f"COORDINATED_BURST_{claims_in_window}_CLAIMS")
                score += 0.7
            elif claims_in_window > 30:
                flags.append(f"ELEVATED_BURST_{claims_in_window}_CLAIMS")
                score += 0.3
            elif claims_in_window > 10:
                score += 0.1

        # DB check: zone residency — worker should have GPS pings in the zone
        cutoff = datetime.now(timezone.utc) - timedelta(days=ZONE_RESIDENCY_DAYS)
        result = await db.execute(
            select(func.count(GpsPing.id)).where(
                GpsPing.worker_id == worker_id,
                GpsPing.recorded_at >= cutoff,
            )
        )
        residency_pings = result.scalar() or 0

        if residency_pings < 5:
            flags.append("LOW_ZONE_RESIDENCY")
            score += 0.2

        # DB check: claim frequency — more than 3 claims in 7 days is suspicious
        from models.claim import Claim
        claim_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        result = await db.execute(
            select(func.count(Claim.id)).where(
                Claim.worker_id == worker_id,
                Claim.created_at >= claim_cutoff,
            )
        )
        recent_claims = result.scalar() or 0

        if recent_claims >= 5:
            flags.append(f"HIGH_CLAIM_FREQUENCY_{recent_claims}")
            score += 0.3
        elif recent_claims >= 3:
            flags.append(f"ELEVATED_CLAIM_FREQUENCY_{recent_claims}")
            score += 0.1

        return min(1.0, score)

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two GPS coordinates in kilometers."""
        R = 6371.0  # Earth radius in km
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(d_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
