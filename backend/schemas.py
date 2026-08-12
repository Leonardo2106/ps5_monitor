"""Pydantic request and response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PromotionSourceType = Literal["web", "telegram_public", "telegram_bot", "whatsapp_cloud"]


class ProductBase(BaseModel):
    name: str = Field(min_length=3, max_length=180)
    search_query: str = Field(min_length=2, max_length=220)
    target_price: float = Field(gt=0)
    active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=180)
    search_query: str | None = Field(default=None, min_length=2, max_length=220)
    target_price: float | None = Field(default=None, gt=0)
    active: bool | None = None


class ProductRead(ProductBase):
    id: int
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class StoreBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    base_url: str = Field(min_length=8, max_length=500)
    search_url: str = Field(min_length=8, max_length=1000)
    active: bool = True
    card_selectors: str | None = None
    title_selectors: str | None = None
    price_selectors: str | None = None
    link_selectors: str | None = None
    cash_selectors: str | None = None
    installment_selectors: str | None = None
    coupon_selectors: str | None = None

    @field_validator("base_url", "search_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("A URL deve começar com http:// ou https://")
        return value.strip()


class StoreCreate(StoreBase):
    pass


class StoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    base_url: str | None = Field(default=None, min_length=8, max_length=500)
    search_url: str | None = Field(default=None, min_length=8, max_length=1000)

    @field_validator("base_url", "search_url")
    @classmethod
    def validate_optional_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("http://", "https://")):
            raise ValueError("A URL deve começar com http:// ou https://")
        return value.strip() if value else value
    active: bool | None = None
    card_selectors: str | None = None
    title_selectors: str | None = None
    price_selectors: str | None = None
    link_selectors: str | None = None
    cash_selectors: str | None = None
    installment_selectors: str | None = None
    coupon_selectors: str | None = None


class StoreRead(StoreBase):
    id: int
    is_builtin: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class ProductStoreLinkCreate(BaseModel):
    product_id: int = Field(gt=0)
    store_id: int = Field(gt=0)
    url: str = Field(min_length=8, max_length=1500)
    active: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("A URL deve começar com http:// ou https://")
        return value.strip()


class ProductStoreLinkUpdate(BaseModel):
    url: str | None = Field(default=None, min_length=8, max_length=1500)
    active: bool | None = None

    @field_validator("url")
    @classmethod
    def validate_optional_url(cls, value: str | None) -> str | None:
        if value and not value.startswith(("http://", "https://")):
            raise ValueError("A URL deve começar com http:// ou https://")
        return value.strip() if value else value


class ProductStoreLinkRead(BaseModel):
    id: int
    product_id: int
    product_name: str
    store_id: int
    store_name: str
    url: str
    active: bool
    created_at: str


class PriceRead(BaseModel):
    id: int
    date: str
    store: str
    product: str
    price: float
    title: str | None = None
    url: str | None = None
    cash_price: float | None = None
    installment_price: float | None = None
    installment_count: int | None = None
    coupon: str | None = None
    coupon_discount: str | None = None
    coupon_conditions: str | None = None
    coupon_confidence: float | None = None
    source_type: str = "store"

    model_config = ConfigDict(from_attributes=True)


class BestOffer(BaseModel):
    product: str
    store: str
    price: float
    cash_price: float | None = None
    installment_price: float | None = None
    installment_count: int | None = None
    coupon: str | None = None
    coupon_discount: str | None = None
    coupon_conditions: str | None = None
    coupon_confidence: float | None = None
    title: str | None = None
    date: str
    url: str | None = None
    source_type: str = "store"


class ProductStats(BaseModel):
    product_id: int
    product: str
    last_price: float | None
    minimum_price: float | None
    best_store: str | None
    last_update: str | None
    target_price: float
    samples: int


class StatsResponse(BaseModel):
    products: list[ProductStats]
    last_update: str | None


class PromotionSourceBase(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    source_type: PromotionSourceType = "web"
    url: str = Field(default="", max_length=1500)
    external_id: str | None = Field(default=None, max_length=160)
    product_id: int | None = Field(default=None, gt=0)
    store_id: int | None = Field(default=None, gt=0)
    keywords: str | None = Field(default=None, max_length=1000)
    active: bool = True

    @model_validator(mode="after")
    def validate_connection(self) -> "PromotionSourceBase":
        self.url = self.url.strip()
        self.external_id = self.external_id.strip() if self.external_id else None
        if self.source_type in {"web", "telegram_public"}:
            if not self.url.startswith(("http://", "https://")):
                raise ValueError("Fontes web devem ter uma URL HTTP ou HTTPS.")
        elif not self.external_id:
            raise ValueError("Fontes via webhook devem informar o ID externo do chat.")
        return self

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return value.strip()


class PromotionSourceCreate(PromotionSourceBase):
    pass


class PromotionSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    source_type: PromotionSourceType | None = None
    url: str | None = Field(default=None, max_length=1500)
    external_id: str | None = Field(default=None, max_length=160)

    @field_validator("url")
    @classmethod
    def validate_optional_url(cls, value: str | None) -> str | None:
        if value and not value.startswith(("http://", "https://")):
            raise ValueError("A URL deve começar com http:// ou https://")
        return value.strip() if value else value
    product_id: int | None = Field(default=None, gt=0)
    store_id: int | None = Field(default=None, gt=0)
    keywords: str | None = Field(default=None, max_length=1000)
    active: bool | None = None


class PromotionSourceRead(PromotionSourceBase):
    id: int
    created_at: str
    product_name: str | None = None
    store_name: str | None = None


class PromotionRead(BaseModel):
    id: int
    date: str
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

    model_config = ConfigDict(from_attributes=True)


class TelegramTestRequest(BaseModel):
    message: str = "✅ Teste do monitor de preços do PS5 realizado com sucesso."
    url: str | None = None


class TelegramResult(BaseModel):
    success: bool
    detail: str


class MonitorRunResult(BaseModel):
    success: bool
    collected: int
    errors: int
    alerts: int
    promotions: int = 0


class SettingsRead(BaseModel):
    check_interval: int
    telegram_configured: bool
    telegram_webhook_configured: bool
    whatsapp_webhook_configured: bool
    timezone: str
    stores: list[str]
    alert_cooldown_seconds: int
    alert_best_offer: bool
    scan_promotion_sources: bool
    promotion_max_age_hours: int


class SettingsUpdate(BaseModel):
    check_interval: int | None = Field(default=None, ge=60, le=86400)
    alert_best_offer: bool | None = None
    scan_promotion_sources: bool | None = None
    promotion_max_age_hours: int | None = Field(default=None, ge=1, le=720)
