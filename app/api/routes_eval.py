"""Evaluation, memory, and LLM observability endpoints."""

from fastapi import APIRouter

from app.storage.eval_store import get_all_evals, get_latest_eval
from app.storage.memory_store import get_all_memory
from app.storage.trace_store import get_all_traces, get_latest_trace
from app.adapters.llm_client import get_status as llm_status, get_reasoning_log

router = APIRouter(tags=["eval"])


@router.get("/eval/latest")
def latest_eval():
    """Return the most recent evaluation score."""
    ev = get_latest_eval()
    if ev is None:
        return {"eval": None, "message": "No evaluations yet"}
    return {"eval": ev.model_dump()}


@router.get("/eval/all")
def all_evals():
    """Return all evaluation records."""
    evals = get_all_evals()
    return {"evals": [e.model_dump() for e in evals], "count": len(evals)}


@router.get("/memory")
def get_memory():
    """Return all memory entries (self-improvement state)."""
    entries = get_all_memory()
    return {"memory": [m.model_dump() for m in entries], "count": len(entries)}


@router.get("/traces/latest")
def latest_trace():
    """Return the most recent trace record."""
    tr = get_latest_trace()
    if tr is None:
        return {"trace": None, "message": "No traces yet"}
    return {"trace": tr.model_dump()}


@router.get("/traces/all")
def all_traces():
    """Return all trace records."""
    traces = get_all_traces()
    return {"traces": [t.model_dump() for t in traces], "count": len(traces)}


@router.get("/llm/status")
def get_llm_status():
    """Return LLM provider status and call count."""
    return llm_status()


@router.get("/llm/reasoning")
def get_llm_reasoning():
    """Return the full LLM reasoning log for observability."""
    log = get_reasoning_log()
    return {"reasoning_log": log, "count": len(log)}
