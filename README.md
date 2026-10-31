# UrbanPulse — Smart City Transparency Platform

Evidence-based civic intelligence platform for Bengaluru, built as a college final-year project.  
Combines BBMP construction data, D47 crime records, police station maps, ESG environmental metrics, and a local Ollama AI assistant into a single interactive dashboard.

---

## Project Structure

```
urbanpulse/
├── backend/
│   ├── app/
│   │   ├── core/        # Settings (Pydantic)
│   │   ├── db/          # SQLAlchemy session, Base
│   │   ├── models/      # ORM models
│   │   ├── routes/      # FastAPI routers
│   │   ├── schemas/     # Pydantic request/response schemas
│   │   ├── services/    # Business logic, ESG updater, Intelligence
│   │   └── main.py      # Single application entrypoint
│   ├── alembic/         # Database migrations
│   ├── scripts/         # seed_db.py, seed_esg.py
│   ├── tests/           # pytest test suite
│   ├── Dockerfile       # Multi-stage Python 3.11-slim image
│   └── requirements.txt
├── frontend/            # Plain HTML / CSS / JavaScript (no framework)
│   ├── dashboard.html   # Main dashboard with interactive Leaflet map
│   ├── analytics.html   # Construction & crime charts
│   ├── esg.html         # ESG scorecard
│   ├── assistant.html   # AI Intelligence Assistant
│   ├── complaints.html  # Public complaint portal
│   ├── css/style.css
│   └── js/              # api.js, map.js, assistant.js, …
├── data/
│   ├── construction/    # BBMP work-order CSV + JSON
│   ├── crime/           # D47 crime JSON, police KML
│   └── kml/             # KML boundary files
├── docker-compose.yml   # api + postgres + redis
├── .env.example         # Copy → .env and fill secrets
├── pytest.ini
└── alembic.ini
```

---

## Quick Start

### Option A — Docker Compose (recommended)

```bash
# 1. Copy and fill secrets
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD and optionally Supabase/Google AQI keys

# 2. Ensure Ollama is running on the host with the required models
ollama serve &
ollama pull qwen3:4b
ollama pull nomic-embed-text

# 3. Start everything
docker compose up --build

# Dashboard: http://localhost:8000/frontend/dashboard.html
# API docs:  http://localhost:8000/docs
# Health:    http://localhost:8000/api/v1/health
```

> **Ollama note:** Docker Compose sets `OLLAMA_BASE_URL=http://host.docker.internal:11434`  
> so the container can reach Ollama running on your Mac/Linux host without any extra config.

---

### Option B — Local (without Docker)

**Prerequisites:** Python 3.11+, PostgreSQL 15, Ollama

```bash
# 1. Clone and enter
git clone https://github.com/sanika717/Majorproject.git urbanpulse
cd urbanpulse

# 2. Virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 3. Create database
createdb urbanpulse

# 4. Copy and fill secrets
cp .env.example .env
# Set DATABASE_URL=postgresql://localhost:5432/urbanpulse and any optional keys

# 5. Run database migrations / seed
python -m backend.scripts.seed_db
python -m backend.scripts.seed_esg   # optional — seeds ESG live data

# 6. Start Ollama (in a separate terminal)
ollama serve
ollama pull qwen3:4b
ollama pull nomic-embed-text

# 7. Start the backend (serves frontend too)
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Dashboard: http://localhost:8000/frontend/dashboard.html
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/dashboard/kpis` | Headline KPI figures |
| GET | `/api/v1/construction/wards` | BBMP ward-level data |
| GET | `/api/v1/crime/historical` | D47 crime dataset |
| GET | `/api/v1/police/locations` | KML-derived police station locations |
| GET | `/api/v1/esg/aqi` | Live Bengaluru AQI |
| POST | `/api/v1/intelligence/ask` | AI assistant (3-level strategy) |
| GET | `/api/v1/intelligence/urban-score` | UrbanScore for a locality |
| GET | `/api/v1/intelligence/compare` | Compare up to 5 localities |
| POST | `/api/v1/complaints/` | Submit civic complaint |
| GET | `/docs` | Swagger UI (dev only) |

---

## Intelligence Assistant

Three-level answering strategy — all grounded in the project's PostgreSQL datasets:

1. **Verified UrbanPulse Data** — construction/crime/ESG facts answered directly from DB records
2. **Hybrid (Data + AI)** — UrbanScore + Qwen3:4b interpretation for locality/property questions
3. **General AI** — Urban planning concepts answered by Qwen3:4b; clearly labelled, no fake citations

When Ollama is offline, the assistant degrades gracefully to **data-only mode** and returns a deterministic answer from the database. Redis semantic cache is optional — the service bypasses it transparently if Redis is unavailable.

---

## Running Tests

```bash
# Unit + API tests (no Ollama required — Ollama is mocked)
pytest backend/tests/ -v -m "not slow"

# Live Ollama integration tests (requires Ollama running locally)
pytest backend/tests/ -v -m slow
```

---

## Environment Variables

See [`.env.example`](.env.example) for the full list. Key variables:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `POSTGRES_PASSWORD` | Required when using Docker Compose |
| `OLLAMA_BASE_URL` | Ollama server URL (`http://127.0.0.1:11434` locally) |
| `OLLAMA_PRIMARY_MODEL` | Primary LLM (`qwen3:4b`) |
| `REDIS_URL` | Optional Redis URL for semantic cache |
| `SUPABASE_*` | Supabase auth credentials (optional — JWT auth) |
| `GOOGLE_AQI_API_KEY` | Optional live AQI feed |

---

## Dataset Sources

| Dataset | Source | Coverage |
|---------|--------|----------|
| BBMP Construction | data.gov.in — Work Orders 2025–26 | 198 wards, 4,729 records |
| Crime (D47) | Karnataka Police — IPC categories | 2014–2021, 35,971 records |
| Police Stations | Karnataka KML open data | 150 locations |
| ESG — AQI | Google Air Quality API | Live, Bengaluru |
| ESG — Water | KSPCB MINARS | 2020–21, 102 stations |
| Civic Map | OpenStreetMap Overpass + verified snapshot | 314 features |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy, PostgreSQL 15 |
| Auth | Supabase + PyJWT |
| AI | Ollama (qwen3:4b), nomic-embed-text, Redis |
| Frontend | Plain HTML, Vanilla CSS, Vanilla JS, Leaflet |
| Container | Docker + Docker Compose |
| CI | GitHub Actions |
