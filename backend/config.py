"""Application configuration loaded from environment variables and .env."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

BASE_DIR: Final[Path] = Path(__file__).resolve().parent
PROJECT_DIR: Final[Path] = BASE_DIR.parent
ENV_FILE: Final[Path] = PROJECT_DIR / ".env"


def _load_env_file(path: Path) -> None:
    """Load a simple KEY=VALUE .env file without adding another dependency."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_env_file(ENV_FILE)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "SEU_CHAT_ID")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "1800"))
DIGITAL_TARGET = float(os.getenv("DIGITAL_TARGET", "3100"))
DISK_TARGET = float(os.getenv("DISK_TARGET", "3500"))

_database_path = Path(os.getenv("DATABASE_PATH", "ps5_prices.db"))
DATABASE_PATH = (
    _database_path if _database_path.is_absolute() else PROJECT_DIR / _database_path
).resolve()
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

_log_file = Path(os.getenv("LOG_FILE", "backend/monitor.log"))
LOG_FILE = (_log_file if _log_file.is_absolute() else PROJECT_DIR / _log_file).resolve()
TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))
PLAYWRIGHT_TIMEOUT = int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000"))
START_MONITOR_WITH_API = os.getenv("START_MONITOR_WITH_API", "true").lower() == "true"
RUN_ON_STARTUP = os.getenv("RUN_ON_STARTUP", "true").lower() == "true"
HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "43200"))

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

USER_AGENT = os.getenv(
    "USER_AGENT",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
)
