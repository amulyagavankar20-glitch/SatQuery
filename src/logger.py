import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

logs_dir = Path(os.getcwd()) / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
log_file_path = logs_dir / "satquery.log"

logger = logging.getLogger("satquery")
logger.setLevel(logging.INFO)

# Avoid duplicate handlers if imported multiple times
if not logger.handlers:
    formatter = logging.Formatter("[%(asctime)s] %(lineno)d %(name)s - %(levelname)s - %(message)s")

    # Rotating file handler (10 MB max, 3 backups)
    file_handler = RotatingFileHandler(
        str(log_file_path),
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    # Console stream handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

# Configure root logger as well for standard logging.info() calls
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(lineno)d %(name)s - %(levelname)s - %(message)s",
    handlers=[file_handler, console_handler],
    force=True,
)

if __name__ == "__main__":
    logger.info("SatQuery logging initialized.")