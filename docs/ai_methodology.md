# AI & ML Methodology

## Core Principle: Deterministic First, AI as Annotator

UrbanPulse follows the **ZeroResidual principle**:

> Every metric, score, citation, and statistic must come from a verified government dataset.
> LLMs are used **only** to synthesize natural language explanations of verified data.
> LLMs never generate, estimate, or hallucinate civic metrics.

---

## Three-Level Answering Strategy

### Level 1 — Verified UrbanPulse Data Only

**Trigger:** Pure factual queries about construction, crime, ESG, complaints, AQI.

**Pipeline:**
1. `QuestionClassifier` detects Level 1 (data-only query)
2. `EvidenceRetriever` pulls verified metrics from PostgreSQL
3. Answer built from deterministic data template — **no LLM call**

**Examples:**
- "How many BBMP work orders are in Indiranagar?"
- "What is the current AQI?"
- "How many crimes were recorded in 2021?"

### Level 2 — Hybrid (Verified Data + AI Synthesis)

**Trigger:** Locality-specific investment, safety, or livability assessment.

**Pipeline:**
1. `EvidenceRetriever` pulls ward data, police coverage, water index, complaints
2. `UrbanScoreEngine` computes deterministic UrbanScore (0-100)
3. `AIFactory.get_provider()` selects Ollama (Qwen3) or Deterministic Fallback
4. LLM synthesizes a contextualized explanation — **strictly grounded in evidence**

**Examples:**
- "Is Whitefield safe for investment?"
- "Compare Indiranagar and Koramangala"

### Level 3 — General AI Answer

**Trigger:** Urban planning concepts, ESG theory, generic civic questions.

**Pipeline:**
1. No local evidence retrieved
2. `AIFactory.get_provider()` → Qwen3:4b (primary) or Mistral (fallback)
3. LLM answers with explicit "General AI Answer" label — no fake citations

---

## AI Strategy Pattern

```python
class AIProviderStrategy(ABC):
    def generate(prompt, system_prompt, timeout) -> (text, model, fail_reason)
    def stream(prompt, system_prompt, timeout) -> Iterator[str]
    def is_available() -> bool

# Concrete implementations:
class OllamaProviderStrategy(AIProviderStrategy)     # calls local Ollama API
class DeterministicFallbackStrategy(AIProviderStrategy)  # zero-hallucination fallback
```

```python
# Factory selects strategy automatically:
provider = AIFactory.get_provider(preference="auto")
# → OllamaProviderStrategy  if Ollama is reachable
# → DeterministicFallbackStrategy  if Ollama is offline
```

---

## Semantic Cache

- **Key:** `sha256(normalize(question) + data_version)` — exact match, no cosine similarity
- **Backend:** Redis (optional, graceful fallback to no-cache)
- **TTL:** 24 hours (configurable via `REDIS_CACHE_TTL`)
- **Store policy:** Only cache real answers — never cache fallback or error messages

---

## Fallback Guarantees

| Condition | Behaviour |
|-----------|-----------|
| Ollama offline | Returns `MODE_DATA_ONLY` verified data summary |
| Redis offline | Cache miss on every request, LLM always called |
| External API (Open-Meteo) fails | HTTP 502 with explicit upstream error |
| Data metric unavailable | Disclosed as `unavailable`, never fabricated |
| LLM timeout | Falls back to Mistral, then to data-only response |

---

## Model Configuration

| Setting | Default | Purpose |
|---------|---------|---------|
| `OLLAMA_PRIMARY_MODEL` | `qwen3:4b` | Level 2/3 primary |
| `OLLAMA_FALLBACK_MODEL` | `mistral` | Level 3 fallback |
| `OLLAMA_TIMEOUT_SECONDS` | `30` | Per-request timeout |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama instance |
