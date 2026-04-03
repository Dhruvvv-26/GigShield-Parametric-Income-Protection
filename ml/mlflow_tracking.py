"""
KavachAI ML — MLflow Tracking Wrapper
========================================
Logs parameters, metrics, and model artifacts from all 3 training scripts.

Usage:
  python ml/mlflow_tracking.py
"""
import os
import sys

import joblib

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")


def log_experiment():
    """Log all trained model metrics to MLflow."""
    try:
        import mlflow
        import mlflow.sklearn
        import mlflow.pytorch
    except ImportError:
        print("MLflow not installed — skipping tracking")
        return

    mlflow.set_tracking_uri("file:///tmp/kavachai_mlruns")
    mlflow.set_experiment("KavachAI-Models")

    # ── Premium Model ─────────────────────────────────────────────────────
    meta_path = os.path.join(MODEL_DIR, "premium_meta.pkl")
    if os.path.exists(meta_path):
        meta = joblib.load(meta_path)
        with mlflow.start_run(run_name="premium_xgb_lgb_v1"):
            mlflow.log_params({
                "model_type": "XGBoost+LightGBM Ensemble",
                "n_features": meta["n_features"],
                "n_train": meta["n_train"],
                "xgb_estimators": 300,
                "xgb_depth": 6,
                "xgb_lr": 0.05,
                "lgb_estimators": 300,
                "lgb_leaves": 63,
                "ensemble_weights": "60% XGB + 40% LGB",
            })
            mlflow.log_metrics({
                "r2_score": meta["r2"],
                "mae": meta["mae"],
                "rmse": meta["rmse"],
            })
            xgb_path = os.path.join(MODEL_DIR, "premium_xgb.pkl")
            lgb_path = os.path.join(MODEL_DIR, "premium_lgb.pkl")
            if os.path.exists(xgb_path):
                mlflow.log_artifact(xgb_path, "models")
            if os.path.exists(lgb_path):
                mlflow.log_artifact(lgb_path, "models")
            print(f"✅ Premium model logged: R²={meta['r2']:.4f}, MAE=₹{meta['mae']:.2f}")

    # ── Fraud Model ───────────────────────────────────────────────────────
    meta_path = os.path.join(MODEL_DIR, "fraud_meta.pkl")
    if os.path.exists(meta_path):
        meta = joblib.load(meta_path)
        with mlflow.start_run(run_name="fraud_isoforest_gb_v1"):
            mlflow.log_params({
                "model_type": "IsolationForest + GradientBoosting",
                "iso_estimators": 200,
                "iso_contamination": 0.15,
                "gb_estimators": 200,
                "gb_depth": 5,
                "gb_lr": 0.05,
                "ensemble_weights": "40% ISO + 60% GB",
                "n_features": len(meta["feature_columns"]),
            })
            mlflow.log_metrics({
                "auc_roc": meta["auc"],
                "false_positive_rate": meta["fpr"],
                "precision": meta["precision"],
                "recall": meta["recall"],
            })
            iso_path = os.path.join(MODEL_DIR, "iso_forest.pkl")
            gb_path = os.path.join(MODEL_DIR, "gb_fraud.pkl")
            if os.path.exists(iso_path):
                mlflow.log_artifact(iso_path, "models")
            if os.path.exists(gb_path):
                mlflow.log_artifact(gb_path, "models")
            print(f"✅ Fraud model logged: AUC={meta['auc']:.4f}, FPR={meta['fpr']:.4f}")

    # ── LSTM Model ────────────────────────────────────────────────────────
    meta_path = os.path.join(MODEL_DIR, "lstm_meta.pkl")
    if os.path.exists(meta_path):
        meta = joblib.load(meta_path)
        with mlflow.start_run(run_name="lstm_disruption_v1"):
            mlflow.log_params({
                "model_type": "PyTorch LSTM",
                "input_size": meta["input_size"],
                "hidden_size": meta["hidden_size"],
                "num_layers": meta["num_layers"],
                "dropout": meta["dropout"],
                "sequence_length": meta["sequence_length"],
                "prediction_horizon": meta["prediction_horizon"],
                "optimizer": "Adam",
                "lr": 0.001,
                "scheduler": "ReduceLROnPlateau",
            })
            mlflow.log_metrics({
                "test_auc": meta["test_auc"],
                "best_val_auc": meta["best_val_auc"],
            })
            lstm_path = os.path.join(MODEL_DIR, "lstm_disruption.pt")
            if os.path.exists(lstm_path):
                mlflow.log_artifact(lstm_path, "models")
            print(f"✅ LSTM model logged: Test AUC={meta['test_auc']:.4f}")

    print("\n🎉 All models logged to MLflow!")
    print(f"   Tracking URI: file:///tmp/kavachai_mlruns")
    print(f"   Run `mlflow ui --backend-store-uri file:///tmp/kavachai_mlruns` to view")


if __name__ == "__main__":
    log_experiment()
