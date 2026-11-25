from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from drip.api.v1 import outfits as api
from drip.catalog.abuse import require_public_catalog_rate_limit
from drip.core.config import settings
from drip.outfit.contracts import OutfitDraftInput
from drip.outfit.service import OutfitCursor, decode_cursor, encode_cursor, public_outfit
from httpx import ASGITransport, AsyncClient


def _outfit(**overrides):
    values = {
        "id": uuid4(),
        "brand": SimpleNamespace(id=uuid4(), display_name="Test-only brand", status="active"),
        "title": "Test-only editorial record",
        "caption": "Synthetic integration fixture",
        "image_url": "https://media.example/editorial.jpg",
        "image_alt": "Test-only editorial image",
        "rights_ref": "test-rights-ref",
        "approval_ref": "test-approval-ref",
        "status": "published",
        "published_at": datetime(2026, 11, 20, tzinfo=UTC),
        "items": [SimpleNamespace(position=1, product_id=uuid4()), SimpleNamespace(position=2, product_id=uuid4())],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _public_product(product_id):
    variant_id = UUID(int=(product_id.int + 1) % (1 << 128) or 1)
    return SimpleNamespace(
        id=product_id,
        title="Test-only product",
        listings=[SimpleNamespace(variants=[SimpleNamespace(
            id=variant_id, image_url="https://media.example/product.jpg", image_alt="Test-only product image",
        )])],
    )


def _eligible_product(product_id):
    return SimpleNamespace(representative={"variant_id": _public_product(product_id).listings[0].variants[0].id})


def test_outfit_cursor_is_signed_and_tampering_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "test-only-secret-key-that-is-at-least-32-characters")
    cursor = OutfitCursor(datetime(2026, 11, 20, tzinfo=UTC), uuid4())
    token = encode_cursor(cursor)
    assert decode_cursor(token) == cursor
    with pytest.raises(ValueError, match="Invalid OOTD cursor"):
        decode_cursor(token[:-1] + ("A" if token[-1] != "A" else "B"))


@pytest.mark.asyncio
async def test_public_outfit_includes_only_public_product_projection(monkeypatch):
    import drip.outfit.service as service

    outfit = _outfit(secret="must-not-leak")
    # Async service dependency is replaced with an async test double.
    async def detail(_session, product_id):
        return _public_product(product_id)

    async def eligible(_session, *, product_id, limit):
        assert limit == 1
        return ([_eligible_product(product_id)], None)

    monkeypatch.setattr(service, "product_detail", detail)
    monkeypatch.setattr(service, "eligible_product_page", eligible)
    result = await public_outfit(object(), outfit)
    assert result is not None
    payload = result.model_dump(mode="json")
    assert set(payload) == {"id", "title", "caption", "brand", "image", "products"}
    assert len(payload["products"]) == 2
    assert "secret" not in str(payload).lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "draft"},
        {"published_at": None},
        {"rights_ref": " "},
        {"approval_ref": " "},
        {"items": [SimpleNamespace(position=1, product_id=uuid4())]},
        {"image_url": "http://media.example/editorial.jpg"},
        {"image_url": "https://user@media.example/editorial.jpg"},
    ],
)
async def test_ineligible_outfit_is_suppressed(monkeypatch, overrides):
    import drip.outfit.service as service

    async def unexpected_product_read(*_args):
        pytest.fail("Suppressed outfit must not read or expose product records.")

    monkeypatch.setattr(service, "product_detail", unexpected_product_read)
    async def unexpected_eligibility_read(*_args, **_kwargs):
        pytest.fail("Suppressed outfit must not query component products.")

    monkeypatch.setattr(service, "eligible_product_page", unexpected_eligibility_read)
    assert await public_outfit(object(), _outfit(**overrides)) is None


@pytest.mark.asyncio
async def test_outfit_is_suppressed_if_any_component_is_not_public(monkeypatch):
    import drip.outfit.service as service

    call_count = 0

    async def detail(_session, product_id):
        nonlocal call_count
        call_count += 1
        return _public_product(product_id) if call_count == 1 else None

    async def eligible(_session, *, product_id, limit):
        return ([_eligible_product(product_id)], None)

    monkeypatch.setattr(service, "product_detail", detail)
    monkeypatch.setattr(service, "eligible_product_page", eligible)
    assert await public_outfit(object(), _outfit()) is None


@pytest.mark.asyncio
async def test_outfit_is_suppressed_if_any_component_is_no_longer_eligible(monkeypatch):
    import drip.outfit.service as service

    async def eligible(_session, *, product_id, limit):
        return ([_eligible_product(product_id)], None) if limit == 1 and product_id == outfit.items[0].product_id else ([], None)

    async def detail(_session, product_id):
        return _public_product(product_id)

    outfit = _outfit()
    monkeypatch.setattr(service, "eligible_product_page", eligible)
    monkeypatch.setattr(service, "product_detail", detail)
    assert await public_outfit(object(), outfit) is None


@pytest.mark.asyncio
async def test_ootd_route_uses_signed_cursor_and_redacts_invalid_cursor(monkeypatch):
    from drip.core.database import get_db_session
    from drip.main import create_app

    app = create_app()

    async def session():
        yield object()

    async def allow_rate_limit():
        return None

    async def page(_session, *, limit, cursor):
        assert limit == 5
        return [], None

    monkeypatch.setattr(api, "list_public_outfits", page)
    app.dependency_overrides[get_db_session] = session
    app.dependency_overrides[require_public_catalog_rate_limit] = allow_rate_limit
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/ootd")
            assert response.status_code == 200
            assert response.json() == {"items": [], "next_cursor": None}
            assert response.headers["cache-control"] == "no-store"

            invalid = await client.get("/api/v1/ootd", params={"cursor": "sensitive-input"})
            assert invalid.status_code == 422
            assert "sensitive-input" not in invalid.text
            assert invalid.json()["code"] == "INVALID_CURSOR"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ootd_detail_returns_only_public_projection_and_hides_ineligible_records(monkeypatch):
    from drip.core.database import get_db_session
    from drip.main import create_app

    app = create_app()
    outfit = _outfit(secret="must-not-leak")

    async def session():
        yield object()

    async def allow_rate_limit():
        return None

    async def public(_session, outfit_id):
        assert outfit_id == outfit.id
        from drip.outfit.contracts import PublicOutfit, OutfitImage, OutfitProduct

        return PublicOutfit(
            id=outfit.id,
            title=outfit.title,
            caption=outfit.caption,
            brand={"id": outfit.brand.id, "name": outfit.brand.display_name},
            image=OutfitImage(url=outfit.image_url, alt=outfit.image_alt),
            products=[
                OutfitProduct(id=item.product_id, title="Public piece", image=OutfitImage(
                    url="https://media.example/piece.jpg", alt="Public piece image"
                ))
                for item in outfit.items
            ],
        )

    monkeypatch.setattr(api, "get_public_outfit", public)
    app.dependency_overrides[get_db_session] = session
    app.dependency_overrides[require_public_catalog_rate_limit] = allow_rate_limit
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/ootd/{outfit.id}")
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            assert set(response.json()) == {"id", "title", "caption", "brand", "image", "products"}
            assert "rights_ref" not in response.text
            assert "approval_ref" not in response.text

            async def hidden(_session, _outfit_id):
                return None

            monkeypatch.setattr(api, "get_public_outfit", hidden)
            missing = await client.get(f"/api/v1/ootd/{uuid4()}")
            assert missing.status_code == 404
            assert "must-not-leak" not in missing.text
    finally:
        app.dependency_overrides.clear()


def test_ootd_endpoint_is_in_openapi():
    from drip.main import create_app

    app = create_app()
    operation = app.openapi()["paths"]["/api/v1/ootd"]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("OutfitPage")
    assert "/api/v1/admin/ootd" in app.openapi()["paths"]
    assert "/api/v1/ootd/{outfit_id}" in app.openapi()["paths"]


def test_outfit_draft_contract_rejects_duplicate_or_malformed_components():
    product_id = uuid4()
    base = {
        "title": "Editorial draft",
        "brand_id": str(uuid4()),
        "image_url": "https://media.example/editorial.jpg",
        "image_alt": "Editorial image",
        "rights_ref": "rights-review-reference",
        "approval_ref": "editorial-review-reference",
    }
    assert OutfitDraftInput.model_validate(base).product_ids == []
    with pytest.raises(ValueError):
        OutfitDraftInput.model_validate({**base, "product_ids": [str(product_id), str(product_id)]})
    with pytest.raises(ValueError):
        OutfitDraftInput.model_validate({**base, "unexpected": "must be rejected"})


@pytest.mark.asyncio
async def test_admin_outfit_mutations_fail_closed_without_configured_authority():
    from drip.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/admin/ootd", json={
            "title": "No persisted content",
            "brand_id": str(uuid4()),
            "image_url": "https://media.example/editorial.jpg",
            "image_alt": "Editorial image",
            "rights_ref": "unapproved",
            "approval_ref": "unapproved",
            "product_ids": [],
        })
    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    assert "unapproved" not in response.text
