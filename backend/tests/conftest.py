from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

RUNTIME_DB = Path("/tmp/ps5_monitor_runtime_test.db")
os.environ["DATABASE_PATH"] = str(RUNTIME_DB)
os.environ["START_MONITOR_WITH_API"] = "false"
os.environ["TELEGRAM_TOKEN"] = "SEU_TOKEN"
os.environ["CHAT_ID"] = "SEU_CHAT_ID"
os.environ["TELEGRAM_WEBHOOK_SECRET"] = "telegram-test-secret"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "whatsapp-verify-token"
os.environ["WHATSAPP_APP_SECRET"] = "whatsapp-app-secret"

from backend.database import Base, get_db  # noqa: E402
from backend.main import app  # noqa: E402


test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_engine():
    return test_engine


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
