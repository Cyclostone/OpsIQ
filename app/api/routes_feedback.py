"""Feedback endpoints — capture user feedback on cases and analyst outputs."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.models.schemas import FeedbackItem, FeedbackType, CaseStatus
from app.storage.feedback_store import save_feedback, get_all_feedback, get_feedback_counts
from app.storage.case_store import update_case_status, get_case
from app.agents.memory_agent import process_feedback, get_improvement_summary
from app.agents.evaluator_agent import evaluate_run

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    target_type: str  # "case" or "analyst"
    target_id: str
    feedback_type: str  # "approve", "reject", "false_positive", "useful", "not_useful"
    comment: str = ""


@router.post("")
def submit_feedback(req: FeedbackRequest):
    """Submit feedback on a case or analyst output."""
    item = FeedbackItem(
        target_type=req.target_type,
        target_id=req.target_id,
        feedback_type=FeedbackType(req.feedback_type),
        comment=req.comment,
    )
    saved = save_feedback(item)

    # Also update case status if feedback is on a case
    if req.target_type == "case":
        if req.feedback_type == "approve":
            update_case_status(req.target_id, CaseStatus.approved)
        elif req.feedback_type == "false_positive":
            update_case_status(req.target_id, CaseStatus.false_positive)
        elif req.feedback_type == "reject":
            update_case_status(req.target_id, CaseStatus.rejected)

    # Trigger memory agent — processes feedback into memory updates
    memory_updates = process_feedback(saved)

    # Trigger evaluator — re-score the run
    eval_score = None
    if req.target_type == "case":
        case = get_case(req.target_id)
        if case:
            eval_score = evaluate_run(case.run_id)

    return {
        "status": "ok",
        "feedback": saved.model_dump(),
        "memory_updates": [m.model_dump() for m in memory_updates],
        "eval_score": eval_score.model_dump() if eval_score else None,
    }


@router.get("/improvement")
def improvement_summary():
    """Return the self-improvement summary (memory changes, notes)."""
    return get_improvement_summary()


@router.get("")
def list_feedback():
    """Return all feedback records."""
    items = get_all_feedback()
    return {"feedback": [f.model_dump() for f in items], "count": len(items)}


@router.get("/counts")
def feedback_counts():
    """Return feedback counts by type."""
    return get_feedback_counts()
