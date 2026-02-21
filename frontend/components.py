"""Reusable Streamlit UI components for OpsIQ."""

from __future__ import annotations

import streamlit as st
from typing import Any

API_BASE = "http://localhost:8000"


def api_url(path: str) -> str:
    """Build full API URL."""
    return f"{API_BASE}{path}"


def severity_color(severity: str) -> str:
    """Return color for severity badge."""
    return {
        "critical": "#DC2626",
        "high": "#EA580C",
        "medium": "#CA8A04",
        "low": "#16A34A",
    }.get(severity, "#6B7280")


def confidence_color(confidence: str) -> str:
    """Return color for confidence badge."""
    return {
        "high": "#16A34A",
        "medium": "#CA8A04",
        "low": "#DC2626",
    }.get(confidence, "#6B7280")


def status_color(status: str) -> str:
    """Return color for case status."""
    return {
        "open": "#3B82F6",
        "approved": "#16A34A",
        "rejected": "#DC2626",
        "false_positive": "#F59E0B",
    }.get(status, "#6B7280")


def badge(text: str, color: str) -> str:
    """Return HTML for a colored badge."""
    return f'<span style="background-color:{color};color:white;padding:2px 8px;border-radius:4px;font-size:0.8em;font-weight:600;">{text}</span>'


def metric_card(label: str, value: str, delta: str = "", color: str = "#3B82F6") -> None:
    """Render a styled metric card."""
    delta_html = ""
    if delta:
        delta_color = "#16A34A" if not delta.startswith("-") else "#DC2626"
        delta_html = f'<div style="color:{delta_color};font-size:0.85em;">{delta}</div>'

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{color}15,{color}05);border-left:4px solid {color};
                padding:12px 16px;border-radius:8px;margin-bottom:8px;">
        <div style="color:#6B7280;font-size:0.8em;text-transform:uppercase;letter-spacing:0.05em;">{label}</div>
        <div style="font-size:1.6em;font-weight:700;color:#1F2937;">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def case_card(case: dict[str, Any], show_feedback: bool = True) -> str | None:
    """Render a triage case card. Returns feedback action if button clicked."""
    sev = case.get("severity", "medium")
    conf = case.get("confidence", "medium")
    status = case.get("status", "open")
    impact = case.get("estimated_impact", 0)

    st.markdown(f"""
    <div style="border:1px solid #E5E7EB;border-radius:10px;padding:16px;margin-bottom:12px;
                background:white;box-shadow:0 1px 3px rgba(0,0,0,0.06);">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <span style="font-weight:700;font-size:1.05em;color:#1F2937;">{case.get('title','Untitled')}</span>
            <span>{badge(status.upper(), status_color(status))}</span>
        </div>
        <div style="margin-bottom:8px;">
            {badge(sev.upper(), severity_color(sev))}
            {badge(f'Confidence: {conf}', confidence_color(conf))}
            <span style="margin-left:8px;font-weight:600;color:#1F2937;">Impact: ${impact:,.2f}</span>
        </div>
        <div style="color:#4B5563;font-size:0.9em;margin-bottom:6px;">
            {'<br>'.join('• ' + e for e in case.get('evidence', []))}
        </div>
        <div style="color:#2563EB;font-size:0.85em;font-style:italic;">
            Recommended: {case.get('recommended_action', 'N/A')}
        </div>
    </div>
    """, unsafe_allow_html=True)

    if show_feedback and status == "open":
        case_id = case.get("case_id", "")
        cols = st.columns(3)
        with cols[0]:
            if st.button("✅ Approve", key=f"approve_{case_id}", use_container_width=True):
                return "approve"
        with cols[1]:
            if st.button("⚠️ False Positive", key=f"fp_{case_id}", use_container_width=True):
                return "false_positive"
        with cols[2]:
            if st.button("❌ Reject", key=f"reject_{case_id}", use_container_width=True):
                return "reject"
    return None
