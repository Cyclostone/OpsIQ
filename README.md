# 🧠 OpsIQ: Self-Improving Operational Intelligence Agent

> **Hackathon:** Self Improving Agents Hack (Datadog / Lightdash / Airia / Modulate)

A self-improving multi-agent operations intelligence system that monitors real-time business signals, investigates anomalies (revenue leakage, billing exceptions), answers business questions, takes governed action, and improves using feedback + eval traces + memory — powered by **real LLM reasoning** (Groq) and **4 sponsor integrations**.

---

## Features

### Module 1: Autonomous Analyst
- Ask natural-language business questions
- Get answers with charts, SQL, confidence scores, and follow-up suggestions
- Supported: revenue analysis, refund trends, underbilling by tier, regional breakdowns

### Module 2: Revenue Leak / Exception Triage
- Autonomous anomaly detection across 5 rule types:
  - Duplicate refunds
  - Underbilling (expected vs billed gap)
  - Tier mismatch (subscription vs invoice)
  - Refund spikes by region
  - Suspicious manual credits
- Ranked cases with impact estimation, evidence, and recommended actions
- **Modulate sentiment analysis** on case evidence (risk scoring per case)

### Module 3: QA Lab / Self-Improvement
- Feedback capture (approve / reject / false positive / useful / not useful)
- **LLM-powered evaluation** — Groq analyzes run quality, calibration, and generates improvement suggestions
- **LLM-powered memory** — AI reasons about feedback to decide threshold adjustments
- Visible improvement: confidence downgrades, threshold adjustments, impact penalties
- Full LLM reasoning log for observability

### Module 4: Real LLM Reasoning (Groq)
- **Orchestrator** — LLM analyzes signals, decides investigation strategy, synthesizes findings
- **Evaluator** — LLM assesses run quality and generates calibration advice
- **Memory Agent** — LLM reasons about feedback to generate learning updates
- All reasoning traces visible in the UI

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                      │
│  Mission Control │ Triage │ Analyst │ QA Lab │ Sponsors   │
│  (reasoning traces, sentiment scores, real mode badges)   │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTP
┌────────────────────────▼─────────────────────────────────┐
│                    FastAPI Backend                         │
│                                                           │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐             │
│  │ Monitor  │→│  Triage    │→│  Action    │             │
│  │  Agent   │  │  Agent     │  │  Agent    │             │
│  └────┬─────┘  └──┬──┬─────┘  └────┬──────┘             │
│       │           │  │              │                     │
│  ┌────▼─────┐ ┌───▼──┘  ┌──────┐ ┌─▼────────┐          │
│  │ Datadog  │ │Anomaly│  │Modu- │ │  Airia   │          │
│  │ Adapter  │ │+Score │  │late  │ │ Adapter  │          │
│  └──────────┘ │Tools  │  │Senti-│ │(Execute  │          │
│               └───────┘  │ment  │ │ API)     │          │
│                          └──────┘ └──────────┘           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │Lightdash │  │Evaluator │  │ Memory   │               │
│  │ Adapter  │  │  Agent   │  │  Agent   │               │
│  │(Metrics) │  │ (+ LLM)  │  │ (+ LLM)  │               │
│  └──────────┘  └──────────┘  └──────────┘               │
│                                                           │
│  ┌────────────────┐  ┌─────────────────────┐             │
│  │  Groq LLM      │  │  Orchestrator       │             │
│  │  (llama-3.3-   │  │  (LLM reasoning     │             │
│  │   70b)         │  │   at every step)     │             │
│  └────────────────┘  └─────────────────────┘             │
│                                                           │
│  ┌─────────────────────────────────────────┐             │
│  │  DuckDB (analytics)  │  SQLite (state)  │             │
│  └─────────────────────────────────────────┘             │
└───────────────────────────────────────────────────────────┘
```

---

## Sponsor Tool Usage

| Sponsor | Tool | Role in OpsIQ | Integration |
|---------|------|---------------|-------------|
| **Datadog** | Monitoring & Alerting | Signal source — anomaly alerts and metric threshold events trigger autonomous investigation | `app/adapters/datadog_adapter.py` |
| **Lightdash** | BI Analytics | Semantic metric layer — 8 metric definitions power the Analyst module; real API uses `Authorization: ApiKey` header | `app/adapters/lightdash_adapter.py` |
| **Airia** | AI Workflow Orchestration | Action routing — cases, alerts, approvals flow through governed Airia pipelines via `POST /execute` with `X-API-Key` | `app/adapters/airia_adapter.py` |
| **Modulate** | Sentiment / Risk Analysis | Sentiment scoring on case evidence text — detects fraud language, risk indicators; enriches triage cases | `app/adapters/modulate_adapter.py` |

All adapters support **mock mode** (works without API keys) and **real mode** (plug in credentials in `.env`).
**LLM reasoning (Groq) is always active** when `GROQ_API_KEY` is set — this is the core intelligence layer.

---

## Tech Stack

- **Python 3.11+**
- **FastAPI** — backend API + agent orchestration
- **Streamlit** — frontend demo UI (5 pages)
- **Groq** — LLM provider (llama-3.3-70b-versatile, free tier)
- **DuckDB** — in-memory analytics engine (loaded from CSV)
- **SQLite** — persistence for feedback, evals, memory, traces, cases
- **Plotly** — interactive charts
- **Pydantic** — data models and validation
- **httpx** — async HTTP client for sponsor API calls

---

## Project Structure

```
opsiq/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Settings from .env (Groq, sponsors)
│   ├── models/
│   │   └── schemas.py          # Pydantic models (incl. sentiment_score)
│   ├── api/
│   │   ├── routes_health.py    # GET /health
│   │   ├── routes_monitor.py   # POST /monitor/run, GET /monitor/signals
│   │   ├── routes_triage.py    # GET /triage/cases, POST /triage/rerun
│   │   ├── routes_analyst.py   # POST /analyst/query
│   │   ├── routes_feedback.py  # POST /feedback, GET /feedback/improvement
│   │   ├── routes_eval.py      # GET /eval, GET /llm/status, GET /llm/reasoning
│   │   ├── routes_sentiment.py # POST /sentiment/analyze, GET /sentiment/status
│   │   └── routes_demo.py      # POST /demo/reset, GET /sponsors/status
│   ├── agents/
│   │   ├── monitor_agent.py    # Signal ingestion from all sources
│   │   ├── triage_agent.py     # Anomaly detection → scoring → sentiment → cases
│   │   ├── analyst_agent.py    # Business Q&A orchestration
│   │   ├── evaluator_agent.py  # LLM-powered run quality scoring
│   │   ├── memory_agent.py     # LLM-powered feedback → memory updates
│   │   └── orchestrator.py     # LLM-powered autonomous pipeline
│   ├── tools/
│   │   ├── anomaly_tool.py     # 5 rule-based anomaly detectors
│   │   ├── scoring_tool.py     # Severity/confidence/impact scoring
│   │   ├── sql_tool.py         # Template-based SQL query engine
│   │   └── chart_tool.py       # Plotly chart builder
│   ├── adapters/
│   │   ├── datadog_adapter.py  # Datadog signal ingestion
│   │   ├── lightdash_adapter.py# Lightdash metric layer + API
│   │   ├── airia_adapter.py    # Airia Execute API workflows
│   │   ├── modulate_adapter.py # Modulate sentiment analysis
│   │   └── llm_client.py       # Groq/OpenAI LLM client + reasoning log
│   ├── services/
│   │   └── data_service.py     # DuckDB loader
│   └── storage/
│       ├── db.py               # SQLite connection + DDL
│       ├── case_store.py       # Triage case persistence
│       ├── feedback_store.py   # User feedback
│       ├── eval_store.py       # Evaluation scores
│       ├── memory_store.py     # Self-improvement state
│       └── trace_store.py      # Run observability
├── frontend/
│   ├── streamlit_app.py        # 5-page Streamlit UI
│   └── components.py           # Reusable UI components
├── data/
│   ├── seed_data.py            # CSV generator with seeded anomalies
│   ├── customers.csv
│   ├── subscriptions.csv
│   ├── invoices.csv
│   ├── payments.csv
│   ├── refunds.csv
│   ├── usage_events.csv
│   └── signal_events.csv
├── tests/
│   ├── test_schemas.py         # Pydantic model tests
│   ├── test_config.py          # Config & API key logic tests
│   ├── test_adapters.py        # All sponsor adapter tests
│   ├── test_storage.py         # SQLite persistence tests
│   ├── test_tools.py           # Anomaly detection & scoring tests
│   ├── test_agents.py          # Monitor & triage agent tests
│   └── test_api.py             # Full API endpoint integration tests
├── storage/                    # SQLite DB created at runtime
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Setup

### Prerequisites
- Python 3.11+
- pip

### Install

```bash
cd opsiq
pip install -r requirements.txt
```

### Configure API Keys

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
# REQUIRED — LLM reasoning (free)
GROQ_API_KEY=your_groq_key          # https://console.groq.com → API Keys

# RECOMMENDED — Mode setting
OPSIQ_MODE=real                      # "real" enables all real integrations

# OPTIONAL — Sponsor APIs (mock mode works without these)
AIRIA_API_KEY=your_airia_key         # https://app.airia.com → Agent Studio → API Key
MODULATE_API_KEY=your_modulate_key   # https://console.modulate.ai → API Key
LIGHTDASH_API_KEY=your_lightdash_key # https://app.lightdash.cloud → Settings → Tokens
LIGHTDASH_URL=https://app.lightdash.cloud
LIGHTDASH_PROJECT_UUID=your_project_uuid
DATADOG_API_KEY=your_dd_key          # https://app.datadoghq.com → Organization Settings
DATADOG_APP_KEY=your_dd_app_key
```

**Minimum for real mode:** Just `GROQ_API_KEY` — all sponsor adapters gracefully fall back to mock when their keys are missing.

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

### 2. Start Frontend (in a separate terminal)

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

## Demo Flow (3-minute walkthrough)

1. **Mission Control** — Click "Run Autonomous Investigation"
   - LLM analyzes signals and decides investigation strategy
   - 6 anomaly cases detected, ranked by impact ($2,478 total)
   - Modulate sentiment analysis scores each case's evidence
   - 3 Airia actions created (case, alert, approval task)
   - **LLM reasoning trace** visible — see the AI's thought process

2. **Triage Cases** — Review the top case (EMEA refund spike, $1,128 impact)
   - See evidence, recommended action, **sentiment risk score**
   - Mark the duplicate refund case as **False Positive**

3. **QA Lab** — See the self-improvement in action
   - **LLM Reasoning tab** — full log of all AI reasoning calls
   - Memory updated: LLM decides which thresholds to adjust and by how much
   - Evaluation: LLM analyzes calibration and suggests improvements

4. **Triage Cases** — Click "Rerun Triage"
   - Duplicate refund case now shows **medium** confidence (was high)
   - Impact reduced from $150 to $127.50 (15% penalty applied)

5. **Analyst** — Ask "Why is revenue down this month?"
   - Get answer with chart, SQL, confidence, follow-ups

6. **Sponsor Tools** — Show all 4 integrations with activity logs
   - Datadog, Lightdash, Airia, Modulate — each with mode indicator and API format

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (mode, tables) |
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
| POST | `/sentiment/analyze` | Analyze text sentiment (Modulate) |
| GET | `/sentiment/status` | Modulate adapter status |
| GET | `/sentiment/log` | Sentiment analysis audit trail |
| GET | `/memory` | Current memory state |
| GET | `/traces/latest` | Latest trace |
| POST | `/demo/reset` | Reset all demo state |
| GET | `/sponsors/status` | Sponsor tool status |
| GET | `/sponsors/activity` | Sponsor activity logs |

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
- Evaluator (LLM) recalculates correctness and generates calibration advice

---

## Graceful Degradation

| Component | With API Key | Without API Key |
|-----------|-------------|-----------------|
| **Groq LLM** | Real AI reasoning at every step | Deterministic fallback (rule-based) |
| **Airia** | Real pipeline execution via Execute API | Mock workflow with simulated audit trail |
| **Modulate** | Real ToxMod sentiment analysis | Heuristic keyword-based scoring |
| **Lightdash** | Real API queries (charts, SQL runner) | Mock metric layer from DuckDB |
| **Datadog** | Real Events API signal ingestion | Mock signals from CSV seed data |

The system is **fully functional in mock mode** — every feature works without any API keys.
With `GROQ_API_KEY` set, the agents become truly intelligent.

---

## License

MIT — Built for Self Improving Agents Hack 2026
