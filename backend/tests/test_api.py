from __future__ import annotations

import hashlib
import hmac
import json


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_list_product(client):
    payload = {
        "name": "PlayStation 5 Pro",
        "search_query": "PlayStation 5 Pro",
        "target_price": 4500,
        "active": True,
    }
    created = client.post("/products", json=payload)
    assert created.status_code == 201
    assert created.json()["target_price"] == 4500

    products = client.get("/products")
    assert products.status_code == 200
    assert any(item["name"] == "PlayStation 5 Pro" for item in products.json())


def test_settings_update(client):
    response = client.put("/settings", json={"check_interval": 900})
    assert response.status_code == 200
    assert response.json()["check_interval"] == 900


def test_create_store_and_direct_product_url(client):
    product = client.post(
        "/products",
        json={
            "name": "Console de teste",
            "search_query": "console teste",
            "target_price": 2500,
            "active": True,
        },
    ).json()
    store_response = client.post(
        "/stores",
        json={
            "name": "Loja de Teste",
            "base_url": "https://example.com",
            "search_url": "https://example.com/search?q={query}",
            "active": True,
        },
    )
    assert store_response.status_code == 201
    store = store_response.json()

    link_response = client.post(
        "/product-links",
        json={
            "product_id": product["id"],
            "store_id": store["id"],
            "url": "https://example.com/produto/console",
            "active": True,
        },
    )
    assert link_response.status_code == 201
    assert link_response.json()["product_name"] == "Console de teste"
    assert link_response.json()["store_name"] == "Loja de Teste"


def test_create_public_promotion_source(client):
    response = client.post(
        "/promotion-sources",
        json={
            "name": "Canal público de teste",
            "source_type": "telegram_public",
            "url": "https://t.me/s/teste_publico",
            "product_id": None,
            "store_id": None,
            "keywords": "ps5, cupom",
            "active": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["source_type"] == "telegram_public"


def test_delete_endpoints_return_empty_204(client):
    product = client.post(
        "/products",
        json={
            "name": "Console removível",
            "search_query": "console removível",
            "target_price": 2500,
            "active": True,
        },
    ).json()
    store = client.post(
        "/stores",
        json={
            "name": "Loja removível",
            "base_url": "https://example.com",
            "search_url": "https://example.com/search?q={query}",
            "active": True,
        },
    ).json()
    link = client.post(
        "/product-links",
        json={
            "product_id": product["id"],
            "store_id": store["id"],
            "url": "https://example.com/console",
            "active": True,
        },
    ).json()
    source = client.post(
        "/promotion-sources",
        json={
            "name": "Fonte removível",
            "source_type": "web",
            "url": "https://example.com/promotions",
            "product_id": product["id"],
            "store_id": store["id"],
            "active": True,
        },
    ).json()

    for endpoint in (
        f"/product-links/{link['id']}",
        f"/promotion-sources/{source['id']}",
        f"/products/{product['id']}",
        f"/stores/{store['id']}",
    ):
        response = client.delete(endpoint)
        assert response.status_code == 204
        assert response.content == b""


def test_telegram_webhook_ingests_and_deduplicates_message(client):
    client.post(
        "/products",
        json={
            "name": "PlayStation 5 Slim Digital",
            "search_query": "PS5 Slim Digital",
            "target_price": 3100,
            "active": True,
        },
    )
    source = client.post(
        "/promotion-sources",
        json={
            "name": "Grupo Telegram autorizado",
            "source_type": "telegram_bot",
            "url": "",
            "external_id": "-1001234567890",
            "product_id": None,
            "store_id": None,
            "keywords": "PS5",
            "active": True,
        },
    )
    assert source.status_code == 201
    payload = {
        "update_id": 10,
        "message": {
            "message_id": 99,
            "chat": {"id": -1001234567890, "title": "Ofertas"},
            "text": "PS5 Slim Digital por R$ 3.099,00 no PIX. Cupom GAME200 com 5% de desconto.",
        },
    }
    headers = {"X-Telegram-Bot-Api-Secret-Token": "telegram-test-secret"}

    rejected = client.post(
        "/webhooks/telegram",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )
    first = client.post("/webhooks/telegram", json=payload, headers=headers)
    repeated = client.post("/webhooks/telegram", json=payload, headers=headers)

    assert rejected.status_code == 403
    assert first.status_code == 200
    assert first.json()["promotions"] == 1
    assert repeated.json()["promotions"] == 0
    promotions = client.get("/promotions").json()
    assert promotions[0]["coupon"] == "GAME200"
    assert promotions[0]["coupon_confidence"] >= 0.9


def test_whatsapp_webhook_verification_signature_and_ingestion(client):
    verified = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "whatsapp-verify-token",
            "hub.challenge": "challenge-123",
        },
    )
    assert verified.status_code == 200
    assert verified.text == "challenge-123"

    client.post(
        "/products",
        json={
            "name": "PlayStation 5 Slim Digital",
            "search_query": "PS5 Slim Digital",
            "target_price": 3100,
            "active": True,
        },
    )

    source = client.post(
        "/promotion-sources",
        json={
            "name": "WhatsApp autorizado",
            "source_type": "whatsapp_cloud",
            "url": "",
            "external_id": "5511999999999",
            "product_id": None,
            "store_id": None,
            "keywords": "PS5",
            "active": True,
        },
    )
    assert source.status_code == 201
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "business-number"},
                            "messages": [
                                {
                                    "id": "wamid.message-1",
                                    "from": "5511999999999",
                                    "type": "text",
                                    "text": {
                                        "body": "PS5 Slim Digital por R$ 2.999,00. Use o cupom ZAP100 para 10% de desconto."
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = "sha256=" + hmac.new(
        b"whatsapp-app-secret", body, hashlib.sha256
    ).hexdigest()
    response = client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )
    rejected = client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=invalid",
        },
    )

    assert response.status_code == 200
    assert response.json()["promotions"] == 1
    assert rejected.status_code == 403
