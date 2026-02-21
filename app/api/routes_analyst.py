"""Analyst Q&A endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.analyst_agent import ask

router = APIRouter(prefix="/analyst", tags=["analyst"])


class QueryRequest(BaseModel):
    question: str
    context: str | None = None


@router.post("/query")
def analyst_query(req: QueryRequest):
    """Ask a business question and get an analyst-style response with chart + SQL."""
    response = ask(req.question)
    return response.model_dump()
