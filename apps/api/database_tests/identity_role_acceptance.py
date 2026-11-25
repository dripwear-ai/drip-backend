from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

API_ROOT = Path(__file__).resolve().parents[1]
class RedactedTestSecret:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "RedactedTestSecret(<redacted>)"


async def migrate_as_migrator(database_url: str | URL, revision: str) -> None:
    """Run Alembic through a connection authenticated as the migrator role."""
    engine = create_async_engine(make_url(database_url), poolclass=NullPool)
    try:
        # Keep Alembic's DDL and version update inside an explicit transaction
        # that this helper commits. A prior role-attestation SELECT on a plain
        # ``connect()`` autobegins a transaction; disposing that connection
        # after Alembic then silently rolls back otherwise successful DDL.
        async with engine.begin() as connection:
            assert await connection.scalar(text("SELECT current_user")) == "drip_identity_migrator"

            def run(sync_connection) -> None:
                config = Config(str(API_ROOT / "alembic.ini"))
                config.attributes["connection"] = sync_connection
                config.attributes["version_table_schema"] = "public"
                command.upgrade(config, revision)

            await connection.run_sync(run)
    finally:
        await engine.dispose()


async def verify_identity_foundation(
    admin_url: str | URL, runtime_url: str | URL, migrator_url: str | URL
) -> None:
    admin = create_async_engine(make_url(admin_url), poolclass=NullPool)
    runtime = create_async_engine(make_url(runtime_url), poolclass=NullPool)
    try:
        async with admin.connect() as connection:
            relation_rows = (
                await connection.execute(
                    text(
                        """SELECT c.relname, owner.rolname AS owner, c.relrowsecurity,
                                  c.relforcerowsecurity
                           FROM pg_catalog.pg_class AS c
                           JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
                           JOIN pg_catalog.pg_roles AS owner ON owner.oid = c.relowner
                           WHERE n.nspname = 'drip_identity' AND c.relkind = 'r'
                           ORDER BY c.relname"""
                    )
                )
            ).mappings().all()
            actual_relations = [
                (r["relname"], r["owner"], r["relrowsecurity"], r["relforcerowsecurity"])
                for r in relation_rows
            ]
            assert actual_relations == [
                ("external_identities", "drip_identity_owner", True, True),
                ("users", "drip_identity_owner", True, True),
            ], f"Identity table/RLS manifest mismatch: {actual_relations!r}"

            function_rows = (
                await connection.execute(
                    text(
                        """SELECT p.proname, owner.rolname AS owner, p.prosecdef, p.proconfig,
                                  pg_catalog.has_function_privilege('drip_identity_runtime', p.oid, 'EXECUTE') AS runtime_execute,
                                  pg_catalog.has_function_privilege('drip_identity_migrator', p.oid, 'EXECUTE') AS migrator_execute
                           FROM pg_catalog.pg_proc AS p
                           JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
                           JOIN pg_catalog.pg_roles AS owner ON owner.oid = p.proowner
                           WHERE n.nspname = 'drip_identity'
                           ORDER BY p.proname"""
                    )
                )
            ).mappings().all()
            functions = {row["proname"]: row for row in function_rows}
            assert set(functions) == {
                "enforce_user_update",
                "identity_tables_empty_for_migration",
                "lookup_identity",
                "register_identity",
                "reject_external_identity_update",
            }
            for name in ("lookup_identity", "register_identity", "identity_tables_empty_for_migration"):
                row = functions[name]
                assert row["owner"] == "drip_identity_executor"
                assert row["prosecdef"] is True
                assert row["proconfig"] == ["search_path=pg_catalog, pg_temp"]
            assert functions["lookup_identity"]["runtime_execute"] is True
            assert functions["register_identity"]["runtime_execute"] is True
            assert functions["identity_tables_empty_for_migration"]["runtime_execute"] is False
            assert sum(row["migrator_execute"] for row in functions.values()) == 1
            assert functions["identity_tables_empty_for_migration"]["migrator_execute"] is True
            assert functions["lookup_identity"]["migrator_execute"] is False
            assert functions["register_identity"]["migrator_execute"] is False

            runtime_table_privileges = await connection.scalar(
                text(
                    """SELECT bool_or(
                              pg_catalog.has_table_privilege('drip_identity_runtime',
                                  'drip_identity.' || c.relname, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                          )
                       FROM pg_catalog.pg_class AS c
                       JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
                       WHERE n.nspname = 'drip_identity' AND c.relkind IN ('r','p')"""
                )
            )
            assert runtime_table_privileges is False

            # PUBLIC and any platform roles present must have no ACL grant on
            # the private schema, identity relations, or identity functions.
            prohibited_acl = await connection.scalar(
                text(
                    """WITH blocked AS (
                           SELECT 0::oid AS oid
                           UNION ALL SELECT oid FROM pg_catalog.pg_roles
                           WHERE rolname IN ('anon','authenticated','service_role')
                       ), schema_grants AS (
                           SELECT acl.grantee FROM pg_catalog.pg_namespace AS n
                           CROSS JOIN LATERAL pg_catalog.aclexplode(
                               COALESCE(n.nspacl, pg_catalog.acldefault('n', n.nspowner))
                           ) AS acl
                           WHERE n.nspname = 'drip_identity'
                       ), relation_grants AS (
                           SELECT acl.grantee FROM pg_catalog.pg_class AS c
                           JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
                           CROSS JOIN LATERAL pg_catalog.aclexplode(
                               COALESCE(c.relacl, pg_catalog.acldefault('r', c.relowner))
                           ) AS acl
                           WHERE n.nspname = 'drip_identity' AND c.relkind IN ('r','p')
                       ), function_grants AS (
                           SELECT acl.grantee FROM pg_catalog.pg_proc AS p
                           JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
                           CROSS JOIN LATERAL pg_catalog.aclexplode(
                               COALESCE(p.proacl, pg_catalog.acldefault('f', p.proowner))
                           ) AS acl
                           WHERE n.nspname = 'drip_identity'
                       )
                       SELECT EXISTS (SELECT 1 FROM schema_grants WHERE grantee IN (SELECT oid FROM blocked))
                           OR EXISTS (SELECT 1 FROM relation_grants WHERE grantee IN (SELECT oid FROM blocked))
                           OR EXISTS (SELECT 1 FROM function_grants WHERE grantee IN (SELECT oid FROM blocked))"""
                )
            )
            assert prohibited_acl is False

            revision = await connection.scalar(text("SELECT version_num FROM public.alembic_version"))
            assert revision == "0004_identity_foundation"

        # RLS is forced: an owner that is not the executor sees no rows, while
        # the explicitly policed executor can see the registered row.
        issuer = "https://identity.example/"
        subject = "opaque|provider-subject"
        async with runtime.begin() as connection:
            result = (
                await connection.execute(
                    text(
                        "SELECT * FROM drip_identity.register_identity "
                        "(:candidate, 'auth0', :issuer, :subject)"
                    ).bindparams(candidate=uuid.uuid7()),
                    {"issuer": issuer, "subject": subject},
                )
            ).mappings().one()
            user_id = result["id"]
            assert result["status"] == "disabled"
            found = (
                await connection.execute(
                    text("SELECT * FROM drip_identity.lookup_identity('auth0', :issuer, :subject)"),
                    {"issuer": issuer, "subject": subject},
                )
            ).mappings().one()
            assert found["id"] == user_id

        async with admin.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.exec_driver_sql("SET LOCAL ROLE drip_identity_owner")
                owner_count = await connection.scalar(text("SELECT count(*) FROM drip_identity.users"))
                assert owner_count == 0
                await connection.exec_driver_sql("RESET ROLE")
                await connection.exec_driver_sql("SET LOCAL ROLE drip_identity_executor")
                executor_count = await connection.scalar(text("SELECT count(*) FROM drip_identity.users"))
                assert executor_count == 1
            finally:
                await transaction.rollback()

        # Runtime can call the two fixed functions but cannot read identity rows.
        async with runtime.connect() as connection:
            with pytest.raises(DBAPIError):
                await connection.execute(text("SELECT id FROM drip_identity.users"))

        # A duplicate external pair fails and the candidate user insert rolls back.
        duplicate_id = uuid.uuid7()
        try:
            async with runtime.begin() as connection:
                await connection.execute(
                    text(
                        "SELECT * FROM drip_identity.register_identity "
                        "(:candidate, 'auth0', :issuer, :subject)"
                    ),
                    {"candidate": duplicate_id, "issuer": issuer, "subject": subject},
                )
        except DBAPIError:
            pass
        else:
            raise AssertionError("Duplicate issuer/subject registration unexpectedly succeeded.")
        async with admin.connect() as connection:
            assert await connection.scalar(
                text("SELECT count(*) FROM drip_identity.users WHERE id = :id"), {"id": duplicate_id}
            ) == 0

        # Concurrent registration for the same pair has one winner and one conflict.
        concurrent_issuer = "https://identity.example/"
        concurrent_subject = "concurrent|pair"

        async def concurrent_registration() -> bool:
            try:
                async with runtime.begin() as connection:
                    await connection.execute(
                        text(
                            "SELECT * FROM drip_identity.register_identity "
                            "(:candidate, 'auth0', :issuer, :subject)"
                        ),
                        {
                            "candidate": uuid.uuid7(),
                            "issuer": concurrent_issuer,
                            "subject": concurrent_subject,
                        },
                    )
                return True
            except DBAPIError:
                return False

        outcomes = await asyncio.gather(concurrent_registration(), concurrent_registration())
        assert sorted(outcomes) == [False, True]
        async with admin.connect() as connection:
            assert await connection.scalar(
                text("SELECT count(*) FROM drip_identity.external_identities WHERE issuer=:issuer AND subject=:subject"),
                {"issuer": concurrent_issuer, "subject": concurrent_subject},
            ) == 1

        # An outer caller rollback removes both rows written by the definer.
        rollback_id = uuid.uuid7()
        rollback_subject = "rollback|pair"
        async with runtime.connect() as connection:
            transaction = await connection.begin()
            await connection.execute(
                text(
                    "SELECT * FROM drip_identity.register_identity "
                    "(:candidate, 'auth0', :issuer, :subject)"
                ),
                {"candidate": rollback_id, "issuer": issuer, "subject": rollback_subject},
            )
            await transaction.rollback()
        async with admin.connect() as connection:
            assert await connection.scalar(
                text("SELECT count(*) FROM drip_identity.users WHERE id=:id"), {"id": rollback_id}
            ) == 0
            assert await connection.scalar(
                text("SELECT count(*) FROM drip_identity.external_identities WHERE subject=:subject"),
                {"subject": rollback_subject},
            ) == 0

        # Downgrade must refuse populated identity tables and retain revision 0004.
        migrator = create_async_engine(make_url(migrator_url), poolclass=NullPool)
        try:
            async with migrator.connect() as connection:
                def reject_downgrade(sync_connection) -> None:
                    config = Config(str(API_ROOT / "alembic.ini"))
                    config.attributes["connection"] = sync_connection
                    config.attributes["version_table_schema"] = "public"
                    command.downgrade(config, "0003_portable_identity_ckpt")

                with pytest.raises(RuntimeError, match="refuses populated identity tables"):
                    await connection.run_sync(reject_downgrade)
            async with migrator.connect() as connection:
                assert await connection.scalar(
                    text("SELECT version_num FROM public.alembic_version")
                ) == "0004_identity_foundation"
        finally:
            await migrator.dispose()
    finally:
        await admin.dispose()
        await runtime.dispose()


async def verify_catalog_foundation(
    admin_url: str | URL, runtime_url: str | URL, migrator_url: str | URL
) -> None:
    admin = create_async_engine(make_url(admin_url), poolclass=NullPool)
    runtime = create_async_engine(make_url(runtime_url), poolclass=NullPool)
    migrator = create_async_engine(make_url(migrator_url), poolclass=NullPool)
    try:
        async with admin.connect() as connection:
            tables = (
                await connection.execute(
                    text(
                        """SELECT c.relname, owner.rolname AS owner
                           FROM pg_catalog.pg_class AS c
                           JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
                           JOIN pg_catalog.pg_roles AS owner ON owner.oid = c.relowner
                           WHERE n.nspname = 'drip_catalog' AND c.relkind = 'r'
                           ORDER BY c.relname"""
                    )
                )
            ).all()
            assert tables == [
                ("brands", "drip_identity_migrator"),
                ("listings", "drip_identity_migrator"),
                ("merchants", "drip_identity_migrator"),
                ("outfit_items", "drip_identity_migrator"),
                ("outfit_publications", "drip_identity_migrator"),
                ("outfits", "drip_identity_migrator"),
                ("prices", "drip_identity_migrator"),
                ("products", "drip_identity_migrator"),
                ("publications", "drip_identity_migrator"),
                ("variants", "drip_identity_migrator"),
            ]
            assert await connection.scalar(
                text("SELECT version_num FROM public.alembic_version")
            ) == "0006_curated_outfits"
            assert await connection.scalar(
                text(
                    """SELECT count(*) FROM pg_catalog.pg_constraint AS c
                       JOIN pg_catalog.pg_class AS t ON t.oid = c.conrelid
                       JOIN pg_catalog.pg_namespace AS n ON n.oid = t.relnamespace
                       WHERE n.nspname='drip_catalog' AND c.contype='f'"""
                )
            ) >= 10
            assert await connection.scalar(
                text(
                    """SELECT count(*) FROM pg_catalog.pg_index AS i
                       JOIN pg_catalog.pg_class AS t ON t.oid = i.indrelid
                       JOIN pg_catalog.pg_namespace AS n ON n.oid = t.relnamespace
                       WHERE n.nspname='drip_catalog' AND i.indisvalid"""
                )
                ) >= 18

        async with runtime.connect() as connection:
            assert await connection.scalar(
                text("SELECT has_schema_privilege(current_user, 'drip_catalog', 'USAGE')")
            )
            assert await connection.scalar(
                text("SELECT has_table_privilege(current_user, 'drip_catalog.products', 'SELECT')")
            )
            assert await connection.scalar(
                text("SELECT has_table_privilege(current_user, 'drip_catalog.outfits', 'SELECT')")
            )
            assert await connection.scalar(
                text("SELECT has_table_privilege(current_user, 'drip_catalog.outfit_items', 'SELECT')")
            )
            assert not await connection.scalar(
                text("SELECT has_table_privilege(current_user, 'drip_catalog.outfit_publications', 'SELECT')")
            )
            for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"):
                for table in ("products", "outfits", "outfit_items", "outfit_publications"):
                    assert not await connection.scalar(
                        text(
                            f"SELECT has_table_privilege(current_user, 'drip_catalog.{table}', :privilege)"
                        ),
                        {"privilege": privilege},
                    )
            with pytest.raises(DBAPIError):
                await connection.execute(text("SELECT id FROM drip_identity.users"))

        async with migrator.connect() as connection:
            assert await connection.scalar(
                text("SELECT current_user")
            ) == "drip_identity_migrator"
            assert await connection.scalar(
                text("SELECT has_table_privilege(current_user, 'drip_catalog.products', 'SELECT')")
            )
    finally:
        await admin.dispose()
        await runtime.dispose()
        await migrator.dispose()


async def verify_public_catalog_api(
    admin_url: str | URL, runtime_url: str | URL
) -> None:
    """Exercise real public catalog reads with the restricted runtime role."""
    from drip.catalog.abuse import require_public_catalog_rate_limit
    from drip.core.database import get_db_session
    from drip.main import create_app
    from drip.models.catalog import (
        Brand,
        CanonicalProduct,
        CatalogPublication,
        ListingVariant,
        Merchant,
        MerchantListing,
        PriceRecord,
    )
    from drip.models.outfit import Outfit, OutfitItem

    admin_engine = create_async_engine(make_url(admin_url), poolclass=NullPool)
    runtime_engine = create_async_engine(make_url(runtime_url), poolclass=NullPool)
    session_factory = async_sessionmaker(runtime_engine, expire_on_commit=False)
    brand_id = uuid.uuid7()
    merchant_id = uuid.uuid7()
    publication_id = uuid.uuid7()
    product_id = uuid.uuid7()
    listing_id = uuid.uuid7()
    variant_id = uuid.uuid7()
    price_id = uuid.uuid7()
    product_two_id = uuid.uuid7()
    listing_two_id = uuid.uuid7()
    variant_two_id = uuid.uuid7()
    price_two_id = uuid.uuid7()
    outfit_id = uuid.uuid7()
    request_id = uuid.uuid7()
    now = datetime.now(UTC)
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    """INSERT INTO drip_catalog.brands
                       (id, slug, display_name, status, source_ref, reviewer_ref)
                       VALUES (:id, :slug, :name, 'active', 'test-source', 'test-reviewer')"""
                ),
                {"id": brand_id, "slug": f"it-{brand_id.hex}", "name": "Integration Test Brand"},
            )
            await connection.execute(
                text(
                    """INSERT INTO drip_catalog.merchants
                       (id, slug, display_name, status, purchase_mode,
                        allowed_destination_hosts, allowed_image_hosts, source_ref, reviewer_ref)
                       VALUES (:id, :slug, 'Integration Test Merchant', 'active', 'external_redirect',
                               ARRAY['shop.example'], ARRAY['images.example'], 'test-source', 'test-reviewer')"""
                ),
                {"id": merchant_id, "slug": f"it-{merchant_id.hex}"},
            )
            await connection.execute(
                text(
                    """INSERT INTO drip_catalog.publications
                       (id, merchant_id, request_key, manifest_sha256, schema_version,
                        reviewer_ref, approval_ref, status, change_summary)
                       VALUES (:id, :merchant_id, :request_key, :digest, 1,
                               'test-reviewer', 'test-approval', 'applied', '{}'::jsonb)"""
                ),
                {
                    "id": publication_id,
                    "merchant_id": merchant_id,
                    "request_key": request_id,
                    "digest": "a" * 64,
                },
            )
            await connection.execute(
                text(
                    """INSERT INTO drip_catalog.products
                       (id, brand_id, canonical_key, title, description, category_code,
                        status, last_publication_id)
                       VALUES (:id, :brand_id, 'integration-test-item-two',
                               'Integration Test Garment Two', 'Synthetic test-only row',
                               'tops', 'published', :publication_id)"""
                ),
                {"id": product_two_id, "brand_id": brand_id, "publication_id": publication_id},
            )
            await connection.execute(
                text(
                    """INSERT INTO drip_catalog.listings
                       (id, product_id, merchant_id, source_listing_key, destination_url,
                        status, last_publication_id)
                       VALUES (:id, :product_id, :merchant_id, 'integration-test-listing-two',
                               'https://shop.example/test-item-two', 'published', :publication_id)"""
                ),
                {"id": listing_two_id, "product_id": product_two_id, "merchant_id": merchant_id,
                 "publication_id": publication_id},
            )
            await connection.execute(
                text(
                    """INSERT INTO drip_catalog.variants
                       (id, listing_id, source_variant_key, size_label, color_label, color_family,
                        image_url, image_alt, image_rights_ref, status, last_publication_id)
                       VALUES (:id, :listing_id, 'integration-test-variant-two', 'L', 'Blue', 'blue',
                               'https://images.example/test-item-two.jpg', 'Test image two', 'test-rights',
                               'active', :publication_id)"""
                ),
                {"id": variant_two_id, "listing_id": listing_two_id, "publication_id": publication_id},
            )
            await connection.execute(
                text(
                    """INSERT INTO drip_catalog.prices
                       (id, variant_id, publication_id, amount_minor, currency, observed_at, valid_until)
                       VALUES (:id, :variant_id, :publication_id, 23456, 'INR', :observed_at, :valid_until)"""
                ),
                {"id": price_two_id, "variant_id": variant_two_id, "publication_id": publication_id,
                 "observed_at": now - timedelta(minutes=1), "valid_until": now + timedelta(hours=1)},
            )
            await connection.execute(
                text(
                    """INSERT INTO drip_catalog.products
                       (id, brand_id, canonical_key, title, description, category_code,
                        status, last_publication_id)
                       VALUES (:id, :brand_id, 'integration-test-item',
                               'Integration Test Garment', 'Synthetic test-only row',
                               'tops', 'published', :publication_id)"""
                ),
                {"id": product_id, "brand_id": brand_id, "publication_id": publication_id},
            )
            await connection.execute(
                text(
                    """INSERT INTO drip_catalog.listings
                       (id, product_id, merchant_id, source_listing_key, destination_url,
                        status, last_publication_id)
                       VALUES (:id, :product_id, :merchant_id, 'integration-test-listing',
                               'https://shop.example/test-item', 'published', :publication_id)"""
                ),
                {
                    "id": listing_id,
                    "product_id": product_id,
                    "merchant_id": merchant_id,
                    "publication_id": publication_id,
                },
            )
            await connection.execute(
                text(
                    """INSERT INTO drip_catalog.variants
                       (id, listing_id, source_variant_key, size_label, color_label, color_family,
                        image_url, image_alt, image_rights_ref, status, last_publication_id)
                       VALUES (:id, :listing_id, 'integration-test-variant', 'M', 'Blue', 'blue',
                               'https://images.example/test-item.jpg', 'Test image', 'test-rights',
                               'active', :publication_id)"""
                ),
                {"id": variant_id, "listing_id": listing_id, "publication_id": publication_id},
            )
            await connection.execute(
                text(
                    """INSERT INTO drip_catalog.prices
                       (id, variant_id, publication_id, amount_minor, currency, observed_at, valid_until)
                       VALUES (:id, :variant_id, :publication_id, 12345, 'INR', :observed_at, :valid_until)"""
                ),
                {
                    "id": price_id,
                    "variant_id": variant_id,
                    "publication_id": publication_id,
                    "observed_at": now - timedelta(minutes=1),
                    "valid_until": now + timedelta(hours=1),
                },
            )
            await connection.execute(
                text(
                    """INSERT INTO drip_catalog.outfits
                       (id, brand_id, title, caption, image_url, image_alt, rights_ref, approval_ref,
                        status, published_at)
                       VALUES (:id, :brand_id, 'Integration Test Outfit', 'Synthetic test-only outfit',
                               'https://media.example/test-outfit.jpg', 'Test-only outfit image',
                               'test-rights', 'test-approval', 'published', :published_at)"""
                ),
                {"id": outfit_id, "brand_id": brand_id, "published_at": now},
            )
            await connection.execute(
                text(
                    """INSERT INTO drip_catalog.outfit_items (outfit_id, position, product_id)
                       VALUES (:outfit_id, 1, :first_product), (:outfit_id, 2, :second_product)"""
                ),
                {"outfit_id": outfit_id, "first_product": product_id, "second_product": product_two_id},
            )

        async def runtime_session():
            async with session_factory() as session:
                assert await session.scalar(text("SELECT current_user")) == "drip_identity_runtime"
                yield session

        async def allow_test_request() -> None:
            return None

        app = create_app()
        app.dependency_overrides[get_db_session] = runtime_session
        app.dependency_overrides[require_public_catalog_rate_limit] = allow_test_request
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            listing = await client.get(
                "/api/v1/catalog/products", params={"q": "Integration Test Garment"}
            )
            assert listing.status_code == 200, listing.text
            listed = listing.json()["items"]
            assert len(listed) == 1
            assert listed[0]["id"] == str(product_id)
            assert listed[0]["price"]["money"] == {"currency": "INR", "amount_minor": "12345"}

            detail = await client.get(f"/api/v1/catalog/products/{product_id}")
            assert detail.status_code == 200, detail.text
            assert detail.json()["title"] == "Integration Test Garment"
            assert detail.json()["listings"][0]["destination_url"] == "https://shop.example/test-item"
            assert detail.json()["listings"][0]["variants"][0]["price"]["money"]["amount_minor"] == "12345"

            facets = await client.get("/api/v1/catalog/facets")
            assert facets.status_code == 200, facets.text
            assert any(item["code"] == "tops" for item in facets.json()["categories"])
            assert "M" in facets.json()["sizes"]

            outfits = await client.get("/api/v1/ootd")
            assert outfits.status_code == 200, outfits.text
            payload = outfits.json()
            assert len(payload["items"]) == 1
            outfit = payload["items"][0]
            assert set(outfit) == {"id", "title", "caption", "brand", "image", "products"}
            assert outfit["brand"] == {"id": str(brand_id), "name": "Integration Test Brand"}
            assert outfit["id"] == str(outfit_id)
            assert {row["id"] for row in outfit["products"]} == {str(product_id), str(product_two_id)}
            assert "rights_ref" not in outfits.text and "approval_ref" not in outfits.text

            async with admin_engine.begin() as connection:
                await connection.execute(
                    text("UPDATE drip_catalog.products SET status='withdrawn' WHERE id=:id"),
                    {"id": product_two_id},
                )
            suppressed = await client.get("/api/v1/ootd")
            assert suppressed.status_code == 200, suppressed.text
            assert suppressed.json()["items"] == []

            admin_attempt = await client.post(
                "/api/v1/admin/catalog/products",
                json={
                    "brand_id": str(brand_id),
                    "canonical_key": "unauthorized-test",
                    "title": "Unauthorized test",
                    "category_code": "tops",
                    "listing": {
                        "merchant_id": str(merchant_id),
                        "source_listing_key": "unauthorized-test-listing",
                        "destination_url": "https://shop.example/unauthorized",
                        "variants": [{
                            "source_variant_key": "unauthorized-variant",
                            "image_url": "https://images.example/unauthorized.jpg",
                            "image_alt": "Test image",
                            "image_rights_ref": "test-rights",
                        }],
                    },
                },
            )
            assert admin_attempt.status_code == 503

    finally:
        try:
            async with admin_engine.begin() as connection:
                await connection.execute(delete(OutfitItem).where(OutfitItem.outfit_id == outfit_id))
                await connection.execute(delete(Outfit).where(Outfit.id == outfit_id))
                await connection.execute(delete(PriceRecord).where(PriceRecord.id.in_([price_id, price_two_id])))
                await connection.execute(delete(ListingVariant).where(ListingVariant.id.in_([variant_id, variant_two_id])))
                await connection.execute(delete(MerchantListing).where(MerchantListing.id.in_([listing_id, listing_two_id])))
                await connection.execute(delete(CanonicalProduct).where(CanonicalProduct.id.in_([product_id, product_two_id])))
                await connection.execute(delete(CatalogPublication).where(CatalogPublication.id == publication_id))
                await connection.execute(delete(Merchant).where(Merchant.id == merchant_id))
                await connection.execute(delete(Brand).where(Brand.id == brand_id))
        finally:
            await admin_engine.dispose()
            await runtime_engine.dispose()
