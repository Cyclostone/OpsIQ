"""Triage case endpoints."""

from fastapi import APIRouter, HTTPException

from app.agents.triage_agent import run_triage
from app.storage.case_store import get_all_cases, get_cases_by_run, get_case, get_open_cases

router = APIRouter(prefix="/triage", tags=["triage"])


@router.get("/cases")
def list_cases(run_id: str | None = None):
    """Return all triage cases, optionally filtered by run_id."""
    if run_id:
        cases = get_cases_by_run(run_id)
    else:
        cases = get_all_cases()
    return {"cases": [c.model_dump() for c in cases], "count": len(cases)}


@router.get("/cases/open")
def list_open_cases():
    """Return only open (unresolved) cases."""
    cases = get_open_cases()
    return {"cases": [c.model_dump() for c in cases], "count": len(cases)}


@router.get("/cases/{case_id}")
def get_case_detail(case_id: str):
    """Return a single case by ID."""
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return case.model_dump()


@router.post("/rerun")
def rerun_triage():
    """Rerun triage with current memory state.

    After feedback and memory updates, this produces different results
    (e.g. adjusted thresholds, confidence penalties).
    """
    from app.storage.case_store import clear_cases
    clear_cases()
    cases = run_triage()
    return {
        "cases": [c.model_dump() for c in cases],
        "count": len(cases),
        "message": "Triage rerun complete with updated memory/thresholds",
    }
