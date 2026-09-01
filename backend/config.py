"""
SatQuery AI — Configuration
"""
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+psycopg://localhost/satquery"
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
