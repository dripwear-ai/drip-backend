from fastapi import APIRouter

from drip.api.v1.catalog import router as catalog_router
from drip.api.v1.health import router as health_router
from drip.api.v1.outfits import router as outfit_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(catalog_router)
api_v1_router.include_router(outfit_router)
