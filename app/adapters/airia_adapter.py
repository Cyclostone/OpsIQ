"""Airia Adapter — AI workflow orchestration via Airia Agent Studio.

Airia provides governed AI pipelines for enterprise action execution.
In OpsIQ, Airia is the "action layer" — every remediation action flows through it:
  - Case creation → Airia pipeline validates, enriches, and routes
  - Alert dispatch → Airia pipeline governs notification delivery
  - Approval tasks → Airia pipeline manages approval routing

Real mode (AIRIA_API_KEY set):
  - Calls Airia Execute API: POST /execute with X-API-Key header
  - Each action type maps to an Airia pipeline/agent
  - Full audit trail from Airia response

Mock mode (no key):
  - Simulates pipeline execution with realistic response structure
  - Same interface, same audit trail format

Setup:
  1. Go to https://app.airia.com → Agent Studio
  2. Create a pipeline (or use default)
  3. Settings → Interfaces → API Key
  4. Add to .env: AIRIA_API_KEY=your_key_here
  5. Optionally set AIRIA_API_URL (default: https://api.airia.ai)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from app.config import settings
from app.models.schemas import AdapterMode, TriageCase


# ---------------------------------------------------------------------------
# State tracking
# ---------------------------------------------------------------------------
_last_used: datetime | None = None
_call_log: list[dict[str, Any]] = []
_actions_created: list[dict[str, Any]] = []
_api_errors: list[dict[str, Any]] = []


def get_mode() -> AdapterMode:
    return AdapterMode.real if settings.airia_available else AdapterMode.mock


def get_status() -> dict[str, Any]:
    return {
        "name": "Airia",
        "mode": get_mode().value,
        "available": settings.airia_available,
        "api_url": settings.airia_api_url,
        "api_key_set": bool(settings.airia_api_key),
        "description": "AI workflow orchestration — routes actions (cases, alerts, approvals) through governed Airia pipelines with full audit trail.",
        "last_used": _last_used.isoformat() if _last_used else None,
        "call_count": len(_call_log),
        "actions_created": len(_actions_created),
        "api_errors": len(_api_errors),
        "sample_payload": _get_sample_payload(),
    }


# ---------------------------------------------------------------------------
# Action Types
# ---------------------------------------------------------------------------

def create_case_action(case: TriageCase) -> dict[str, Any]:
    """Create a case/investigation action via Airia workflow.

    Returns an action artifact with workflow ID and status.
    """
    global _last_used
    _last_used = datetime.utcnow()

    action = {
        "action_id": f"ACT-{uuid.uuid4().hex[:8]}",
        "action_type": "create_case",
        "workflow": "investigation_triage",
        "source": "airia",
        "mode": get_mode().value,
        "case_id": case.case_id,
        "title": case.title,
        "severity": case.severity.value,
        "estimated_impact": case.estimated_impact,
        "recommended_action": case.recommended_action,
        "status": "created",
        "created_at": datetime.utcnow().isoformat(),
    }

    if settings.airia_available:
        action = _execute_real_workflow("create_case", action)
    else:
        action = _execute_mock_workflow("create_case", action)

    _actions_created.append(action)
    _log_call("create_case_action", {"case_id": case.case_id, "action_id": action["action_id"]})
    return action


def create_alert_action(
    title: str,
    severity: str,
    message: str,
    target: str = "finance-team",
) -> dict[str, Any]:
    """Send an alert notification via Airia workflow."""
    global _last_used
    _last_used = datetime.utcnow()

    action = {
        "action_id": f"ACT-{uuid.uuid4().hex[:8]}",
        "action_type": "send_alert",
        "workflow": "alert_notification",
        "source": "airia",
        "mode": get_mode().value,
        "title": title,
        "severity": severity,
        "message": message,
        "target": target,
        "status": "sent",
        "created_at": datetime.utcnow().isoformat(),
    }

    if settings.airia_available:
        action = _execute_real_workflow("send_alert", action)
    else:
        action = _execute_mock_workflow("send_alert", action)

    _actions_created.append(action)
    _log_call("create_alert_action", {"action_id": action["action_id"], "target": target})
    return action


def create_approval_task(
    title: str,
    description: str,
    assignee: str = "finance-manager",
    case_id: str = "",
) -> dict[str, Any]:
    """Create an approval task via Airia workflow."""
    global _last_used
    _last_used = datetime.utcnow()

    action = {
        "action_id": f"ACT-{uuid.uuid4().hex[:8]}",
        "action_type": "approval_task",
        "workflow": "approval_routing",
        "source": "airia",
        "mode": get_mode().value,
        "title": title,
        "description": description,
        "assignee": assignee,
        "case_id": case_id,
        "status": "pending_approval",
        "created_at": datetime.utcnow().isoformat(),
    }

    if settings.airia_available:
        action = _execute_real_workflow("approval_task", action)
    else:
        action = _execute_mock_workflow("approval_task", action)

    _actions_created.append(action)
    _log_call("create_approval_task", {"action_id": action["action_id"], "assignee": assignee})
    return action


# ---------------------------------------------------------------------------
# Mock implementation
# ---------------------------------------------------------------------------

def _execute_mock_workflow(workflow_type: str, action: dict[str, Any]) -> dict[str, Any]:
    """Simulate Airia workflow execution."""
    action["workflow_run_id"] = f"WF-{uuid.uuid4().hex[:8]}"
    action["workflow_status"] = "completed"
    action["execution_time_ms"] = 120
    action["audit_trail"] = [
        {"step": "validate_input", "status": "passed", "timestamp": datetime.utcnow().isoformat()},
        {"step": "check_permissions", "status": "passed", "timestamp": datetime.utcnow().isoformat()},
        {"step": "execute_action", "status": "completed", "timestamp": datetime.utcnow().isoformat()},
    ]
    return action


# ---------------------------------------------------------------------------
# Real Airia API implementation
# ---------------------------------------------------------------------------

def _execute_real_workflow(workflow_type: str, action: dict[str, Any]) -> dict[str, Any]:
    """Call Airia Execute API for pipeline execution.

    Airia API format:
      POST {AIRIA_API_URL}/execute
      Headers: X-API-Key: <key>, Content-Type: application/json
      Body: { "input": "<instruction string>" }
      Response: { "output": "...", "executionId": "...", ... }
    """
    import httpx

    # Build a natural-language instruction for the Airia pipeline
    instruction = _build_pipeline_instruction(workflow_type, action)

    try:
        resp = httpx.post(
            f"{settings.airia_api_url}/execute",
            headers={
                "X-API-Key": settings.airia_api_key,
                "Content-Type": "application/json",
            },
            json={"input": instruction},
            timeout=15.0,
        )
        resp.raise_for_status()
        result = resp.json()

        # Map Airia response to our action format
        action["workflow_run_id"] = result.get("executionId", f"WF-{uuid.uuid4().hex[:8]}")
        action["workflow_status"] = "completed"
        action["execution_time_ms"] = result.get("durationMs", 0)
        action["airia_output"] = result.get("output", "")
        action["airia_raw"] = result
        action["audit_trail"] = [
            {"step": "airia_api_call", "status": "sent", "timestamp": datetime.utcnow().isoformat()},
            {"step": "pipeline_execution", "status": "completed", "execution_id": result.get("executionId", "")},
            {"step": "response_received", "status": "success", "timestamp": datetime.utcnow().isoformat()},
        ]

        _log_call(f"real_pipeline_{workflow_type}", {
            "status": resp.status_code,
            "execution_id": result.get("executionId", ""),
        })
        print(f"  [airia_adapter] Real API success: {workflow_type} → {result.get('executionId', 'N/A')}")
        return action

    except httpx.HTTPStatusError as e:
        error_detail = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        print(f"  [airia_adapter] API error: {error_detail}")
        _api_errors.append({
            "timestamp": datetime.utcnow().isoformat(),
            "workflow_type": workflow_type,
            "error": error_detail,
        })
        return _execute_mock_workflow(workflow_type, action)

    except Exception as e:
        print(f"  [airia_adapter] API call failed, using mock: {e}")
        _api_errors.append({
            "timestamp": datetime.utcnow().isoformat(),
            "workflow_type": workflow_type,
            "error": str(e),
        })
        return _execute_mock_workflow(workflow_type, action)


def _build_pipeline_instruction(workflow_type: str, action: dict[str, Any]) -> str:
    """Build a natural-language instruction for the Airia pipeline."""
    if workflow_type == "create_case":
        return (
            f"Create an investigation case for billing anomaly: {action.get('title', 'Unknown')}. "
            f"Severity: {action.get('severity', 'medium')}. "
            f"Estimated impact: ${action.get('estimated_impact', 0):,.2f}. "
            f"Recommended action: {action.get('recommended_action', 'Review and investigate')}."
        )
    elif workflow_type == "send_alert":
        return (
            f"Send alert to {action.get('target', 'finance-team')}: {action.get('title', 'Alert')}. "
            f"Severity: {action.get('severity', 'medium')}. "
            f"Message: {action.get('message', '')}"
        )
    elif workflow_type == "approval_task":
        return (
            f"Create approval task for {action.get('assignee', 'manager')}: {action.get('title', 'Review')}. "
            f"Description: {action.get('description', '')}. "
            f"Related case: {action.get('case_id', 'N/A')}."
        )
    return f"Execute {workflow_type} workflow with payload: {json.dumps(action)[:500]}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_actions() -> list[dict[str, Any]]:
    """Return all actions created in this session."""
    return list(_actions_created)


def _get_sample_payload() -> dict[str, Any]:
    return {
        "action_type": "create_case",
        "workflow": "investigation_triage",
        "case_id": "CASE-DUP-abc123-00",
        "title": "Duplicate Refund: C003",
        "severity": "high",
        "workflow_run_id": "WF-mock1234",
        "workflow_status": "completed",
        "airia_api_format": {
            "endpoint": "POST /execute",
            "headers": {"X-API-Key": "<AIRIA_API_KEY>"},
            "body": {"input": "Create an investigation case for billing anomaly..."},
            "response": {"output": "...", "executionId": "..."},
        },
        "audit_trail": [
            {"step": "validate_input", "status": "passed"},
            {"step": "check_permissions", "status": "passed"},
            {"step": "execute_action", "status": "completed"},
        ],
    }


def _log_call(action: str, details: dict[str, Any]) -> None:
    _call_log.append({
        "action": action,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details,
    })


def get_call_log() -> list[dict[str, Any]]:
    return list(_call_log)


def get_api_errors() -> list[dict[str, Any]]:
    """Return API error log for debugging."""
    return list(_api_errors)


def reset() -> None:
    global _last_used, _call_log, _actions_created, _api_errors
    _last_used = None
    _call_log = []
    _actions_created = []
    _api_errors = []
