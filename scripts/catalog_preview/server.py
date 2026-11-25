"""Loopback-only, read-only adapter for testing mobile catalog presentation."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "test-catalog.csv"
PORT = 8010
PREVIEW_IMAGE_URL = "http://127.0.0.1:8010/test-image.svg"
ALLOWED_ORIGINS = {"http://localhost:8083", "http://127.0.0.1:8083"}
MAX_CSV_BYTES = 128 * 1024
MAX_REQUEST_BYTES = 8192
MAX_ROWS = 25
IMAGE = b'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="1000" viewBox="0 0 800 1000"><rect width="800" height="1000" fill="#e9ecef"/><rect x="90" y="360" width="620" height="260" rx="8" fill="#fff" stroke="#748091" stroke-width="4"/><text x="400" y="455" text-anchor="middle" font-family="Arial,sans-serif" font-size="38" fill="#263445">TEST CATALOG ONLY</text><text x="400" y="520" text-anchor="middle" font-family="Arial,sans-serif" font-size="26" fill="#596675">No real product image</text></svg>'''


def stable_id(kind: str, value: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"drip-local-catalog-test:{kind}:{value}")


def load_rows() -> list[dict[str, str]]:
    if not CSV_PATH.is_file() or CSV_PATH.stat().st_size > MAX_CSV_BYTES:
        raise RuntimeError("Local test catalog fixture is missing or too large.")
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows or len(rows) > MAX_ROWS:
        raise RuntimeError("Local test catalog fixture has an invalid row count.")
    required = {"brand_slug", "brand_name", "category_code", "canonical_key", "title", "description", "size_label", "color_label", "amount_minor"}
    if not required.issubset(rows[0]):
        raise RuntimeError("Local test catalog fixture is missing required columns.")
    for row in rows:
        if not row["title"].startswith("TEST ONLY") or not row["brand_name"].startswith("TEST ONLY"):
            raise RuntimeError("Preview rows must be explicitly marked TEST ONLY.")
        if not row["amount_minor"].isdigit() or int(row["amount_minor"]) <= 0:
            raise RuntimeError("Preview prices must be positive integer paise strings.")
    return rows


ROWS = load_rows()
BRANDS = {row["brand_slug"]: {"id": stable_id("brand", row["brand_slug"]), "name": row["brand_name"]} for row in ROWS}
PRODUCTS = [
    {
        "id": stable_id("product", row["canonical_key"]),
        "brand": BRANDS[row["brand_slug"]],
        "title": row["title"],
        "description": row["description"],
        "category_code": row["category_code"],
        "row": row,
    }
    for row in ROWS
]


def as_card(product: dict[str, object]) -> dict[str, object]:
    row = product["row"]
    assert isinstance(row, dict)
    brand = product["brand"]
    assert isinstance(brand, dict)
    now = datetime.now(UTC).isoformat()
    return {
        "id": str(product["id"]), "brand": {"id": str(brand["id"]), "name": brand["name"]},
        "title": product["title"], "category_code": product["category_code"],
        "image": {"url": PREVIEW_IMAGE_URL, "alt": row["image_alt"]},
        "representative": {"listing_id": str(stable_id("listing", row["source_listing_key"])),
                            "variant_id": str(stable_id("variant", row["source_variant_key"]))},
        "price": {"money": {"currency": "INR", "amount_minor": row["amount_minor"]},
                  "observed_at": now, "valid_until": "2035-01-01T00:00:00Z"},
        "price_is_from": False, "inventory": None,
    }


class PreviewHandler(BaseHTTPRequestHandler):
    server_version = "DRIPLocalCatalogPreview/1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _headers(self, status: int, content_type: str, body: bytes, *, no_store: bool = True) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if no_store else "public, max-age=60")
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: object) -> None:
        self._headers(status, "application/json; charset=utf-8", json.dumps(value).encode("utf-8"))

    def do_OPTIONS(self) -> None:
        origin = self.headers.get("Origin")
        if origin not in ALLOWED_ORIGINS:
            self._json(403, {"detail": "Origin is not allowed for this local preview."})
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Accept, Content-Type")
        self.send_header("Access-Control-Max-Age", "300")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/test-image.svg":
            self._headers(200, "image/svg+xml; charset=utf-8", IMAGE)
            return
        if path == "/api/v1/catalog/facets":
            self._json(200, {
                "brands": [{"id": str(item["id"]), "name": item["name"]} for item in BRANDS.values()],
                "categories": [{"code": code, "label": code.title()} for code in sorted({p["category_code"] for p in PRODUCTS})],
                "colors": [{"code": color, "label": color} for color in sorted({r["color_label"] for r in ROWS})],
                "sizes": sorted({r["size_label"] for r in ROWS}),
                "catalog_mode": "local-test-only",
            })
            return
        prefix = "/api/v1/catalog/products/"
        if path.startswith(prefix):
            raw_id = unquote(path[len(prefix):])
            product = next((p for p in PRODUCTS if str(p["id"]) == raw_id), None)
            if product is None:
                self._json(404, {"detail": "Test product not found."})
                return
            row = product["row"]
            assert isinstance(row, dict)
            brand = product["brand"]
            assert isinstance(brand, dict)
            now = datetime.now(UTC).isoformat()
            self._json(200, {
                "id": str(product["id"]), "brand": {"id": str(brand["id"]), "name": brand["name"]},
                "title": product["title"], "description": product["description"],
                "category_code": product["category_code"],
                "listings": [{"id": str(stable_id("listing", row["source_listing_key"])),
                    "merchant": {"id": str(stable_id("merchant", row["merchant_slug"])), "name": row["merchant_name"]},
                    "purchase_mode": "external_redirect", "destination_url": row["destination_url"],
                    "variants": [{"id": str(stable_id("variant", row["source_variant_key"])),
                        "size_label": row["size_label"], "color_label": row["color_label"],
                        "image_url": PREVIEW_IMAGE_URL, "image_alt": row["image_alt"], "price_state": "current",
                        "price": {"money": {"currency": "INR", "amount_minor": row["amount_minor"]},
                                  "observed_at": now, "valid_until": "2035-01-01T00:00:00Z"}}]}],
                "catalog_mode": "local-test-only",
            })
            return
        self._json(404, {"detail": "Not found."})

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/v1/discover":
            self._json(404, {"detail": "Not found."})
            return
        if int(self.headers.get("Content-Length", "0")) > MAX_REQUEST_BYTES:
            self._json(413, {"detail": "Request is too large."})
            return
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"detail": "Invalid request."})
            return
        if not isinstance(payload, dict):
            self._json(400, {"detail": "Invalid request."})
            return
        anchor_id = payload.get("anchor_product_id")
        anchor = next((p for p in PRODUCTS if str(p["id"]) == anchor_id), None)
        candidates = PRODUCTS
        if payload.get("cursor"):
            intent = payload.get("intent")
            if anchor is None:
                self._json(422, {"detail": "Invalid local test cursor."})
                return
            anchor_row = anchor["row"]
            assert isinstance(anchor_row, dict)
            if intent == "similar":
                candidates = [p for p in PRODUCTS if p is not anchor and p["category_code"] == anchor["category_code"] and p["row"]["color_label"] == anchor_row["color_label"]]
            elif intent == "different_brand":
                candidates = [p for p in PRODUCTS if p is not anchor and p["brand"]["id"] != anchor["brand"]["id"]]
            else:
                candidates = [p for p in PRODUCTS if p is not anchor]
        else:
            query = str(payload.get("q", "")).strip().casefold()
            brand_ids = {str(value) for value in payload.get("brand_id", [])}
            categories = set(payload.get("category", []))
            colors = set(payload.get("color", []))
            sizes = set(payload.get("size", []))
            candidates = [p for p in PRODUCTS if
                (not query or query in f"{p['title']} {p['brand']['name']} {p['category_code']}".casefold()) and
                (not brand_ids or str(p["brand"]["id"]) in brand_ids) and
                (not categories or p["category_code"] in categories) and
                (not colors or p["row"]["color_label"] in colors) and
                (not sizes or p["row"]["size_label"] in sizes)]
        if candidates:
            item = as_card(candidates[0])
            result = {"items": [item], "next_cursor": f"local-test:{candidates[0]['id']}",
                      "empty_reason": None, "catalog_mode": "local-test-only"}
        else:
            result = {"items": [], "next_cursor": None,
                      "empty_reason": "no_eligible_products", "catalog_mode": "local-test-only"}
        self._json(200, result)


class LoopbackServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


if __name__ == "__main__":
    server = LoopbackServer(("127.0.0.1", PORT), PreviewHandler)
    print(f"Read-only TEST DATA preview: http://127.0.0.1:{PORT}")
    print(f"CSV source: {CSV_PATH}")
    print("Loopback only; no database or external services. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
