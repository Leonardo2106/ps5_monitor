"""Database engine, sessions, lightweight SQLite migrations and seeds."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

try:
    from .config import CHECK_INTERVAL, DATABASE_URL, DIGITAL_TARGET, DISK_TARGET
except ImportError:
    from config import CHECK_INTERVAL, DATABASE_URL, DIGITAL_TARGET, DISK_TARGET


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_missing_columns() -> None:
    """Add nullable columns to databases created by older project versions."""
    migrations: dict[str, dict[str, str]] = {
        "prices": {
            "title": "TEXT",
            "url": "TEXT",
            "cash_price": "REAL",
            "installment_price": "REAL",
            "installment_count": "INTEGER",
            "coupon": "VARCHAR(120)",
            "coupon_discount": "VARCHAR(120)",
            "coupon_conditions": "TEXT",
            "coupon_confidence": "REAL",
            "source_type": "VARCHAR(40) NOT NULL DEFAULT 'store'",
        },
        "promotions": {
            "coupon_conditions": "TEXT",
            "coupon_confidence": "REAL",
        },
        "promotion_sources": {
            "external_id": "VARCHAR(160)",
        },
        "alert_events": {
            "fingerprint": "VARCHAR(64)",
            "kind": "VARCHAR(40) NOT NULL DEFAULT 'best_offer'",
            "cash_price": "REAL",
            "installment_price": "REAL",
            "installment_count": "INTEGER",
            "coupon": "VARCHAR(120)",
            "url": "TEXT",
        },
    }

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table_name, columns in migrations.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for column_name, definition in columns.items():
                if column_name not in existing_columns:
                    connection.execute(
                        text(
                            f'ALTER TABLE "{table_name}" '
                            f'ADD COLUMN "{column_name}" {definition}'
                        )
                    )
        if "alert_events" in existing_tables:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "ix_alert_events_fingerprint_unique "
                    "ON alert_events(fingerprint) WHERE fingerprint IS NOT NULL"
                )
            )
        if "promotion_sources" in existing_tables:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_promotion_sources_external_id "
                    "ON promotion_sources(external_id)"
                )
            )


def _setting(db: Session, key: str, default: str) -> None:
    try:
        from .models import AppSetting
    except ImportError:
        from models import AppSetting

    if db.get(AppSetting, key) is None:
        db.add(AppSetting(key=key, value=default))


def init_db() -> None:
    """Create/migrate tables and seed products, stores and settings."""
    try:
        from .models import Product, Store
        from .scraper import builtin_store_payloads
    except ImportError:
        from models import Product, Store
        from scraper import builtin_store_payloads

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()

    with SessionLocal() as db:
        existing_names = set(db.scalars(select(Product.name)).all())
        defaults = [
            Product(
                name="PlayStation 5 Slim Digital",
                search_query="PlayStation 5 Slim Digital",
                target_price=DIGITAL_TARGET,
                active=True,
            ),
            Product(
                name="PlayStation 5 Slim com Leitor de Disco",
                search_query="PlayStation 5 Slim leitor disco",
                target_price=DISK_TARGET,
                active=True,
            ),
        ]
        for product in defaults:
            if product.name not in existing_names:
                db.add(product)

        existing_stores = {
            store.name: store for store in db.scalars(select(Store)).all()
        }
        for payload in builtin_store_payloads():
            current = existing_stores.get(payload["name"])
            if current is None:
                db.add(Store(**payload, is_builtin=True, active=True))
            elif current.is_builtin:
                for key, value in payload.items():
                    setattr(current, key, value)

        _setting(db, "check_interval", str(CHECK_INTERVAL))
        _setting(db, "alert_best_offer", "true")
        _setting(db, "scan_promotion_sources", "true")
        _setting(db, "promotion_max_age_hours", "72")
        db.commit()
