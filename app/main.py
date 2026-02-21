"""OpsIQ FastAPI application — Self-Improving Operational Intelligence Agent."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.data_service import get_db
from app.api.routes_health import router as health_router
from app.api.routes_monitor import router as monitor_router
from app.api.routes_triage import router as triage_router
from app.api.routes_analyst import router as analyst_router
from app.api.routes_feedback import router as feedback_router
from app.api.routes_eval import router as eval_router
from app.api.routes_demo import router as demo_router
from app.api.routes_sentiment import router as sentiment_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DuckDB on startup."""
    print("[main] OpsIQ starting up...")
    print(f"[main] Mode: {settings.opsiq_mode}")
    get_db()  # Eagerly load data
    print("[main] Ready.")
    yield
    print("[main] Shutting down.")


app = FastAPI(
    title="OpsIQ",
    description="Self-Improving Operational Intelligence Agent",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(monitor_router)
app.include_router(triage_router)
app.include_router(analyst_router)
app.include_router(feedback_router)
app.include_router(eval_router)
app.include_router(demo_router)
app.include_router(sentiment_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
    )
