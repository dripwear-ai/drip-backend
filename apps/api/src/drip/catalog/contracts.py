from __future__ import annotations

import ipaddress
import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BrandInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    display_name: str = Field(min_length=1, max_length=160)
    source_ref: str = Field(min_length=1, max_length=200)


class MerchantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    display_name: str = Field(min_length=1, max_length=160)
    allowed_destination_hosts: list[str] = Field(min_length=1, max_length=20)
    allowed_image_hosts: list[str] = Field(min_length=1, max_length=20)
    source_ref: str = Field(min_length=1, max_length=200)

    @field_validator("allowed_destination_hosts", "allowed_image_hosts")
    @classmethod
    def normalized_hosts(cls, hosts: list[str]) -> list[str]:
        for host in hosts:
            labels = host.split(".")
            if len(host) > 253 or host != host.lower() or any(
                not label
                or len(label) > 63
                or re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) is None
                for label in labels
            ):
                raise ValueError("Hosts must be normalized DNS names.")
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError("IP literals are not allowed as catalog hosts.")
        if len(set(hosts)) != len(hosts):
            raise ValueError("Hosts must be unique.")
        return hosts


class PriceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount_minor: str = Field(pattern=r"^[1-9][0-9]{0,18}$")
    observed_at: datetime
    valid_until: datetime

    @field_validator("amount_minor")
    @classmethod
    def bigint_positive(cls, value: str) -> str:
        if int(value) > 9_223_372_036_854_775_807:
            raise ValueError("Price exceeds signed BIGINT range.")
        return value

    @field_validator("observed_at", "valid_until")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Price timestamps must include a timezone.")
        return value


class VariantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_variant_key: str = Field(min_length=1, max_length=160)
    size_label: str | None = Field(default=None, max_length=80)
    color_label: str | None = Field(default=None, max_length=80)
    color_family: str | None = Field(default=None, max_length=40)
    image_url: str = Field(min_length=1, max_length=2048)
    image_alt: str = Field(min_length=1, max_length=240)
    image_rights_ref: str = Field(min_length=1, max_length=200)


class ListingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    merchant_id: UUID
    source_listing_key: str = Field(min_length=1, max_length=160)
    destination_url: str = Field(min_length=1, max_length=2048)
    variants: list[VariantInput] = Field(min_length=1, max_length=100)

    @field_validator("variants")
    @classmethod
    def unique_source_variant_keys(cls, variants: list[VariantInput]) -> list[VariantInput]:
        keys = [variant.source_variant_key for variant in variants]
        if len(set(keys)) != len(keys):
            raise ValueError("Source variant keys must be unique within a listing.")
        return variants


class ProductDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brand_id: UUID
    canonical_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    category_code: str = Field(min_length=1, max_length=40)
    listing: ListingInput


class AdditionalListingInput(ListingInput):
    expected_revision: int = Field(ge=1)


class ProductUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    category_code: str = Field(min_length=1, max_length=40)


class PublicationPreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approval_ref: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(ge=1)
    listing_ids: list[UUID] = Field(min_length=1, max_length=20)
    prices: list[VariantPriceInput] = Field(min_length=1, max_length=100)

    @field_validator("listing_ids")
    @classmethod
    def unique_listing_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Listing identifiers must be unique.")
        return value


class PublishInput(PublicationPreviewInput):
    request_key: UUID
    preview_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class VariantPriceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    variant_id: UUID
    price: PriceInput


class WithdrawInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason_category: str = Field(min_length=1, max_length=80)
    approval_ref: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(ge=1)


class MoneyDTO(BaseModel):
    currency: Literal["INR"] = "INR"
    amount_minor: str


class PublicPrice(BaseModel):
    money: MoneyDTO
    observed_at: datetime
    valid_until: datetime


class PublicVariant(BaseModel):
    id: UUID
    size_label: str | None
    color_label: str | None
    image_url: str
    image_alt: str
    price: PublicPrice | None
    price_state: str
    inventory: None = None


class PublicListing(BaseModel):
    id: UUID
    merchant: dict[str, str | UUID]
    purchase_mode: str = "external_redirect"
    destination_url: str | None
    variants: list[PublicVariant]


class PublicProduct(BaseModel):
    id: UUID
    brand: dict[str, str | UUID]
    title: str
    description: str
    category_code: str
    listings: list[PublicListing]


class ProductCard(BaseModel):
    id: UUID
    brand: dict[str, str | UUID]
    title: str
    category_code: str
    image: dict[str, str]
    representative: dict[str, UUID]
    price: PublicPrice
    price_is_from: bool
    inventory: None = None


class DiscoveryRequest(BaseModel):
    """Strict initial-query or continuation request for public one-card discovery."""

    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(default=None, max_length=80)
    brand_id: list[UUID] | None = Field(default=None, max_length=10)
    category: list[str] | None = Field(default=None, max_length=10)
    color: list[str] | None = Field(default=None, max_length=10)
    size: list[str] | None = Field(default=None, max_length=10)
    min_price_minor: str | None = Field(default=None, pattern=r"^(0|[1-9][0-9]{0,18})$")
    max_price_minor: str | None = Field(default=None, pattern=r"^(0|[1-9][0-9]{0,18})$")
    limit: Literal[1] = 1
    cursor: str | None = Field(default=None, max_length=24 * 1024)
    anchor_product_id: UUID | None = None
    intent: Literal["next", "similar", "different_brand"] | None = None

    @field_validator("q")
    @classmethod
    def normalized_query(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("category", "color", "size")
    @classmethod
    def normalized_filter_values(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized) or any(len(item) > 80 for item in normalized):
            raise ValueError("Filter values are invalid.")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Filter values must be unique.")
        return normalized

    @field_validator("brand_id")
    @classmethod
    def unique_brand_ids(cls, value: list[UUID] | None) -> list[UUID] | None:
        if value is not None and len(set(value)) != len(value):
            raise ValueError("Brand identifiers must be unique.")
        return value

    @field_validator("min_price_minor", "max_price_minor")
    @classmethod
    def signed_bigint_filter(cls, value: str | None) -> str | None:
        if value is not None and int(value) > 9_223_372_036_854_775_807:
            raise ValueError("Price filter exceeds signed BIGINT range.")
        return value

    @model_validator(mode="after")
    def valid_discovery_mode(self) -> DiscoveryRequest:
        if self.min_price_minor is not None and self.max_price_minor is not None:
            if int(self.min_price_minor) > int(self.max_price_minor):
                raise ValueError("Minimum price must not exceed maximum price.")
        if self.cursor is None:
            if self.anchor_product_id is not None or self.intent is not None:
                raise ValueError("Initial discovery cannot include a continuation anchor or intent.")
        else:
            filter_fields = {
                "q", "brand_id", "category", "color", "size",
                "min_price_minor", "max_price_minor", "limit",
            }
            if filter_fields.intersection(self.model_fields_set):
                raise ValueError("Discovery continuation cannot change its filters.")
            if self.intent is None:
                raise ValueError("Discovery continuation intent is required.")
            if self.intent in {"similar", "different_brand"} and self.anchor_product_id is None:
                raise ValueError("This discovery intent requires an anchor product.")
        normalized = {
            "q": self.q,
            "brand_id": sorted(str(value) for value in (self.brand_id or [])),
            "category": sorted(self.category or []),
            "color": sorted(self.color or []),
            "size": sorted(self.size or []),
            "min_price_minor": self.min_price_minor,
            "max_price_minor": self.max_price_minor,
            "limit": self.limit,
        }
        import json

        if len(json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")) > 2048:
            raise ValueError("Normalized discovery filters exceed the supported size.")
        return self

    def normalized_filters(self) -> dict[str, object]:
        return {
            "q": self.q,
            "brand_id": sorted(str(value) for value in (self.brand_id or [])),
            "category": sorted(self.category or []),
            "color": sorted(self.color or []),
            "size": sorted(self.size or []),
            "min_price_minor": self.min_price_minor,
            "max_price_minor": self.max_price_minor,
            "limit": 1,
        }


class DiscoveryPage(BaseModel):
    items: list[ProductCard] = Field(max_length=1)
    next_cursor: str | None = Field(default=None, max_length=24 * 1024)
    empty_reason: Literal[
        "no_eligible_products", "no_similar_candidate", "no_different_brand", "exhausted"
    ] | None = None
    catalog_as_of: datetime
