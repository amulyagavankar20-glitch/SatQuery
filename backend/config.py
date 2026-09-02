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
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

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

    TALKING_VLM_MODEL: str = "OpenGVLab/InternVL3-1B"
    TALKING_VLM_BACKEND: str = "mock"

    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def assemble_database_url(self) -> "Settings":
        if self.DATABASE_URL:
            return self
        user = quote_plus(self.POSTGRES_USER)
        password = quote_plus(self.POSTGRES_PASSWORD)
        self.DATABASE_URL = (
            f"postgresql+psycopg://{user}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
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


settings = Settings()
