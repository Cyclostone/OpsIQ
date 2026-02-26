"""Pydantic models for OpsIQ — used across API, agents, and storage."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Confidence(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class CaseStatus(str, Enum):
    open = "open"
    approved = "approved"
    rejected = "rejected"
    false_positive = "false_positive"


class FeedbackType(str, Enum):
    approve = "approve"
    reject = "reject"
    false_positive = "false_positive"
    useful = "useful"
    not_useful = "not_useful"


# ---------------------------------------------------------------------------
# Signal Events
# ---------------------------------------------------------------------------

class SignalEvent(BaseModel):
    signal_id: str
    timestamp: datetime
    signal_type: str
    severity: Severity
    source: str  # datadog, lightdash, internal
    related_entity: str
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Triage Cases (output of anomaly detection)
# ---------------------------------------------------------------------------

class TriageCase(BaseModel):
    case_id: str
    run_id: str
    title: str
    anomaly_type: str  # duplicate_refund, underbilling, tier_mismatch, refund_spike, manual_credit
    severity: Severity
    confidence: Confidence
    estimated_impact: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    affected_entities: dict[str, Any] = Field(default_factory=dict)
    recommended_action: str = ""
    status: CaseStatus = CaseStatus.open
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sentiment_score: Optional[dict[str, Any]] = None  # Sentiment analysis


# ---------------------------------------------------------------------------
# Analyst Q&A
# ---------------------------------------------------------------------------

class AnalystQuery(BaseModel):
    question: str
    context: Optional[str] = None


class AnalystResponse(BaseModel):
    question: str
    answer: str
    sql_used: str = ""
    chart_data: Optional[dict[str, Any]] = None
    chart_type: str = "bar"
    confidence: Confidence = Confidence.medium
    follow_ups: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

class FeedbackItem(BaseModel):
    feedback_id: str = ""
    target_type: str  # "case" or "analyst"
    target_id: str  # case_id or query hash
    feedback_type: FeedbackType
    comment: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

class EvalScore(BaseModel):
    eval_id: str = ""
    run_id: str
    actionability: int = Field(ge=1, le=5, default=3)
    correctness: int = Field(ge=1, le=5, default=3)
    specificity: int = Field(ge=1, le=5, default=3)
    calibration_note: str = ""
    total_cases: int = 0
    false_positive_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Memory (self-improvement state)
# ---------------------------------------------------------------------------

class MemoryEntry(BaseModel):
    memory_id: str = ""
    key: str  # e.g. "duplicate_refund_window_hours"
    value: Any
    reason: str = ""
    source: str = ""  # "feedback", "eval", "manual"
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Trace (observability)
# ---------------------------------------------------------------------------

class TraceRecord(BaseModel):
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trigger_source: str = ""  # signal_id or "manual"
    steps: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    cases_generated: int = 0
    actions_created: int = 0
    eval_summary: Optional[Any] = None  # dict or string from LLM
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# Autonomous Run (top-level response)
# ---------------------------------------------------------------------------

class AutonomousRunResult(BaseModel):
    run_id: str
    signal: Optional[SignalEvent] = None
    cases: list[TriageCase] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    trace: Optional[TraceRecord] = None
    eval_score: Optional[EvalScore] = None
    reasoning_trace: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# API Responses
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    tables_loaded: list[str] = Field(default_factory=list)


class ResetResponse(BaseModel):
    status: str = "ok"
    message: str = "Demo state reset"
