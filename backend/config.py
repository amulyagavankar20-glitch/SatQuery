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
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    DATABASE_URL: str | None = None
    DATABASE_REPLICA_URL: str | None = None
    DB_POOL_SIZE: int
    DB_MAX_OVERFLOW: int
    DB_POOL_TIMEOUT: int
    DB_ECHO: bool

    # Security & JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # Environment & Logging
    ENVIRONMENT: str
    LOG_LEVEL: str

    # Geospatial Settings
    DEFAULT_SRID: int

    # Storage Settings (Programmatic Root & Relative Paths)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: str
    JOB_STORAGE_PATH: str
    WEIGHTS_DIR: str

    # Vision-Language Model (VLM) via OpenRouter API (Server-side)
    VLM_PROVIDER: str
    VLM_MODEL: str
    VLM_COST_SAFETY_ENFORCE_FREE: bool
    OPENROUTER_API_KEY: str | None = None
    QWEN_API_KEY: str | None = None  # Alias support if configured as QWEN_API_KEY in .env
    QWEN_VL_MODEL: str | None = None  # Legacy alias
    OPENROUTER_BASE_URL: str
    OPENROUTER_TIMEOUT_SECONDS: float

    # Model Slotting & Weights Architecture
    ROUTER_BACKEND: str
    ROUTER_WEIGHTS_PATH: str | None = None
    TALKING_VLM_MODEL: str | None = None
    TALKING_VLM_BACKEND: str
    TALKING_VLM_WEIGHTS_PATH: str | None = None
    BIT_WEIGHTS_PATH: str | None = None
    FUSION_WEIGHTS_PATH: str | None = None
    # Optional flood head (Prithvi-EO Sen1Floods11).
    PRITHVI_FLOOD_WEIGHTS_PATH: str | None = None
    # Optional reBEN ResNet50 (12-band S2).
    BIGEARTHNET_WEIGHTS_PATH: str | None = None

    # Sentinel-1 reBEN ResNet50 (BigEarthNet v2)
    BEN_S1_WEIGHTS_PATH: str | None = None

    # CORS
    CORS_ORIGINS: str

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
