# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend
```bash
# Start backend (from repo root)
python -m uvicorn api.main:app --reload --port 8000

# Run all tests
python -m unittest discover -s tests -p "test_*.py"

# Run a single test file
python -m unittest tests.test_analysis_service
```

### Frontend
```bash
cd frontend
npm install
npm run dev        # dev server at http://127.0.0.1:5173
npm run build      # tsc + vite build
```

### Environment
Copy `.env.template` to `.env` in the repo root and set `GOOGLE_API_KEY`. The backend loads it automatically on startup via `python-dotenv`.

## Architecture

This is a legal document analysis tool. A user submits a vendor's URL; the app discovers the vendor's legal pages, fetches them, and runs LLM analysis to surface risks.

### Backend (`api/`)
FastAPI server. `api/main.py` wires up five endpoints:
- `POST /api/analyze` — Terms & Conditions (risk highlights)
- `POST /api/analyze-dpa` — Data Processing Agreement checklist
- `POST /api/analyze-dpia` — DPIA threshold assessment + sections
- `POST /api/analyze-ropa` — ROPA fields (requires DPA + DPIA results in the request body)
- `POST /api/link-previews` — Metadata for a list of URLs

`api/schemas.py` defines all Pydantic request/response models shared by the API and mirrored as TypeScript interfaces in `frontend/src/api.ts`.

`api/services/` has one file per analysis type (`analysis_service.py`, `dpa_analysis_service.py`, etc.). Each service:
1. Calls a discovery tool from `legal_scout/tools/` to find relevant URLs on the vendor's site
2. Fetches page excerpts via `source_page_service.py`
3. Builds a prompt and calls the LLM via `langchain_runner.invoke_with_retry` (3 retries)
4. Parses the JSON response, validates citations against discovered URLs, and returns a typed dataclass

`api/services/formatter.py` generates confidence notes (e.g. blocked pages, citation failures).

### Agent Layer (`legal_scout/`)
`legal_scout/agents/` has one subdirectory per agent type (`terms_agent`, `dpa_agent`, `dpia_agent`, `ropa_agent`). Each contains:
- `agent.py` — constructs a `ChatGoogleGenerativeAI` instance (model: `gemini-2.5-flash`, temperature 0) and a `build_*_messages()` function
- `*.md` — the system prompt for that agent

`legal_scout/tools/` contains the URL discovery tools. They use `requests` + `BeautifulSoup` to crawl the homepage and find links matching known patterns for terms, DPA, and privacy pages.

### Frontend (`frontend/src/`)
React 18 + Vite + TypeScript. No state management library; all state lives in `App.tsx` hooks. Two routes:
- `/` → `LandingPage.tsx`
- `/app` → `App.tsx`

**Analysis flow in `App.tsx`**: The four analyses run sequentially — Terms → DPA → DPIA → ROPA (ROPA requires the DPA and DPIA responses as inputs). User can select which modules to run via checkboxes.

**Sessions** are persisted to `localStorage` under key `legal_scout_sessions` (versioned with `SESSIONS_VERSION = 1`). The sidebar shows past sessions; clicking one restores full results without re-fetching.

`frontend/src/api.ts` is the only API client. `VITE_API_BASE_URL` env var overrides the default `http://127.0.0.1:8000`.

### CORS
The backend allows origins `http://localhost:5173` and `http://127.0.0.1:5173` only. If you change the frontend port, update `api/main.py`.
