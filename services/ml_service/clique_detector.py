"""
kavachai/ml_service/clique_detector.py

NetworkX-based Louvain community detection for coordinated fraud ring identification.
Phase 3 addition — runs as a background task every 60 seconds on the claims stream.

Graph schema:
  Nodes: riders (worker_id), devices (device_fingerprint), claims (claim_id)
  Edges:
    rider → claim   (weight=1.0)
    rider → device  (weight=1.0, shared device = strong fraud signal)
    claim → zone    (weight=fraud_score, elevated in active trigger zones)

Fraud ring detection:
  1. Build bipartite graph from last 24h claims
  2. Run Louvain community detection
  3. Flag communities where: size ≥ RING_SIZE_THRESHOLD AND
     avg fraud_score ≥ RING_SCORE_THRESHOLD AND
     submission timestamps within BURST_WINDOW_SECONDS
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

try:
    import networkx as nx
    from networkx.algorithms.community import louvain_communities
    HAS_NX = True
except ImportError:
    HAS_NX = False
    logger.warning("networkx not installed — Louvain clique detection disabled. pip install networkx")

# ── Thresholds ─────────────────────────────────────────────────────────────────
RING_SIZE_THRESHOLD   = 5      # Minimum community size to flag as a potential ring
RING_SCORE_THRESHOLD  = 0.60   # Average fraud score in community to trigger alert
BURST_WINDOW_SECONDS  = 120    # Claims within this window are considered coordinated
DEVICE_SHARE_WEIGHT   = 3.0    # Edge weight multiplier for shared device fingerprint
ZONE_BURST_WEIGHT     = 2.0    # Edge weight multiplier for same-zone burst submissions


# ── Data Models ────────────────────────────────────────────────────────────────

@dataclass
class ClaimNode:
    claim_id: str
    worker_id: str
    zone: str
    fraud_score: float
    device_fingerprint: str
    submitted_at: datetime
    ip_hash: str = ""


@dataclass
class FraudRingAlert:
    community_id: int
    member_worker_ids: list[str]
    member_claim_ids: list[str]
    avg_fraud_score: float
    max_fraud_score: float
    zone: str
    submission_burst_seconds: float
    shared_devices: list[str]
    risk_level: str              # "SUSPECTED" | "HIGH_CONFIDENCE" | "CRITICAL"
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Graph Builder ──────────────────────────────────────────────────────────────

class FraudGraphBuilder:
    """Builds a weighted undirected graph from claim nodes."""

    def __init__(self) -> None:
        self.G: Any = None

    def build(self, claims: list[ClaimNode]) -> Any:
        if not HAS_NX:
            return None

        G = nx.Graph()

        # Add rider nodes
        for c in claims:
            G.add_node(f"rider:{c.worker_id}", node_type="rider", worker_id=c.worker_id)
            G.add_node(f"claim:{c.claim_id}", node_type="claim",
                       claim_id=c.claim_id, fraud_score=c.fraud_score, zone=c.zone)
            G.add_edge(f"rider:{c.worker_id}", f"claim:{c.claim_id}", weight=1.0)

        # Device fingerprint edges — shared device is a strong fraud signal
        device_to_riders: dict[str, list[str]] = defaultdict(list)
        for c in claims:
            if c.device_fingerprint:
                device_to_riders[c.device_fingerprint].append(c.worker_id)

        for device_fp, rider_ids in device_to_riders.items():
            if len(rider_ids) > 1:
                for i in range(len(rider_ids)):
                    for j in range(i + 1, len(rider_ids)):
                        u = f"rider:{rider_ids[i]}"
                        v = f"rider:{rider_ids[j]}"
                        if G.has_edge(u, v):
                            G[u][v]["weight"] += DEVICE_SHARE_WEIGHT
                        else:
                            G.add_edge(u, v, weight=DEVICE_SHARE_WEIGHT, shared_device=device_fp)

        # Temporal burst edges — riders submitting within the burst window
        sorted_claims = sorted(claims, key=lambda c: c.submitted_at)
        for i in range(len(sorted_claims)):
            for j in range(i + 1, len(sorted_claims)):
                ci, cj = sorted_claims[i], sorted_claims[j]
                delta = (cj.submitted_at - ci.submitted_at).total_seconds()
                if delta > BURST_WINDOW_SECONDS:
                    break
                if ci.zone == cj.zone and ci.worker_id != cj.worker_id:
                    u = f"rider:{ci.worker_id}"
                    v = f"rider:{cj.worker_id}"
                    w = ZONE_BURST_WEIGHT * (1 - delta / BURST_WINDOW_SECONDS)  # Closer = higher weight
                    if G.has_edge(u, v):
                        G[u][v]["weight"] += w
                    else:
                        G.add_edge(u, v, weight=w, burst_pair=True)

        self.G = G
        return G


# ── Louvain Community Detection ─────────────────────────────────────────────────

class LouvainRingDetector:
    """
    Runs Louvain community detection and scores each community for fraud ring likelihood.
    Phase 3 live — integrated into ML Service background task.
    """

    def __init__(self) -> None:
        self.builder = FraudGraphBuilder()
        self.last_run: datetime | None = None
        self.last_alerts: list[FraudRingAlert] = []

    def detect(self, claims: list[ClaimNode]) -> list[FraudRingAlert]:
        if not HAS_NX:
            logger.warning("NetworkX unavailable — skipping Louvain detection")
            return []

        if not claims:
            return []

        try:
            G = self.builder.build(claims)
            if G is None or G.number_of_nodes() < RING_SIZE_THRESHOLD:
                return []

            communities = louvain_communities(G, weight="weight", seed=42)
            alerts: list[FraudRingAlert] = []

            for comm_id, community in enumerate(communities):
                rider_nodes   = [n for n in community if n.startswith("rider:")]
                claim_nodes   = [n for n in community if n.startswith("claim:")]

                if len(rider_nodes) < RING_SIZE_THRESHOLD:
                    continue

                worker_ids = [n.removeprefix("rider:") for n in rider_nodes]
                claim_ids  = [n.removeprefix("claim:") for n in claim_nodes]

                # Score the community
                claim_data = [c for c in claims if c.worker_id in worker_ids]
                if not claim_data:
                    continue

                avg_score = sum(c.fraud_score for c in claim_data) / len(claim_data)
                max_score = max(c.fraud_score for c in claim_data)

                if avg_score < RING_SCORE_THRESHOLD:
                    continue

                # Burst analysis
                times = sorted(c.submitted_at for c in claim_data)
                burst_span = (times[-1] - times[0]).total_seconds() if len(times) > 1 else 0.0

                # Shared device detection
                devices: list[str] = []
                for u, v, data in G.edges(rider_nodes, data=True):
                    if "shared_device" in data:
                        devices.append(data["shared_device"])

                # Dominant zone
                zones = [c.zone for c in claim_data]
                dominant_zone = max(set(zones), key=zones.count)

                # Risk classification
                if avg_score >= 0.85 or len(rider_nodes) >= 50:
                    risk_level = "CRITICAL"
                elif avg_score >= 0.75 or len(rider_nodes) >= 20:
                    risk_level = "HIGH_CONFIDENCE"
                else:
                    risk_level = "SUSPECTED"

                alert = FraudRingAlert(
                    community_id=comm_id,
                    member_worker_ids=worker_ids,
                    member_claim_ids=claim_ids,
                    avg_fraud_score=round(avg_score, 4),
                    max_fraud_score=round(max_score, 4),
                    zone=dominant_zone,
                    submission_burst_seconds=round(burst_span, 1),
                    shared_devices=list(set(devices)),
                    risk_level=risk_level,
                )
                alerts.append(alert)
                logger.warning(
                    "FRAUD RING DETECTED | community=%d | size=%d | avg_score=%.3f | zone=%s | risk=%s",
                    comm_id, len(rider_nodes), avg_score, dominant_zone, risk_level
                )

            self.last_run = datetime.now(timezone.utc)
            self.last_alerts = alerts
            return alerts

        except Exception as exc:
            logger.exception("Louvain detection failed: %s", exc)
            return []

    def run_on_window(self, all_claims: list[dict], window_hours: int = 24) -> list[FraudRingAlert]:
        """
        Entry point called by the APScheduler background task.
        Filters claims to the rolling time window before running detection.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        nodes: list[ClaimNode] = []
        for raw in all_claims:
            try:
                submitted = datetime.fromisoformat(raw["created_at"].replace("Z", "+00:00"))
                if submitted < cutoff:
                    continue
                nodes.append(ClaimNode(
                    claim_id=raw["claim_id"],
                    worker_id=raw["worker_id"],
                    zone=raw.get("zone", "unknown"),
                    fraud_score=float(raw.get("fraud_score", 0.0)),
                    device_fingerprint=raw.get("device_fingerprint", ""),
                    submitted_at=submitted,
                    ip_hash=raw.get("ip_hash", ""),
                ))
            except (KeyError, ValueError) as e:
                logger.debug("Skipping malformed claim node: %s", e)

        logger.info("Louvain detection running on %d claims (window=%dh)", len(nodes), window_hours)
        return self.detect(nodes)


# ── Singleton ──────────────────────────────────────────────────────────────────

detector = LouvainRingDetector()
