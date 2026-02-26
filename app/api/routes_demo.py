"""State management endpoints."""

from fastapi import APIRouter

from app.services.data_service import reset_db, get_db
from app.storage.db import reset_sqlite
from app.storage.feedback_store import clear_feedback
from app.storage.eval_store import clear_evals
from app.storage.memory_store import clear_memory
from app.storage.trace_store import clear_traces
from app.storage.case_store import clear_cases
from app.adapters import datadog_adapter, lightdash_adapter, airia_adapter, modulate_adapter, llm_client
from app.models.schemas import ResetResponse

router = APIRouter(tags=["demo"])


@router.post("/demo/reset", response_model=ResetResponse)
def reset_demo():
    """Reset all demo state: feedback, evals, memory, traces, cases, adapters."""
    # Reset SQLite stores
    clear_feedback()
    clear_evals()
    clear_memory()
    clear_traces()
    clear_cases()

    # Reset adapter state
    datadog_adapter.reset()
    lightdash_adapter.reset()
    airia_adapter.reset()
    modulate_adapter.reset()
    llm_client.reset()

    # Re-seed DuckDB
    reset_db()
    get_db()

    return ResetResponse(status="ok", message="Demo state fully reset")


