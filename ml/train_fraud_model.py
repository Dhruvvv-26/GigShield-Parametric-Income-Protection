"""
KavachAI ML — Isolation Forest + GradientBoosting Fraud Detection
====================================================================
Trains a dual-model fraud ensemble on 50,000 synthetic labeled rows:
  - Isolation Forest (unsupervised anomaly, trained on legitimate-only)
  - GradientBoosting classifier (supervised, trained on all labeled data)
  - Combined score: 40% IsoForest + 60% GradientBoosting

Corrections applied:
  2. GPS variance: log-normal for genuine (matches real hardware), sub-mm for spoofed
  2b. Monsoon month feature: legitimate riders with high IP-GPS delta not flagged
  2c. Cold start time as feature (genuine: 15-45s, spoofed: 50-250ms)

Validation targets:
  - AUC-ROC > 0.93
  - False positive rate < 8%
  - Spoofed GPS correctly classified > 95%
  - Genuine monsoon claims correctly approved > 90%

Usage:
  python ml/train_fraud_model.py
"""
import os
import random
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    roc_auc_score, precision_score, recall_score,
    confusion_matrix, classification_report,
)
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)

SEED = 42
N_ROWS = 50_000
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")

random.seed(SEED)
np.random.seed(SEED)


def generate_fraud_dataset(n: int = N_ROWS) -> pd.DataFrame:
    """
    Generate 50K labeled fraud detection rows.
    70% legitimate, 20% GPS spoofed, 10% suspicious (blend).

    Correction 2: GPS distributions match real hardware specs.
    """
    rows = []
    n_legitimate = int(n * 0.70)
    n_spoofed = int(n * 0.20)
    n_suspicious = n - n_legitimate - n_spoofed

    # ── Legitimate claims (70%) ───────────────────────────────────────────────
    for _ in range(n_legitimate):
        month = random.randint(1, 12)
        is_monsoon = month in [6, 7, 8, 9]

        # GPS variance: log-normal (real hardware behavior)
        gps_variance = float(np.clip(
            np.random.lognormal(mean=1.2, sigma=0.4), 0.8, 20.0
        ))
        # Accuracy correlated with variance
        gps_accuracy = float(np.clip(
            gps_variance * random.uniform(2.5, 4.0), 5.0, 50.0
        ))
        # Cold start: genuine satellite acquisition
        gps_cold_start_ms = random.randint(15000, 45000)

        # Accelerometer: cycling vibration
        accel_rms = random.uniform(0.8, 2.4)
        # Gyroscope: normal heading changes
        gyro_yaw_mismatch = random.uniform(0, 12)

        # Mock location: never on real device
        mock_location = 0

        # IP-GPS delta: monsoon causes higher delta due to network rerouting
        if is_monsoon:
            ip_gps_delta_km = random.uniform(0.1, 3.5)
        else:
            ip_gps_delta_km = random.uniform(0.1, 1.8)

        # Tower handoffs: normal mobility
        tower_handoffs = random.randint(2, 8)
        # Zone residency: rider was in zone before trigger
        zone_resident = 1
        # Claims in window: normal volume
        claims_in_window = int(np.random.poisson(5))

        rows.append({
            "gps_variance_sigma": gps_variance,
            "gps_accuracy_m": gps_accuracy,
            "gps_cold_start_ms": gps_cold_start_ms,
            "accel_rms": accel_rms,
            "gyro_yaw_mismatch_deg": gyro_yaw_mismatch,
            "mock_location_enabled": mock_location,
            "ip_gps_delta_km": ip_gps_delta_km,
            "tower_handoffs_30min": tower_handoffs,
            "zone_resident_t_minus_30": zone_resident,
            "claims_in_window_same_zone": claims_in_window,
            "month": month,
            "is_monsoon": int(is_monsoon),
            "label": 0,  # legitimate
        })

    # ── GPS Spoofed claims (20%) ──────────────────────────────────────────────
    for _ in range(n_spoofed):
        month = random.randint(1, 12)
        is_monsoon = month in [6, 7, 8, 9]

        # Mock GPS apps: sub-millimeter variance (physically impossible)
        gps_variance = random.uniform(0.0, 0.0008)
        gps_accuracy = random.uniform(0.0, 0.5)
        gps_cold_start_ms = random.randint(50, 250)  # instant lock

        # Stationary device
        accel_rms = random.uniform(0.0, 0.1)
        # Large heading mismatch (GPS says moving, device is still)
        gyro_yaw_mismatch = random.uniform(30, 90)

        mock_location = 1
        ip_gps_delta_km = random.uniform(5.0, 15.0)
        tower_handoffs = 0
        zone_resident = 0
        claims_in_window = random.randint(80, 200)

        rows.append({
            "gps_variance_sigma": gps_variance,
            "gps_accuracy_m": gps_accuracy,
            "gps_cold_start_ms": gps_cold_start_ms,
            "accel_rms": accel_rms,
            "gyro_yaw_mismatch_deg": gyro_yaw_mismatch,
            "mock_location_enabled": mock_location,
            "ip_gps_delta_km": ip_gps_delta_km,
            "tower_handoffs_30min": tower_handoffs,
            "zone_resident_t_minus_30": zone_resident,
            "claims_in_window_same_zone": claims_in_window,
            "month": month,
            "is_monsoon": int(is_monsoon),
            "label": 1,  # fraud
        })

    # ── Suspicious claims (10%) — blend between legitimate and spoofed ────────
    for _ in range(n_suspicious):
        month = random.randint(1, 12)
        is_monsoon = month in [6, 7, 8, 9]

        # Intermediate GPS characteristics
        gps_variance = random.uniform(0.001, 1.5)
        gps_accuracy = random.uniform(0.5, 8.0)
        gps_cold_start_ms = random.randint(500, 15000)

        accel_rms = random.uniform(0.1, 0.8)
        gyro_yaw_mismatch = random.uniform(10, 35)

        mock_location = random.choice([0, 0, 1])  # 33% chance
        ip_gps_delta_km = random.uniform(1.5, 6.0)
        tower_handoffs = random.randint(0, 3)
        zone_resident = random.choice([0, 1])
        claims_in_window = random.randint(15, 80)

        # 60% of suspicious are actually fraud, 40% are just anomalous legitimate
        is_fraud = 1 if random.random() < 0.6 else 0

        rows.append({
            "gps_variance_sigma": gps_variance,
            "gps_accuracy_m": gps_accuracy,
            "gps_cold_start_ms": gps_cold_start_ms,
            "accel_rms": accel_rms,
            "gyro_yaw_mismatch_deg": gyro_yaw_mismatch,
            "mock_location_enabled": mock_location,
            "ip_gps_delta_km": ip_gps_delta_km,
            "tower_handoffs_30min": tower_handoffs,
            "zone_resident_t_minus_30": zone_resident,
            "claims_in_window_same_zone": claims_in_window,
            "month": month,
            "is_monsoon": int(is_monsoon),
            "label": is_fraud,
        })

    df = pd.DataFrame(rows)
    return df.sample(frac=1, random_state=SEED).reset_index(drop=True)


FEATURE_COLS = [
    "gps_variance_sigma",
    "gps_accuracy_m",
    "gps_cold_start_ms",
    "accel_rms",
    "gyro_yaw_mismatch_deg",
    "mock_location_enabled",
    "ip_gps_delta_km",
    "tower_handoffs_30min",
    "zone_resident_t_minus_30",
    "claims_in_window_same_zone",
    "month",
    "is_monsoon",
]


def train():
    print("=" * 70)
    print("KavachAI Fraud Detection — IsolationForest + GradientBoosting")
    print("=" * 70)

    # ── Generate data ─────────────────────────────────────────────────────────
    print(f"\n[1/5] Generating {N_ROWS:,} synthetic fraud rows...")
    df = generate_fraud_dataset(N_ROWS)
    print(f"  → Data shape: {df.shape}")
    print(f"  → Class distribution: {dict(df['label'].value_counts())}")
    print(f"  → Fraud rate: {df['label'].mean():.1%}")

    X = df[FEATURE_COLS].values.astype(float)
    y = df["label"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=SEED, stratify=y
    )

    # Scale features for Isolation Forest
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Separate legitimate-only training set for Isolation Forest
    X_train_legit = X_train_scaled[y_train == 0]
    print(f"  → Train: {X_train.shape[0]:,}, Test: {X_test.shape[0]:,}")
    print(f"  → Legitimate-only for IsoForest: {X_train_legit.shape[0]:,}")

    # ── Train Isolation Forest (unsupervised) ─────────────────────────────────
    print("\n[2/5] Training Isolation Forest (200 estimators, contamination=0.15)...")
    iso_forest = IsolationForest(
        n_estimators=200,
        contamination=0.15,
        max_samples="auto",
        random_state=SEED,
        n_jobs=-1,
    )
    iso_forest.fit(X_train_legit)

    # Score: higher = more anomalous (invert sklearn's convention)
    iso_raw = -iso_forest.score_samples(X_test_scaled)
    # Normalize to 0-1
    iso_min, iso_max = iso_raw.min(), iso_raw.max()
    iso_score = (iso_raw - iso_min) / (iso_max - iso_min + 1e-8)
    iso_auc = roc_auc_score(y_test, iso_score)
    print(f"  → Isolation Forest AUC: {iso_auc:.4f}")

    # ── Train GradientBoosting (supervised) ───────────────────────────────────
    print("\n[3/5] Training GradientBoosting (200 estimators, depth=5, lr=0.05)...")
    gb_clf = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        random_state=SEED,
    )
    gb_clf.fit(X_train, y_train)
    gb_proba = gb_clf.predict_proba(X_test)[:, 1]
    gb_auc = roc_auc_score(y_test, gb_proba)
    print(f"  → GradientBoosting AUC: {gb_auc:.4f}")

    # ── Combined ensemble: 40% IsoForest + 60% GB ────────────────────────────
    combined_score = 0.40 * iso_score + 0.60 * gb_proba
    combined_auc = roc_auc_score(y_test, combined_score)

    # Decision threshold at 0.5
    combined_pred = (combined_score >= 0.5).astype(int)
    precision = precision_score(y_test, combined_pred, zero_division=0)
    recall = recall_score(y_test, combined_pred, zero_division=0)
    cm = confusion_matrix(y_test, combined_pred)
    tn, fp, fn, tp = cm.ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    print(f"\n{'─' * 50}")
    print(f"  ENSEMBLE (40% IsoForest + 60% GB)")
    print(f"  AUC-ROC:   {combined_auc:.4f}")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall:    {recall:.4f}")
    print(f"  FPR:       {fpr:.4f} ({fpr:.1%})")
    print(f"  Confusion Matrix:")
    print(f"    TN={tn:,}  FP={fp:,}")
    print(f"    FN={fn:,}  TP={tp:,}")
    print(f"{'─' * 50}")

    # ── Detailed validation ───────────────────────────────────────────────────
    print("\n[4/5] Detailed validation...")

    # Spoofed GPS detection rate
    df_test = pd.DataFrame(X_test, columns=FEATURE_COLS)
    df_test["label"] = y_test
    df_test["score"] = combined_score

    # Find spoofed samples (very low GPS variance + mock location)
    spoofed_mask = (
        (df_test["gps_variance_sigma"] < 0.001) &
        (df_test["mock_location_enabled"] == 1) &
        (df_test["label"] == 1)
    )
    if spoofed_mask.sum() > 0:
        spoof_detection = (df_test.loc[spoofed_mask, "score"] >= 0.5).mean()
        print(f"  Spoofed GPS detection rate: {spoof_detection:.1%}")
    else:
        spoof_detection = 1.0
        print("  Spoofed GPS detection rate: N/A (no spoofed in test split)")

    # Genuine monsoon claims — should NOT be flagged
    monsoon_legit_mask = (
        (df_test["is_monsoon"] == 1) &
        (df_test["label"] == 0)
    )
    if monsoon_legit_mask.sum() > 0:
        monsoon_approval = (df_test.loc[monsoon_legit_mask, "score"] < 0.5).mean()
        print(f"  Genuine monsoon approval rate: {monsoon_approval:.1%}")
    else:
        monsoon_approval = 1.0
        print("  Genuine monsoon approval rate: N/A")

    # ── Feature importance ────────────────────────────────────────────────────
    print("\n  Feature importance (GradientBoosting):")
    importances = gb_clf.feature_importances_
    feat_imp = sorted(zip(FEATURE_COLS, importances), key=lambda x: -x[1])
    for name, imp in feat_imp[:6]:
        print(f"    {name:40s} {imp:.3f}")

    # ── Assertions ────────────────────────────────────────────────────────────
    print("\n── VALIDATION ──")
    assert combined_auc > 0.93, f"AUC {combined_auc:.4f} < 0.93 — retrain"
    print(f"  ✅ AUC-ROC: {combined_auc:.4f} > 0.93")
    assert fpr < 0.08, f"FPR {fpr:.4f} > 0.08 — retrain"
    print(f"  ✅ FPR: {fpr:.4f} < 0.08")
    if spoofed_mask.sum() > 0:
        assert spoof_detection > 0.95, f"Spoof detection {spoof_detection:.1%} < 95%"
        print(f"  ✅ Spoofed detection: {spoof_detection:.1%} > 95%")
    if monsoon_legit_mask.sum() > 0:
        assert monsoon_approval > 0.90, f"Monsoon approval {monsoon_approval:.1%} < 90%"
        print(f"  ✅ Monsoon approval: {monsoon_approval:.1%} > 90%")
    print("  ✅ All validation targets PASSED")

    # ── Save models ───────────────────────────────────────────────────────────
    print("\n[5/5] Saving models...")
    os.makedirs(MODEL_DIR, exist_ok=True)

    iso_path = os.path.join(MODEL_DIR, "iso_forest.pkl")
    gb_path = os.path.join(MODEL_DIR, "gb_fraud.pkl")
    scaler_path = os.path.join(MODEL_DIR, "fraud_scaler.pkl")
    meta_path = os.path.join(MODEL_DIR, "fraud_meta.pkl")

    joblib.dump(iso_forest, iso_path)
    joblib.dump(gb_clf, gb_path)
    joblib.dump(scaler, scaler_path)

    meta = {
        "feature_columns": FEATURE_COLS,
        "auc": combined_auc,
        "fpr": fpr,
        "precision": precision,
        "recall": recall,
        "iso_score_min": float(iso_min),
        "iso_score_max": float(iso_max),
    }
    joblib.dump(meta, meta_path)

    print(f"  → iso_forest.pkl ({os.path.getsize(iso_path) / 1024:.0f} KB)")
    print(f"  → gb_fraud.pkl ({os.path.getsize(gb_path) / 1024:.0f} KB)")
    print(f"  → fraud_scaler.pkl")
    print(f"  → fraud_meta.pkl")

    print("\n✅ Fraud model training complete.")
    return combined_auc, fpr


if __name__ == "__main__":
    train()
