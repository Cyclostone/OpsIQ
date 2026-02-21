"""Monitor / autonomous run endpoints."""

from fastapi import APIRouter

from app.agents.orchestrator import run_autonomous
from app.agents.monitor_agent import fetch_all_signals

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.post("/run")
def autonomous_run():
    """Execute the full autonomous investigation pipeline.

    1. Ingest signals from Datadog / Lightdash / internal
    2. Pick highest-priority trigger
    3. Run triage (detect → score → create cases)
    4. Create actions via Airia
    5. Log trace

    Returns the full run result.
    """
    result = run_autonomous()
    return result.model_dump()


@router.get("/signals")
def get_signals():
    """Fetch all available signals from all sources."""
    signals = fetch_all_signals()
    return {"signals": [s.model_dump() for s in signals]}
