from __future__ import annotations

from backend.scraper import STORES, _extract_offers, _matches_product, _parse_price


def test_parse_brazilian_prices():
    assert _parse_price("R$ 3.499,00 à vista") == 3499.0
    assert _parse_price("R$4.742 no Pix") == 4742.0
    assert _parse_price("10x de R$ 349,90") is None


def test_product_variant_filter():
    digital = "PlayStation 5 Slim Digital"
    disk = "PlayStation 5 Slim com Leitor de Disco"

    assert _matches_product("Console PlayStation 5 Slim Digital 1TB", digital)
    assert not _matches_product("Console PlayStation 5 Slim com Leitor", digital)
    assert _matches_product("Console PlayStation 5 Slim com Leitor 1TB", disk)
    assert not _matches_product("Console PlayStation 5 Slim Digital 1TB", disk)
    assert not _matches_product("Controle para PlayStation 5 Slim", disk)


def test_extract_json_ld_offer():
    html = """
    <html><head>
      <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Console PlayStation 5 Slim Digital 1TB",
          "url": "/produto/ps5",
          "offers": {"@type": "Offer", "price": "3099.90"}
        }
      </script>
    </head></html>
    """
    offers = _extract_offers(html, STORES[0], "PlayStation 5 Slim Digital")
    assert len(offers) == 1
    assert offers[0].price == 3099.90
    assert offers[0].url.endswith("/produto/ps5")


def test_parse_payment_and_coupon_details():
    from backend.scraper import _parse_payment_details

    text = (
        "R$ 3.299,00 no Pix ou em até 10x de R$ 349,90. "
        "Use o cupom GAME200 para 5% de desconto."
    )
    cash, installment, count, coupon, discount = _parse_payment_details(text)
    assert cash == 3299.0
    assert installment == 349.9
    assert count == 10
    assert coupon == "GAME200"
    assert discount == "5%"


def test_coupon_details_include_conditions_and_avoid_false_positives():
    from backend.scraper import _parse_coupon_details

    details = _parse_coupon_details(
        "Aplique o cupom `GAME-200` e ganhe R$ 200 OFF em compras acima de "
        "R$ 3.000,00. Exclusivo no app, válido até 10/08/2026."
    )
    assert details.code == "GAME-200"
    assert details.discount == "R$ 200"
    assert details.confidence >= 0.9
    assert details.conditions == (
        "Compra mínima: R$ 3.000,00; Validade: 10/08/2026; Exclusivo no app"
    )

    assert _parse_coupon_details("Aproveite esta oferta com desconto aplicado").code is None
