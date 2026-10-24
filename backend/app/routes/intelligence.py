"""
FastAPI Routes for UrbanPulse Intelligence Assistant, UrbanScore, and Comparisons.
Strictly grounded in verified PostgreSQL civic datasets and Ollama qwen3:8b.
"""

import time
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.core.config import settings
from backend.app.schemas.intelligence import (
    AskRequest,
    AskResponse,
    UrbanScoreResponse,
    CompareResponse,
)
from backend.app.services.intelligence.assistant_service import assistant_service
from backend.app.services.intelligence.retriever import evidence_retriever
from backend.app.services.intelligence.urban_score import calculate_urban_score
from backend.app.services.intelligence.cache import semantic_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intelligence", tags=["Intelligence Assistant"])


@router.post("/ask", response_model=AskResponse, summary="Three-level civic Q&A: Verified Data / Hybrid / General AI")
def ask_assistant(
    request: AskRequest,
    db: Session = Depends(get_db)
):
    """
    Three-level intelligent answering strategy:

    **Level 1 — Verified UrbanPulse Data**: Bengaluru-specific civic questions
    (construction, crime, ESG, complaints) answered from PostgreSQL records only.

    **Level 2 — Hybrid (Data + AI)**: Locality-specific investment/property/safety
    questions: real UrbanScore + component data enriched by Qwen3:8b interpretation.

    **Level 3 — General AI**: Urban planning, ESG concepts, generic advice answered
    by Qwen3:8b (primary) or Mistral (fallback). Clearly labelled, no fake citations.

    Redis semantic cache is checked first; LLMs are called only on cache miss.
    """
    if not request.question or not request.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty."
        )

    try:
        result = assistant_service.answer_question(
            db=db,
            question=request.question,
            locality=request.locality,
            use_cache=request.enable_cache
        )
        return AskResponse(**result)
    except Exception as exc:
        logger.error(f"[Intelligence API] Error processing question: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Intelligence assistant error: {str(exc)}"
        )


@router.get("/urban-score", response_model=UrbanScoreResponse, summary="Calculate verified UrbanScore for a locality")
def get_urban_score(
    area: str = Query(..., min_length=2, max_length=100, description="Locality or ward name, e.g. Whitefield, HSR Layout, Indiranagar"),
    db: Session = Depends(get_db)
):
    """
    Calculates the UrbanPulse UrbanScore (0-100) for a Bengaluru locality
    using real datasets across Safety (25%), Infrastructure (25%), Environment (20%),
    Social Infrastructure (15%), and Governance (15%).
    Never invents data; discloses all missing metrics and coverage limitations.
    """
    clean_area = area.strip()
    evidence = evidence_retriever.get_locality_evidence(db, clean_area)
    score_data = calculate_urban_score(evidence)
    return UrbanScoreResponse(**score_data)


@router.get("/compare", response_model=CompareResponse, summary="Compare UrbanScores and metrics of two or more localities")
def compare_localities(
    areas: str = Query(..., description="Comma-separated locality names, e.g. 'Whitefield,HSR Layout' or 'Indiranagar,Koramangala'"),
    db: Session = Depends(get_db)
):
    """
    Compares two or more Bengaluru localities side-by-side using comparable
    civic indicators from BBMP construction, police presence, lake water, complaints, and UrbanScore.
    """
    area_list = [a.strip() for a in areas.split(",") if a.strip()]
    if len(area_list) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide at least 2 comma-separated areas to compare."
        )
    if len(area_list) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 5 areas can be compared simultaneously."
        )

    score_results = []
    evidence_list = []
    for a in area_list:
        ev = evidence_retriever.get_locality_evidence(db, a)
        evidence_list.append(ev)
        sc = calculate_urban_score(ev)
        score_results.append(sc)

    # Determine highest scoring
    sorted_scores = sorted(score_results, key=lambda s: s["score"], reverse=True)
    winner = sorted_scores[0]["locality"] if sorted_scores else None

    # Build comparison summary
    diff = round(sorted_scores[0]["score"] - sorted_scores[-1]["score"], 1) if len(sorted_scores) >= 2 else 0
    summary_parts = [
        f"Compared {len(score_results)} localities: {', '.join(a['locality'] for a in score_results)}.",
        f"{sorted_scores[0]['locality']} leads with an UrbanScore of {sorted_scores[0]['score']}/100 ({sorted_scores[0]['grade']}), "
        f"outperforming {sorted_scores[-1]['locality']} ({sorted_scores[-1]['score']}/100, {sorted_scores[-1]['grade']}) by {diff} points."
    ]
    summary_parts.append(
        "Scores reflect verified BBMP 2025-26 capital expenditure, mapped police coverage, lake water quality indices, and recorded public complaints."
    )

    # Build metrics comparison table
    metrics_table = []
    # Row: Overall UrbanScore
    metrics_table.append({
        "metric": "UrbanScore (Overall)",
        "values": {sc["locality"]: f"{sc['score']}/100 ({sc['grade']})" for sc in score_results}
    })
    # Component: Safety
    metrics_table.append({
        "metric": "Safety Score (Weight: 25%)",
        "values": {
            sc["locality"]: (f"{sc['components']['safety']['score']}/100" if sc['components']['safety']['score'] is not None else "Data Unavailable")
            for sc in score_results
        }
    })
    # Component: Infrastructure
    metrics_table.append({
        "metric": "Infrastructure Score (Weight: 25%)",
        "values": {
            sc["locality"]: (f"{sc['components']['infrastructure']['score']}/100" if sc['components']['infrastructure']['score'] is not None else "Data Unavailable")
            for sc in score_results
        }
    })
    # Component: Environment
    metrics_table.append({
        "metric": "Environment Score (Weight: 20%)",
        "values": {
            sc["locality"]: (f"{sc['components']['environment']['score']}/100" if sc['components']['environment']['score'] is not None else "Data Unavailable")
            for sc in score_results
        }
    })
    # Component: Social Infrastructure
    metrics_table.append({
        "metric": "Social Infrastructure (Weight: 15%)",
        "values": {
            sc["locality"]: (f"{sc['components'].get('social_infrastructure', {}).get('score')}/100" if sc['components'].get('social_infrastructure', {}).get('score') is not None else "Data Unavailable")
            for sc in score_results
        }
    })
    # Component: Governance
    metrics_table.append({
        "metric": "Governance Score (Weight: 15%)",
        "values": {
            sc["locality"]: (f"{sc['components']['governance']['score']}/100" if sc['components']['governance']['score'] is not None else "Data Unavailable")
            for sc in score_results
        }
    })
    # Detailed BBMP Investment
    metrics_table.append({
        "metric": "BBMP Construction Investment (2025–26)",
        "values": {
            ev["display_name"]: (f"₹{ev['ward_data']['total_amount_cr']} Cr ({ev['ward_data']['total_work_orders']} orders)" if ev.get("ward_data") else "Not Mapped")
            for ev in evidence_list
        }
    })
    # Police Coverage
    metrics_table.append({
        "metric": "Police Presence (GIS Mapped)",
        "values": {
            ev["display_name"]: (f"{ev['police_data']['station_count']} station(s), {ev['police_data']['outpost_count']} outpost(s)" if ev.get("police_data") else "Not Mapped")
            for ev in evidence_list
        }
    })
    # Data Coverage
    metrics_table.append({
        "metric": "Data Coverage & Confidence",
        "values": {
            sc["locality"]: f"{sc['data_coverage_pct']}% ({sc['confidence']})"
            for sc in score_results
        }
    })

    return CompareResponse(
        areas=[sc["locality"] for sc in score_results],
        scores=score_results,
        comparison_summary=" ".join(summary_parts),
        winner_overall=winner,
        metrics_table=metrics_table
    )


@router.get("/status", summary="Check status of LLM (Ollama), Redis semantic cache, and datasets")
def get_intelligence_status():
    """
    Returns live connectivity and operational readiness of Ollama (qwen3:8b),
    Redis semantic vector cache, and supported locality mappings.
    """
    cache_health = semantic_cache.health_check()
    ollama_info = assistant_service.get_ollama_status()
    locality_count = len(evidence_retriever.get_all_supported_localities())

    return {
        "status": "operational",
        "platform": "UrbanPulse Intelligence",
        "model": ollama_info,
        "cache": cache_health,
        "localities_indexed": locality_count,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S IST", time.localtime())
    }


@router.post("/cache/clear", summary="Clear the Redis semantic cache")
def clear_cache():
    """Admin endpoint to invalidate the Redis semantic cache."""
    cleared = semantic_cache.clear()
    return {"cleared": cleared, "message": "Semantic cache cleared successfully."}

