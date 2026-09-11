"""
SatQuery AI — Configuration Schema & Programmatic Properties
"""

from pathlib import Path
from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings schema loaded from environment variables and .env file.

    Contains NO concrete environment-specific defaults. All concrete configuration
    values must be supplied via .env or the deployment environment.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database Configuration
    POSTGRES_USER: str = "satquery"
    POSTGRES_PASSWORD: str = "satquery"
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "satquery"
    DATABASE_URL: str | None = None
    DATABASE_REPLICA_URL: str | None = None
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    # Security & JWT
    JWT_SECRET_KEY: str = "dev-secret-key-satquery-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Redis & Celery
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_BROKER_URL: str = "redis://127.0.0.1:6379/0"

    # Vector DB (Qdrant)
    QDRANT_HOST: str = "127.0.0.1"
    QDRANT_PORT: int = 6333

    # Environment & Logging
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Geospatial Settings
    DEFAULT_SRID: int = 4326

    # Storage Settings (Programmatic Root & Relative Paths)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: str = "data"
    JOB_STORAGE_PATH: str = "data/jobs"
    WEIGHTS_DIR: str = "weights"

    # Vision-Language Model (VLM) via OpenRouter API (Server-side)
    VLM_PROVIDER: str = "openrouter"
    VLM_MODEL: str = "qwen/qwen-2.5-72b-instruct:free"
    VLM_COST_SAFETY_ENFORCE_FREE: bool = True
    OPENROUTER_API_KEY: str | None = None
    QWEN_API_KEY: str | None = None  # Alias support if configured as QWEN_API_KEY in .env
    QWEN_VL_MODEL: str | None = None  # Legacy alias
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_TIMEOUT_SECONDS: float = 60.0

    # Legacy/Fallback Qwen Router via Ollama (retained for backward compatibility)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_ROUTER_MODEL: str | None = "qwen2.5:3b-instruct"
    OLLAMA_TIMEOUT_SECONDS: float = 180.0

    # Model Slotting & Weights Architecture (3 Slots: Router, Talking VLM, Specialists)
    ROUTER_BACKEND: str = "ollama"
    ROUTER_WEIGHTS_PATH: str | None = None
    TALKING_VLM_MODEL: str | None = "OpenGVLab/InternVL3-1B"
    TALKING_VLM_BACKEND: str = "mock"
    TALKING_VLM_WEIGHTS_PATH: str | None = None
    # Local specialist checkpoints.  Their loaders are isolated under
    # backend.inference and are never fetched or run remotely by default.
    GEOGROUND_MODEL_PATH: str | None = None
    BIT_CHECKPOINT_PATH: str | None = None
    BIT_ROOT: str | None = None
    BIT_PROJECT_NAME: str = "BIT_LEVIR"
    BIT_CHECKPOINT_NAME: str = "best_ckpt.pt"
    BIT_IMAGE_SIZE: int = 256
    # Values from the final mask-cleanup cell in models/BIT.ipynb.
    BIT_CLOSE_KERNEL_SIZE: int = 7
    BIT_OPEN_KERNEL_SIZE: int = 3
    BIT_MIN_REGION_AREA: int = 200
    BIT_WEIGHTS_PATH: str | None = None
    SAM_WEIGHTS_PATH: str | None = None
    FUSION_WEIGHTS_PATH: str | None = None
    # Optional flood head (Prithvi-EO Sen1Floods11). Leave unset to keep the
    # default land-cover path at Dynamic World / spectral (~no extra RAM).
    PRITHVI_FLOOD_WEIGHTS_PATH: str | None = None
    # Optional reBEN ResNet50 (12-band S2). Leave unset: BEN-19 tags come from
    # the Dynamic World / spectral fractions (taxonomy only, no extra download).
    BIGEARTHNET_WEIGHTS_PATH: str | None = None

    # Sentinel-1 reBEN ResNet50 (BigEarthNet v2)
    BEN_S1_WEIGHTS_PATH: str | None = None

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def assemble_database_url(self) -> "Settings":
        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
        base_url = f"postgresql+psycopg://{user}:{password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

        if not self.DATABASE_URL:
            self.DATABASE_URL = base_url
        if not self.DATABASE_REPLICA_URL:
            # Fallback to primary for replica if not explicitly set
            self.DATABASE_REPLICA_URL = self.DATABASE_URL

        if not self.JWT_SECRET_KEY or not self.JWT_SECRET_KEY.strip():
            raise ValueError("JWT_SECRET_KEY must be configured in environment or .env file.")

        if not self.OPENROUTER_API_KEY and self.QWEN_API_KEY:
            self.OPENROUTER_API_KEY = self.QWEN_API_KEY

        if not self.VLM_MODEL and self.QWEN_VL_MODEL:
            self.VLM_MODEL = self.QWEN_VL_MODEL

        return self

    @property
    def full_data_dir(self) -> Path:
        """Return the absolute path to the root data directory."""
        path = Path(self.DATA_DIR)
        return path if path.is_absolute() else self.BASE_DIR / path

    @property
    def full_job_storage_dir(self) -> Path:
        """Return the absolute path to the job storage directory."""
        path = Path(self.JOB_STORAGE_PATH)
        return path if path.is_absolute() else self.BASE_DIR / path

    @property
    def full_weights_dir(self) -> Path:
        """Return the absolute path to the weights directory."""
        path = Path(self.WEIGHTS_DIR)
        return path if path.is_absolute() else self.BASE_DIR / path


settings = Settings()
