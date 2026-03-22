# Clarity — AI Output Verification Layer

**Clarity** intercepts LLM API calls, runs a multi-agent verification pipeline, and returns a trust score (0–100) with detailed analysis. It's middleware for developers who need to know how much to trust AI output.

## Quick Start

### 1. Install Dependencies
```bash
pip install -e .
```

### 2. Set Up Environment
Copy `.env.example` to `.env` and fill in your API keys:
```bash
cp .env.example .env
# Edit .env with your Anthropic, InsForge, TinyFish, and Ada keys
```

### 3. Initialize Database (Optional)
If using InsForge for persistence:
```bash
python -m clarity.setup_db
```

### 4. Run the Server
```bash
python -m clarity.main
```

Server runs on `http://localhost:8000`
- Dashboard: `http://localhost:8000/`
- API: `http://localhost:8000/api/v1/`

## Developer SDK Usage

```python
from clarity.sdk import ClarityClient

# Remote mode (calls the server)
client = ClarityClient(clarity_api_url="http://localhost:8000")

# Or local mode (everything in-process)
client = ClarityClient(local_mode=True, anthropic_api_key="sk-ant-...")

# Get LLM output + trust report
result = client.verify(
    messages=[{"role": "user", "content": "Write a merge sort in Python"}],
    system="You are a helpful coding assistant.",
    temperature=0.7,
)

print(result.content)      # The LLM output
print(result.score)        # 0-100 trust score
print(result.risk)         # "low", "medium", "high", "critical"
print(result.warnings)     # List of warnings
print(result.summary)      # Dict with per-agent scores
```

## Team Structure

- **Person A** — Backend Core (this repo layer)
- **Person B** — Verification Agents & LangGraph Pipeline
- **Person C** — Frontend Dashboard, SDK, and UX

See `CLARITY_CONTEXT.md` for detailed team responsibilities.

## Architecture

```
User Request
    ↓
[Interceptor] ← Captures request/response metadata
    ↓
[Metadata Extraction] ← Derives context signals
    ↓
[LangGraph Orchestrator] ← Fans out to 4 agents in parallel
    ├→ Hallucination Detector (30% weight)
    ├→ Reasoning Validator (25% weight)
    ├→ Confidence Calibrator (25% weight)
    └→ Context Analyzer (20% weight)
    ↓
[Aggregate] ← Weighted average + warnings
    ↓
[Trust Report] ← Persisted to InsForge
    ↓
User Response
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/verify` | Send messages → get LLM output + trust report |
| POST | `/api/v1/explain` | Explain trust report in plain language (Ada) |
| GET | `/api/v1/reports` | List recent reports |
| GET | `/api/v1/reports/{report_id}` | Fetch a single report |
| GET | `/api/v1/health` | Health check |

## Project Structure

```
clarity/
├── pyproject.toml              # Dependencies
├── .env.example                # Environment template
├── README.md                   # This file
├── dashboard/
│   └── index.html              # Trust report dashboard (Person C)
└── clarity/
    ├── config.py               # Settings from .env
    ├── sdk.py                  # Developer SDK
    ├── setup_db.py             # Database initialization
    ├── main.py                 # Server entry point
    ├── proxy/
    │   ├── interceptor.py      # Anthropic SDK wrapper
    │   └── metadata.py         # Context extraction
    ├── models/
    │   ├── request_capture.py  # CapturedExchange, RequestMetadata
    │   └── trust_report.py     # TrustReport, AgentVerdict
    ├── agents/
    │   ├── state.py            # LangGraph state (Person B)
    │   ├── orchestrator.py     # Pipeline runner (Person B)
    │   ├── hallucination.py    # Hallucination detector (Person B)
    │   ├── reasoning.py        # Reasoning validator (Person B)
    │   ├── confidence.py       # Confidence calibrator (Person B)
    │   └── context_analyzer.py # Context analyzer (Person B)
    ├── integrations/
    │   ├── insforge_client.py  # InsForge database client
    │   ├── tinyfish_client.py  # TinyFish web verification (Person B)
    │   └── ada_client.py       # Ada explainer (Person C)
    └── api/
        ├── app.py              # FastAPI setup
        └── routes.py           # API endpoints
```

## Next Steps

1. **Person A (You!)** — This layer is ready for backend testing
2. **Person B** — Implement the 4 agents and LangGraph orchestrator
3. **Person C** — Build out the dashboard and Ada integration
4. **Integration** — Connect all pieces and test end-to-end

See `CLARITY_CONTEXT.md` for detailed task breakdown.

---

**Questions?** Check the context doc or ask your team!
