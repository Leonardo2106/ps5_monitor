"""Scheduled price collection, public-promotion scans and Telegram alerts."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

try:
    import schedule
except ImportError:
    try:
        from . import scheduler_fallback as schedule
    except ImportError:
        import scheduler_fallback as schedule
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

try:
    from .config import CHECK_INTERVAL
    from .database import SessionLocal, init_db
    from .models import (
        AlertEvent,
        AppSetting,
        Price,
        Product,
        ProductStoreLink,
        Promotion,
        PromotionSource,
        ReceivedMessage,
        Store,
    )
    from .promotions import PromotionHit, promotion_hits_from_text, scan_promotion_source
    from .scraper import ScrapedOffer, scrape_store_product, store_config_from_model
    from .telegram_notifier import safe_html, send_telegram_message
    from .utils import format_brl, local_datetime, now_utc_iso
except ImportError:
    from config import CHECK_INTERVAL
    from database import SessionLocal, init_db
    from models import (
        AlertEvent,
        AppSetting,
        Price,
        Product,
        ProductStoreLink,
        Promotion,
        PromotionSource,
        ReceivedMessage,
        Store,
    )
    from promotions import PromotionHit, promotion_hits_from_text, scan_promotion_source
    from scraper import ScrapedOffer, scrape_store_product, store_config_from_model
    from telegram_notifier import safe_html, send_telegram_message
    from utils import format_brl, local_datetime, now_utc_iso

logger = logging.getLogger(__name__)
_monitor_lock = threading.Lock()


@dataclass(slots=True)
class MonitorSummary:
    collected: int = 0
    errors: int = 0
    alerts: int = 0
    promotions: int = 0


def _bool_setting(db: Session, key: str, default: bool) -> bool:
    setting = db.get(AppSetting, key)
    if setting is None:
        return default
    return setting.value.strip().lower() in {"1", "true", "yes", "on"}


def get_check_interval(db: Session | None = None) -> int:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        setting = session.get(AppSetting, "check_interval")
        if setting is None:
            return CHECK_INTERVAL
        try:
            return max(60, int(setting.value))
        except ValueError:
            return CHECK_INTERVAL
    finally:
        if owns_session:
            session.close()


def _offer_fingerprint(offer: ScrapedOffer, kind: str) -> str:
    normalized_url = offer.url.split("#", 1)[0].rstrip("/")
    raw = "|".join(
        [
            offer.product.lower().strip(),
            offer.store.lower().strip(),
            f"{offer.price:.2f}",
            f"{offer.cash_price or 0:.2f}",
            f"{offer.installment_count or 0}",
            f"{offer.installment_price or 0:.2f}",
            (offer.coupon or "").upper().strip(),
            (offer.coupon_conditions or "").lower().strip(),
            normalized_url,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _already_alerted(db: Session, fingerprint: str) -> bool:
    return db.scalar(
        select(AlertEvent.id).where(AlertEvent.fingerprint == fingerprint).limit(1)
    ) is not None



def _lowest_alerted_price(
    db: Session, product: str, kind: str | None = None
) -> float | None:
    query = select(AlertEvent.price).where(AlertEvent.product == product)
    if kind is not None:
        query = query.where(AlertEvent.kind == kind)
    return db.scalar(query.order_by(AlertEvent.price.asc()).limit(1))

def _installment_text(
    count: int | None, installment_price: float | None
) -> str:
    if not count or installment_price is None:
        return "Não identificado"
    total = count * installment_price
    return f"{count}x de {format_brl(installment_price)} (total {format_brl(total)})"


def _offer_message(offer: ScrapedOffer, target_price: float, kind: str) -> str:
    local_date = local_datetime().strftime("%d/%m/%Y %H:%M")
    reached = offer.price <= target_price
    headline = (
        "🚨 <b>NOVO MENOR PREÇO ENCONTRADO!</b>"
        if kind == "best_offer"
        else "🔥 <b>NOVA PROMOÇÃO ENCONTRADA!</b>"
    )
    status = "✅ Atingiu o preço-alvo" if reached else "📊 Ainda acima do preço-alvo"
    coupon = safe_html(offer.coupon) if offer.coupon else "Não identificado"
    if offer.coupon_discount:
        coupon += f" ({safe_html(offer.coupon_discount)})"
    if offer.coupon_conditions:
        coupon += f" — {safe_html(offer.coupon_conditions)}"
    return "\n".join(
        [
            headline,
            "",
            f"<b>Produto:</b> {safe_html(offer.product)}",
            f"<b>Loja:</b> {safe_html(offer.store)}",
            f"<b>À vista/PIX:</b> {format_brl(offer.cash_price or offer.price)}",
            f"<b>Parcelado:</b> {_installment_text(offer.installment_count, offer.installment_price)}",
            f"<b>Cupom:</b> {coupon}",
            f"<b>Preço-alvo:</b> {format_brl(target_price)}",
            f"<b>Status:</b> {status}",
            f"<b>Data:</b> {local_date}",
            "",
            f"🔗 {safe_html(offer.url)}",
        ]
    )


def _save_price(db: Session, offer: ScrapedOffer) -> Price:
    record = Price(
        date=now_utc_iso(),
        store=offer.store,
        product=offer.product,
        price=offer.price,
        title=offer.title,
        url=offer.url,
        cash_price=offer.cash_price,
        installment_price=offer.installment_price,
        installment_count=offer.installment_count,
        coupon=offer.coupon,
        coupon_discount=offer.coupon_discount,
        coupon_conditions=offer.coupon_conditions,
        coupon_confidence=offer.coupon_confidence,
        source_type=offer.source_type,
    )
    db.add(record)
    return record


def _record_and_send_alert(
    db: Session,
    offer: ScrapedOffer,
    target_price: float,
    kind: str,
) -> bool:
    fingerprint = _offer_fingerprint(offer, kind)
    if _already_alerted(db, fingerprint):
        logger.info(
            "Alerta ignorado por duplicidade: %s / %s / %.2f",
            offer.product,
            offer.store,
            offer.price,
        )
        return False

    message = _offer_message(offer, target_price, kind)
    logger.warning("%s", message.replace("<b>", "").replace("</b>", ""))
    print(message.replace("<b>", "").replace("</b>", ""))
    sent = send_telegram_message(message, offer.url)
    db.add(
        AlertEvent(
            date=now_utc_iso(),
            store=offer.store,
            product=offer.product,
            price=offer.price,
            target_price=target_price,
            channel="telegram" if sent else "terminal_log",
            fingerprint=fingerprint,
            kind=kind,
            cash_price=offer.cash_price,
            installment_price=offer.installment_price,
            installment_count=offer.installment_count,
            coupon=offer.coupon,
            url=offer.url,
        )
    )
    db.commit()
    return True


def _direct_link_map(db: Session) -> dict[tuple[int, int], str]:
    links = db.scalars(
        select(ProductStoreLink).where(ProductStoreLink.active.is_(True))
    ).all()
    return {(link.product_id, link.store_id): link.url for link in links}


def _collect_store_offers(db: Session, summary: MonitorSummary) -> dict[int, list[ScrapedOffer]]:
    products = list(
        db.scalars(select(Product).where(Product.active.is_(True)).order_by(Product.id)).all()
    )
    stores = list(
        db.scalars(select(Store).where(Store.active.is_(True)).order_by(Store.id)).all()
    )
    direct_links = _direct_link_map(db)
    offers_by_product: dict[int, list[ScrapedOffer]] = {product.id: [] for product in products}

    for product in products:
        for store_row in stores:
            store = store_config_from_model(store_row)
            direct_url = direct_links.get((product.id, store_row.id))
            try:
                offer = scrape_store_product(
                    store,
                    product.name,
                    product.search_query,
                    direct_url=direct_url,
                )
            except Exception as exc:
                summary.errors += 1
                logger.exception(
                    "Erro não tratado ao coletar %s em %s: %s",
                    product.name,
                    store.name,
                    exc,
                )
                continue
            if offer is None:
                summary.errors += 1
                continue
            _save_price(db, offer)
            db.commit()
            summary.collected += 1
            offers_by_product[product.id].append(offer)
            logger.info(
                "Preço salvo: %s | %s | %.2f | %s",
                product.name,
                store.name,
                offer.price,
                offer.url,
            )
    return offers_by_product


def _alert_best_offers(
    db: Session,
    offers_by_product: dict[int, list[ScrapedOffer]],
    summary: MonitorSummary,
) -> None:
    if not _bool_setting(db, "alert_best_offer", True):
        return
    products = {product.id: product for product in db.scalars(select(Product)).all()}
    for product_id, offers in offers_by_product.items():
        if not offers or product_id not in products:
            continue
        best = min(offers, key=lambda item: item.price)
        previous_low = _lowest_alerted_price(db, best.product)
        if previous_low is not None and best.price > previous_low:
            logger.info(
                "Melhor preço atual de %s (%.2f) não supera o menor já alertado (%.2f).",
                best.product,
                best.price,
                previous_low,
            )
            continue
        if _record_and_send_alert(
            db, best, products[product_id].target_price, kind="best_offer"
        ):
            summary.alerts += 1


def _promotion_as_offer(hit: PromotionHit) -> ScrapedOffer:
    return ScrapedOffer(
        store=hit.store or hit.source,
        product=hit.product,
        title=hit.title,
        price=hit.price,
        url=hit.url,
        cash_price=hit.cash_price,
        installment_price=hit.installment_price,
        installment_count=hit.installment_count,
        coupon=hit.coupon,
        coupon_discount=hit.coupon_discount,
        coupon_conditions=hit.coupon_conditions,
        coupon_confidence=hit.coupon_confidence,
        source_type="promotion_source",
    )


def ingest_promotion_message(
    db: Session,
    source: PromotionSource,
    external_message_id: str,
    text: str,
    url: str,
    title: str | None = None,
) -> tuple[int, int]:
    """Persist and alert offers received through an authenticated webhook."""
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    received = db.scalar(
        select(ReceivedMessage).where(
            ReceivedMessage.source_id == source.id,
            ReceivedMessage.external_message_id == external_message_id,
        )
    )
    if received and received.content_hash == content_hash:
        return 0, 0
    if received:
        received.content_hash = content_hash
        received.received_at = now_utc_iso()
    else:
        db.add(
            ReceivedMessage(
                source_id=source.id,
                external_message_id=external_message_id,
                content_hash=content_hash,
            )
        )

    products = list(db.scalars(select(Product).where(Product.active.is_(True))).all())
    store = db.get(Store, source.store_id) if source.store_id else None
    hits = promotion_hits_from_text(source, products, store, text, url, title)
    new_hits: list[PromotionHit] = []
    for hit in hits:
        if db.scalar(
            select(Promotion.id).where(Promotion.fingerprint == hit.fingerprint).limit(1)
        ) is not None:
            continue
        db.add(
            Promotion(
                date=now_utc_iso(),
                source=hit.source,
                store=hit.store,
                product=hit.product,
                title=hit.title,
                price=hit.price,
                cash_price=hit.cash_price,
                installment_price=hit.installment_price,
                installment_count=hit.installment_count,
                coupon=hit.coupon,
                coupon_discount=hit.coupon_discount,
                coupon_conditions=hit.coupon_conditions,
                coupon_confidence=hit.coupon_confidence,
                url=hit.url,
                fingerprint=hit.fingerprint,
            )
        )
        new_hits.append(hit)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return 0, 0

    alerts = 0
    products_by_name = {product.name: product for product in products}
    for hit in new_hits:
        product = products_by_name.get(hit.product)
        if product is None:
            continue
        previous_low = _lowest_alerted_price(db, hit.product)
        if previous_low is not None and hit.price > previous_low:
            continue
        if _record_and_send_alert(
            db, _promotion_as_offer(hit), product.target_price, kind="promotion"
        ):
            alerts += 1
    return len(new_hits), alerts


def _scan_promotions(db: Session, summary: MonitorSummary) -> None:
    if not _bool_setting(db, "scan_promotion_sources", True):
        return
    products = list(db.scalars(select(Product).where(Product.active.is_(True))).all())
    sources = list(
        db.scalars(
            select(PromotionSource)
            .where(
                PromotionSource.active.is_(True),
                PromotionSource.source_type.in_(("web", "telegram_public")),
            )
            .order_by(PromotionSource.id)
        ).all()
    )
    products_by_name = {product.name: product for product in products}
    setting = db.get(AppSetting, "promotion_max_age_hours")
    try:
        max_age_hours = int(setting.value) if setting else 72
    except ValueError:
        max_age_hours = 72

    new_hits: list[PromotionHit] = []
    for source in sources:
        store = db.get(Store, source.store_id) if source.store_id else None
        try:
            hits = scan_promotion_source(
                source, products, store, max_age_hours=max_age_hours
            )
        except Exception as exc:
            summary.errors += 1
            logger.exception("Falha ao pesquisar promoções em %s: %s", source.name, exc)
            continue

        for hit in hits:
            existing = db.scalar(
                select(Promotion.id)
                .where(Promotion.fingerprint == hit.fingerprint)
                .limit(1)
            )
            if existing is not None:
                continue
            db.add(
                Promotion(
                    date=now_utc_iso(),
                    source=hit.source,
                    store=hit.store,
                    product=hit.product,
                    title=hit.title,
                    price=hit.price,
                    cash_price=hit.cash_price,
                    installment_price=hit.installment_price,
                    installment_count=hit.installment_count,
                    coupon=hit.coupon,
                    coupon_discount=hit.coupon_discount,
                    coupon_conditions=hit.coupon_conditions,
                    coupon_confidence=hit.coupon_confidence,
                    url=hit.url,
                    fingerprint=hit.fingerprint,
                )
            )
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                continue
            summary.promotions += 1
            new_hits.append(hit)

    best_new_by_product: dict[str, PromotionHit] = {}
    for hit in new_hits:
        current = best_new_by_product.get(hit.product)
        if current is None or hit.price < current.price:
            best_new_by_product[hit.product] = hit

    for hit in best_new_by_product.values():
        product = products_by_name.get(hit.product)
        if product is None:
            continue
        previous_low = _lowest_alerted_price(db, hit.product)
        if previous_low is not None and hit.price > previous_low:
            logger.info(
                "Promoção de %s (%.2f) não supera o menor já alertado (%.2f).",
                hit.product,
                hit.price,
                previous_low,
            )
            continue
        if _record_and_send_alert(
            db, _promotion_as_offer(hit), product.target_price, kind="promotion"
        ):
            summary.alerts += 1


def run_monitor_once() -> MonitorSummary:
    """Run one complete scan without allowing concurrent executions."""
    summary = MonitorSummary()
    if not _monitor_lock.acquire(blocking=False):
        logger.warning("Uma coleta já está em execução; nova rodada ignorada.")
        return summary

    try:
        init_db()
        logger.info("Iniciando verificação de preços e promoções.")
        with SessionLocal() as db:
            offers_by_product = _collect_store_offers(db, summary)
            _alert_best_offers(db, offers_by_product, summary)
            _scan_promotions(db, summary)
        logger.info(
            "Verificação concluída: %s preços, %s promoções, %s falhas, %s alertas.",
            summary.collected,
            summary.promotions,
            summary.errors,
            summary.alerts,
        )
        return summary
    finally:
        _monitor_lock.release()


class MonitorService:
    """Background scheduler used by FastAPI and standalone execution."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            schedule.run_pending()
            self._stop_event.wait(1)

    def reschedule(self, interval: int | None = None) -> None:
        seconds = interval or get_check_interval()
        schedule.clear("price-monitor")
        schedule.every(seconds).seconds.do(run_monitor_once).tag("price-monitor")
        logger.info("Monitor reagendado para cada %s segundos.", seconds)

    def start(self, run_immediately: bool = False) -> None:
        if self._running:
            return
        self._stop_event.clear()
        self.reschedule()
        self._thread = threading.Thread(
            target=self._loop,
            name="ps5-price-monitor",
            daemon=True,
        )
        self._thread.start()
        self._running = True
        if run_immediately:
            threading.Thread(target=run_monitor_once, daemon=True).start()
        logger.info("Serviço de monitoramento iniciado.")

    def stop(self) -> None:
        if not self._running:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        schedule.clear("price-monitor")
        self._running = False
        logger.info("Serviço de monitoramento encerrado.")


monitor_service = MonitorService()


def main() -> None:
    init_db()
    monitor_service.start(run_immediately=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor_service.stop()


if __name__ == "__main__":
    main()
