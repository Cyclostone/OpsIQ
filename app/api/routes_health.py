"""Health check endpoint."""

from fastapi import APIRouter

from app.config import settings
from app.models.schemas import HealthResponse
from app.services.data_service import get_loaded_tables

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(
        status="ok",
        version="0.1.0",
        mode=settings.opsiq_mode,
        tables_loaded=get_loaded_tables(),
    )
