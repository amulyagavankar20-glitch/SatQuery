"""
SatQuery AI — Configuration
"""

from pathlib import Path
from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database — prefer POSTGRES_* in .env; DATABASE_URL overrides if set.
    POSTGRES_USER: str = "satquery"
    POSTGRES_PASSWORD: str = "satquery"
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "satquery"
    DATABASE_URL: str | None = None
    DATABASE_REPLICA_URL: str | None = None
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    # Security & JWT
    JWT_SECRET_KEY: str = "your-super-secret-jwt-key"  # Change in production
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440 # 24 hours

    # Redis & Celery
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    CELERY_BROKER_URL: str = "redis://127.0.0.1:6379/1"

    # Vector DB (Qdrant)
    QDRANT_HOST: str = "127.0.0.1"
    QDRANT_PORT: int = 6333

    # Environment & Logging
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Geospatial Settings
    DEFAULT_SRID: int = 4326

    # Storage Settings
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: str = "data"
    JOB_STORAGE_PATH: str = "data/jobs"

    # Qwen2.5-3B-Instruct router via Ollama (architecture §1 / §6 / §14)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_ROUTER_MODEL: str = "qwen2.5:3b-instruct"
    OLLAMA_TIMEOUT_SECONDS: float = 180.0

    # Model Slotting & Weights Architecture (3 Slots: Router, Talking VLM, Specialists)
    WEIGHTS_DIR: str = "weights"
    ROUTER_BACKEND: str = "auto"  # auto | ollama | local | mock
    ROUTER_WEIGHTS_PATH: str | None = None
    TALKING_VLM_MODEL: str = "OpenGVLab/InternVL3-1B"
    TALKING_VLM_BACKEND: str = "auto"  # auto | local | mock
    TALKING_VLM_WEIGHTS_PATH: str | None = None
    BIT_WEIGHTS_PATH: str | None = None
    SAM_WEIGHTS_PATH: str | None = None
    FUSION_WEIGHTS_PATH: str | None = None

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
