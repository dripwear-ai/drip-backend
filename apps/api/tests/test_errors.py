import pytest
from drip.core.errors import NotFoundException
from fastapi import APIRouter
from httpx import AsyncClient

dummy_router = APIRouter()


@dummy_router.get("/test-not-found")
async def trigger_not_found():
    raise NotFoundException("Requested entity does not exist", code="ENTITY_NOT_FOUND")


@pytest.mark.asyncio
async def test_custom_exception_handling(app, client: AsyncClient):
    app.include_router(dummy_router)
    response = await client.get("/test-not-found")
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == "ENTITY_NOT_FOUND"
    assert data["message"] == "Requested entity does not exist"
    assert "timestamp" in data
