"""Scan configured public promotion pages and Telegram public previews."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

try:
    from .models import Product, PromotionSource, Store
    from .scraper import (
        ScrapedOffer,
        _matches_product,
        _normalize,
        _parse_coupon_details,
        _parse_payment_details,
        _parse_price,
        fetch_playwright,
        fetch_requests,
    )
except ImportError:
    from models import Product, PromotionSource, Store
    from scraper import (
        ScrapedOffer,
        _matches_product,
        _normalize,
        _parse_coupon_details,
        _parse_payment_details,
        _parse_price,
        fetch_playwright,
        fetch_requests,
    )

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"https?://[^\s<>'\"]+", re.I)


@dataclass(frozen=True, slots=True)
class PromotionHit:
    source: str
    store: str | None
    product: str
    title: str
    price: float
    cash_price: float | None
    installment_price: float | None
    installment_count: int | None
    coupon: str | None
    coupon_discount: str | None
    coupon_conditions: str | None
    coupon_confidence: float | None
    url: str
    fingerprint: str


def promotion_fingerprint(hit: PromotionHit) -> str:
    raw = "|".join(
        [
            _normalize(hit.source),
            _normalize(hit.store or ""),
            _normalize(hit.product),
            f"{hit.price:.2f}",
            f"{hit.installment_count or 0}",
            f"{hit.installment_price or 0:.2f}",
            _normalize(hit.coupon or ""),
            _normalize(hit.coupon_conditions or ""),
            hit.url.split("#", 1)[0],
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _candidate_nodes(soup: BeautifulSoup, source_type: str) -> list[Tag]:
    selectors = (
        (
            ".tgme_widget_message_wrap",
            ".tgme_widget_message",
        )
        if source_type == "telegram_public"
        else (
            "article",
            "[class*='deal']",
            "[class*='promo']",
            "[class*='offer']",
            "[class*='coupon']",
            "li",
        )
    )
    nodes: list[Tag] = []
    seen: set[int] = set()
    for selector in selectors:
        try:
            matches = soup.select(selector)
        except Exception:
            continue
        for node in matches:
            if id(node) not in seen:
                nodes.append(node)
                seen.add(id(node))
    if not nodes and soup.body:
        nodes = [soup.body]
    return nodes[:400]


def _unwrap_telegram_url(url: str) -> str:
    """Extract the destination from Telegram redirect links when possible."""
    parsed = urlparse(url)
    if parsed.scheme == "tg" and parsed.netloc == "unsafe_url":
        destination = parse_qs(parsed.query).get("url", [None])[0]
        return unquote(destination) if destination else url
    return url


def _node_url(node: Tag, source: PromotionSource) -> str:
    """Prefer the retailer/product URL and fall back to the source post."""
    anchors = node.select("a[href]")
    fallback: str | None = None
    for anchor in anchors:
        raw_href = str(anchor.get("href") or "").strip()
        if not raw_href:
            continue
        href = _unwrap_telegram_url(urljoin(source.url, raw_href))
        parsed = urlparse(href)
        domain = parsed.netloc.lower().removeprefix("www.")
        if source.source_type == "telegram_public":
            if "tgme_widget_message_date" in (anchor.get("class") or []):
                fallback = fallback or href
                continue
            if domain and domain not in {"t.me", "telegram.me", "telegram.org"}:
                return href
        else:
            return href

    text = node.get_text(" ", strip=True)
    for match in URL_PATTERN.finditer(text):
        href = _unwrap_telegram_url(match.group(0).rstrip(".,);]"))
        domain = urlparse(href).netloc.lower().removeprefix("www.")
        if source.source_type != "telegram_public" or domain not in {
            "t.me",
            "telegram.me",
            "telegram.org",
        }:
            return href
    return fallback or source.url


def _matches_keywords(text: str, keywords: str | None) -> bool:
    if not keywords:
        return True
    normalized = _normalize(text)
    terms = [
        _normalize(term)
        for term in re.split(r"[,;\n]+", keywords)
        if term.strip()
    ]
    return any(term in normalized for term in terms)


def _store_name(source: PromotionSource, store: Store | None, text: str) -> str | None:
    if store:
        return store.name
    domain = urlparse(_node_safe_url(source.url)).netloc.replace("www.", "")
    known = {
        "amazon": "Amazon Brasil",
        "kabum": "Kabum",
        "magazineluiza": "Magazine Luiza",
        "mercadolivre": "Mercado Livre",
        "casasbahia": "Casas Bahia",
        "pontofrio": "Ponto",
        "fastshop": "Fast Shop",
    }
    normalized = _normalize(text + " " + domain)
    for token, name in known.items():
        if token in normalized:
            return name
    if source.source_type == "telegram_public":
        return None
    return domain or None


def _node_safe_url(url: str) -> str:
    return url if url.startswith(("http://", "https://")) else "https://" + url


def _is_recent(node: Tag, max_age_hours: int) -> bool:
    time_node = node.select_one("time[datetime]")
    if not time_node or not time_node.get("datetime"):
        return True
    raw = str(time_node.get("datetime")).replace("Z", "+00:00")
    try:
        published = datetime.fromisoformat(raw)
    except ValueError:
        return True
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return published >= datetime.now(timezone.utc) - timedelta(hours=max_age_hours)


def promotion_hits_from_text(
    source: PromotionSource,
    products: list[Product],
    store: Store | None,
    text: str,
    url: str,
    title: str | None = None,
) -> list[PromotionHit]:
    """Parse a promotion message from web, Telegram, or WhatsApp."""
    if len(text.strip()) < 20 or not _matches_keywords(text, source.keywords):
        return []
    price = _parse_price(text)
    if price is None:
        return []
    cash, installment, count, coupon, discount = _parse_payment_details(text)
    coupon_details = _parse_coupon_details(text)
    selected_products = (
        [product for product in products if product.id == source.product_id]
        if source.product_id
        else products
    )
    hits: list[PromotionHit] = []
    for product in selected_products:
        product_normalized = _normalize(product.name + " " + product.search_query)
        if ("playstation 5" in product_normalized or "ps5" in product_normalized) and price < 1500:
            continue
        if not _matches_product(text, product.name) and not _matches_product(
            text, product.search_query
        ):
            continue
        hit = PromotionHit(
            source=source.name,
            store=_store_name(source, store, text),
            product=product.name,
            title=(title or text[:220]).strip(),
            price=cash or price,
            cash_price=cash or price,
            installment_price=installment,
            installment_count=count,
            coupon=coupon,
            coupon_discount=discount,
            coupon_conditions=coupon_details.conditions,
            coupon_confidence=coupon_details.confidence if coupon else None,
            url=url or source.url,
            fingerprint="",
        )
        hits.append(replace(hit, fingerprint=promotion_fingerprint(hit)))
    return hits


def scan_promotion_source(
    source: PromotionSource,
    products: list[Product],
    store: Store | None,
    max_age_hours: int = 72,
) -> list[PromotionHit]:
    """Return new-looking product promotions from one configured public source."""
    try:
        html = fetch_requests(source.url)
    except requests.RequestException as exc:
        logger.warning("Fonte %s falhou via Requests: %s", source.name, exc)
        try:
            html = fetch_playwright(source.url)
        except Exception as playwright_exc:
            logger.exception("Fonte %s falhou via Playwright: %s", source.name, playwright_exc)
            return []

    soup = BeautifulSoup(html, "html.parser")
    candidates = _candidate_nodes(soup, source.source_type)
    hits: list[PromotionHit] = []

    for node in candidates:
        if not _is_recent(node, max_age_hours):
            continue
        text = node.get_text(" ", strip=True)
        if len(text) < 20 or not _matches_keywords(text, source.keywords):
            continue
        url = _node_url(node, source)
        title_node = node.select_one("h1, h2, h3, strong, [class*='title']")
        raw_title = title_node.get_text(" ", strip=True) if title_node else text[:220]
        hits.extend(
            promotion_hits_from_text(source, products, store, text, url, raw_title)
        )

    deduplicated: dict[str, PromotionHit] = {hit.fingerprint: hit for hit in hits}
    return sorted(deduplicated.values(), key=lambda item: item.price)
