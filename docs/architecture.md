# UrbanPulse Architecture

## Overview

UrbanPulse is an evidence-based Smart City Transparency platform for Bengaluru, India.
It aggregates public government datasets (BBMP, CPCB, Karnataka Police, KSPCB, BESCOM) into a
single civic intelligence dashboard with ESG scoring, construction analytics, crime risk mapping,
and an AI-powered Q&A assistant grounded strictly in verified data.

---

## Layered Backend Architecture

```
HTTP Requests
      │
      ▼
┌─────────────────────────────────┐
│          Routes Layer            │  FastAPI route handlers
│  (routes/*.py)                   │  — input validation, HTTP concerns only
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│          Services Layer          │  Business logic orchestration
│  (services/*.py)                 │  — complaint_service, esg_service, etc.
└──────────────┬──────────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
┌───────────┐    ┌──────────────┐
│  Engines  │    │   Adapters   │  Pure computation vs. External I/O
│  Layer    │    │   Layer      │
└───────────┘    └──────────────┘
      │                 │
      ▼                 ▼
┌─────────────────────────────────┐
│        Repositories Layer        │  Database query encapsulation
│  (repositories/*.py)             │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│          Models Layer            │  SQLAlchemy ORM models
│  (models/*.py)                   │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│          Database Layer          │  PostgreSQL via psycopg2
│  (db/session.py)                 │
└──────────────┬──────────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
┌───────────┐    ┌──────────────┐
│   Cache   │    │  Intelligence │
│  (Redis)  │    │  (Ollama LLM) │
└───────────┘    └──────────────┘
```

---

## Module Map

```
backend/app/
├── core/
│   ├── config.py              # Pydantic settings from .env
│   └── logging_config.py      # Structured logging configuration
├── routes/                    # FastAPI route handlers (HTTP only)
│   ├── esg.py
│   ├── intelligence.py
│   ├── construction.py
│   ├── crime.py
│   ├── complaints.py
│   └── ...
├── services/                  # Business logic orchestration
│   ├── esg_service.py
│   ├── construction_service.py
│   ├── crime_service.py
│   ├── complaint_service.py
│   ├── auth_service.py
│   ├── esg_update/            # Scheduled ESG data ingestion jobs
│   │   ├── air_cpcb.py
│   │   ├── electricity_bescom.py
│   │   ├── file_sources.py
│   │   └── scheduler.py
│   └── intelligence/          # AI assistant pipeline
│       ├── assistant_service.py
│       ├── ai_strategy.py     # Strategy + Factory patterns
│       ├── ollama_client.py
│       ├── retriever.py
│       ├── urban_score.py
│       ├── cache.py
│       └── classifier.py
├── adapters/                  # Adapter Design Pattern — data normalization
│   ├── base.py                # BaseDataAdapter ABC
│   ├── factory.py             # AdapterFactory
│   ├── bbmp_adapter.py        # BBMP work orders
│   ├── crime_adapter.py       # Crime statistics
│   ├── aqi_adapter.py         # CPCB / Open-Meteo AQI
│   ├── water_adapter.py       # KSPCB MINARS water
│   ├── electricity_adapter.py # BESCOM electricity
│   └── geospatial_adapter.py  # Police GIS / GeoJSON
├── engines/                   # Deterministic calculation engines (zero LLM)
│   ├── esg_engine.py          # CPCB AQI + ESG pillar scoring
│   ├── clustering_engine.py   # K-Means++ ward analytics
│   └── urban_score_engine.py  # Multi-locality comparison
├── repositories/              # Repository Pattern — DB access
│   ├── base.py                # BaseRepository generic
│   ├── construction_repo.py
│   ├── crime_repo.py
│   ├── complaint_repo.py
│   └── esg_repo.py
├── models/                    # SQLAlchemy ORM models
├── schemas/                   # Pydantic request/response schemas
└── db/                        # SQLAlchemy engine & session factory
```

---

## Design Patterns Applied

| Pattern | Location | Purpose |
|---|---|---|
| **Adapter** | `adapters/` | Normalize heterogeneous external data sources |
| **Factory** | `adapters/factory.py` | Dynamic adapter discovery by source type |
| **Strategy** | `services/intelligence/ai_strategy.py` | Swap Ollama ↔ Deterministic fallback |
| **Factory** | `services/intelligence/ai_strategy.py` | Select AI provider based on availability |
| **Repository** | `repositories/` | Decouple DB queries from business services |
| **Template Method** | `adapters/base.py` | Enforce fetch→normalize→validate→handle_missing→ingest pipeline |

---

## Data Flow: ESG Scoring

```
Live API Call (Open-Meteo CAMS)
        │
        ▼
   AqiDataAdapter
   .fetch() → .normalize() → .validate() → .handle_missing()
        │
        ▼
   EsgEngine.calculate_cpcb_aqi(pm25, pm10)
   ← CPCB National AQI Breakpoints formula
        │
        ▼
   EsgEngine.calculate_environmental_pillar(aqi_score, avg_lake_bod)
        │
   EsgEngine.calculate_social_pillar(resolution_rate, safety_index)
        │
   EsgEngine.calculate_governance_pillar(contractor_diversity, transparency)
        │
        ▼
   EsgEngine.calculate_composite_esg(env, social, gov)
   ← 40% Env + 35% Social + 25% Gov → Composite 0-100
        │
        ▼
   /api/v1/esg/* response (no LLM involved)
```

---

## Data Flow: AI Intelligence Q&A

```
POST /api/v1/intelligence/ask
        │
        ▼
   SemanticCache.lookup(sha256(normalized_question))
   ├── CACHE HIT → return immediately
   └── CACHE MISS ↓
        │
        ▼
   QuestionClassifier → Level 1/2/3
        │
   Level 1: EvidenceRetriever (SQL) → deterministic data template
   Level 2: EvidenceRetriever + AIFactory.get_provider() → Qwen3 synthesis
   Level 3: AIFactory.get_provider() → Qwen3 / Mistral general answer
        │
        ▼
   AIFactory (Strategy Pattern)
   ├── OllamaProviderStrategy  (if Ollama reachable)
   └── DeterministicFallbackStrategy (if Ollama offline)
        │
        ▼
   SemanticCache.store() (only real answers, not fallback/error)
        │
        ▼
   AskResponse (answer, sources, answer_mode, latency_ms)
```
