"""
GigShield — Shared Configuration
Loaded via pydantic-settings from environment variables.
All services import from this module.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ───────────────────────────────────────────────
    env: str = "development"
    log_level: str = "INFO"
    service_name: str = "gigshield"
    service_port: int = 8000

    # ── Database ──────────────────────────────────────────
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "gigshield"
    db_user: str = "gigshield"
    db_password: str = "gigshield_secure_2026"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # ── Redis ──────────────────────────────────────────────
    redis_url: str = "redis://:redis_secure_2026@localhost:6379/0"
    redis_cache_ttl_seconds: int = 600  # 10 minutes

    # ── Redpanda / Kafka ───────────────────────────────────
    redpanda_brokers: str = "localhost:9092"

    # Kafka Topics
    topic_raw_external_events: str = "raw.external.events"
    topic_raw_worker_location: str = "raw.worker.location"
    topic_processed_trigger_events: str = "processed.trigger.events"
    topic_processed_fraud_signals: str = "processed.fraud.signals"
    topic_claims_approved: str = "claims.approved"
    topic_claims_soft_hold: str = "claims.soft_hold"
    topic_claims_blocked: str = "claims.blocked"
    topic_payments_initiated: str = "payments.initiated"
    topic_payments_completed: str = "payments.completed"

    # ── JWT ────────────────────────────────────────────────
    jwt_secret_key: str = "change_me_in_production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # ── External APIs ──────────────────────────────────────
    owm_api_key: str = "demo_key"
    owm_base_url: str = "https://api.openweathermap.org/data/2.5"
    cpcb_api_key: str = "demo_key"
    cpcb_base_url: str = "https://api.data.gov.in/resource"

    # WAQI (World Air Quality Index) — AQI from CPCB sensors
    waqi_api_key: str = ""

    # WeatherAPI.com — Severe weather alerts (IMD Red Alerts)
    weatherapi_key: str = ""

    # IPinfo.io — Server-side IP geolocation for fraud detection
    ipinfo_token: str = ""

    # OneSignal — Push notifications to riders
    onesignal_app_id: str = ""
    onesignal_rest_key: str = ""

    # Supabase — Worker app authentication (Phone OTP)
    supabase_url: str = ""
    supabase_anon_key: str = ""

    # Trigger Engine
    trigger_poll_interval_minutes: int = 15
    policy_service_url: str = "http://localhost:8002"
    claims_service_url: str = "http://localhost:8004"
    payment_service_url: str = "http://localhost:8005"
    # notification_service_url removed — FCM now wired directly into Payment Service
    worker_service_url: str = "http://localhost:8001"

    # ── Razorpay (test mode by default) ────────────────────────
    razorpay_key_id: str = "demo_key"
    razorpay_key_secret: str = "demo_secret"
    razorpay_account_number: str = "2323230085726431"
    razorpay_webhook_secret: str = "change_me"

    # ── Firebase (FCM push notifications) ──────────────────────
    firebase_credentials: str = ""  # Path to service account JSON
    firebase_service_account_path: str = ""  # Alt env var for Docker
    fcm_dispatch_enabled: bool = True  # Set false for local dev without Firebase

    # ── Cyclone Trigger thresholds ─────────────────────────────
    cyclone_tier1_threshold_kmh: float = 55.0
    cyclone_tier2_threshold_kmh: float = 80.0
    cyclone_tier3_threshold_kmh: float = 110.0
    cyclone_tier1_payout: int = 250
    cyclone_tier2_payout: int = 450
    cyclone_tier3_payout: int = 750

    # ── Curfew Trigger thresholds (mocked for Phase 2) ────────
    curfew_tier1_payout: int = 200
    curfew_tier2_payout: int = 400
    curfew_tier3_payout: int = 700

    # ── GigShield Business Rules ───────────────────────────
    # Cities covered in Phase 1
    covered_cities: list[str] = [
        "delhi_ncr",
        "mumbai",
        "bengaluru",
        "hyderabad",
        "pune",
        "kolkata",
    ]

    # AQI Trigger thresholds (Tier 1 / 2 / 3)
    aqi_tier1_threshold: int = 300
    aqi_tier2_threshold: int = 400
    aqi_tier3_threshold: int = 500
    aqi_tier1_payout: int = 150
    aqi_tier2_payout: int = 300
    aqi_tier3_payout: int = 500
    aqi_tier1_duration_hours: int = 4
    aqi_tier2_duration_hours: int = 3

    # Rain Trigger thresholds
    rain_tier1_threshold_mm: float = 35.0
    rain_tier2_threshold_mm: float = 65.0
    rain_tier3_threshold_mm: float = 100.0
    rain_tier1_payout: int = 200
    rain_tier2_payout: int = 380
    rain_tier3_payout: int = 600
    rain_duration_hours: int = 2

    # Heat Trigger thresholds
    heat_tier1_threshold_celsius: float = 43.0
    heat_tier2_threshold_celsius: float = 45.0
    heat_tier3_threshold_celsius: float = 47.0
    heat_tier1_payout: int = 150
    heat_tier2_payout: int = 250
    heat_tier3_payout: int = 450

    # Premium Base Rate
    premium_base_rate: int = 25  # ₹25/week minimum


@lru_cache()
def get_settings() -> Settings:
    return Settings()
