from __future__ import annotations

import inspect

import pytest
from drip.api.v1.catalog import admin
from drip.catalog.security import get_catalog_writer_session, require_catalog_admin
from drip.core.errors import ServiceUnavailableException
from drip.main import create_app


def test_catalog_routes_are_registered_with_fail_closed_admin_and_writer_dependencies():
    app = create_app()
    paths = app.openapi()["paths"]
    assert "/api/v1/catalog/products" in paths
    assert "/api/v1/catalog/products/{product_id}" in paths
    assert "/api/v1/admin/catalog/products" in paths
    create_route = next(route for route in admin.routes if route.path == "/admin/catalog/products")
    dependencies = {dependency.call for dependency in create_route.dependant.dependencies}
    assert require_catalog_admin in dependencies
    assert get_catalog_writer_session in dependencies


def test_admin_boundary_has_no_client_claim_or_header_shortcut():
    source = inspect.getsource(require_catalog_admin)
    assert "raise ServiceUnavailableException" in source
    assert "request" not in inspect.signature(require_catalog_admin).parameters
    with pytest.raises(ServiceUnavailableException, match="authorization is not configured"):
        _run_immediate(require_catalog_admin())


def _run_immediate(coroutine):
    """Run a database-free coroutine that contains no event-loop suspension."""
    if not inspect.iscoroutine(coroutine):
        raise TypeError("Expected a coroutine.")
    try:
        coroutine.send(None)
    except StopIteration as completed:
        return completed.value
    raise AssertionError("Test double unexpectedly suspended on external I/O.")
