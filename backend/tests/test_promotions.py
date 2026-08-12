from __future__ import annotations

from datetime import datetime, timezone

import backend.promotions as promotions
from backend.models import Product, PromotionSource


def test_public_telegram_preview_extracts_offer(monkeypatch):
    html = f"""
    <div class="tgme_widget_message_wrap">
      <div class="tgme_widget_message_text">
        <strong>PlayStation 5 Slim Digital 1TB</strong>
        por R$ 3.099,00 no Pix ou 10x de R$ 329,90.
        Use o cupom PS5OFF para 5% de desconto.
      </div>
      <a class="tgme_widget_message_date" href="https://t.me/canal/1">
        <time datetime="{datetime.now(timezone.utc).isoformat()}"></time>
      </a>
    </div>
    """
    monkeypatch.setattr(promotions, "fetch_requests", lambda _url: html)

    source = PromotionSource(
        name="Canal público",
        source_type="telegram_public",
        url="https://t.me/s/canal",
        active=True,
    )
    product = Product(
        id=1,
        name="PlayStation 5 Slim Digital",
        search_query="PS5 Slim Digital",
        target_price=3100,
        active=True,
    )

    hits = promotions.scan_promotion_source(source, [product], None)
    assert len(hits) == 1
    assert hits[0].price == 3099.0
    assert hits[0].installment_count == 10
    assert hits[0].coupon == "PS5OFF"
    assert hits[0].url == "https://t.me/canal/1"


def test_public_telegram_prefers_external_offer_link(monkeypatch):
    html = """
    <div class="tgme_widget_message_wrap">
      <div class="tgme_widget_message_text">
        PS5 Slim Digital por R$ 2.999,00 no PIX. Cupom: GAME100
        <a href="https://loja.example.com/ps5-slim">Comprar agora</a>
      </div>
      <a class="tgme_widget_message_date" href="https://t.me/promocoes/123">Post</a>
    </div>
    """
    monkeypatch.setattr("backend.promotions.fetch_requests", lambda _url: html)
    product = Product(
        id=1,
        name="PlayStation 5 Slim Digital",
        search_query="PS5 Slim Digital",
        target_price=3100,
        active=True,
    )
    source = PromotionSource(
        id=1,
        name="Canal público",
        url="https://t.me/s/promocoes",
        source_type="telegram_public",
        product_id=1,
        store_id=None,
        keywords="PS5",
        active=True,
    )

    hits = promotions.scan_promotion_source(source, [product], None)

    assert len(hits) == 1
    assert hits[0].url == "https://loja.example.com/ps5-slim"
