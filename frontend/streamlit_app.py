"""OpsIQ Streamlit Frontend — 5-page demo UI for hackathon presentation."""

import streamlit as st
import requests
import plotly.graph_objects as go
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE = "http://localhost:8000"
st.set_page_config(
    page_title="OpsIQ — Operational Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global CSS — Professional dark theme with polished components
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* ---- Global Typography ---- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
h1 { font-weight: 800 !important; letter-spacing: -0.02em; }
h2, h3 { font-weight: 700 !important; }

/* ---- Sidebar polish ---- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F172A 0%, #1a1f3a 100%) !important;
    border-right: 1px solid rgba(99, 102, 241, 0.15);
}
section[data-testid="stSidebar"] .stRadio > label { font-weight: 600; color: #94A3B8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; }
section[data-testid="stSidebar"] .stRadio > div > label { padding: 0.5rem 0.75rem; border-radius: 8px; transition: all 0.2s; }
section[data-testid="stSidebar"] .stRadio > div > label:hover { background: rgba(99, 102, 241, 0.1); }
section[data-testid="stSidebar"] .stRadio > div > label[data-checked="true"] { background: rgba(99, 102, 241, 0.15); }

/* ---- Metric cards ---- */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.08), rgba(99, 102, 241, 0.02));
    border: 1px solid rgba(99, 102, 241, 0.12);
    border-radius: 12px;
    padding: 16px 20px;
}
[data-testid="stMetric"] label { color: #94A3B8 !important; font-size: 0.75rem !important; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600 !important; }
[data-testid="stMetric"] [data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 700 !important; color: #F1F5F9 !important; }

/* ---- Container cards ---- */
[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid rgba(148, 163, 184, 0.1) !important;
    border-radius: 14px !important;
    background: rgba(30, 41, 59, 0.5) !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2), 0 2px 4px -2px rgba(0, 0, 0, 0.15) !important;
    transition: border-color 0.2s ease;
}
[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: rgba(99, 102, 241, 0.25) !important;
}

/* ---- Tabs ---- */
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: rgba(15, 23, 42, 0.5); border-radius: 12px; padding: 4px; }
.stTabs [data-baseweb="tab"] { border-radius: 8px; padding: 8px 16px; font-weight: 600; font-size: 0.85rem; color: #94A3B8; }
.stTabs [aria-selected="true"] { background: rgba(99, 102, 241, 0.15) !important; color: #A5B4FC !important; }

/* ---- Expanders ---- */
.streamlit-expanderHeader { font-weight: 600 !important; color: #CBD5E1 !important; font-size: 0.9rem; }
[data-testid="stExpander"] { border: 1px solid rgba(148, 163, 184, 0.08) !important; border-radius: 10px !important; background: rgba(15, 23, 42, 0.3) !important; }

/* ---- Buttons ---- */
.stButton > button { border-radius: 10px !important; font-weight: 600 !important; font-size: 0.85rem !important; padding: 0.5rem 1.25rem !important; transition: all 0.2s !important; letter-spacing: 0.01em; }
.stButton > button[kind="primary"] { background: linear-gradient(135deg, #6366F1, #8B5CF6) !important; border: none !important; box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35) !important; }
.stButton > button[kind="primary"]:hover { box-shadow: 0 6px 20px rgba(99, 102, 241, 0.5) !important; transform: translateY(-1px); }
.stButton > button[kind="secondary"] { border: 1px solid rgba(99, 102, 241, 0.3) !important; color: #A5B4FC !important; }
.stButton > button[kind="secondary"]:hover { background: rgba(99, 102, 241, 0.1) !important; }

/* ---- Dividers ---- */
hr { border-color: rgba(148, 163, 184, 0.08) !important; margin: 1.5rem 0 !important; }

/* ---- Info/Success/Error boxes ---- */
.stAlert { border-radius: 10px !important; border: none !important; }

/* ---- Text input ---- */
.stTextInput > div > div > input { border-radius: 10px !important; border: 1px solid rgba(99, 102, 241, 0.2) !important; background: rgba(15, 23, 42, 0.5) !important; }
.stTextInput > div > div > input:focus { border-color: #6366F1 !important; box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2) !important; }

/* ---- Custom badge classes ---- */
.opsiq-badge { display: inline-block; padding: 3px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.03em; text-transform: uppercase; }
.opsiq-badge-critical { background: rgba(239, 68, 68, 0.15); color: #FCA5A5; border: 1px solid rgba(239, 68, 68, 0.3); }
.opsiq-badge-high { background: rgba(249, 115, 22, 0.15); color: #FDBA74; border: 1px solid rgba(249, 115, 22, 0.3); }
.opsiq-badge-medium { background: rgba(234, 179, 8, 0.15); color: #FDE047; border: 1px solid rgba(234, 179, 8, 0.3); }
.opsiq-badge-low { background: rgba(34, 197, 94, 0.15); color: #86EFAC; border: 1px solid rgba(34, 197, 94, 0.3); }
.opsiq-badge-real { background: rgba(34, 197, 94, 0.15); color: #86EFAC; border: 1px solid rgba(34, 197, 94, 0.3); }
.opsiq-badge-mock { background: rgba(234, 179, 8, 0.15); color: #FDE047; border: 1px solid rgba(234, 179, 8, 0.3); }
.opsiq-badge-open { background: rgba(59, 130, 246, 0.15); color: #93C5FD; border: 1px solid rgba(59, 130, 246, 0.3); }
.opsiq-badge-approved { background: rgba(34, 197, 94, 0.15); color: #86EFAC; border: 1px solid rgba(34, 197, 94, 0.3); }
.opsiq-badge-rejected { background: rgba(239, 68, 68, 0.15); color: #FCA5A5; border: 1px solid rgba(239, 68, 68, 0.3); }
.opsiq-badge-false_positive { background: rgba(249, 115, 22, 0.15); color: #FDBA74; border: 1px solid rgba(249, 115, 22, 0.3); }

/* ---- Hero section ---- */
.opsiq-hero { padding: 2rem 0 1rem 0; }
.opsiq-hero h1 { font-size: 2.2rem !important; background: linear-gradient(135deg, #A5B4FC, #6366F1, #8B5CF6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin-bottom: 0.25rem !important; }
.opsiq-hero p { color: #94A3B8; font-size: 1rem; margin-top: 0; }

/* ---- Sponsor card ---- */
.sponsor-card { padding: 1.25rem; border-radius: 12px; border: 1px solid rgba(148, 163, 184, 0.1); background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.6)); margin-bottom: 0.75rem; }
.sponsor-card h4 { margin: 0 0 0.5rem 0; color: #F1F5F9; font-weight: 700; }
.sponsor-card .desc { color: #94A3B8; font-size: 0.85rem; }

/* ---- Scrollbar ---- */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(99, 102, 241, 0.3); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(99, 102, 241, 0.5); }
</style>
""", unsafe_allow_html=True)


def sev_badge(severity: str) -> str:
    """Return HTML badge for severity level."""
    return f'<span class="opsiq-badge opsiq-badge-{severity}">{severity}</span>'

def status_badge(status: str) -> str:
    """Return HTML badge for case status."""
    return f'<span class="opsiq-badge opsiq-badge-{status}">{status}</span>'

def mode_badge(mode: str) -> str:
    """Return HTML badge for adapter mode."""
    return f'<span class="opsiq-badge opsiq-badge-{mode}">{mode}</span>'


def api(method: str, path: str, silent: bool = False, **kwargs) -> dict | list | None:
    """Call the FastAPI backend."""
    try:
        url = f"{API_BASE}{path}"
        if method == "GET":
            r = requests.get(url, timeout=30)
        else:
            r = requests.post(url, timeout=30, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError:
        if not silent:
            st.error("Could not connect to backend. Start it with: `python -m uvicorn app.main:app --port 8000`")
        return None
    except requests.Timeout:
        if not silent:
            st.error("Backend request timed out. The server may be overloaded.")
        return None
    except requests.HTTPError as e:
        if not silent:
            st.error(f"Backend returned an error: {e.response.status_code} — {e.response.text[:200]}")
        return None
    except Exception as e:
        if not silent:
            st.error(f"API error: {e}")
        return None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar():
    st.sidebar.markdown("""
    <div style="text-align:center; padding: 1rem 0 0.5rem 0;">
        <div style="font-size: 2.5rem;">🧠</div>
        <div style="font-size: 1.4rem; font-weight: 800; background: linear-gradient(135deg, #A5B4FC, #6366F1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">OpsIQ</div>
        <div style="color: #64748B; font-size: 0.75rem; letter-spacing: 0.1em; text-transform: uppercase; margin-top: 2px;">Operational Intelligence</div>
    </div>
    """, unsafe_allow_html=True)
    st.sidebar.divider()

    page = st.sidebar.radio(
        "Navigate",
        ["🏠 Mission Control", "🔍 Triage Cases", "📊 Analyst", "🧪 QA Lab", "🔧 Sponsor Tools"],
        index=0,
    )

    st.sidebar.divider()

    # Health check
    health = api("GET", "/health", silent=True)
    if health:
        mode = health.get('mode', 'mock')
        st.sidebar.markdown(f"""
        <div style="background: rgba(34,197,94,0.08); border: 1px solid rgba(34,197,94,0.2); border-radius: 10px; padding: 10px 14px; margin-bottom: 8px;">
            <div style="color: #86EFAC; font-weight: 700; font-size: 0.8rem;">✦ SYSTEM ONLINE</div>
            <div style="color: #94A3B8; font-size: 0.75rem; margin-top: 4px;">Mode: {mode_badge(mode)} &nbsp; Tables: {len(health.get('tables_loaded', []))}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.sidebar.markdown("""
        <div style="background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.2); border-radius: 10px; padding: 10px 14px; margin-bottom: 8px;">
            <div style="color: #FCA5A5; font-weight: 700; font-size: 0.8rem;">✦ BACKEND OFFLINE</div>
            <div style="color: #94A3B8; font-size: 0.7rem; margin-top: 4px;">Start: python -m uvicorn app.main:app --port 8000</div>
        </div>
        """, unsafe_allow_html=True)

    # LLM status
    llm = api("GET", "/llm/status", silent=True)
    if llm:
        provider = llm.get('provider', 'none')
        if provider != 'none':
            st.sidebar.markdown(f"""
            <div style="background: rgba(99,102,241,0.08); border: 1px solid rgba(99,102,241,0.15); border-radius: 10px; padding: 10px 14px; margin-bottom: 8px;">
                <div style="color: #A5B4FC; font-weight: 700; font-size: 0.8rem;">🤖 LLM: {provider.upper()}</div>
                <div style="color: #94A3B8; font-size: 0.75rem; margin-top: 4px;">{llm.get('model', '?')} · {llm.get('call_count', 0)} calls</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.sidebar.caption("LLM: Deterministic fallback")

    st.sidebar.divider()
    if st.sidebar.button("🔄 Reset Demo", use_container_width=True):
        api("POST", "/demo/reset")
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown("""
    <div style="color: #475569; font-size: 0.65rem; text-align: center; padding-top: 1rem;">
        Built for Self Improving Agents Hack 2026
    </div>
    """, unsafe_allow_html=True)

    return page


# ---------------------------------------------------------------------------
# Page 1: Mission Control
# ---------------------------------------------------------------------------
def page_mission_control():
    st.markdown('<div class="opsiq-hero"><h1>🏠 Mission Control</h1><p>Autonomous operational intelligence — signal-triggered investigation</p></div>', unsafe_allow_html=True)

    # Run button
    col_btn, col_spacer = st.columns([1, 2])
    with col_btn:
        run_clicked = st.button("🚀 Run Autonomous Investigation", type="primary", use_container_width=True)

    if run_clicked:
        with st.spinner("🧠 Running autonomous pipeline — ingesting signals, detecting anomalies, creating actions..."):
            result = api("POST", "/monitor/run")
        if result:
            st.session_state["last_run"] = result
            st.toast(f"Run {result['run_id']} complete!", icon="✅")

    # Show last run results
    result = st.session_state.get("last_run")
    if not result:
        st.markdown("""
        <div style="text-align: center; padding: 3rem 2rem; border: 1px dashed rgba(99,102,241,0.3); border-radius: 16px; margin: 2rem 0;">
            <div style="font-size: 3rem; margin-bottom: 0.5rem;">🚀</div>
            <div style="color: #CBD5E1; font-size: 1.1rem; font-weight: 600;">Ready to Investigate</div>
            <div style="color: #64748B; font-size: 0.9rem; margin-top: 0.5rem;">Click <b>Run Autonomous Investigation</b> to start. The agent will ingest signals,<br>detect anomalies, and create governed actions — all autonomously.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    st.divider()

    # Signal panel
    signal = result.get("signal")
    if signal:
        st.markdown("### 📡 Trigger Signal")
        sig_cols = st.columns(4)
        with sig_cols[0]:
            st.metric("Signal ID", signal["signal_id"])
        with sig_cols[1]:
            st.metric("Source", signal["source"].upper())
        with sig_cols[2]:
            st.metric("Type", signal["signal_type"])
        with sig_cols[3]:
            st.metric("Severity", signal["severity"].upper())

        if signal.get("payload"):
            with st.expander("📦 Signal Payload"):
                st.json(signal["payload"])

    st.divider()

    # Summary metrics
    cases = result.get("cases", [])
    actions = result.get("actions", [])
    total_impact = sum(c.get("estimated_impact", 0) for c in cases)
    high_sev = sum(1 for c in cases if c.get("severity") in ("high", "critical"))

    st.markdown("### � Run Summary")
    m_cols = st.columns(4)
    with m_cols[0]:
        st.metric("Anomalies Detected", len(cases))
    with m_cols[1]:
        st.metric("Estimated Impact", f"${total_impact:,.0f}")
    with m_cols[2]:
        st.metric("Actions Created", len(actions))
    with m_cols[3]:
        st.metric("High Severity", high_sev)

    st.divider()

    # Cases preview
    st.markdown("### 🔍 Top Cases")
    for c in cases[:5]:
        sev = c.get("severity", "medium")
        conf = c.get("confidence", "medium")
        impact = c.get("estimated_impact", 0)

        with st.container(border=True):
            tc1, tc2, tc3 = st.columns([3, 1, 1])
            with tc1:
                st.markdown(f"{sev_badge(sev)} &nbsp; **{c.get('title', 'Untitled')}**", unsafe_allow_html=True)
                st.caption(f"`{c.get('anomaly_type', '')}` · {c.get('recommended_action', '')}")
            with tc2:
                st.metric("Impact", f"${impact:,.0f}")
            with tc3:
                st.metric("Confidence", conf.upper())

    # Actions
    if actions:
        st.divider()
        st.markdown("### ⚡ Airia Actions")
        for a in actions:
            with st.container(border=True):
                ac1, ac2, ac3 = st.columns(3)
                with ac1:
                    st.markdown(f"**{a.get('action_type', '')}**")
                with ac2:
                    st.caption(f"ID: `{a.get('action_id', '')}`")
                with ac3:
                    st.markdown(f"{status_badge(a.get('workflow_status', 'pending'))}", unsafe_allow_html=True)

    # LLM Reasoning Trace
    reasoning = result.get("reasoning_trace", {})
    if reasoning:
        st.divider()
        st.markdown("### 🧠 LLM Reasoning Trace")
        st.caption("Real-time AI reasoning — see how the agent thinks at every step")
        for key, value in reasoning.items():
            label = key.replace("_", " ").title()
            with st.expander(f"💭 {label}", expanded=(key == "executive_summary")):
                st.markdown(value)

    # Sponsor activity
    sponsor = result.get("sponsor_activity", {})
    if sponsor:
        st.divider()
        st.markdown("### 🏢 Sponsor Tool Activity")
        sp_cols = st.columns(4)
        sponsor_info = [
            ("Datadog", "🐕", sponsor.get("datadog", {}), "signals_fetched"),
            ("Lightdash", "💡", sponsor.get("lightdash", {}), "metrics_loaded"),
            ("Airia", "🤖", sponsor.get("airia", {}), "actions_created"),
            ("Modulate", "🛡️", sponsor.get("modulate", {}), "cases_analyzed"),
        ]
        for i, (name, icon, data, key) in enumerate(sponsor_info):
            with sp_cols[i]:
                st.markdown(f"**{icon} {name}**")
                st.caption(f"{data.get('action', 'N/A')}")
                val = data.get(key, 0)
                if val:
                    st.caption(f"{key.replace('_', ' ').title()}: **{val}**")


# ---------------------------------------------------------------------------
# Page 2: Triage Cases
# ---------------------------------------------------------------------------
def page_triage_cases():
    st.markdown('<div class="opsiq-hero"><h1>🔍 Triage Cases</h1><p>Review anomaly cases, provide feedback to improve the system</p></div>', unsafe_allow_html=True)

    col_refresh, col_rerun, col_spacer = st.columns([1, 1, 2])
    with col_refresh:
        refresh = st.button("🔄 Refresh", use_container_width=True)
    with col_rerun:
        rerun = st.button("🔁 Rerun with Memory", type="primary", use_container_width=True)

    if rerun:
        with st.spinner("🧠 Rerunning triage with learned thresholds..."):
            result = api("POST", "/triage/rerun")
        if result:
            st.toast(f"Rerun complete: {result['count']} cases with updated memory", icon="🧠")

    # Fetch cases
    data = api("GET", "/triage/cases")
    if not data or not data.get("cases"):
        st.markdown("""
        <div style="text-align: center; padding: 3rem 2rem; border: 1px dashed rgba(99,102,241,0.3); border-radius: 16px; margin: 2rem 0;">
            <div style="font-size: 3rem; margin-bottom: 0.5rem;">🔍</div>
            <div style="color: #CBD5E1; font-size: 1.1rem; font-weight: 600;">No Cases Yet</div>
            <div style="color: #64748B; font-size: 0.9rem; margin-top: 0.5rem;">Run an autonomous investigation from Mission Control first.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    cases = data["cases"]
    st.markdown(f'<div style="color: #64748B; font-size: 0.85rem; margin-bottom: 1rem;">Showing <b style="color: #A5B4FC;">{len(cases)}</b> cases</div>', unsafe_allow_html=True)

    for c in cases:
        case_id = c.get("case_id", "")
        sev = c.get("severity", "medium")
        conf = c.get("confidence", "medium")
        status = c.get("status", "open")
        impact = c.get("estimated_impact", 0)

        with st.container(border=True):
            # Header row with badges
            h1, h2, h3, h4 = st.columns([3, 1, 1, 1])
            with h1:
                st.markdown(f"{sev_badge(sev)} &nbsp; **{c.get('title', 'Untitled')}**", unsafe_allow_html=True)
            with h2:
                st.metric("Impact", f"${impact:,.0f}")
            with h3:
                st.markdown(f"Confidence: {sev_badge(conf)}", unsafe_allow_html=True)
            with h4:
                st.markdown(f"Status: {status_badge(status)}", unsafe_allow_html=True)

            # Sentiment score (Modulate)
            sentiment = c.get("sentiment_score")
            if sentiment:
                risk = sentiment.get("overall_risk_level", "neutral")
                polarity = sentiment.get("overall_polarity", 0)
                assessment = sentiment.get('overall_assessment', '')[:80]
                risk_color = {"high": "#FCA5A5", "elevated": "#FDBA74", "neutral": "#FDE047", "low": "#86EFAC"}.get(risk, "#94A3B8")
                st.markdown(f'<div style="font-size: 0.8rem; color: {risk_color}; margin: 4px 0;">🛡️ Sentiment: <b>{risk.upper()}</b> (polarity: {polarity:.2f}) — {assessment}</div>', unsafe_allow_html=True)

            # Evidence
            evidence = c.get("evidence", [])
            if evidence:
                with st.expander("📋 Evidence & Details"):
                    for e in evidence:
                        st.markdown(f"- {e}")
                    st.markdown(f"**Recommended action:** {c.get('recommended_action', 'N/A')}")
                    st.caption(f"Case ID: `{case_id}` · Type: `{c.get('anomaly_type', '')}` · Run: `{c.get('run_id', '')}`")

                    # Detailed sentiment breakdown
                    if sentiment and sentiment.get("evidence_scores"):
                        st.markdown("**Sentiment Analysis (Modulate):**")
                        for i, es in enumerate(sentiment["evidence_scores"]):
                            p = es.get("polarity", 0)
                            r = es.get("risk_level", "neutral")
                            st.caption(f"  Evidence {i+1}: polarity={p:.2f}, risk={r} — {es.get('assessment', '')[:60]}")

            # Feedback buttons (only for open cases)
            if status == "open":
                fb_cols = st.columns([1, 1, 1, 2])
                with fb_cols[0]:
                    if st.button("✅ Approve", key=f"ap_{case_id}", use_container_width=True):
                        _submit_feedback("case", case_id, "approve")
                with fb_cols[1]:
                    if st.button("⚠️ False Positive", key=f"fp_{case_id}", use_container_width=True):
                        _submit_feedback("case", case_id, "false_positive")
                with fb_cols[2]:
                    if st.button("❌ Reject", key=f"rj_{case_id}", use_container_width=True):
                        _submit_feedback("case", case_id, "reject")


def _submit_feedback(target_type: str, target_id: str, feedback_type: str):
    """Submit feedback and show result."""
    result = api("POST", "/feedback", json={
        "target_type": target_type,
        "target_id": target_id,
        "feedback_type": feedback_type,
    })
    if result:
        updates = result.get("memory_updates", [])
        if updates:
            st.toast(f"Feedback saved! {len(updates)} memory update(s) applied.", icon="🧠")
        else:
            st.toast("Feedback saved!", icon="✅")
        st.rerun()


# ---------------------------------------------------------------------------
# Page 3: Analyst
# ---------------------------------------------------------------------------
def page_analyst():
    st.markdown('<div class="opsiq-hero"><h1>📊 Analyst</h1><p>Ask business questions — get answers with charts, SQL, and follow-ups</p></div>', unsafe_allow_html=True)

    # Suggested questions
    st.markdown('<div style="color: #94A3B8; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.5rem;">Quick Questions</div>', unsafe_allow_html=True)
    q_cols = st.columns(2)
    with q_cols[0]:
        if st.button("💰 Why is revenue down this month?", use_container_width=True):
            st.session_state["analyst_q"] = "Why is revenue down this month?"
        if st.button("🌍 Which region has the highest refund amount?", use_container_width=True):
            st.session_state["analyst_q"] = "Which region has the highest refund amount?"
    with q_cols[1]:
        if st.button("📉 What changed in refunds this week?", use_container_width=True):
            st.session_state["analyst_q"] = "What changed in refunds this week?"
        if st.button("📊 Show underbilling by plan tier", use_container_width=True):
            st.session_state["analyst_q"] = "Show underbilling by plan tier"

    st.divider()

    # Input
    question = st.text_input(
        "Ask a business question:",
        value=st.session_state.get("analyst_q", ""),
        placeholder="e.g. Why is revenue down this month?",
    )

    col_ask, col_spacer = st.columns([1, 3])
    with col_ask:
        ask_clicked = st.button("🔎 Ask", type="primary", disabled=not question, use_container_width=True)

    if ask_clicked:
        with st.spinner("🧠 Analyzing your question..."):
            result = api("POST", "/analyst/query", json={"question": question})
        if result:
            st.session_state["analyst_result"] = result

    # Show result
    result = st.session_state.get("analyst_result")
    if not result:
        return

    st.divider()

    # Confidence badge
    conf = result.get("confidence", "medium")
    st.markdown(f'Confidence: {sev_badge(conf)}', unsafe_allow_html=True)

    # Answer
    st.markdown("### 💡 Answer")
    with st.container(border=True):
        st.markdown(result.get("answer", "No answer available."))

    # Chart
    chart_data = result.get("chart_data")
    if chart_data and chart_data.get("data"):
        st.markdown("### 📈 Chart")
        try:
            layout = chart_data.get("layout", {})
            layout.update({
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(15,23,42,0.3)",
                "font": {"color": "#94A3B8"},
                "xaxis": {"gridcolor": "rgba(148,163,184,0.1)"},
                "yaxis": {"gridcolor": "rgba(148,163,184,0.1)"},
            })
            fig = go.Figure(data=chart_data["data"], layout=layout)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"Chart rendering error: {e}")

    # SQL
    sql = result.get("sql_used", "")
    if sql:
        with st.expander("🔧 SQL Query Used"):
            st.code(sql, language="sql")

    # Follow-ups
    follow_ups = result.get("follow_ups", [])
    if follow_ups:
        st.markdown("### 🔗 Suggested Follow-ups")
        for fu in follow_ups:
            if st.button(f"→ {fu}", key=f"fu_{fu[:30]}"):
                st.session_state["analyst_q"] = fu
                st.rerun()

    # Feedback
    st.divider()
    fc1, fc2, fc_spacer = st.columns([1, 1, 3])
    with fc1:
        if st.button("👍 Useful", use_container_width=True):
            _submit_feedback("analyst", question[:50], "useful")
    with fc2:
        if st.button("👎 Not Useful", use_container_width=True):
            _submit_feedback("analyst", question[:50], "not_useful")


# ---------------------------------------------------------------------------
# Page 4: QA Lab
# ---------------------------------------------------------------------------
def page_qa_lab():
    st.markdown('<div class="opsiq-hero"><h1>🧪 QA Lab / Self-Improvement</h1><p>Evaluation scores, feedback history, memory updates, and LLM reasoning traces</p></div>', unsafe_allow_html=True)

    tab_eval, tab_feedback, tab_memory, tab_trace, tab_llm = st.tabs(
        ["📊 Evaluation", "💬 Feedback", "🧠 Memory", "📜 Traces", "🤖 LLM Reasoning"]
    )

    # --- Eval tab ---
    with tab_eval:
        evals = api("GET", "/eval/all")
        if evals and evals.get("evals"):
            st.markdown("### Evaluation Scores")
            for ev in evals["evals"][:5]:
                with st.container(border=True):
                    ec1, ec2, ec3, ec4 = st.columns(4)
                    with ec1:
                        st.metric("Actionability", f"{ev['actionability']}/5")
                    with ec2:
                        st.metric("Correctness", f"{ev['correctness']}/5")
                    with ec3:
                        st.metric("Specificity", f"{ev['specificity']}/5")
                    with ec4:
                        st.metric("False Positives", f"{ev['false_positive_count']}/{ev['total_cases']}")
                    st.caption(f"Run: `{ev['run_id']}` | {ev['calibration_note']}")
        else:
            st.info("No evaluations yet. Submit feedback on cases to trigger evaluation.")

    # --- Feedback tab ---
    with tab_feedback:
        fb_data = api("GET", "/feedback")
        if fb_data and fb_data.get("feedback"):
            st.markdown(f"### Feedback History ({fb_data['count']} items)")
            for fb in fb_data["feedback"][:10]:
                fb_emoji = {
                    "approve": "✅", "false_positive": "⚠️", "reject": "❌",
                    "useful": "👍", "not_useful": "👎",
                }.get(fb["feedback_type"], "💬")
                with st.container(border=True):
                    st.markdown(f"{fb_emoji} **{fb['feedback_type']}** on `{fb['target_type']}:{fb['target_id']}`")
                    if fb.get("comment"):
                        st.caption(fb["comment"])
                    st.caption(f"ID: `{fb['feedback_id']}` | {fb['timestamp']}")
        else:
            st.info("No feedback submitted yet.")

        # Counts
        counts = api("GET", "/feedback/counts")
        if counts:
            st.markdown("### Feedback Counts")
            cnt_cols = st.columns(len(counts) if counts else 1)
            for i, (k, v) in enumerate(counts.items()):
                with cnt_cols[i]:
                    st.metric(k.replace("_", " ").title(), v)

    # --- Memory tab ---
    with tab_memory:
        improvement = api("GET", "/feedback/improvement")
        if improvement:
            # LLM learning summary
            llm_summary = improvement.get("llm_summary", "")
            if llm_summary:
                st.markdown("### 🤖 AI Learning Summary")
                with st.container(border=True):
                    st.markdown(llm_summary)

            # Improvement notes
            notes = improvement.get("improvement_notes", [])
            if notes:
                st.markdown("### 🎯 Improvement Notes")
                for n in notes:
                    st.markdown(f"- {n}")

            # Changes
            changes = improvement.get("changes", [])
            if changes:
                st.markdown("### 📝 Memory Changes (vs defaults)")
                for ch in changes:
                    with st.container(border=True):
                        st.markdown(f"**{ch['key']}**: `{ch['default']}` → `{ch['current']}`")
                        st.caption(f"{ch['reason']} | Source: {ch['source']}")

            # Full memory
            memory = improvement.get("current_memory", [])
            if memory:
                st.markdown("### 🧠 Current Memory State")
                for m in memory:
                    st.markdown(f"- **{m['key']}** = `{m['value']}` — _{m['reason']}_")

    # --- Trace tab ---
    with tab_trace:
        trace_data = api("GET", "/traces/latest")
        if trace_data and trace_data.get("trace"):
            tr = trace_data["trace"]
            st.markdown("### Latest Trace")
            with st.container(border=True):
                tr_cols = st.columns(4)
                with tr_cols[0]:
                    st.metric("Run ID", tr["run_id"])
                with tr_cols[1]:
                    st.metric("Cases", tr["cases_generated"])
                with tr_cols[2]:
                    st.metric("Actions", tr["actions_created"])
                with tr_cols[3]:
                    st.metric("Duration", f"{tr['duration_ms']}ms")

                st.markdown("**Steps:**")
                for i, step in enumerate(tr.get("steps", [])):
                    st.markdown(f"{i+1}. `{step}`")

                st.markdown("**Tools called:**")
                st.markdown(", ".join(f"`{t}`" for t in tr.get("tools_called", [])))

                st.caption(f"Trigger: `{tr.get('trigger_source', 'N/A')}` | {tr['timestamp']}")
        else:
            st.info("No traces yet. Run an autonomous investigation first.")

        # All traces
        all_traces = api("GET", "/traces/all")
        if all_traces and all_traces.get("traces") and len(all_traces["traces"]) > 1:
            st.markdown("### All Traces")
            for tr in all_traces["traces"]:
                st.caption(f"`{tr['run_id']}` | Cases: {tr['cases_generated']} | Actions: {tr['actions_created']} | {tr['duration_ms']}ms | {tr['timestamp']}")

    # --- LLM Reasoning tab ---
    with tab_llm:
        llm_status = api("GET", "/llm/status")
        if llm_status:
            st.markdown("### LLM Provider Status")
            with st.container(border=True):
                lc1, lc2, lc3, lc4 = st.columns(4)
                with lc1:
                    avail = llm_status.get("available", False)
                    st.metric("Status", "Active" if avail else "Fallback")
                with lc2:
                    st.metric("Provider", llm_status.get("provider", "none").upper())
                with lc3:
                    st.metric("Model", llm_status.get("model", "N/A"))
                with lc4:
                    st.metric("Total Calls", llm_status.get("call_count", 0))

        reasoning_data = api("GET", "/llm/reasoning")
        if reasoning_data and reasoning_data.get("reasoning_log"):
            log = reasoning_data["reasoning_log"]
            st.markdown(f"### Reasoning Log ({len(log)} calls)")
            for entry in reversed(log):
                purpose = entry.get("purpose", "unknown")
                provider = entry.get("provider", "?")
                model = entry.get("model", "?")
                ts = entry.get("timestamp", "")[:19]
                with st.expander(f"💭 {purpose} — {provider}/{model} @ {ts}"):
                    st.markdown(f"**Prompt preview:** {entry.get('prompt_preview', 'N/A')}")
                    st.divider()
                    st.markdown(f"**Response:**")
                    st.markdown(entry.get("response_preview", "N/A"))
                    st.caption(f"~{entry.get('tokens_approx', 0)} tokens")
        else:
            st.info("No LLM reasoning calls yet. Run an autonomous investigation to see reasoning traces.")

        # Sentiment analysis log
        sentiment_data = api("GET", "/sentiment/log")
        if sentiment_data and sentiment_data.get("analysis_log"):
            slog = sentiment_data["analysis_log"]
            st.markdown(f"### Modulate Sentiment Log ({len(slog)} analyses)")
            for entry in reversed(slog[:20]):
                risk = entry.get("risk_level", "neutral")
                risk_emoji = {"high": "🔴", "elevated": "🟠", "neutral": "🟡", "low": "🟢"}.get(risk, "⚪")
                st.caption(f"{risk_emoji} polarity={entry.get('polarity', 0):.2f} | {entry.get('provider', '?')} | {entry.get('text_preview', '')[:60]}...")


# ---------------------------------------------------------------------------
# Page 5: Sponsor Tools
# ---------------------------------------------------------------------------
def page_sponsor_tools():
    st.markdown('<div class="opsiq-hero"><h1>🔧 Sponsor Integrations</h1><p>How OpsIQ uses Datadog, Lightdash, Airia, and Modulate</p></div>', unsafe_allow_html=True)

    status_data = api("GET", "/sponsors/status")
    if not status_data:
        st.error("Could not fetch sponsor status")
        return

    sponsors = status_data.get("sponsors", [])
    icon_map = {"Datadog": "🐕", "Lightdash": "💡", "Airia": "🤖", "modulate": "🛡️"}
    role_map = {
        "Datadog": "Signal source — anomaly alerts trigger investigation",
        "Lightdash": "Analytics layer — semantic metrics power the Analyst",
        "Airia": "Action routing — governed pipeline execution",
        "modulate": "Sentiment analysis — risk scoring on evidence text",
    }

    # Sponsor cards in a 2x2 grid
    for row_start in range(0, len(sponsors), 2):
        cols = st.columns(2)
        for i, sp in enumerate(sponsors[row_start:row_start+2]):
            with cols[i]:
                name = sp.get("name", "Unknown")
                mode = sp.get("mode", "mock")
                icon = icon_map.get(name, "🔧")
                with st.container(border=True):
                    st.markdown(f"{icon} **{name}** &nbsp; {mode_badge(mode)}", unsafe_allow_html=True)
                    st.caption(role_map.get(name, sp.get("description", "")))
                    meta_parts = []
                    if sp.get("call_count"):
                        meta_parts.append(f"API calls: {sp['call_count']}")
                    if sp.get("actions_created"):
                        meta_parts.append(f"Actions: {sp['actions_created']}")
                    if sp.get("last_used"):
                        meta_parts.append(f"Last: {sp['last_used'][:19]}")
                    if meta_parts:
                        st.caption(" · ".join(meta_parts))

                    sample = sp.get("sample_payload")
                    if sample:
                        with st.expander("📦 Sample Payload"):
                            st.json(sample)

    # LLM status
    llm = status_data.get("llm", {})
    st.divider()
    st.markdown("### 🤖 LLM Enhancement Layer")
    with st.container(border=True):
        l1, l2, l3, l4 = st.columns(4)
        avail = llm.get("available", False)
        with l1:
            st.metric("Status", "Active" if avail else "Fallback")
        with l2:
            st.metric("Provider", llm.get("provider", "none").upper())
        with l3:
            st.metric("Model", llm.get("model", "N/A"))
        with l4:
            st.metric("Total Calls", llm.get("call_count", 0))

    # Activity log
    st.divider()
    st.markdown("### 📜 Activity Log")
    activity = api("GET", "/sponsors/activity")
    if activity:
        act_tabs = st.tabs(["🐕 Datadog", "💡 Lightdash", "🤖 Airia", "🛡️ Modulate"])
        with act_tabs[0]:
            dd_log = activity.get("datadog", [])
            if dd_log:
                for entry in dd_log[:5]:
                    st.caption(f"`{entry.get('action', '')}` — {entry.get('timestamp', '')[:19]}")
            else:
                st.caption("No activity yet")
        with act_tabs[1]:
            lh_log = activity.get("lightdash", [])
            if lh_log:
                for entry in lh_log[:5]:
                    st.caption(f"`{entry.get('action', '')}` — {entry.get('timestamp', '')[:19]}")
            else:
                st.caption("No activity yet")
        with act_tabs[2]:
            ai_data = activity.get("airia", {})
            ai_log = ai_data.get("calls", []) if isinstance(ai_data, dict) else []
            ai_actions = ai_data.get("actions", []) if isinstance(ai_data, dict) else []
            if ai_actions:
                for a in ai_actions[:5]:
                    st.caption(f"`{a.get('action_type', '')}` — {a.get('action_id', '')} — {a.get('workflow_status', '')}")
            if ai_log:
                for entry in ai_log[:5]:
                    st.caption(f"`{entry.get('action', '')}` — {entry.get('timestamp', '')[:19]}")
            if not ai_log and not ai_actions:
                st.caption("No activity yet")
        with act_tabs[3]:
            mod_log = api("GET", "/sentiment/log")
            if mod_log and mod_log.get("analysis_log"):
                for entry in mod_log["analysis_log"][:10]:
                    risk = entry.get("risk_level", "neutral")
                    st.markdown(f"{sev_badge(risk)} polarity={entry.get('polarity', 0):.2f} · {entry.get('text_preview', '')[:50]}...", unsafe_allow_html=True)
            else:
                st.caption("No sentiment analyses yet")

    # Integration architecture
    st.divider()
    st.markdown("### 🏗️ Architecture")
    st.markdown("""
    | Sponsor | Role in OpsIQ | Integration Point |
    |---------|--------------|-------------------|
    | **Datadog** | Signal source — anomaly alerts trigger autonomous investigation | `monitor_agent` → `datadog_adapter` |
    | **Lightdash** | Analytics layer — semantic metric definitions power the Analyst module | `analyst_agent` → `lightdash_adapter` |
    | **Airia** | Action routing — cases, alerts, approvals flow through governed Airia pipelines | `orchestrator` → `airia_adapter` |
    | **Modulate** | Sentiment analysis — risk scoring on case evidence text via ToxMod | `triage_agent` → `modulate_adapter` |

    All adapters support **mock mode** (demo-safe) and **real mode** (plug in API keys in `.env`).
    LLM reasoning (Groq) is always active when `GROQ_API_KEY` is set.
    """)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    page = render_sidebar()

    # Check backend connectivity before rendering pages
    health = api("GET", "/health", silent=True)
    if not health:
        st.markdown("""
        <div style="text-align: center; padding: 4rem 2rem;">
            <div style="font-size: 4rem; margin-bottom: 1rem;">⚠️</div>
            <div style="font-size: 1.8rem; font-weight: 800; color: #FCA5A5; margin-bottom: 0.5rem;">Backend Not Reachable</div>
            <div style="color: #94A3B8; font-size: 1rem; margin-bottom: 2rem;">The OpsIQ backend is not running. Start it in a separate terminal:</div>
            <div style="background: rgba(15,23,42,0.8); border: 1px solid rgba(148,163,184,0.15); border-radius: 12px; padding: 1.25rem; display: inline-block; text-align: left;">
                <code style="color: #A5B4FC; font-size: 0.9rem;">cd opsiq && python -m uvicorn app.main:app --port 8000</code>
            </div>
            <div style="color: #64748B; font-size: 0.85rem; margin-top: 1.5rem;">Then refresh this page.</div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    if page == "🏠 Mission Control":
        page_mission_control()
    elif page == "🔍 Triage Cases":
        page_triage_cases()
    elif page == "📊 Analyst":
        page_analyst()
    elif page == "🧪 QA Lab":
        page_qa_lab()
    elif page == "🔧 Sponsor Tools":
        page_sponsor_tools()


if __name__ == "__main__":
    main()
