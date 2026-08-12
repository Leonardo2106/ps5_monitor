"""Telegram notification integration with optional offer button."""

from __future__ import annotations

import asyncio
import logging
from html import escape

import requests

try:
    from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.error import TelegramError
except ImportError:
    Bot = None  # type: ignore[assignment]
    InlineKeyboardButton = None  # type: ignore[assignment]
    InlineKeyboardMarkup = None  # type: ignore[assignment]

    class TelegramError(Exception):
        pass

try:
    from .config import CHAT_ID, TELEGRAM_TOKEN
except ImportError:
    from config import CHAT_ID, TELEGRAM_TOKEN

logger = logging.getLogger(__name__)


def telegram_is_configured() -> bool:
    return bool(
        TELEGRAM_TOKEN
        and CHAT_ID
        and TELEGRAM_TOKEN != "SEU_TOKEN"
        and CHAT_ID != "SEU_CHAT_ID"
    )


async def _send_with_library(message: str, url: str | None) -> None:
    if Bot is None:
        raise ImportError("python-telegram-bot não está instalado")
    reply_markup = None
    if url and InlineKeyboardButton and InlineKeyboardMarkup:
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🛒 Abrir oferta", url=url)]]
        )
    bot = Bot(token=TELEGRAM_TOKEN)
    async with bot:
        try:
            await bot.send_message(
                chat_id=CHAT_ID,
                text=message,
                parse_mode="HTML",
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
        except TypeError:
            # Keeps lightweight test doubles and older compatible clients working.
            await bot.send_message(chat_id=CHAT_ID, text=message)


def _send_with_requests(message: str, url: str | None) -> None:
    payload: dict[str, object] = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if url:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "🛒 Abrir oferta", "url": url}]]
        }
    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    body = response.json()
    if not body.get("ok"):
        raise TelegramError(str(body))


def send_telegram_message(message: str, url: str | None = None) -> bool:
    """Send an HTML Telegram message synchronously from the monitor thread."""
    if not telegram_is_configured():
        logger.warning("Telegram não configurado; mensagem não enviada.")
        return False

    try:
        if Bot is not None:
            asyncio.run(_send_with_library(message, url))
        else:
            logger.warning("Biblioteca Telegram indisponível; usando fallback HTTP.")
            _send_with_requests(message, url)
        logger.info("Mensagem enviada ao Telegram.")
        return True
    except (TelegramError, requests.RequestException, RuntimeError, OSError) as exc:
        logger.exception("Falha ao enviar mensagem ao Telegram: %s", exc)
        return False


def safe_html(value: str | None) -> str:
    return escape(value or "—")
