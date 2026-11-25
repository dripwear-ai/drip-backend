from __future__ import annotations

from drip.models.base import Base
from drip.models.catalog import (
    Brand,
    CanonicalProduct,
    CatalogPublication,
    ListingVariant,
    Merchant,
    MerchantListing,
    PriceRecord,
)
from drip.models.outfit import Outfit, OutfitItem, OutfitPublication
from sqlalchemy import BigInteger


def test_catalog_tables_are_registered_in_private_schema():
    expected = {
        "brands",
        "merchants",
        "publications",
        "products",
        "listings",
        "variants",
        "prices",
        "outfits",
        "outfit_items",
        "outfit_publications",
    }
    tables = {table.name for table in Base.metadata.tables.values() if table.schema == "drip_catalog"}
    assert tables == expected


def test_product_and_merchant_listing_are_distinct_relationships():
    assert CanonicalProduct.__table__.c.brand_id.foreign_keys
    assert MerchantListing.__table__.c.product_id.foreign_keys
    assert MerchantListing.__table__.c.merchant_id.foreign_keys
    assert CanonicalProduct.listings.property.uselist
    assert CanonicalProduct.__table__.c.last_publication_id.foreign_keys
    assert any(
        check.name == "ck_catalog_publication_digest"
        for check in CatalogPublication.__table__.constraints
    )
    assert MerchantListing.product.property.mapper.class_ is CanonicalProduct
    assert MerchantListing.merchant.property.mapper.class_ is Merchant


def test_variant_media_and_price_integrity_metadata():
    assert ListingVariant.__table__.c.image_url.nullable is False
    assert ListingVariant.__table__.c.image_rights_ref.nullable is False
    assert PriceRecord.__table__.c.amount_minor.type.__class__ is BigInteger
    assert PriceRecord.__table__.c.amount_minor.nullable is False
    assert any("amount_minor > 0" in str(check.sqltext) for check in PriceRecord.__table__.constraints if hasattr(check, "sqltext"))
    assert any("currency = 'INR'" in str(check.sqltext) for check in PriceRecord.__table__.constraints if hasattr(check, "sqltext"))
    assert Brand.__table__.schema == Merchant.__table__.schema == CatalogPublication.__table__.schema == "drip_catalog"
    assert Outfit.__table__.schema == OutfitItem.__table__.schema == OutfitPublication.__table__.schema == "drip_catalog"
