# 🧠 OpsIQ — Self-Improving Billing Anomaly Detection Agent

A multi-agent system that autonomously monitors business signals, detects billing anomalies (revenue leakage, duplicate refunds, tier mismatches), takes remediation actions, and **learns from human feedback** to improve over time — powered by LLM reasoning at every decision point.

## The Problem

Finance teams lose millions annually to billing anomalies — duplicate refunds, underbilling gaps, tier mismatches, manual credit abuse. These issues are caught late (if at all), investigated manually, and the same mistakes repeat because systems don't learn.

**OpsIQ solves this with a closed-loop autonomous agent:**

1. **Detect** — Ingest signals, run 5 anomaly detectors, score and rank findings
2. **Act** — Create remediation actions (cases, alerts, approval tasks) with audit trails
3. **Learn** — Human feedback flows through an LLM-powered memory agent that adjusts detection thresholds, penalties, and confidence scoring
4. **Improve** — Rerun triage with updated memory → fewer false positives, better calibration

---

## Features

### Autonomous Investigation Pipeline
- Signal ingestion from monitoring sources → LLM-powered investigation strategy
- 5 anomaly detectors: duplicate refunds, underbilling, tier mismatch, refund spikes, manual credits
- Severity/confidence/impact scoring with sentiment analysis on evidence text
- Remediation actions with workflow audit trails

### Self-Improvement Loop
- **Feedback capture** — approve, reject, false positive on each case
- **LLM-powered memory** — AI reasons about feedback to decide threshold adjustments
- **LLM-powered evaluation** — AI assesses run quality and generates calibration advice
- **Visible improvement** — rerun triage and see confidence downgrades, threshold adjustments, and impact penalties

### Natural Language Analyst
- Ask business questions in plain English
- Get answers with charts, SQL, confidence scores, and follow-up suggestions
- Revenue analysis, refund trends, underbilling by tier, regional breakdowns

### LLM Reasoning at Every Step
- **Orchestrator** — analyzes signals, decides investigation strategy, synthesizes findings
- **Memory Agent** — reasons about feedback to generate learning updates
- **Evaluator** — assesses run quality and generates calibration advice
- All reasoning traces visible in the UI for full observability

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Streamlit Frontend                      │
│  Mission Control │ Triage Cases │ Analyst │ QA Lab       │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP
┌────────────────────────▼────────────────────────────────┐
│                   FastAPI Backend                         │
│                                                          │
│  ┌──────────┐  ┌───────────┐  ┌────────────┐           │
│  │ Monitor  │→│  Triage    │→│  Action     │           │
│  │  Agent   │  │  Agent     │  │  Engine    │           │
│  └────┬─────┘  └──┬──┬─────┘  └────┬───────┘           │
│       │           │  │              │                    │
│  ┌────▼─────┐ ┌───▼──┘  ┌──────┐  │                    │
│  │ Signal   │ │Anomaly│  │Senti-│  │                    │
│  │ Adapter  │ │+Score │  │ment  │  │                    │
│  └──────────┘ │Tools  │  │Engine│  │                    │
│               └───────┘  └──────┘  │                    │
│  ┌──────────┐  ┌──────────┐  ┌─────▼────┐              │
│  │ Metric   │  │Evaluator │  │ Memory   │              │
│  │ Layer    │  │  Agent   │  │  Agent   │              │
│  └──────────┘  │ (+ LLM)  │  │ (+ LLM)  │              │
│                └──────────┘  └──────────┘              │
│                                                          │
│  ┌────────────────┐  ┌─────────────────────┐            │
│  │  Groq/OpenAI   │  │  Orchestrator       │            │
│  │  LLM Client    │  │  (LLM reasoning     │            │
│  └────────────────┘  │   at every step)     │            │
│                      └─────────────────────┘            │
│  ┌──────────────────────────────────────────┐           │
│  │  DuckDB (analytics)  │  SQLite (state)   │           │
│  └──────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────┘
```

---

## Tech Stack

- **Python 3.11+** / **FastAPI** — backend API + agent orchestration
- **Streamlit** — frontend UI (4 pages)
- **Groq** (or OpenAI) — LLM reasoning (llama-3.3-70b-versatile, free tier)
- **DuckDB** — in-memory analytics engine (loaded from CSV seed data)
- **SQLite** — persistence for feedback, evals, memory, traces, cases
- **Plotly** — interactive charts
- **Pydantic** — data models and validation

---

## Project Structure

```
opsiq/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Settings from .env (LLM keys, server)
│   ├── models/schemas.py       # Pydantic models
│   ├── api/                    # REST endpoints
│   ├── agents/
│   │   ├── orchestrator.py     # LLM-powered autonomous pipeline
│   │   ├── monitor_agent.py    # Signal ingestion
│   │   ├── triage_agent.py     # Anomaly detection → scoring → cases
│   │   ├── analyst_agent.py    # Business Q&A
│   │   ├── evaluator_agent.py  # LLM-powered quality scoring
│   │   └── memory_agent.py     # LLM-powered feedback → memory updates
│   ├── tools/                  # Anomaly detectors, scoring, SQL, charts
│   ├── adapters/               # Signal, metric, action, sentiment, LLM
│   ├── services/               # DuckDB data loader
│   └── storage/                # SQLite persistence layer
├── frontend/
│   └── streamlit_app.py        # 4-page Streamlit UI
├── data/                       # Seed CSV data with planted anomalies
├── tests/                      # 133 tests (schemas, adapters, agents, API)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup

### Prerequisites
- Python 3.11+

### Install

```bash
cd opsiq
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
```

Edit `.env`:

```env
# LLM reasoning (free — recommended)
GROQ_API_KEY=your_groq_key    # https://console.groq.com → API Keys

# Or use OpenAI instead
OPENAI_API_KEY=your_key        # optional fallback
```

> **No LLM key?** The system still works — agents fall back to deterministic rule-based logic. With an LLM key, the agents reason about signals, synthesize findings, and learn from feedback intelligently.

### Seed Data (if CSVs are missing)

```bash
python data/seed_data.py
```

---

## Run

### 1. Start Backend

```bash
cd opsiq
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Start Frontend (separate terminal)

```bash
cd opsiq
python -m streamlit run frontend/streamlit_app.py --server.port 8501
```

### 3. Run Tests

```bash
python -m pytest tests/ -v
```

### 4. Open Browser

- **Frontend:** http://localhost:8501
- **API Docs:** http://localhost:8000/docs

---

## Deploy (Render + Streamlit Community Cloud)

This is the simplest production setup for OpsIQ:

- **Backend (FastAPI)** on Render
- **Frontend (Streamlit)** on Streamlit Community Cloud

### 1) Deploy backend to Render

Create a new **Web Service** from your GitHub repo.

- **Root Directory:** `opsiq`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Set env vars in Render:

- `GROQ_API_KEY` (recommended)
- `OPENAI_API_KEY` (optional)

After deploy, copy your backend URL, e.g.:

`https://opsiq-backend.onrender.com`

### 2) Deploy frontend to Streamlit Community Cloud

Create a new Streamlit app pointing to this repo:

- **Main file path:** `opsiq/frontend/streamlit_app.py`

In Streamlit app settings, add secrets/environment variables:

```toml
BACKEND_URL="https://opsiq-backend.onrender.com"
```

This is read by the frontend at runtime via `BACKEND_URL`.

### 3) Verify deployment

1. Open backend docs: `https://<your-backend>/docs`
2. Open Streamlit app
3. Run "Mission Control" investigation
4. Confirm cases, traces, and analyst queries all work

### Notes

- Render free tier may cold-start; first API call can take a few seconds.
- SQLite storage is ephemeral on many free hosts. For durable production state, move to a managed DB.

---

## Walkthrough

1. **Mission Control** — Click "Run Autonomous Investigation"
   - LLM analyzes signals and decides investigation strategy
   - ~6 anomaly cases detected, ranked by impact
   - Remediation actions created (case, alert, approval task)
   - Full **LLM reasoning trace** visible at every step

2. **Triage Cases** — Review cases, mark one as **False Positive**
   - See evidence, recommended action, sentiment risk score
   - Feedback triggers the self-improvement loop

3. **QA Lab** — See the learning in action
   - Memory updated: LLM decides which thresholds to adjust and by how much
   - Evaluation: LLM analyzes calibration and suggests improvements
   - Full reasoning log for observability

4. **Triage Cases** — Click "Rerun with Memory"
   - False-positive case now shows **lower confidence** (was high → medium)
   - Impact reduced by 15% penalty
   - System learned from one interaction

5. **Analyst** — Ask "Why is revenue down this month?"
   - Get answer with chart, SQL, confidence, follow-ups

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/monitor/run` | Run autonomous investigation |
| GET | `/monitor/signals` | Fetch all signals |
| GET | `/triage/cases` | List all cases (with sentiment scores) |
| POST | `/triage/rerun` | Rerun with updated memory |
| POST | `/analyst/query` | Ask a business question |
| POST | `/feedback` | Submit feedback |
| GET | `/feedback/improvement` | Self-improvement summary |
| GET | `/eval/latest` | Latest evaluation |
| GET | `/llm/status` | LLM provider status |
| GET | `/llm/reasoning` | Full LLM reasoning log |
| POST | `/sentiment/analyze` | Analyze text sentiment |
| GET | `/sentiment/log` | Sentiment analysis audit trail |
| GET | `/memory` | Current memory state |
| GET | `/traces/latest` | Latest run trace |
| POST | `/demo/reset` | Reset all state |

---

## Self-Improvement Loop

```
User Feedback → Memory Agent (LLM) → Memory Store → Triage Agent (rerun)
                      ↓
                Evaluator Agent (LLM) → Eval Store → QA Lab UI
```

**What changes on rerun after feedback:**
- LLM reasons about feedback → decides which thresholds to adjust and by how much
- `false_positive_penalty` increases → confidence downgraded for that anomaly type
- Type-specific thresholds adjust (e.g. duplicate window narrows, underbilling threshold rises)
- Scoring tool applies penalty → lower impact scores
- Evaluator recalculates correctness and generates calibration advice

---

## Graceful Degradation

| Component | With API Key | Without API Key |
|-----------|-------------|-----------------|
| **LLM (Groq/OpenAI)** | Real AI reasoning at every decision point | Deterministic fallback (rule-based) |

The system is **fully functional without any API keys** — every feature works with deterministic logic. With a Groq key (free), the agents become truly intelligent.

---

## License

MIT
