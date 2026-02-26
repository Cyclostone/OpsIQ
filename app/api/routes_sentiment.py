"""Sentiment analysis endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.adapters import modulate_adapter

router = APIRouter(tags=["sentiment"])


class SentimentRequest(BaseModel):
    text: str
    context: str = ""


@router.post("/sentiment/analyze")
def analyze_sentiment(req: SentimentRequest):
    """Analyze sentiment of arbitrary text via Modulate adapter."""
    result = modulate_adapter.analyze_text(req.text, req.context)
    return result


@router.get("/sentiment/log")
def sentiment_log():
    """Return sentiment analysis log for observability."""
    log = modulate_adapter.get_analysis_log()
    return {"analysis_log": log, "count": len(log)}
