from __future__ import annotations

import backend.telegram_notifier as notifier


class FakeBot:
    sent: list[tuple[str, str]] = []

    def __init__(self, token: str):
        self.token = token

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def send_message(self, chat_id: str, text: str):
        self.sent.append((chat_id, text))


def test_send_telegram_message(monkeypatch):
    monkeypatch.setattr(notifier, "TELEGRAM_TOKEN", "123:test")
    monkeypatch.setattr(notifier, "CHAT_ID", "123456")
    monkeypatch.setattr(notifier, "Bot", FakeBot)

    assert notifier.send_telegram_message("teste") is True
    assert FakeBot.sent[-1] == ("123456", "teste")
