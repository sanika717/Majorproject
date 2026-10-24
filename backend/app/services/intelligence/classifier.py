"""
UrbanPulse Question Classifier — Three-Level Answering Strategy.

Determines whether a question is:
  LEVEL_1  — Answered purely from verified UrbanPulse PostgreSQL data
  LEVEL_2  — Hybrid: UrbanPulse data + Qwen/Mistral interpretation
  LEVEL_3  — General: no relevant local data, answered by AI only

Priority rules (evaluated in order):
  1. Explanation/concept question (starts with "what is", "explain", etc.) and no
     locality evidence → LEVEL_3 (general AI), unless a specific Bengaluru locality
     is named.
  2. Locality evidence present + property intent → LEVEL_2 (hybrid)
  3. Locality evidence present + any local data signal → LEVEL_2
  4. Strong local data signals (>=2) without locality evidence → LEVEL_1
  5. Weak local data signal, no general signals → LEVEL_2
  6. General AI signals only → LEVEL_3
  7. No signals → LEVEL_3
  8. Mixed → LEVEL_2
"""

from typing import Tuple

# Level labels
LEVEL_1 = "VERIFIED_DATA"   # answer purely from database
LEVEL_2 = "HYBRID"          # data + AI interpretation
LEVEL_3 = "GENERAL_AI"      # general knowledge, no local data

# ── Locality names (trigger strong local-data signal even without DB evidence) ─
_BENGALURU_LOCALITIES = {
    "whitefield", "hsr layout", "hsr", "koramangala", "indiranagar",
    "bellandur", "jayanagar", "peenya", "yelahanka", "malleswaram",
    "hebbal", "btm", "marathahalli", "varthur", "hoodi", "kadugodi",
    "electronic city", "mahadevapura", "bommanahalli", "rajajinagar",
    "basavanagudi", "banashankari", "hebbal", "yeshwanthpur", "kr puram",
    "rt nagar", "mathikere", "vijayanagar",
}

# ── Civic data terms — signals that UrbanPulse DB may have relevant records ──
_URBANPULSE_DATA_TERMS = {
    # Construction / BBMP
    "bbmp", "work order", "construction", "ward", "investment", "expenditure",
    "contractor", "drain", "road project", "civic work", "deduction", "cluster",
    # Crime / police
    "crime", "d47", "police", "station", "outpost", "risk score",
    "murder", "theft", "robbery", "assault", "cyber crime", "women crime",
    "children crime", "fatal",
    # ESG / environment (specific measurements)
    "air quality", "aqi", "pm2.5", "pm10", "no2", "so2",
    "lake", "water quality", "carbon emission", "electricity consumption", "bescom",
    "ghg emission", "greenhouse emission",
    # Complaints / grievance
    "complaint", "grievance", "civic issue", "resolution", "pending",
    # Scoring
    "urban score", "urbanscore",
    # Financial / property decision (with locality context)
    "buy house", "buy a house", "invest in ", "property in ", "real estate in ",
    "should i move", "buy flat", "buy apartment", "buy in ", "live in ", "settle in ",
    # Generic bengaluru
    "bengaluru", "bangalore", "bbmp ward",
}

# ── General AI / concept terms ─────────────────────────────────────────────────
_GENERAL_AI_TERMS = {
    "urban planning", "city planning", "zoning",
    "factors to consider", "what should i consider", "how to choose",
    "advice on", "tips for", "guide to", "recommend", "suggestion",
    "interest rate", "loan", "emi", "market trend", "inflation",
    "machine learning", "artificial intelligence", "data science",
    "how can a city", "public safety strategy",
}

# ── Explanation/concept prefixes — always LEVEL_3 unless specific locality ─────
_EXPLANATION_PREFIXES = (
    "what is ", "what are ", "explain ", "how does ", "how do ",
    "how can a ", "why is ", "why are ", "difference between",
    "what factors", "tips for ", "guide to ", "limitations of",
    "what are the limitations",
)


def _has_locality(q: str) -> bool:
    """Returns True if any known Bengaluru locality is mentioned in the lowercased question."""
    return any(loc in q for loc in _BENGALURU_LOCALITIES)


def classify_question(question: str, has_locality_evidence: bool = False) -> Tuple[str, str]:
    """
    Routes the question to one of three levels.

    Returns:
        (level, reason) — level is LEVEL_1/2/3, reason is a human-readable note.
    """
    q = question.lower().strip()

    local_hits = sum(1 for term in _URBANPULSE_DATA_TERMS if term in q)
    general_hits = sum(1 for term in _GENERAL_AI_TERMS if term in q)

    # Count locality name mentions as strong local signals
    has_loc = _has_locality(q)
    if has_loc:
        local_hits += 2   # boost

    property_terms = {"buy", "invest", "property", "flat", "apartment", "house", "home", "residential"}
    has_property_intent = any(t in q for t in property_terms)

    # ── Rule 1: Explanation/concept question with no specific metric data terms ──
    # Only applies when: explanation prefix is present AND no specific Bengaluru data
    # terms (other than the locality bonus) make it look like a factual data query.
    is_explanation = any(q.startswith(p) or p in q for p in _EXPLANATION_PREFIXES)
    # "What is the total BBMP investment" has data terms → NOT a concept question
    raw_local_hits = sum(1 for term in _URBANPULSE_DATA_TERMS if term in q)  # without locality boost
    if is_explanation and not has_locality_evidence and not has_loc and raw_local_hits < 2:
        return LEVEL_3, "Concept/explanation question — general AI"

    # ── Rule 2: Locality evidence + property intent → hybrid ──
    if has_locality_evidence and has_property_intent:
        return LEVEL_2, "Property/investment question with verified locality data"

    # ── Rule 2b: Locality named in question + property intent → hybrid ──
    if has_loc and has_property_intent:
        return LEVEL_2, "Property/investment question mentioning a Bengaluru locality"

    # ── Rule 3: Locality evidence + local data signal → hybrid ──
    if has_locality_evidence and local_hits >= 1:
        return LEVEL_2, "Locality-specific civic question with verified evidence"

    # ── Rule 3b: Locality named + local data signal → hybrid ──
    if has_loc and local_hits >= 1:
        return LEVEL_2, "Locality named with local data signal — hybrid response"

    # ── Rule 4: Strong local data signals (without locality), no explanation intent ──
    if raw_local_hits >= 2 and not has_locality_evidence and not is_explanation:
        return LEVEL_1, "Citywide UrbanPulse data question"

    # ── Rule 5: Weak local signal only → hybrid ──
    if local_hits >= 1 and general_hits == 0:
        return LEVEL_2, "Partial UrbanPulse data match — hybrid response"

    # ── Rule 6: General AI signals only ──
    if general_hits >= 1 and local_hits == 0:
        return LEVEL_3, "General knowledge question — no local data match"

    # ── Rule 7: No signals → general AI ──
    if local_hits == 0 and general_hits == 0:
        return LEVEL_3, "No local data signals detected"

    # ── Rule 8: Mixed signals → hybrid ──
    return LEVEL_2, "Mixed local + general signals — hybrid response"



def is_general_question(question: str) -> bool:
    level, _ = classify_question(question, has_locality_evidence=False)
    return level == LEVEL_3
