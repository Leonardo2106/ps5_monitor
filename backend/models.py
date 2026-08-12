"""SQLAlchemy ORM models for products, stores, prices and promotions."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.sqlite import REAL
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from .database import Base
except ImportError:
    from database import Base


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Price(Base):
    """Historical price record.

    The original requested columns are preserved. Extra nullable columns keep the
    page URL, cash price, installments and coupon details.
    """

    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    store: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    product: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    price: Mapped[float] = mapped_column(REAL, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    cash_price: Mapped[float | None] = mapped_column(REAL, nullable=True)
    installment_price: Mapped[float | None] = mapped_column(REAL, nullable=True)
    installment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coupon: Mapped[str | None] = mapped_column(String(120), nullable=True)
    coupon_discount: Mapped[str | None] = mapped_column(String(120), nullable=True)
    coupon_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    coupon_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="store")


class Product(Base):
    """Configurable product monitored by the system."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    search_query: Mapped[str] = mapped_column(String(220), nullable=False)
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(String(40), default=utc_now_iso)

    direct_links: Mapped[list[ProductStoreLink]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class Store(Base):
    """Built-in or user-created retailer configuration."""

    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    search_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    card_selectors: Mapped[str | None] = mapped_column(Text, nullable=True)
    title_selectors: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_selectors: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_selectors: Mapped[str | None] = mapped_column(Text, nullable=True)
    cash_selectors: Mapped[str | None] = mapped_column(Text, nullable=True)
    installment_selectors: Mapped[str | None] = mapped_column(Text, nullable=True)
    coupon_selectors: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=utc_now_iso)

    direct_links: Mapped[list[ProductStoreLink]] = relationship(
        back_populates="store", cascade="all, delete-orphan"
    )


class ProductStoreLink(Base):
    """Optional direct product URL for one product/store pair."""

    __tablename__ = "product_store_links"
    __table_args__ = (UniqueConstraint("product_id", "store_id", name="uq_product_store"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[int] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(1500), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(String(40), default=utc_now_iso)

    product: Mapped[Product] = relationship(back_populates="direct_links")
    store: Mapped[Store] = relationship(back_populates="direct_links")


class PromotionSource(Base):
    """Public promotion page or public Telegram channel preview to scan."""

    __tablename__ = "promotion_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="web")
    url: Mapped[str] = mapped_column(String(1500), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    store_id: Mapped[int | None] = mapped_column(
        ForeignKey("stores.id", ondelete="SET NULL"), nullable=True, index=True
    )
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(String(40), default=utc_now_iso)


class Promotion(Base):
    """Promotion/coupon discovered from a configured public source."""

    __tablename__ = "promotions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    store: Mapped[str | None] = mapped_column(String(120), nullable=True)
    product: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[float] = mapped_column(REAL, nullable=False)
    cash_price: Mapped[float | None] = mapped_column(REAL, nullable=True)
    installment_price: Mapped[float | None] = mapped_column(REAL, nullable=True)
    installment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coupon: Mapped[str | None] = mapped_column(String(120), nullable=True)
    coupon_discount: Mapped[str | None] = mapped_column(String(120), nullable=True)
    coupon_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    coupon_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    url: Mapped[str] = mapped_column(String(1500), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class ReceivedMessage(Base):
    """Deduplication record for webhook messages and edited messages."""

    __tablename__ = "received_messages"
    __table_args__ = (
        UniqueConstraint("source_id", "external_message_id", name="uq_source_message"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("promotion_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_message_id: Mapped[str] = mapped_column(String(200), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[str] = mapped_column(String(40), default=utc_now_iso)


class AlertEvent(Base):
    """Notification audit and exact de-duplication record."""

    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    store: Mapped[str] = mapped_column(String(120), nullable=False)
    product: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False, default="telegram")
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="best_offer")
    cash_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    installment_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    installment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coupon: Mapped[str | None] = mapped_column(String(120), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)


class AppSetting(Base):
    """Small persistent key/value configuration table."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
