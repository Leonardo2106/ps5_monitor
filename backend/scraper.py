"""Retail scraper with configurable stores and Playwright fallback."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Any, Iterable
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup, Tag
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

try:
    from .config import HEADLESS, PLAYWRIGHT_TIMEOUT, REQUEST_TIMEOUT, USER_AGENT
except ImportError:
    from config import HEADLESS, PLAYWRIGHT_TIMEOUT, REQUEST_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)

BRL_PATTERN = re.compile(r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})", re.I)
WHOLE_BRL_PATTERN = re.compile(
    r"R\$\s*([1-9][0-9]{0,2}(?:\.[0-9]{3})+|[1-9][0-9]{3,4})(?![0-9,])",
    re.I,
)
PLAIN_PRICE_PATTERN = re.compile(r"(?<!\d)([1-9][0-9]{3,4})[,.]([0-9]{2})(?!\d)")
PLAIN_THOUSANDS_PATTERN = re.compile(
    r"(?<![0-9])([1-9][0-9]{0,2}(?:\.[0-9]{3})+)(?![0-9,])"
)
INSTALLMENT_PATTERN = re.compile(
    r"(?:em\s+at[eé]\s+)?(?P<count>\d{1,2})\s*x\s*(?:de\s*)?"
    r"R\$\s*(?P<value>[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})",
    re.I,
)
CASH_PATTERNS = (
    re.compile(
        r"R\$\s*(?P<value>[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})"
        r"[^\n]{0,45}?(?:[àa]\s*vista|no\s+pix|via\s+pix|pix|boleto)",
        re.I,
    ),
    re.compile(
        r"(?:[àa]\s*vista|no\s+pix|via\s+pix|pix|boleto)[^\n]{0,45}?"
        r"R\$\s*(?P<value>[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})",
        re.I,
    ),
)
COUPON_CODE_PATTERNS = (
    re.compile(
        r"(?:cupom|c[oó]digo(?:\s+promocional)?|voucher|promo\s*code)"
        r"(?:\s+de\s+desconto)?\s*(?:[ée]\s*)?[:=\-]?\s*[`'\"*]*"
        r"(?P<code>[A-Z0-9][A-Z0-9_-]{2,30})",
        re.I,
    ),
    re.compile(
        r"(?:use|utilize|aplique|insira|digite)\s+(?:o\s+)?"
        r"(?:(?:cupom|c[oó]digo)\s*)?[:=\-]?\s*[`'\"*]*"
        r"(?P<code>[A-Z0-9][A-Z0-9_-]{2,30})",
        re.I,
    ),
)
DISCOUNT_PATTERN = re.compile(
    r"(?P<discount>\d{1,2}(?:[.,]\d+)?\s*%)\s*(?:(?:de\s+)?desconto|off)?"
    r"|(?P<cash_discount>R\$\s*\d+(?:[.,]\d{1,2})?)\s*(?:(?:de\s+)?desconto|off)",
    re.I,
)
COUPON_MINIMUM_PATTERN = re.compile(
    r"(?:compras?|pedidos?|valor)\s*(?:a\s+partir|acima|m[ií]nim[oa])\s*(?:de)?\s*"
    r"(?P<minimum>R\$\s*\d+(?:\.\d{3})*(?:,\d{2})?)",
    re.I,
)
COUPON_VALIDITY_PATTERN = re.compile(
    r"(?:v[aá]lid[oa]|validade|expira|at[eé])\s*(?:at[eé]|em|:)?\s*"
    r"(?P<validity>\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|\d{1,2}h\d{0,2})",
    re.I,
)
BLOCK_MARKERS = (
    "captcha",
    "access denied",
    "robot check",
    "verifique se você é humano",
    "verifique se voce e humano",
)
GENERIC_CARD_SELECTORS = (
    "[data-testid*='product']",
    "[class*='product-card']",
    "[class*='productCard']",
    "[class*='product-summary']",
    "article",
    "li",
)
GENERIC_TITLE_SELECTORS = (
    "[data-testid*='title']",
    "[class*='productName']",
    "[class*='product-name']",
    "[class*='title']",
    "h2",
    "h3",
)
GENERIC_PRICE_SELECTORS = (
    "[data-testid*='price']",
    "[class*='sellingPrice']",
    "[class*='price']",
    ".price",
)
GENERIC_LINK_SELECTORS = ("a[href]",)
STOPWORDS = {
    "de",
    "da",
    "do",
    "com",
    "para",
    "e",
    "o",
    "a",
    "em",
    "the",
    "of",
    "console",
    "produto",
}


@dataclass(frozen=True, slots=True)
class StoreConfig:
    id: int | None
    name: str
    base_url: str
    search_url: str
    card_selectors: tuple[str, ...]
    title_selectors: tuple[str, ...]
    price_selectors: tuple[str, ...]
    link_selectors: tuple[str, ...]
    cash_selectors: tuple[str, ...] = ()
    installment_selectors: tuple[str, ...] = ()
    coupon_selectors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScrapedOffer:
    store: str
    product: str
    title: str
    price: float
    url: str
    cash_price: float | None = None
    installment_price: float | None = None
    installment_count: int | None = None
    coupon: str | None = None
    coupon_discount: str | None = None
    coupon_conditions: str | None = None
    coupon_confidence: float | None = None
    source_type: str = "store"


@dataclass(frozen=True, slots=True)
class CouponDetails:
    code: str | None = None
    discount: str | None = None
    conditions: str | None = None
    confidence: float = 0.0


BUILTIN_STORES: tuple[StoreConfig, ...] = (
    StoreConfig(
        id=None,
        name="Amazon Brasil",
        base_url="https://www.amazon.com.br",
        search_url="https://www.amazon.com.br/s?k={query}",
        card_selectors=("[data-component-type='s-search-result']",),
        title_selectors=("h2 span", "h2"),
        price_selectors=(".a-price[data-a-size='xl'] > .a-offscreen", ".a-price:not([data-a-size='mini']) > .a-offscreen",),
        link_selectors=("h2 a", "a.a-link-normal"),
        cash_selectors=(".a-price[data-a-size='xl'] > .a-offscreen", ".a-price:not([data-a-size='mini']) > .a-offscreen",),
        installment_selectors=("[class*='installment']",),
        coupon_selectors=("[class*='coupon']", "[class*='badge']"),
    ),
    StoreConfig(
        id=None,
        name="Kabum",
        base_url="https://www.kabum.com.br",
        search_url="https://www.kabum.com.br/busca/{slug}",
        card_selectors=("article.productCard", "div.productCard", "article"),
        title_selectors=("span.nameCard", "h2", "h3"),
        price_selectors=("span.priceCard", "[data-testid='price']", ".price"),
        link_selectors=("a.productLink", "a"),
        cash_selectors=("span.priceCard", "[class*='pix']"),
        installment_selectors=("[class*='installment']", "[class*='parcel']"),
        coupon_selectors=("[class*='coupon']", "[class*='cupom']"),
    ),
    StoreConfig(
        id=None,
        name="Magazine Luiza",
        base_url="https://www.magazineluiza.com.br",
        search_url="https://www.magazineluiza.com.br/busca/{query}/",
        card_selectors=("[data-testid='product-card-container']", "li"),
        title_selectors=("[data-testid='product-title']", "h2", "h3"),
        price_selectors=("[data-testid='price-value']", "[data-testid='price-original']"),
        link_selectors=("a",),
        cash_selectors=("[data-testid='price-value']", "[class*='pix']"),
        installment_selectors=("[data-testid*='installment']", "[class*='installment']"),
        coupon_selectors=("[data-testid*='coupon']", "[class*='coupon']"),
    ),
    StoreConfig(
        id=None,
        name="Mercado Livre",
        base_url="https://lista.mercadolivre.com.br",
        search_url="https://lista.mercadolivre.com.br/{slug}",
        card_selectors=("li.ui-search-layout__item", ".ui-search-result", "article"),
        title_selectors=(".poly-component__title", ".ui-search-item__title", "h2"),
        price_selectors=(".andes-money-amount", ".andes-money-amount__fraction"),
        link_selectors=("a.poly-component__title", "a.ui-search-link", "a"),
        cash_selectors=(".andes-money-amount", "[class*='price']"),
        installment_selectors=("[class*='installment']",),
        coupon_selectors=("[class*='coupon']", "[class*='promotion']"),
    ),
    StoreConfig(
        id=None,
        name="Casas Bahia",
        base_url="https://www.casasbahia.com.br",
        search_url="https://www.casasbahia.com.br/{slug}/b",
        card_selectors=("[data-testid='product-card']", "article", "li"),
        title_selectors=("[data-testid='product-title']", "h2", "h3"),
        price_selectors=("[data-testid='product-price']", "[data-testid='price-value']", ".price"),
        link_selectors=("a",),
        cash_selectors=("[class*='pix']", "[data-testid='product-price']"),
        installment_selectors=("[class*='installment']", "[class*='parcel']"),
        coupon_selectors=("[class*='coupon']", "[class*='cupom']"),
    ),
    StoreConfig(
        id=None,
        name="Ponto",
        base_url="https://www.pontofrio.com.br",
        search_url="https://www.pontofrio.com.br/{slug}/b",
        card_selectors=("[data-testid='product-card']", "article", "li"),
        title_selectors=("[data-testid='product-title']", "h2", "h3"),
        price_selectors=("[data-testid='product-price']", "[data-testid='price-value']", ".price"),
        link_selectors=("a",),
        cash_selectors=("[class*='pix']", "[data-testid='product-price']"),
        installment_selectors=("[class*='installment']", "[class*='parcel']"),
        coupon_selectors=("[class*='coupon']", "[class*='cupom']"),
    ),
    StoreConfig(
        id=None,
        name="Fast Shop",
        base_url="https://site.fastshop.com.br",
        search_url="https://site.fastshop.com.br/informatica-e-games/console-jogo-e-acessorio",
        card_selectors=(
            "[data-testid='product-card']",
            ".vtex-search-result-3-x-galleryItem",
            ".vtex-product-summary-2-x-container",
            "[class*='product-summary']",
            ".product-card",
            "article",
            "li",
        ),
        title_selectors=(
            "[data-testid='product-title']",
            "[class*='productBrand']",
            "[class*='productName']",
            ".product-name",
            "h2",
            "h3",
        ),
        price_selectors=(
            "[data-testid='product-price']",
            "[class*='sellingPriceValue']",
            "[class*='currencyContainer']",
            ".price",
            ".sales-price",
        ),
        link_selectors=("a",),
        cash_selectors=("[class*='sellingPriceValue']", "[class*='pix']"),
        installment_selectors=("[class*='installment']",),
        coupon_selectors=("[class*='coupon']", "[class*='promotion']"),
    ),
)

# Backward-compatible constant used by existing tests/imports.
STORES = BUILTIN_STORES


def _selectors_to_text(values: Iterable[str]) -> str:
    return "\n".join(values)


def builtin_store_payloads() -> list[dict[str, Any]]:
    """Return serializable built-in store rows for database seeding."""
    return [
        {
            "name": store.name,
            "base_url": store.base_url,
            "search_url": store.search_url,
            "card_selectors": _selectors_to_text(store.card_selectors),
            "title_selectors": _selectors_to_text(store.title_selectors),
            "price_selectors": _selectors_to_text(store.price_selectors),
            "link_selectors": _selectors_to_text(store.link_selectors),
            "cash_selectors": _selectors_to_text(store.cash_selectors),
            "installment_selectors": _selectors_to_text(store.installment_selectors),
            "coupon_selectors": _selectors_to_text(store.coupon_selectors),
        }
        for store in BUILTIN_STORES
    ]


def _split_selectors(value: str | None, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        return fallback
    parts = [part.strip() for part in re.split(r"[\n,]+", value) if part.strip()]
    return tuple(parts) or fallback


def store_config_from_model(store: Any) -> StoreConfig:
    """Convert a Store ORM row to the scraper's immutable configuration."""
    return StoreConfig(
        id=store.id,
        name=store.name,
        base_url=store.base_url,
        search_url=store.search_url,
        card_selectors=_split_selectors(store.card_selectors, GENERIC_CARD_SELECTORS),
        title_selectors=_split_selectors(store.title_selectors, GENERIC_TITLE_SELECTORS),
        price_selectors=_split_selectors(store.price_selectors, GENERIC_PRICE_SELECTORS),
        link_selectors=_split_selectors(store.link_selectors, GENERIC_LINK_SELECTORS),
        cash_selectors=_split_selectors(store.cash_selectors, ()),
        installment_selectors=_split_selectors(store.installment_selectors, ()),
        coupon_selectors=_split_selectors(store.coupon_selectors, ()),
    )


def store_names(stores: Iterable[Any] | None = None) -> list[str]:
    if stores is None:
        return [store.name for store in BUILTIN_STORES]
    return [store.name for store in stores]


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", value.lower()).strip()


def _build_search_url(store: StoreConfig, query: str) -> str:
    normalized_slug = re.sub(r"[^a-zA-Z0-9]+", "-", _normalize(query)).strip("-")
    try:
        return store.search_url.format(query=quote_plus(query), slug=normalized_slug)
    except (KeyError, ValueError):
        return store.search_url


def _brl_to_float(value: str) -> float | None:
    cleaned = value.strip().replace("R$", "").strip()
    if not cleaned:
        return None
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        parsed = float(cleaned)
    except ValueError:
        return None
    return parsed if 1 <= parsed <= 1_000_000 else None


def _parse_price(text: str) -> float | None:
    prices: list[float] = []
    for match in BRL_PATTERN.finditer(text):
        value = _brl_to_float(match.group(1))
        if value is not None and 50 <= value <= 100_000:
            prices.append(value)

    if not prices:
        for match in PLAIN_PRICE_PATTERN.finditer(text):
            try:
                value = float(f"{match.group(1)}.{match.group(2)}")
            except ValueError:
                continue
            if 50 <= value <= 100_000:
                prices.append(value)

    for pattern in (WHOLE_BRL_PATTERN, PLAIN_THOUSANDS_PATTERN):
        for match in pattern.finditer(text):
            try:
                value = float(match.group(1).replace(".", ""))
            except ValueError:
                continue
            if 50 <= value <= 100_000:
                prices.append(value)

    # Do not mistake a single installment value for the full product price.
    installment_values = {
        round(_brl_to_float(match.group("value")) or -1, 2)
        for match in INSTALLMENT_PATTERN.finditer(text)
    }
    non_installments = [value for value in prices if round(value, 2) not in installment_values]
    if prices and installment_values and not non_installments:
        return None
    return min(non_installments) if non_installments else (min(prices) if prices else None)


def _clean_coupon_code(value: str) -> str | None:
    code = value.strip(" `'*\".,:;()[]{}").upper()
    blocked = {
        "APLICADO",
        "APROVEITE",
        "CODIGO",
        "CUPOM",
        "DESCONTO",
        "DIGITE",
        "EXCLUSIVO",
        "OFERTA",
        "PROMOCAO",
        "PROMOÇÃO",
        "UTILIZE",
    }
    if (
        len(code) < 3
        or len(code) > 31
        or code in blocked
        or code.isdigit()
        or not re.search(r"[A-Z]", code)
    ):
        return None
    return code


def _nearest_discount(text: str, start: int, end: int) -> str | None:
    window_start = max(0, start - 100)
    window_end = min(len(text), end + 120)
    candidates = list(DISCOUNT_PATTERN.finditer(text[window_start:window_end]))
    if not candidates:
        return None
    code_center = ((start + end) / 2) - window_start
    closest = min(candidates, key=lambda item: abs((item.start() + item.end()) / 2 - code_center))
    discount = re.sub(
        r"\s+", "", closest.group("discount") or closest.group("cash_discount")
    ).upper()
    return discount.replace("R$", "R$ ")


def _parse_coupon_details(text: str) -> CouponDetails:
    """Extract the best coupon candidate plus nearby discount and restrictions."""
    normalized_text = re.sub(r"[\u200b-\u200d\ufeff]", "", text)
    candidates: list[tuple[float, int, str, str | None]] = []
    for pattern_index, pattern in enumerate(COUPON_CODE_PATTERNS):
        for match in pattern.finditer(normalized_text):
            code = _clean_coupon_code(match.group("code"))
            if code is None:
                continue
            confidence = 0.98 if pattern_index == 0 else 0.88
            if any(char.isdigit() for char in code):
                confidence += 0.01
            discount = _nearest_discount(normalized_text, match.start(), match.end())
            if discount:
                confidence = min(1.0, confidence + 0.01)
            candidates.append((confidence, match.start(), code, discount))

    if not candidates:
        return CouponDetails()

    confidence, _, code, discount = max(candidates, key=lambda item: (item[0], -item[1]))
    conditions: list[str] = []
    minimum = COUPON_MINIMUM_PATTERN.search(normalized_text)
    if minimum:
        conditions.append(f"Compra mínima: {minimum.group('minimum').strip()}")
    validity = COUPON_VALIDITY_PATTERN.search(normalized_text)
    if validity:
        conditions.append(f"Validade: {validity.group('validity').strip()}")

    normalized = _normalize(normalized_text)
    condition_markers = (
        ("exclusivo no app", "Exclusivo no app"),
        ("somente no app", "Somente no app"),
        ("primeira compra", "Somente primeira compra"),
        ("novos clientes", "Somente novos clientes"),
        ("clientes selecionados", "Clientes selecionados"),
        ("pagamento no pix", "Pagamento via PIX"),
    )
    for marker, label in condition_markers:
        if marker in normalized and label not in conditions:
            conditions.append(label)

    return CouponDetails(
        code=code,
        discount=discount,
        conditions="; ".join(conditions) or None,
        confidence=round(confidence, 2),
    )


def _parse_payment_details(
    text: str,
) -> tuple[float | None, float | None, int | None, str | None, str | None]:
    cash_candidates: list[float] = []
    for pattern in CASH_PATTERNS:
        for match in pattern.finditer(text):
            value = _brl_to_float(match.group("value"))
            if value is not None:
                cash_candidates.append(value)

    installment_price: float | None = None
    installment_count: int | None = None
    installment_totals: list[tuple[float, int, float]] = []
    for match in INSTALLMENT_PATTERN.finditer(text):
        count = int(match.group("count"))
        value = _brl_to_float(match.group("value"))
        if value is None or count < 2:
            continue
        installment_totals.append((count * value, count, value))
    if installment_totals:
        _, installment_count, installment_price = min(installment_totals)
        cash_candidates = [
            value for value in cash_candidates
            if round(value, 2) != round(installment_price, 2)
        ]

    coupon_details = _parse_coupon_details(text)
    return (
        min(cash_candidates) if cash_candidates else None,
        installment_price,
        installment_count,
        coupon_details.code,
        coupon_details.discount,
    )


def _significant_tokens(value: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", _normalize(value)))
    return {token for token in tokens if len(token) > 1 and token not in STOPWORDS}


def _matches_product(title: str, product_name: str) -> bool:
    title_n = _normalize(title)
    product_n = _normalize(product_name)
    blocked = (
        "usado",
        "seminovo",
        "recondicionado",
        "controle",
        "capa",
        "skin",
        "suporte",
        "headset",
        "jogo",
    )
    if any(token in title_n for token in blocked) and "controle" not in product_n:
        return False

    is_ps5 = "playstation 5" in product_n or "ps5" in product_n
    if is_ps5:
        if not (("playstation" in title_n and "5" in title_n) or "ps5" in title_n):
            return False
        if "slim" in product_n and "slim" not in title_n:
            return False
        wants_digital = "digital" in product_n
        title_is_digital = "digital" in title_n
        if wants_digital != title_is_digital:
            return False
        if not wants_digital and "slim" in product_n:
            disc_markers = ("disco", "disc", "leitor", "standard")
            if not any(marker in title_n for marker in disc_markers):
                return "digital" not in title_n
        return True

    product_tokens = _significant_tokens(product_name)
    title_tokens = _significant_tokens(title)
    if not product_tokens:
        return product_n in title_n
    overlap = len(product_tokens & title_tokens) / len(product_tokens)
    return overlap >= 0.55


def _first_text(node: Tag, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        try:
            found = node.select_one(selector)
        except Exception:
            continue
        if found:
            text = found.get_text(" ", strip=True)
            if text:
                return text
    return ""


def _all_text(node: Tag, selectors: tuple[str, ...]) -> str:
    values: list[str] = []
    for selector in selectors:
        try:
            matches = node.select(selector)
        except Exception:
            continue
        for found in matches:
            text = found.get_text(" ", strip=True)
            if text and text not in values:
                values.append(text)
    return " ".join(values)


def _first_link(node: Tag, selectors: tuple[str, ...], base_url: str) -> str:
    for selector in selectors:
        try:
            found = node.select_one(selector)
        except Exception:
            continue
        if found and found.get("href"):
            return urljoin(base_url, str(found.get("href")))
    return base_url


def _json_ld_nodes(payload: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        nodes.append(payload)
        for value in payload.values():
            nodes.extend(_json_ld_nodes(value))
    elif isinstance(payload, list):
        for item in payload:
            nodes.extend(_json_ld_nodes(item))
    return nodes


def _offer_from_text(
    *,
    store: StoreConfig,
    product_name: str,
    title: str,
    url: str,
    text: str,
    explicit_price: float | None = None,
) -> ScrapedOffer | None:
    if not _matches_product(title, product_name):
        return None
    price = explicit_price or _parse_price(text)
    if price is None:
        return None
    product_normalized = _normalize(product_name)
    if ("playstation 5" in product_normalized or "ps5" in product_normalized) and price < 1500:
        return None
    cash, installment, count, coupon, coupon_discount = _parse_payment_details(text)
    coupon_details = _parse_coupon_details(text)
    effective_price = cash or price
    return ScrapedOffer(
        store=store.name,
        product=product_name,
        title=title,
        price=effective_price,
        url=url,
        cash_price=cash or price,
        installment_price=installment,
        installment_count=count,
        coupon=coupon,
        coupon_discount=coupon_discount,
        coupon_conditions=coupon_details.conditions,
        coupon_confidence=coupon_details.confidence if coupon else None,
    )


def _extract_json_ld(
    soup: BeautifulSoup,
    store: StoreConfig,
    product_name: str,
) -> list[ScrapedOffer]:
    offers: list[ScrapedOffer] = []
    for script in soup.select("script[type='application/ld+json']"):
        content = script.string or script.get_text(strip=True)
        if not content:
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue

        for node in _json_ld_nodes(payload):
            node_type = node.get("@type")
            is_product = "Product" in node_type if isinstance(node_type, list) else node_type == "Product"
            if not is_product:
                continue
            title = str(node.get("name", ""))
            offer_data = node.get("offers", {})
            offer_items = offer_data if isinstance(offer_data, list) else [offer_data]
            for offer in offer_items:
                if not isinstance(offer, dict):
                    continue
                raw_price = offer.get("price") or offer.get("lowPrice")
                explicit_price = _brl_to_float(str(raw_price)) if raw_price is not None else None
                url = str(offer.get("url") or node.get("url") or store.base_url)
                text = " ".join(
                    str(value)
                    for value in (
                        title,
                        offer.get("description", ""),
                        node.get("description", ""),
                        raw_price or "",
                    )
                )
                parsed = _offer_from_text(
                    store=store,
                    product_name=product_name,
                    title=title,
                    url=urljoin(store.base_url, url),
                    text=text,
                    explicit_price=explicit_price,
                )
                if parsed:
                    offers.append(parsed)
    return offers


def _extract_cards(
    soup: BeautifulSoup,
    store: StoreConfig,
    product_name: str,
) -> list[ScrapedOffer]:
    nodes: list[Tag] = []
    seen: set[int] = set()
    for selector in store.card_selectors:
        try:
            matches = soup.select(selector)
        except Exception:
            logger.warning("Seletor CSS inválido em %s: %s", store.name, selector)
            continue
        for node in matches:
            if id(node) not in seen:
                nodes.append(node)
                seen.add(id(node))

    offers: list[ScrapedOffer] = []
    for node in nodes[:300]:
        title = _first_text(node, store.title_selectors)
        if not title:
            continue
        primary_price_text = _first_text(node, store.price_selectors)
        explicit_price = _parse_price(primary_price_text)

        payment_text = " ".join(
            part
            for part in (
                _all_text(node, store.cash_selectors),
                _all_text(node, store.installment_selectors),
                _all_text(node, store.coupon_selectors),
                node.get_text(" ", strip=True),
            )
            if part
        )

        parsed = _offer_from_text(
            store=store,
            product_name=product_name,
            title=title,
            url=_first_link(node, store.link_selectors, store.base_url),
            text=payment_text,
            explicit_price=explicit_price,
        )
        if parsed:
            offers.append(parsed)
    return offers


def _extract_offers(html: str, store: StoreConfig, product_name: str) -> list[ScrapedOffer]:
    soup = BeautifulSoup(html, "html.parser")
    combined = _extract_json_ld(soup, store, product_name)
    combined.extend(_extract_cards(soup, store, product_name))

    deduplicated: dict[tuple[str, int, str], ScrapedOffer] = {}
    for offer in combined:
        key = (_normalize(offer.title), round(offer.price * 100), offer.url)
        deduplicated[key] = offer
    return sorted(deduplicated.values(), key=lambda item: item.price)


def _blocked(status_code: int, html: str) -> bool:
    lower = html.lower()
    return status_code in {403, 429, 503} or any(marker in lower for marker in BLOCK_MARKERS)


def fetch_requests(url: str) -> str:
    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    response.raise_for_status()
    if _blocked(response.status_code, response.text):
        raise requests.RequestException("Página bloqueada ou protegida por desafio anti-bot.")
    return response.text


def fetch_playwright(url: str) -> str:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="pt-BR",
            viewport={"width": 1440, "height": 1100},
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_TIMEOUT)
            page.wait_for_timeout(2500)
            return page.content()
        finally:
            context.close()
            browser.close()


def _enrich_offer(offer: ScrapedOffer) -> ScrapedOffer:
    """Read the product page to capture PIX, installments and coupon details."""
    if not offer.url.startswith(("http://", "https://")):
        return offer

    try:
        html = fetch_requests(offer.url)
    except requests.RequestException:
        return offer

    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

    cash, installment, count, coupon, discount = _parse_payment_details(text)
    coupon_details = _parse_coupon_details(text)

    is_ps5 = (
        "ps5" in _normalize(offer.product)
        or "playstation 5" in _normalize(offer.product)
    )

    if is_ps5:
        if cash is not None and cash < 1500:
            logger.warning(
                "Possível parcela ignorada como preço à vista: %.2f",
                cash,
            )
            cash = None

        if (
            cash is not None
            and installment is not None
            and round(cash, 2) == round(installment, 2)
        ):
            cash = None

    parsed_page_price = _parse_price(text)
    effective = cash or offer.cash_price or offer.price or parsed_page_price

    return replace(
        offer,
        price=effective,
        cash_price=cash or offer.cash_price or effective,
        installment_price=installment or offer.installment_price,
        installment_count=count or offer.installment_count,
        coupon=coupon or offer.coupon,
        coupon_discount=discount or offer.coupon_discount,
        coupon_conditions=coupon_details.conditions or offer.coupon_conditions,
        coupon_confidence=(
            coupon_details.confidence if coupon else offer.coupon_confidence
        ),
    )


def scrape_store_product(
    store: StoreConfig,
    product_name: str,
    query: str,
    direct_url: str | None = None,
) -> ScrapedOffer | None:
    """Return the cheapest matching offer for one store/product pair."""
    url = direct_url or _build_search_url(store, query)
    offers: list[ScrapedOffer] = []

    try:
        html = fetch_requests(url)
        offers = _extract_offers(html, store, product_name)
        if direct_url and not offers:
            # Direct pages sometimes have a generic/short title; use the requested
            # product name while preserving all payment parsing.
            text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
            price = _parse_price(text)
            if price is not None and price >= (1500 if ("playstation 5" in _normalize(product_name) or "ps5" in _normalize(product_name)) else 20):
                cash, installment, count, coupon, discount = _parse_payment_details(text)
                coupon_details = _parse_coupon_details(text)
                offers = [
                    ScrapedOffer(
                        store=store.name,
                        product=product_name,
                        title=product_name,
                        price=cash or price,
                        url=direct_url,
                        cash_price=cash or price,
                        installment_price=installment,
                        installment_count=count,
                        coupon=coupon,
                        coupon_discount=discount,
                        coupon_conditions=coupon_details.conditions,
                        coupon_confidence=coupon_details.confidence if coupon else None,
                    )
                ]
        if offers:
            result = _enrich_offer(offers[0])
            logger.info("%s: oferta encontrada via Requests para %s", store.name, product_name)
            return result
    except requests.RequestException as exc:
        logger.warning("%s: Requests falhou (%s). Usando Playwright.", store.name, exc)

    try:
        html = fetch_playwright(url)
        offers = _extract_offers(html, store, product_name)
        if direct_url and not offers:
            text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
            price = _parse_price(text)
            if price is not None and price >= (1500 if ("playstation 5" in _normalize(product_name) or "ps5" in _normalize(product_name)) else 20):
                cash, installment, count, coupon, discount = _parse_payment_details(text)
                coupon_details = _parse_coupon_details(text)
                offers = [
                    ScrapedOffer(
                        store=store.name,
                        product=product_name,
                        title=product_name,
                        price=cash or price,
                        url=direct_url,
                        cash_price=cash or price,
                        installment_price=installment,
                        installment_count=count,
                        coupon=coupon,
                        coupon_discount=discount,
                        coupon_conditions=coupon_details.conditions,
                        coupon_confidence=coupon_details.confidence if coupon else None,
                    )
                ]
        if offers:
            logger.info("%s: oferta encontrada via Playwright para %s", store.name, product_name)
            return offers[0]
        logger.warning("%s: nenhum preço compatível encontrado para %s", store.name, product_name)
    except (PlaywrightError, PlaywrightTimeoutError, OSError) as exc:
        logger.exception("%s: Playwright falhou para %s: %s", store.name, product_name, exc)

    return None
