from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OutfitImage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    alt: str


class OutfitProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    title: str
    image: OutfitImage


class PublicOutfit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    title: str
    caption: str
    brand: dict[str, UUID | str]
    image: OutfitImage
    products: list[OutfitProduct]


class OutfitPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[PublicOutfit]
    next_cursor: str | None


class OutfitDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    brand_id: UUID
    caption: str = Field(default="", max_length=2000)
    image_url: str = Field(min_length=1, max_length=2048)
    image_alt: str = Field(min_length=1, max_length=240)
    rights_ref: str = Field(min_length=1, max_length=200)
    approval_ref: str = Field(min_length=1, max_length=200)
    product_ids: list[UUID] = Field(default_factory=list, max_length=8)

    @field_validator("title", "image_alt", "rights_ref", "approval_ref")
    @classmethod
    def required_values_are_not_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must contain visible characters.")
        return value

    @field_validator("product_ids")
    @classmethod
    def product_ids_are_unique(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Product identifiers must be unique.")
        return value


class OutfitUpdateInput(OutfitDraftInput):
    expected_revision: int = Field(ge=1)


class OutfitPreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


class OutfitPublishInput(OutfitPreviewInput):
    request_key: UUID
    preview_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class OutfitArchiveInput(OutfitPreviewInput):
    request_key: UUID
    approval_ref: str = Field(min_length=1, max_length=200)

    @field_validator("approval_ref")
    @classmethod
    def archive_approval_is_not_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Approval reference must contain visible characters.")
        return value
