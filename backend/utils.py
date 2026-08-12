"""Formatting and date helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

try:
    from .config import TIMEZONE
except ImportError:
    from config import TIMEZONE


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def local_datetime(value: str | None = None) -> datetime:
    if value:
        dt = datetime.fromisoformat(value)
    else:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(TIMEZONE))


def format_brl(value: float) -> str:
    formatted = f"{value:,.2f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")
