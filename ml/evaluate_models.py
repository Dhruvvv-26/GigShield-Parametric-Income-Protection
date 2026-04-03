"""
GigShield ML — Model Evaluation Suite
=======================================
Loads all 3 trained model sets and prints comprehensive metrics.

Usage:
  python ml/evaluate_models.py
"""
import os
import sys

import joblib
import numpy as np

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")


def evaluate_premium():
    """Evaluate premium pricing model."""
    print("\n" + "=" * 60)
    print("📊 PREMIUM PRICING MODEL (XGBoost + LightGBM)")
    print("=" * 60)

    meta_path = os.path.join(MODEL_DIR, "premium_meta.pkl")
    if not os.path.exists(meta_path):
        print("  ⚠  Model not found. Run: python ml/train_premium_model.py")
        return False

    meta = joblib.load(meta_path)
    print(f"  R² Score:       {meta['r2']:.4f}")
    print(f"  MAE:            ₹{meta['mae']:.2f}")
    print(f"  RMSE:           ₹{meta['rmse']:.2f}")
    print(f"  Training rows:  {meta['n_train']:,}")
    print(f"  Features:       {meta['n_features']}")
    print(f"  Status:         {'✅ PASS' if meta['r2'] > 0.85 and meta['mae'] < 15 else '❌ FAIL'}")
    return True


def evaluate_fraud():
    """Evaluate fraud detection model."""
    print("\n" + "=" * 60)
    print("🔍 FRAUD DETECTION MODEL (IsolationForest + GradientBoosting)")
    print("=" * 60)

    meta_path = os.path.join(MODEL_DIR, "fraud_meta.pkl")
    if not os.path.exists(meta_path):
        print("  ⚠  Model not found. Run: python ml/train_fraud_model.py")
        return False

    meta = joblib.load(meta_path)
    print(f"  AUC-ROC:        {meta['auc']:.4f}")
    print(f"  False Pos Rate: {meta['fpr']:.4f} ({meta['fpr']:.1%})")
    print(f"  Precision:      {meta['precision']:.4f}")
    print(f"  Recall:         {meta['recall']:.4f}")
    print(f"  Features:       {meta['feature_columns']}")
    print(f"  Status:         {'✅ PASS' if meta['auc'] > 0.93 and meta['fpr'] < 0.08 else '❌ FAIL'}")

    # Load and display feature importance
    gb_path = os.path.join(MODEL_DIR, "gb_fraud.pkl")
    if os.path.exists(gb_path):
        gb = joblib.load(gb_path)
        print("\n  Feature Importance (Top 6):")
        importances = gb.feature_importances_
        feat_imp = sorted(zip(meta["feature_columns"], importances), key=lambda x: -x[1])
        for name, imp in feat_imp[:6]:
            bar = "█" * int(imp * 50)
            print(f"    {name:40s} {imp:.3f} {bar}")

    return True


def evaluate_lstm():
    """Evaluate LSTM disruption model."""
    print("\n" + "=" * 60)
    print("🌪️  LSTM DISRUPTION PREDICTION MODEL")
    print("=" * 60)

    meta_path = os.path.join(MODEL_DIR, "lstm_meta.pkl")
    if not os.path.exists(meta_path):
        print("  ⚠  Model not found. Run: python ml/train_lstm_model.py")
        return False

    meta = joblib.load(meta_path)
    print(f"  Test AUC:       {meta['test_auc']:.4f}")
    print(f"  Best Val AUC:   {meta['best_val_auc']:.4f}")
    print(f"  Architecture:   LSTM({meta['input_size']}→{meta['hidden_size']}×{meta['num_layers']}→1)")
    print(f"  Sequence:       {meta['sequence_length']} days → {meta['prediction_horizon']} day prediction")
    print(f"  Features:       {meta['feature_names']}")
    print(f"  Cities:         {meta['cities']}")
    print(f"  Status:         {'✅ PASS' if meta['test_auc'] > 0.75 else '❌ FAIL'}")
    return True


def main():
    print("╔" + "═" * 58 + "╗")
    print("║  GigShield ML — Complete Model Evaluation Suite            ║")
    print("╚" + "═" * 58 + "╝")

    results = {}
    results["premium"] = evaluate_premium()
    results["fraud"] = evaluate_fraud()
    results["lstm"] = evaluate_lstm()

    # Model file sizes
    print("\n" + "=" * 60)
    print("📁 MODEL FILES")
    print("=" * 60)
    total_size = 0
    for f in sorted(os.listdir(MODEL_DIR)):
        if f == ".gitkeep":
            continue
        path = os.path.join(MODEL_DIR, f)
        size = os.path.getsize(path)
        total_size += size
        print(f"  {f:30s} {size / 1024:8.1f} KB")
    print(f"  {'TOTAL':30s} {total_size / 1024:8.1f} KB ({total_size / 1024 / 1024:.1f} MB)")

    # Overall verdict
    print("\n" + "=" * 60)
    print("🏁 OVERALL VERDICT")
    print("=" * 60)
    all_pass = all(results.values())
    for model, ok in results.items():
        status = "✅ PASS" if ok else "❌ NOT FOUND"
        print(f"  {model:20s} {status}")

    if all_pass:
        print("\n  🎉 All models trained and passing validation targets!")
    else:
        missing = [k for k, v in results.items() if not v]
        print(f"\n  ⚠  Missing models: {', '.join(missing)}")
        print("  Run the corresponding training scripts first.")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
