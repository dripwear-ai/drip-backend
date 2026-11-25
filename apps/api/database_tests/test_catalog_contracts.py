from __future__ import annotations

from uuid import uuid4

import pytest
from drip.catalog.contracts import MerchantInput, PriceInput
from drip.catalog.pagination import decode_cursor, encode_cursor, filter_fingerprint
from drip.catalog.service import _url_allowed
from pydantic import ValidationError


def test_price_contract_keeps_paise_as_digit_string_and_bigint_exact():
    payload = PriceInput.model_validate(
        {
            "amount_minor": "9007199254740993",
            "observed_at": "2026-11-16T10:00:00Z",
            "valid_until": "2026-11-17T10:00:00Z",
        }
    )
    assert payload.amount_minor == "9007199254740993"
    with pytest.raises(ValidationError):
        PriceInput.model_validate(
            {"amount_minor": 1200, "observed_at": "2026-11-16T10:00:00Z", "valid_until": "2026-11-17T10:00:00Z"}
        )
    with pytest.raises(ValidationError):
        PriceInput.model_validate(
            {"amount_minor": "9223372036854775808", "observed_at": "2026-11-16T10:00:00Z", "valid_until": "2026-11-17T10:00:00Z"}
        )


def test_merchant_host_allowlist_rejects_ip_and_wildcards():
    base = {
        "slug": "approved-retailer",
        "display_name": "Retailer",
        "allowed_image_hosts": ["images.example"],
        "source_ref": "rights-record-1",
    }
    with pytest.raises(ValidationError):
        MerchantInput.model_validate({**base, "allowed_destination_hosts": ["127.0.0.1"]})
    with pytest.raises(ValidationError):
        MerchantInput.model_validate({**base, "allowed_destination_hosts": ["*.example"]})
    assert not _url_allowed("https://127.0.0.1/product", ["127.0.0.1"])
    assert not _url_allowed("https://retailer.example@attacker.example/x", ["retailer.example"])
    assert _url_allowed("https://shop.example/item", ["shop.example"])
    assert not _url_allowed("https://shop.example/item?access_token=hidden", ["shop.example"])


def test_public_cursor_is_signed_and_filter_bound():
    fingerprint = filter_fingerprint({"q": "linen", "category": None, "limit": "10"})
    identifier = uuid4()
    cursor = encode_cursor(identifier, fingerprint)
    assert decode_cursor(cursor, fingerprint) == identifier
    other_fingerprint = filter_fingerprint({"q": "silk", "category": None, "limit": "10"})
    with pytest.raises(ValueError, match="Invalid catalog cursor"):
        decode_cursor(cursor, other_fingerprint)
    altered = cursor[:-1] + ("A" if cursor[-1] != "A" else "B")
    with pytest.raises(ValueError, match="Invalid catalog cursor"):
        decode_cursor(altered, fingerprint)
