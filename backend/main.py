"""FastAPI application for the extensible price monitor."""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import re
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

try:
    from .config import (
        ALERT_COOLDOWN_SECONDS,
        CORS_ORIGINS,
        RUN_ON_STARTUP,
        START_MONITOR_WITH_API,
        TELEGRAM_WEBHOOK_SECRET,
        TIMEZONE,
        WHATSAPP_APP_SECRET,
        WHATSAPP_VERIFY_TOKEN,
    )
    from .database import get_db, init_db
    from .logging_setup import configure_logging
    from .models import (
        AppSetting,
        Price,
        Product,
        ProductStoreLink,
        Promotion,
        PromotionSource,
        Store,
    )
    from .monitor import (
        get_check_interval,
        ingest_promotion_message,
        monitor_service,
        run_monitor_once,
    )
    from .schemas import (
        BestOffer,
        MonitorRunResult,
        PriceRead,
        ProductCreate,
        ProductRead,
        ProductStats,
        ProductStoreLinkCreate,
        ProductStoreLinkRead,
        ProductStoreLinkUpdate,
        ProductUpdate,
        PromotionRead,
        PromotionSourceCreate,
        PromotionSourceRead,
        PromotionSourceUpdate,
        SettingsRead,
        SettingsUpdate,
        StatsResponse,
        StoreCreate,
        StoreRead,
        StoreUpdate,
        TelegramResult,
        TelegramTestRequest,
    )
    from .telegram_notifier import send_telegram_message, telegram_is_configured
except ImportError:
    from config import (
        ALERT_COOLDOWN_SECONDS,
        CORS_ORIGINS,
        RUN_ON_STARTUP,
        START_MONITOR_WITH_API,
        TELEGRAM_WEBHOOK_SECRET,
        TIMEZONE,
        WHATSAPP_APP_SECRET,
        WHATSAPP_VERIFY_TOKEN,
    )
    from database import get_db, init_db
    from logging_setup import configure_logging
    from models import (
        AppSetting,
        Price,
        Product,
        ProductStoreLink,
        Promotion,
        PromotionSource,
        Store,
    )
    from monitor import (
        get_check_interval,
        ingest_promotion_message,
        monitor_service,
        run_monitor_once,
    )
    from schemas import (
        BestOffer,
        MonitorRunResult,
        PriceRead,
        ProductCreate,
        ProductRead,
        ProductStats,
        ProductStoreLinkCreate,
        ProductStoreLinkRead,
        ProductStoreLinkUpdate,
        ProductUpdate,
        PromotionRead,
        PromotionSourceCreate,
        PromotionSourceRead,
        PromotionSourceUpdate,
        SettingsRead,
        SettingsUpdate,
        StatsResponse,
        StoreCreate,
        StoreRead,
        StoreUpdate,
        TelegramResult,
        TelegramTestRequest,
    )
    from telegram_notifier import send_telegram_message, telegram_is_configured

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if START_MONITOR_WITH_API:
        monitor_service.start(run_immediately=RUN_ON_STARTUP)
    yield
    if START_MONITOR_WITH_API:
        monitor_service.stop()


app = FastAPI(
    title="PS5 Price Monitor API",
    description=(
        "Monitor de preços com lojas personalizadas, URLs diretas, detalhes de "
        "pagamento, cupons, fontes públicas de promoção e alertas Telegram sem repetição."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _setting_value(db: Session, key: str, default: str) -> str:
    setting = db.get(AppSetting, key)
    return setting.value if setting else default


def _set_setting(db: Session, key: str, value: str) -> None:
    setting = db.get(AppSetting, key)
    if setting is None:
        db.add(AppSetting(key=key, value=value))
    else:
        setting.value = value


@app.get("/health", tags=["System"])
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected", "version": "2.0.0"}


@app.get("/products", response_model=list[ProductRead], tags=["Products"])
def list_products(db: Session = Depends(get_db)) -> list[Product]:
    return list(db.scalars(select(Product).order_by(Product.id)).all())


@app.post(
    "/products",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Products"],
)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> Product:
    product = Product(**payload.model_dump())
    db.add(product)
    try:
        db.commit()
        db.refresh(product)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Produto já cadastrado.") from exc
    return product


@app.patch("/products/{product_id}", response_model=ProductRead, tags=["Products"])
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    try:
        db.commit()
        db.refresh(product)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Nome de produto já utilizado.") from exc
    return product


@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Products"])
def delete_product(product_id: int, db: Session = Depends(get_db)) -> Response:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    db.delete(product)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/stores", response_model=list[StoreRead], tags=["Stores"])
def list_stores(db: Session = Depends(get_db)) -> list[Store]:
    return list(db.scalars(select(Store).order_by(Store.is_builtin.desc(), Store.name)).all())


@app.post(
    "/stores",
    response_model=StoreRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Stores"],
)
def create_store(payload: StoreCreate, db: Session = Depends(get_db)) -> Store:
    store = Store(**payload.model_dump(), is_builtin=False)
    db.add(store)
    try:
        db.commit()
        db.refresh(store)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Loja já cadastrada.") from exc
    return store


@app.patch("/stores/{store_id}", response_model=StoreRead, tags=["Stores"])
def update_store(
    store_id: int, payload: StoreUpdate, db: Session = Depends(get_db)
) -> Store:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Loja não encontrada.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(store, field, value)
    try:
        db.commit()
        db.refresh(store)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Nome de loja já utilizado.") from exc
    return store


@app.delete("/stores/{store_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Stores"])
def delete_store(store_id: int, db: Session = Depends(get_db)) -> Response:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Loja não encontrada.")
    if store.is_builtin:
        raise HTTPException(
            status_code=400,
            detail="Lojas nativas podem ser pausadas, mas não excluídas.",
        )
    db.delete(store)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _link_read(link: ProductStoreLink, db: Session) -> ProductStoreLinkRead:
    product = db.get(Product, link.product_id)
    store = db.get(Store, link.store_id)
    return ProductStoreLinkRead(
        id=link.id,
        product_id=link.product_id,
        product_name=product.name if product else "Produto removido",
        store_id=link.store_id,
        store_name=store.name if store else "Loja removida",
        url=link.url,
        active=link.active,
        created_at=link.created_at,
    )


@app.get("/product-links", response_model=list[ProductStoreLinkRead], tags=["Stores"])
def list_product_links(db: Session = Depends(get_db)) -> list[ProductStoreLinkRead]:
    links = db.scalars(select(ProductStoreLink).order_by(ProductStoreLink.id)).all()
    return [_link_read(link, db) for link in links]


@app.post(
    "/product-links",
    response_model=ProductStoreLinkRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Stores"],
)
def create_product_link(
    payload: ProductStoreLinkCreate, db: Session = Depends(get_db)
) -> ProductStoreLinkRead:
    if db.get(Product, payload.product_id) is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    if db.get(Store, payload.store_id) is None:
        raise HTTPException(status_code=404, detail="Loja não encontrada.")
    link = ProductStoreLink(**payload.model_dump())
    db.add(link)
    try:
        db.commit()
        db.refresh(link)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Já existe uma URL direta para esse produto nessa loja.",
        ) from exc
    return _link_read(link, db)


@app.patch("/product-links/{link_id}", response_model=ProductStoreLinkRead, tags=["Stores"])
def update_product_link(
    link_id: int,
    payload: ProductStoreLinkUpdate,
    db: Session = Depends(get_db),
) -> ProductStoreLinkRead:
    link = db.get(ProductStoreLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="URL direta não encontrada.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(link, field, value)
    db.commit()
    db.refresh(link)
    return _link_read(link, db)


@app.delete("/product-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Stores"])
def delete_product_link(link_id: int, db: Session = Depends(get_db)) -> Response:
    link = db.get(ProductStoreLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="URL direta não encontrada.")
    db.delete(link)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/prices", response_model=list[PriceRead], tags=["Prices"])
def list_prices(
    product: str | None = None,
    store: str | None = None,
    limit: int = Query(default=100, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[Price]:
    query = select(Price)
    if product:
        query = query.where(Price.product == product)
    if store:
        query = query.where(Price.store == store)
    return list(db.scalars(query.order_by(desc(Price.date)).limit(limit)).all())


@app.get("/prices/history", response_model=list[PriceRead], tags=["Prices"])
def price_history(
    product: str | None = None,
    days: int = Query(default=30, ge=1, le=3650),
    db: Session = Depends(get_db),
) -> list[Price]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    query = select(Price).where(Price.date >= since)
    if product:
        query = query.where(Price.product == product)
    return list(db.scalars(query.order_by(Price.date.asc())).all())


def _latest_by_store_product(db: Session) -> list[Price]:
    rows = list(db.scalars(select(Price).order_by(desc(Price.date))).all())
    latest: dict[tuple[str, str], Price] = {}
    for row in rows:
        latest.setdefault((row.product, row.store), row)
    return list(latest.values())


@app.get("/best-offers", response_model=list[BestOffer], tags=["Prices"])
def best_offers(db: Session = Depends(get_db)) -> list[BestOffer]:
    grouped: dict[str, list[Price]] = defaultdict(list)
    for item in _latest_by_store_product(db):
        grouped[item.product].append(item)

    result: list[BestOffer] = []
    for product, offers in grouped.items():
        best = min(offers, key=lambda item: item.price)
        result.append(
            BestOffer(
                product=product,
                store=best.store,
                price=best.price,
                cash_price=best.cash_price,
                installment_price=best.installment_price,
                installment_count=best.installment_count,
                coupon=best.coupon,
                coupon_discount=best.coupon_discount,
                coupon_conditions=best.coupon_conditions,
                coupon_confidence=best.coupon_confidence,
                title=best.title,
                date=best.date,
                url=best.url,
                source_type=best.source_type,
            )
        )
    return sorted(result, key=lambda item: item.product)


@app.get("/stats", response_model=StatsResponse, tags=["Prices"])
def stats(db: Session = Depends(get_db)) -> StatsResponse:
    products = list(db.scalars(select(Product).order_by(Product.id)).all())
    current_by_product: dict[str, list[Price]] = defaultdict(list)
    for item in _latest_by_store_product(db):
        current_by_product[item.product].append(item)

    result: list[ProductStats] = []
    global_last_update: str | None = None
    for product in products:
        current = current_by_product.get(product.name, [])
        latest_record = db.scalar(
            select(Price)
            .where(Price.product == product.name)
            .order_by(desc(Price.date))
            .limit(1)
        )
        minimum = db.scalar(select(func.min(Price.price)).where(Price.product == product.name))
        samples = db.scalar(select(func.count(Price.id)).where(Price.product == product.name)) or 0
        best = min(current, key=lambda item: item.price) if current else None
        if latest_record and (
            global_last_update is None or latest_record.date > global_last_update
        ):
            global_last_update = latest_record.date
        result.append(
            ProductStats(
                product_id=product.id,
                product=product.name,
                last_price=latest_record.price if latest_record else None,
                minimum_price=minimum,
                best_store=best.store if best else None,
                last_update=latest_record.date if latest_record else None,
                target_price=product.target_price,
                samples=int(samples),
            )
        )
    return StatsResponse(products=result, last_update=global_last_update)


@app.get("/prices/export", tags=["Prices"])
def export_prices_csv(db: Session = Depends(get_db)) -> StreamingResponse:
    rows = list(db.scalars(select(Price).order_by(Price.date.asc())).all())
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "id",
            "date",
            "store",
            "product",
            "price",
            "cash_price",
            "installment_count",
            "installment_price",
            "coupon",
            "coupon_discount",
            "coupon_conditions",
            "coupon_confidence",
            "url",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.id,
                row.date,
                row.store,
                row.product,
                f"{row.price:.2f}",
                row.cash_price,
                row.installment_count,
                row.installment_price,
                row.coupon,
                row.coupon_discount,
                row.coupon_conditions,
                row.coupon_confidence,
                row.url,
            ]
        )
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=ps5_prices.csv"
    return response


def _source_read(source: PromotionSource, db: Session) -> PromotionSourceRead:
    product = db.get(Product, source.product_id) if source.product_id else None
    store = db.get(Store, source.store_id) if source.store_id else None
    return PromotionSourceRead(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        url=source.url,
        external_id=source.external_id,
        product_id=source.product_id,
        store_id=source.store_id,
        keywords=source.keywords,
        active=source.active,
        created_at=source.created_at,
        product_name=product.name if product else None,
        store_name=store.name if store else None,
    )


@app.get("/promotion-sources", response_model=list[PromotionSourceRead], tags=["Promotions"])
def list_promotion_sources(db: Session = Depends(get_db)) -> list[PromotionSourceRead]:
    sources = db.scalars(select(PromotionSource).order_by(PromotionSource.id)).all()
    return [_source_read(source, db) for source in sources]


@app.post(
    "/promotion-sources",
    response_model=PromotionSourceRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Promotions"],
)
def create_promotion_source(
    payload: PromotionSourceCreate, db: Session = Depends(get_db)
) -> PromotionSourceRead:
    if payload.product_id and db.get(Product, payload.product_id) is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    if payload.store_id and db.get(Store, payload.store_id) is None:
        raise HTTPException(status_code=404, detail="Loja não encontrada.")
    source = PromotionSource(**payload.model_dump())
    db.add(source)
    try:
        db.commit()
        db.refresh(source)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Fonte já cadastrada.") from exc
    return _source_read(source, db)


def _validate_source_connection(source: PromotionSource) -> None:
    if source.source_type in {"web", "telegram_public"}:
        if not source.url.startswith(("http://", "https://")):
            raise HTTPException(status_code=422, detail="A fonte exige uma URL HTTP ou HTTPS.")
    elif not source.external_id:
        raise HTTPException(status_code=422, detail="A fonte via webhook exige um ID externo.")


@app.patch(
    "/promotion-sources/{source_id}",
    response_model=PromotionSourceRead,
    tags=["Promotions"],
)
def update_promotion_source(
    source_id: int,
    payload: PromotionSourceUpdate,
    db: Session = Depends(get_db),
) -> PromotionSourceRead:
    source = db.get(PromotionSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Fonte não encontrada.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    _validate_source_connection(source)
    try:
        db.commit()
        db.refresh(source)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Nome de fonte já utilizado.") from exc
    return _source_read(source, db)


@app.delete(
    "/promotion-sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Promotions"],
)
def delete_promotion_source(source_id: int, db: Session = Depends(get_db)) -> Response:
    source = db.get(PromotionSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Fonte não encontrada.")
    db.delete(source)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/promotions", response_model=list[PromotionRead], tags=["Promotions"])
def list_promotions(
    product: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[Promotion]:
    query = select(Promotion)
    if product:
        query = query.where(Promotion.product == product)
    return list(db.scalars(query.order_by(desc(Promotion.date)).limit(limit)).all())


@app.post("/telegram/test", response_model=TelegramResult, tags=["Notifications"])
def telegram_test(payload: TelegramTestRequest) -> TelegramResult:
    success = send_telegram_message(payload.message, payload.url)
    if not success:
        raise HTTPException(
            status_code=503,
            detail="Telegram não configurado ou indisponível. Verifique token e chat ID.",
        )
    return TelegramResult(success=True, detail="Mensagem enviada com sucesso.")


def _require_secret(actual: str | None, expected: str, integration: str) -> None:
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"Segredo do webhook {integration} não configurado.",
        )
    if not actual or not hmac.compare_digest(actual, expected):
        raise HTTPException(status_code=403, detail="Assinatura de webhook inválida.")


def _first_message_url(text_value: str, fallback: str) -> str:
    match = re.search(r"https?://[^\s<>'\"]+", text_value, re.I)
    return match.group(0).rstrip(".,);]") if match else fallback


@app.post("/webhooks/telegram", tags=["Webhooks"])
async def telegram_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, int | str]:
    _require_secret(
        request.headers.get("X-Telegram-Bot-Api-Secret-Token"),
        TELEGRAM_WEBHOOK_SECRET,
        "Telegram",
    )
    try:
        update = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="JSON inválido.") from exc

    message = next(
        (
            update.get(key)
            for key in ("message", "edited_message", "channel_post", "edited_channel_post")
            if isinstance(update.get(key), dict)
        ),
        None,
    )
    if not message:
        return {"status": "ignored", "promotions": 0, "alerts": 0}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    text_value = str(message.get("text") or message.get("caption") or "").strip()
    message_id = str(message.get("message_id", update.get("update_id", "")))
    if not chat_id or not text_value or not message_id:
        return {"status": "ignored", "promotions": 0, "alerts": 0}

    source = db.scalar(
        select(PromotionSource).where(
            PromotionSource.active.is_(True),
            PromotionSource.source_type == "telegram_bot",
            PromotionSource.external_id == chat_id,
        )
    )
    if source is None:
        return {"status": "unregistered_chat", "promotions": 0, "alerts": 0}

    username = str(chat.get("username") or "").strip()
    fallback_url = source.url
    if username:
        fallback_url = f"https://t.me/{username}/{message_id}"
    elif chat_id.startswith("-100"):
        fallback_url = f"https://t.me/c/{chat_id[4:]}/{message_id}"
    promotions, alerts = ingest_promotion_message(
        db,
        source,
        f"{chat_id}:{message_id}",
        text_value,
        _first_message_url(text_value, fallback_url),
        str(chat.get("title") or source.name),
    )
    return {"status": "processed", "promotions": promotions, "alerts": alerts}


@app.get("/webhooks/whatsapp", tags=["Webhooks"])
def verify_whatsapp_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> Response:
    if (
        hub_mode != "subscribe"
        or not WHATSAPP_VERIFY_TOKEN
        or not hub_verify_token
        or not hmac.compare_digest(hub_verify_token, WHATSAPP_VERIFY_TOKEN)
        or hub_challenge is None
    ):
        raise HTTPException(status_code=403, detail="Falha ao verificar webhook do WhatsApp.")
    return Response(content=hub_challenge, media_type="text/plain")


def _whatsapp_text(message: dict) -> str:
    message_type = message.get("type")
    if message_type == "text":
        return str((message.get("text") or {}).get("body") or "")
    if message_type in {"image", "video", "document"}:
        return str((message.get(message_type) or {}).get("caption") or "")
    if message_type == "interactive":
        interactive = message.get("interactive") or {}
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return str(reply.get("title") or reply.get("description") or "")
    return ""


@app.post("/webhooks/whatsapp", tags=["Webhooks"])
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, int | str]:
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not WHATSAPP_APP_SECRET:
        raise HTTPException(status_code=503, detail="Segredo do app WhatsApp não configurado.")
    expected = "sha256=" + hmac.new(
        WHATSAPP_APP_SECRET.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=403, detail="Assinatura de webhook inválida.")
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="JSON inválido.") from exc

    promotion_count = 0
    alert_count = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            phone_number_id = str((value.get("metadata") or {}).get("phone_number_id") or "")
            for message in value.get("messages", []):
                text_value = _whatsapp_text(message).strip()
                message_id = str(message.get("id") or "")
                sender = str(message.get("from") or "")
                group_id = str(message.get("group_id") or "")
                identifiers = {item for item in (group_id, sender, phone_number_id) if item}
                if not text_value or not message_id or not identifiers:
                    continue
                source = db.scalar(
                    select(PromotionSource).where(
                        PromotionSource.active.is_(True),
                        PromotionSource.source_type == "whatsapp_cloud",
                        PromotionSource.external_id.in_(identifiers),
                    )
                )
                if source is None:
                    continue
                fallback_url = source.url or (f"https://wa.me/{sender}" if sender else "")
                promotions, alerts = ingest_promotion_message(
                    db,
                    source,
                    message_id,
                    text_value,
                    _first_message_url(text_value, fallback_url),
                    source.name,
                )
                promotion_count += promotions
                alert_count += alerts
    return {"status": "processed", "promotions": promotion_count, "alerts": alert_count}


@app.post("/monitor/run", response_model=MonitorRunResult, tags=["Monitor"])
def run_monitor() -> MonitorRunResult:
    summary = run_monitor_once()
    return MonitorRunResult(
        success=True,
        collected=summary.collected,
        errors=summary.errors,
        alerts=summary.alerts,
        promotions=summary.promotions,
    )


@app.post("/monitor/run-background", status_code=status.HTTP_202_ACCEPTED, tags=["Monitor"])
def run_monitor_background(background_tasks: BackgroundTasks) -> dict[str, str]:
    background_tasks.add_task(run_monitor_once)
    return {"status": "accepted"}


@app.post("/promotions/scan", response_model=MonitorRunResult, tags=["Promotions"])
def scan_promotions_now() -> MonitorRunResult:
    # A single monitor run scans stores and configured public promotion sources.
    return run_monitor()


@app.get("/settings", response_model=SettingsRead, tags=["Settings"])
def read_settings(db: Session = Depends(get_db)) -> SettingsRead:
    stores = list(db.scalars(select(Store).where(Store.active.is_(True)).order_by(Store.name)).all())
    return SettingsRead(
        check_interval=get_check_interval(db),
        telegram_configured=telegram_is_configured(),
        telegram_webhook_configured=bool(TELEGRAM_WEBHOOK_SECRET),
        whatsapp_webhook_configured=bool(
            WHATSAPP_VERIFY_TOKEN and WHATSAPP_APP_SECRET
        ),
        timezone=TIMEZONE,
        stores=[store.name for store in stores],
        alert_cooldown_seconds=ALERT_COOLDOWN_SECONDS,
        alert_best_offer=_setting_value(db, "alert_best_offer", "true").lower() == "true",
        scan_promotion_sources=_setting_value(db, "scan_promotion_sources", "true").lower() == "true",
        promotion_max_age_hours=int(_setting_value(db, "promotion_max_age_hours", "72")),
    )


@app.put("/settings", response_model=SettingsRead, tags=["Settings"])
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsRead:
    data = payload.model_dump(exclude_unset=True)
    if "check_interval" in data:
        _set_setting(db, "check_interval", str(data["check_interval"]))
    if "alert_best_offer" in data:
        _set_setting(db, "alert_best_offer", str(data["alert_best_offer"]).lower())
    if "scan_promotion_sources" in data:
        _set_setting(
            db,
            "scan_promotion_sources",
            str(data["scan_promotion_sources"]).lower(),
        )
    if "promotion_max_age_hours" in data:
        _set_setting(db, "promotion_max_age_hours", str(data["promotion_max_age_hours"]))
    db.commit()
    if payload.check_interval is not None:
        monitor_service.reschedule(payload.check_interval)
    return read_settings(db)
