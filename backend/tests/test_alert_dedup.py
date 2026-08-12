from __future__ import annotations

from backend.monitor import _record_and_send_alert
from backend.scraper import ScrapedOffer


def test_offer_alert_is_not_repeated(monkeypatch, db_session):
    monkeypatch.setattr("backend.monitor.send_telegram_message", lambda *_args, **_kwargs: True)
    offer = ScrapedOffer(
        store="Loja Teste",
        product="PlayStation 5 Slim Digital",
        title="PlayStation 5 Slim Digital 1TB",
        price=3099.0,
        cash_price=3099.0,
        installment_price=329.9,
        installment_count=10,
        coupon="PS5OFF",
        coupon_discount="5%",
        url="https://example.com/ps5",
    )
    assert _record_and_send_alert(db_session, offer, 3100, "best_offer") is True
    assert _record_and_send_alert(db_session, offer, 3100, "best_offer") is False
