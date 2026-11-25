from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from drip.api.v1 import catalog as catalog_api
from drip.catalog.abuse import require_public_catalog_rate_limit
from drip.catalog.contracts import DiscoveryRequest, MoneyDTO, ProductCard, PublicPrice
from drip.catalog.discovery_cursor import (
    decode_discovery_cursor,
    encode_discovery_cursor,
)
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError


def test_discovery_request_limits_to_one_card_and_normalizes_filters() -> None:
    request = DiscoveryRequest.model_validate({"q": "  coat ", "category": [" outerwear "]})
    assert request.limit == 1
    assert request.q == "coat"
    assert request.category == ["outerwear"]
    assert request.normalized_filters()["category"] == ["outerwear"]


@pytest.mark.parametrize(
    "body",
    [
        {"limit": 2},
        {"category": ["one", "one"]},
        {"min_price_minor": "9", "max_price_minor": "8"},
        {"cursor": "invalid", "intent": "next", "category": ["changed"]},
        {"cursor": "invalid", "intent": "similar"},
        {"unrecognized": True},
    ],
)
def test_discovery_request_rejects_invalid_or_mixed_state(body: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DiscoveryRequest.model_validate(body)


def test_discovery_cursor_is_signed_expiring_and_filter_bound() -> None:
    filters = {"q": "coat", "brand_id": [], "category": [], "color": [], "size": [],
               "min_price_minor": None, "max_price_minor": None, "limit": 1}
    product_id = uuid4()
    token = encode_discovery_cursor(
        filters, [product_id], product_id, mode="similar", anchor_id=product_id
    )
    decoded = decode_discovery_cursor(token, filters)
    assert decoded.seen_ids == (product_id,)
    assert decoded.last_id == product_id
    assert decoded.mode == "similar"
    assert decoded.anchor_id == product_id
    with pytest.raises(ValueError, match="Invalid discovery cursor"):
        decode_discovery_cursor(token, {**filters, "q": "shoe"})
    with pytest.raises(ValueError, match="Invalid discovery cursor"):
        decode_discovery_cursor(token[:-1] + ("A" if token[-1] != "A" else "B"))


def test_catalog_cursor_rejects_noncanonical_base64_aliases() -> None:
    from drip.catalog.pagination import decode_cursor, encode_cursor

    token = encode_cursor(uuid4(), "f" * 64)
    last = token[-1]
    replacement = "A" if last != "A" else "B"
    with pytest.raises(ValueError, match="Invalid catalog cursor"):
        decode_cursor(token[:-1] + replacement, "f" * 64)


def test_discovery_cursor_rejects_expired_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    import drip.catalog.discovery_cursor as cursor_module

    monkeypatch.setattr(cursor_module, "time", type("Clock", (), {"time": staticmethod(lambda: 1000)})())
    filters = {"limit": 1}
    token = encode_discovery_cursor(filters, [], None)
    monkeypatch.setattr(cursor_module, "time", type("Clock", (), {"time": staticmethod(lambda: 2000)})())
    with pytest.raises(TimeoutError):
        decode_discovery_cursor(token)


def test_cursor_rejects_more_than_two_hundred_seen_ids() -> None:
    ids = [UUID(int=value + 1) for value in range(201)]
    with pytest.raises(ValueError):
        encode_discovery_cursor({"limit": 1}, ids, None)


def test_maximum_seen_cursor_stays_within_documented_size() -> None:
    ids = [UUID(int=value + 1) for value in range(200)]
    token = encode_discovery_cursor({"limit": 1}, ids, ids[-1])
    assert len(token) <= 24 * 1024


def test_card_contract_keeps_exact_minor_units_and_one_item() -> None:
    card = ProductCard(
        id=uuid4(), brand={"id": uuid4(), "name": "Test brand"}, title="Test item",
        category_code="test", image={"url": "https://images.example/item", "alt": "Item"},
        representative={"listing_id": uuid4(), "variant_id": uuid4()},
        price=PublicPrice(money=MoneyDTO(amount_minor="9007199254740993"),
                          observed_at="2026-11-19T00:00:00Z", valid_until="2026-11-20T00:00:00Z"),
        price_is_from=False, inventory=None,
    )
    assert card.model_dump(mode="json")["price"]["money"]["amount_minor"] == "9007199254740993"


def _card(product_id: UUID) -> ProductCard:
    return ProductCard(
        id=product_id, brand={"id": uuid4(), "name": "Test brand"}, title="Test item",
        category_code="test", image={"url": "https://images.example/item", "alt": "Item"},
        representative={"listing_id": uuid4(), "variant_id": uuid4()},
        price=PublicPrice(money=MoneyDTO(amount_minor="1000"),
                          observed_at="2026-11-19T00:00:00Z", valid_until="2026-11-20T00:00:00Z"),
        price_is_from=False, inventory=None,
    )


@pytest.mark.asyncio
async def test_discovery_route_returns_one_card_and_continues_signed_chain(app, monkeypatch) -> None:
    from drip.core.database import get_db_session

    calls: list[dict[str, object]] = []
    first, second = _card(uuid4()), _card(uuid4())

    async def page(_session, **kwargs):
        calls.append({**kwargs, "exclude_ids": list(kwargs.get("exclude_ids", []))})
        return ([first], first.id) if len(calls) == 1 else ([second], None)

    async def read_session():
        yield object()

    async def allow_rate_limit():
        return None

    monkeypatch.setattr(catalog_api, "eligible_product_page", page)
    app.dependency_overrides[get_db_session] = read_session
    app.dependency_overrides[require_public_catalog_rate_limit] = allow_rate_limit
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            initial = await client.post("/api/v1/discover", json={"q": " test "})
            assert initial.status_code == 200
            payload = initial.json()
            assert len(payload["items"]) == 1
            assert payload["items"][0]["id"] == str(first.id)
            assert payload["next_cursor"]
            assert initial.headers["cache-control"] == "no-store"

            continued = await client.post("/api/v1/discover", json={
                "cursor": payload["next_cursor"], "intent": "next",
            })
            assert continued.status_code == 200
            assert continued.json()["items"][0]["id"] == str(second.id)
            assert calls[1]["after_id"] == first.id
            assert calls[1]["exclude_ids"] == [first.id]
            assert calls[1]["query"] == "test"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mixed_filter_cursor_is_rejected_with_fixed_error(app) -> None:
    from drip.core.database import get_db_session

    async def read_session():
        yield object()

    app.dependency_overrides[get_db_session] = read_session
    app.dependency_overrides[require_public_catalog_rate_limit] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/discover", json={
                "cursor": "opaque-invalid-cursor", "intent": "next", "q": "secret search",
            })
        assert response.status_code == 422
        assert response.json()["code"] == "INVALID_CURSOR"
        assert "secret search" not in response.text
        assert response.headers["cache-control"] == "no-store"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_mutation_fails_closed_without_configured_authority(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/admin/catalog/brands", json={
            "slug": "review-only", "display_name": "Review only", "source_ref": "test-only",
        })
    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    assert "authorized" not in response.text.lower()


@pytest.mark.asyncio
async def test_discovery_route_rejects_oversize_and_non_json_before_dependencies(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unsupported = await client.post("/api/v1/discover", content="{}", headers={"content-type": "text/plain"})
        oversized = await client.post("/api/v1/discover", content=b" " * (32 * 1024 + 1), headers={"content-type": "application/json"})
    assert unsupported.status_code == 415
    assert unsupported.json()["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert oversized.status_code == 413
    assert oversized.json()["code"] == "REQUEST_TOO_LARGE"


def test_discovery_request_is_present_in_openapi() -> None:
    from drip.main import create_app

    operation = create_app().openapi()["paths"]["/api/v1/discover"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["title"] == "DiscoveryRequest"
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("DiscoveryPage")


@pytest.mark.asyncio
async def test_relation_intents_use_anchor_constraints_and_restart_seen_traversal(app, monkeypatch) -> None:
    from drip.core.database import get_db_session

    first, second = _card(uuid4()), _card(uuid4())
    calls: list[dict[str, object]] = []

    async def page(_session, **kwargs):
        calls.append({**kwargs, "exclude_ids": list(kwargs.get("exclude_ids", []))})
        if kwargs.get("product_id") is not None:
            return [first], None
        return ([first], first.id) if len(calls) == 1 else ([second], second.id)

    async def detail(_session, _product_id):
        return SimpleNamespace(
            brand={"id": first.brand["id"]}, category_code=first.category_code,
            listings=[SimpleNamespace(variants=[SimpleNamespace(
                id=first.representative["variant_id"], color_label="navy",
            )])],
        )

    async def read_session():
        yield object()

    async def allow_rate_limit():
        return None

    monkeypatch.setattr(catalog_api, "eligible_product_page", page)
    monkeypatch.setattr(catalog_api, "product_detail", detail)
    app.dependency_overrides[get_db_session] = read_session
    app.dependency_overrides[require_public_catalog_rate_limit] = allow_rate_limit
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            initial = await client.post("/api/v1/discover", json={})
            cursor = initial.json()["next_cursor"]
            similar = await client.post("/api/v1/discover", json={
                "cursor": cursor, "intent": "similar", "anchor_product_id": str(first.id),
            })
            assert similar.status_code == 200
            assert calls[2]["categories"] == [first.category_code]
            assert calls[2]["colors"] == ["navy"]
            assert calls[2]["after_id"] is None

            different = await client.post("/api/v1/discover", json={
                "cursor": cursor, "intent": "different_brand", "anchor_product_id": str(first.id),
            })
            assert different.status_code == 200
            assert calls[4]["exclude_brand_id"] == first.brand["id"]
            assert calls[4]["after_id"] is None
            assert calls[4]["exclude_ids"] == [first.id]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_empty_relation_page_cursor_preserves_search_intent(app, monkeypatch) -> None:
    from drip.core.database import get_db_session

    first, second = _card(uuid4()), _card(uuid4())
    scanned_to = uuid4()
    calls: list[dict[str, object]] = []
    relation_requests = 0

    async def page(_session, **kwargs):
        nonlocal relation_requests
        calls.append({**kwargs, "exclude_ids": list(kwargs.get("exclude_ids", []))})
        if kwargs.get("product_id") is not None:
            return [first], None
        if kwargs.get("exclude_ids") == []:
            return [first], first.id
        relation_requests += 1
        if relation_requests == 1:
            return [], scanned_to
        return [second], None

    async def detail(_session, _product_id):
        return SimpleNamespace(
            brand={"id": first.brand["id"]}, category_code=first.category_code,
            listings=[SimpleNamespace(variants=[SimpleNamespace(
                id=first.representative["variant_id"], color_label="navy",
            )])],
        )

    async def read_session():
        yield object()

    async def allow_rate_limit():
        return None

    monkeypatch.setattr(catalog_api, "eligible_product_page", page)
    monkeypatch.setattr(catalog_api, "product_detail", detail)
    app.dependency_overrides[get_db_session] = read_session
    app.dependency_overrides[require_public_catalog_rate_limit] = allow_rate_limit
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            initial = await client.post("/api/v1/discover", json={})
            cursor = initial.json()["next_cursor"]
            empty = await client.post("/api/v1/discover", json={
                "cursor": cursor, "intent": "similar", "anchor_product_id": str(first.id),
            })
            assert empty.status_code == 200
            assert empty.json()["items"] == []
            assert empty.json()["next_cursor"]

            continued = await client.post("/api/v1/discover", json={
                "cursor": empty.json()["next_cursor"], "intent": "next",
            })
            assert continued.status_code == 200
            assert continued.json()["items"][0]["id"] == str(second.id)
            assert calls[2]["after_id"] is None
            assert calls[4]["after_id"] == scanned_to
            assert calls[4]["categories"] == [first.category_code]
            assert calls[4]["colors"] == ["navy"]
    finally:
        app.dependency_overrides.clear()
