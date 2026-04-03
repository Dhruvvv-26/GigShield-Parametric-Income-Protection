"""
GigShield ML Service — FastAPI Application
=============================================
Port 8006. Serves premium pricing, fraud scoring, and disruption prediction.
Loads trained models at startup; falls back to rule-based if models missing.
"""
import logging
import os
import sys
from contextlib import asynccontextmanager

import joblib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("ml_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

MODEL_DIR = os.environ.get("MODEL_DIR", "/app/models")

# Global model containers — populated at startup
models = {
    "premium_xgb": None,
    "premium_lgb": None,
    "shap_explainer": None,
    "premium_meta": None,
    "iso_forest": None,
    "gb_fraud": None,
    "fraud_scaler": None,
    "fraud_meta": None,
    "lstm_model": None,
    "lstm_scaler": None,
    "lstm_meta": None,
}


def load_models():
    """Load all trained models. Missing models log a warning but don't crash."""
    pkl_files = {
        "premium_xgb": "premium_xgb.pkl",
        "premium_lgb": "premium_lgb.pkl",
        "shap_explainer": "shap_explainer.pkl",
        "premium_meta": "premium_meta.pkl",
        "iso_forest": "iso_forest.pkl",
        "gb_fraud": "gb_fraud.pkl",
        "fraud_scaler": "fraud_scaler.pkl",
        "fraud_meta": "fraud_meta.pkl",
        "lstm_scaler": "lstm_scaler.pkl",
        "lstm_meta": "lstm_meta.pkl",
    }

    for key, filename in pkl_files.items():
        path = os.path.join(MODEL_DIR, filename)
        if os.path.exists(path):
            try:
                models[key] = joblib.load(path)
                logger.info(f"Loaded model: {filename}")
            except Exception as e:
                logger.warning(f"Failed to load {filename}: {e}")
        else:
            logger.warning(f"Model file not found: {path} — using fallback")

    # Load PyTorch LSTM separately
    lstm_path = os.path.join(MODEL_DIR, "lstm_disruption.pt")
    if os.path.exists(lstm_path) and models["lstm_meta"] is not None:
        try:
            import torch
            import torch.nn as nn

            meta = models["lstm_meta"]

            class GigShieldLSTM(nn.Module):
                def __init__(self, input_size=9, hidden_size=64, num_layers=2, dropout=0.2):
                    super().__init__()
                    self.lstm = nn.LSTM(input_size=input_size, hidden_size=hidden_size,
                                       num_layers=num_layers, dropout=dropout, batch_first=True)
                    self.dropout = nn.Dropout(dropout)
                    self.fc1 = nn.Linear(hidden_size, 32)
                    self.relu = nn.ReLU()
                    self.fc2 = nn.Linear(32, 1)
                    self.sigmoid = nn.Sigmoid()

                def forward(self, x):
                    lstm_out, _ = self.lstm(x)
                    last = lstm_out[:, -1, :]
                    out = self.dropout(last)
                    out = self.fc1(out)
                    out = self.relu(out)
                    out = self.fc2(out)
                    return self.sigmoid(out).squeeze(-1)

            model = GigShieldLSTM(
                input_size=meta.get("input_size", 9),
                hidden_size=meta.get("hidden_size", 64),
                num_layers=meta.get("num_layers", 2),
                dropout=meta.get("dropout", 0.2),
            )
            model.load_state_dict(torch.load(lstm_path, map_location="cpu", weights_only=True))
            model.eval()
            models["lstm_model"] = model
            logger.info(f"Loaded LSTM model: lstm_disruption.pt")
        except Exception as e:
            logger.warning(f"Failed to load LSTM model: {e}")
    else:
        logger.warning("LSTM model file not found — prediction endpoint will return fallback")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_models()
    loaded = sum(1 for v in models.values() if v is not None)
    logger.info(f"ML Service started — {loaded}/{len(models)} models loaded")
    yield
    logger.info("ML Service shutting down")


app = FastAPI(
    title="GigShield ML Service",
    version="1.0.0",
    description="Premium pricing, fraud scoring, and disruption prediction",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and register routes
from routes.premium import router as premium_router
from routes.fraud import router as fraud_router
from routes.prediction import router as prediction_router

app.include_router(premium_router, prefix="/api/v1/premium", tags=["Premium"])
app.include_router(fraud_router, prefix="/api/v1/fraud", tags=["Fraud"])
app.include_router(prediction_router, prefix="/api/v1/predict", tags=["Prediction"])


@app.get("/health")
async def health():
    loaded = sum(1 for v in models.values() if v is not None)
    return {
        "status": "healthy",
        "service": "ml-service",
        "models_loaded": loaded,
        "models_total": len(models),
        "premium_ready": models["premium_xgb"] is not None,
        "fraud_ready": models["gb_fraud"] is not None,
        "lstm_ready": models["lstm_model"] is not None,
    }
