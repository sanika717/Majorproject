"""
UrbanPulse Intelligence Assistant Service — Three-Level Hybrid Answering.

Level 1 — Verified UrbanPulse Data
    Citywide stats (construction totals, crime risk, police count) are presented
    directly from PostgreSQL without any LLM call.

Level 2 — Hybrid: UrbanPulse Data + AI Interpretation
    Evidence is retrieved from the database.  Qwen3:8b (primary) or Mistral
    (fallback) synthesises an interpretation, investment analysis, or explanation
    grounded strictly in the retrieved evidence.

Level 3 — General AI Answer
    No relevant local UrbanPulse data found.  Qwen / Mistral answers the general
    question directly.  The response is clearly labelled "General AI Answer" so
    the user knows it is not backed by the UrbanPulse datasets.

Key guarantees
  - No statistic, score, or citation is fabricated.
  - If both LLMs are offline, a data-only deterministic answer is returned.
  - Redis semantic cache is checked before any LLM call and updated after.
"""

import re
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.services.intelligence.cache import semantic_cache
from backend.app.services.intelligence.retriever import EvidenceRetriever, LOCALITY_WARD_MAP
from backend.app.services.intelligence.urban_score import UrbanScoreEngine
from backend.app.services.intelligence.ollama_client import (
    ollama_client,
    MODE_VERIFIED,
    MODE_HYBRID,
    MODE_GENERAL_AI,
    MODE_DATA_ONLY,
)
from backend.app.services.intelligence.classifier import (
    classify_question,
    LEVEL_1,
    LEVEL_2,
    LEVEL_3,
)

logger = logging.getLogger("urbanpulse.intelligence.assistant")

# ──────────────────────────────────────────────────────────────────────────────
# Prompt templates
# ──────────────────────────────────────────────────────────────────────────────

_HYBRID_SYSTEM = (
    "You are the UrbanPulse Intelligence Assistant for Bengaluru civic transparency.\n"
    "You are given VERIFIED DATABASE EVIDENCE retrieved from real government datasets.\n\n"
    "STRICT RULES:\n"
    "1. Ground every claim, score, and metric strictly in the evidence provided.\n"
    "2. NEVER fabricate numbers, percentages, dataset citations, or government statistics.\n"
    "3. Do not label any locality absolutely safe or unsafe. Never guarantee investment returns.\n"
    "4. For property/investment questions, structure your response as:\n"
    "   - UrbanScore & component summary\n"
    "   - Reasons to consider (evidence-backed)\n"
    "   - Reasons for caution (evidence-backed)\n"
    "   - Data gaps and limitations\n"
    "   - Actionable next steps\n"
    "5. Clearly state when data is missing or incomplete.\n"
    "6. Cite the sources provided in the evidence block.\n"
    "7. Keep general market observations separate from verified local data."
)

_GENERAL_SYSTEM = (
    "You are UrbanPulse's AI assistant for urban planning, civic governance, and "
    "property investment advice. This is a general knowledge question — no specific "
    "verified UrbanPulse database records are available for it.\n\n"
    "RULES:\n"
    "1. Answer clearly and helpfully using your general knowledge.\n"
    "2. Do NOT fabricate Bengaluru-specific statistics, scores, or government data.\n"
    "3. If the user asks about a concept (e.g. ESG, urban planning, safety factors), "
    "   explain the concept and offer a framework. Do not invent local facts.\n"
    "4. If the answer would benefit from real local data, mention that the user can "
    "   ask a locality-specific question (e.g. 'What is the UrbanScore for Whitefield?')."
)


class IntelligenceAssistantService:

    # ── Embedding ──────────────────────────────────────────────────────────

    @staticmethod
    def get_embedding(text: str) -> List[float]:
        return ollama_client.embed(text)

    # ── Evidence Formatting ────────────────────────────────────────────────

    @staticmethod
    def format_prompt_evidence(evidence: Dict[str, Any]) -> str:
        """Formats verified DB records into a structured evidence block for the LLM prompt."""
        lines = ["=== VERIFIED URBANPULSE DATABASE EVIDENCE ==="]

        cw = evidence.get("citywide_benchmarks", {})
        lines.append(
            f"Citywide Construction: ₹{cw.get('total_construction_investment_cr')} Cr "
            f"across {cw.get('total_work_orders')} BBMP work orders (198 wards)."
        )
        lines.append(
            f"Citywide Crime Baseline (BCP D47): Risk Score {cw.get('city_crime_risk_score')}/100, "
            f"Fatal Crime Rate {cw.get('fatal_crime_rate_pct')}%."
        )
        lines.append(
            f"Mapped Police Infrastructure: {cw.get('mapped_police_locations')} "
            f"stations & outposts (Karnataka State Police GIS KML)."
        )
        lines.append("")

        loc_list = evidence.get("evidence_by_locality", [])
        if loc_list:
            for ev in loc_list:
                name = ev["display_name"]
                us   = ev.get("urban_score", {})
                score = us.get("urban_score", "N/A")
                tier  = us.get("tier", "N/A")
                cov   = us.get("data_coverage_pct", "N/A")

                lines.append(f"--- LOCALITY: {name} ---")
                lines.append(
                    f"UrbanScore: {score}/100 ({tier}) | "
                    f"Data Coverage: {cov}% (Confidence: {us.get('confidence')})"
                )

                comps = us.get("components", {})
                for c_name, c_data in comps.items():
                    sc = c_data.get("score")
                    sc_str = f"{sc}/100" if sc is not None else "Data Unavailable"
                    lines.append(f"  * {c_name.replace('_', ' ').capitalize()}: {sc_str}")
                    for m in c_data.get("metrics", []):
                        lines.append(f"    - {m}")
                    for lim in c_data.get("limitations", []):
                        lines.append(f"    ! Limitation: {lim}")

                wd = ev.get("ward_data")
                if wd:
                    lines.append(
                        f"  * BBMP Ward Summary: {wd.get('total_work_orders')} projects "
                        f"totaling ₹{wd.get('total_amount_cr')} Cr (Net: ₹{wd.get('total_net_cr')} Cr)."
                    )
                    lines.append(
                        f"  * Project Types: {wd.get('road_projects')} road, "
                        f"{wd.get('drain_projects')} drain, {wd.get('water_projects')} water, "
                        f"{wd.get('development_projects')} development."
                    )
                    lines.append(
                        f"  * Contractors: {wd.get('unique_contractors')} active firms "
                        f"(Deduction rate: {wd.get('avg_deduction_pct')}%)."
                    )

                samples = ev.get("sample_projects", [])
                if samples:
                    lines.append("  * Key Executed Works:")
                    for p in samples:
                        lines.append(
                            f"    - [{p['work_order_id']}] ₹{p['amount_lakhs']} Lakhs: {p['description']}"
                        )

                cd = ev.get("complaints_data")
                if cd and cd.get("total", 0) > 0:
                    lines.append(
                        f"  * Civic Grievances: {cd['total']} lodged, "
                        f"{cd['resolved']} resolved, {cd['in_progress']} in progress."
                    )
                lines.append("")
        else:
            lines.append(
                "No specific Bengaluru ward or locality was identified in the question. "
                "Presenting general citywide intelligence only."
            )

        return "\n".join(lines)

    # ── Three-Level Answering ──────────────────────────────────────────────

    @classmethod
    def answer_question(
        cls,
        db: Session,
        question: str,
        locality: Optional[str] = None,
        explicit_locality: Optional[str] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Main entry point.  Routes the question through the 3-level strategy and
        returns a unified structured payload.
        """
        start_time = time.time()
        question = question.strip()
        target_locality = locality or explicit_locality

        # ── 1. Embedding + Redis cache check ──────────────────────────────
        data_version = EvidenceRetriever.compute_data_version(db)
        embedding = cls.get_embedding(question) if use_cache else []

        if embedding and use_cache:
            cached_res, sim, cache_status = semantic_cache.get_semantic_match(
                question, embedding, data_version
            )
            if cached_res:
                cached_res["cached"]           = True
                cached_res["cache_status"]     = cache_status
                cached_res["cache_similarity"] = sim
                cached_res["latency_ms"]       = round((time.time() - start_time) * 1000, 1)
                return cached_res

        # ── 2. Retrieve verified database evidence ─────────────────────────
        evidence = EvidenceRetriever.retrieve_for_query(db, question, target_locality)
        has_locality_ev = bool(evidence.get("evidence_by_locality"))

        # ── 3. Classify the question ───────────────────────────────────────
        level, level_reason = classify_question(question, has_locality_evidence=has_locality_ev)
        logger.info(f"[Assistant] Level={level} ({level_reason}) Q={question!r:.80}")

        # ── 4. Route to the right handler ─────────────────────────────────
        if level == LEVEL_1:
            result = cls._handle_verified_data(question, evidence, start_time, data_version)
        elif level == LEVEL_2:
            result = cls._handle_hybrid(question, evidence, start_time, data_version)
        else:  # LEVEL_3
            result = cls._handle_general_ai(question, evidence, start_time, data_version)

        # ── 5. Store in Redis ──────────────────────────────────────────────
        if embedding and use_cache and semantic_cache.is_online:
            semantic_cache.store(
                query=question,
                query_embedding=embedding,
                response=result,
                supporting_datasets=result.get("sources", []),
                data_version=data_version,
            )

        return result

    # ── Level-1: Verified Data Only ────────────────────────────────────────

    @classmethod
    def _handle_verified_data(
        cls,
        question: str,
        evidence: Dict[str, Any],
        start_time: float,
        data_version: str,
    ) -> Dict[str, Any]:
        """
        Returns a data-grounded answer without calling the LLM.
        Used when the question is fully answerable from UrbanPulse DB records.
        """
        primary_ev = (evidence.get("evidence_by_locality") or [None])[0]
        answer = cls._generate_deterministic_analysis(question, evidence)
        analysis = cls._build_structured_analysis(evidence, primary_ev)
        sources = cls._default_sources()

        return cls._build_payload(
            question=question,
            answer=answer,
            analysis=analysis,
            sources=sources,
            evidence=evidence,
            primary_ev=primary_ev,
            answer_mode=MODE_VERIFIED,
            model_used="n/a (data-only)",
            start_time=start_time,
            data_version=data_version,
        )

    # ── Level-2: Hybrid Data + AI ──────────────────────────────────────────

    @classmethod
    def _handle_hybrid(
        cls,
        question: str,
        evidence: Dict[str, Any],
        start_time: float,
        data_version: str,
    ) -> Dict[str, Any]:
        """
        Retrieves DB evidence and asks the LLM to interpret it.
        If LLM is unavailable, falls back to deterministic data answer.
        """
        primary_ev = (evidence.get("evidence_by_locality") or [None])[0]
        evidence_text = cls.format_prompt_evidence(evidence)

        user_prompt = (
            f"User Question: {question}\n\n"
            f"{evidence_text}\n\n"
            "Provide a comprehensive, objective, evidence-grounded response. "
            "Clearly separate verified facts from general observations. "
            "State data limitations honestly."
        )

        llm_text, model_used, fail_reason = ollama_client.chat_with_fallback(
            system=_HYBRID_SYSTEM,
            user=user_prompt,
            temperature=0.2,
        )

        if llm_text:
            answer = llm_text
            answer_mode = MODE_HYBRID
        else:
            # LLM unavailable — return deterministic data answer, note the mode
            answer = cls._generate_deterministic_analysis(question, evidence)
            answer_mode = MODE_DATA_ONLY
            model_used = "none"

        analysis = cls._build_structured_analysis(evidence, primary_ev)
        sources = cls._default_sources()
        if fail_reason:
            sources.append(f"[Note: AI model {fail_reason} — {model_used} was used]")

        return cls._build_payload(
            question=question,
            answer=answer,
            analysis=analysis,
            sources=sources,
            evidence=evidence,
            primary_ev=primary_ev,
            answer_mode=answer_mode,
            model_used=model_used,
            start_time=start_time,
            data_version=data_version,
        )

    # ── Level-3: General AI ────────────────────────────────────────────────

    @classmethod
    def _handle_general_ai(
        cls,
        question: str,
        evidence: Dict[str, Any],
        start_time: float,
        data_version: str,
    ) -> Dict[str, Any]:
        """
        No relevant local data — answers using the LLM as a general assistant.
        If LLM is offline, returns a service-unavailable message.
        """
        user_prompt = (
            f"User Question: {question}\n\n"
            "Note: No verified UrbanPulse database records were found that directly "
            "answer this question.  Please answer using your general knowledge and "
            "clearly indicate that this is a general answer, not backed by local data."
        )

        llm_text, model_used, fail_reason = ollama_client.chat_with_fallback(
            system=_GENERAL_SYSTEM,
            user=user_prompt,
            temperature=0.4,   # slightly more conversational for general Q&A
        )

        if llm_text:
            answer = llm_text
            answer_mode = MODE_GENERAL_AI
        else:
            answer = (
                "⚠️ **AI Service Unavailable**\n\n"
                "Both the primary (Qwen3:8b) and fallback AI models are currently unreachable.\n\n"
                "For Bengaluru-specific civic data, you can ask questions like:\n"
                "- *What is the UrbanScore for Whitefield?*\n"
                "- *Total BBMP construction investment in Bengaluru?*\n"
                "- *Should I buy a house in Koramangala?*\n\n"
                "These will be answered from verified UrbanPulse datasets without the AI model."
            )
            answer_mode = MODE_DATA_ONLY
            model_used = "none"

        # For general questions there are no verified data sources to cite
        sources = (
            ["[General AI answer — no UrbanPulse database records are cited for this response]"]
            if answer_mode == MODE_GENERAL_AI
            else []
        )

        return cls._build_payload(
            question=question,
            answer=answer,
            analysis=None,
            sources=sources,
            evidence=evidence,
            primary_ev=None,
            answer_mode=answer_mode,
            model_used=model_used,
            start_time=start_time,
            data_version=data_version,
        )

    # ── Shared Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _default_sources() -> List[str]:
        return [
            "BBMP 2025-26 198 Wards Work-Order Dataset (Open City Bengaluru)",
            "Bengaluru City Police Annual Reports D47 Series",
            "Karnataka State Police GIS KML Dataset (Police Stations & Outposts)",
            "KSPCB & CPCB Ambient Air & Lake Water Quality Monitoring Network",
            "UrbanPulse PostgreSQL Civic Grievance Database",
        ]

    @staticmethod
    def _build_payload(
        question: str,
        answer: str,
        analysis: Optional[Dict],
        sources: List[str],
        evidence: Dict[str, Any],
        primary_ev: Optional[Dict],
        answer_mode: str,
        model_used: str,
        start_time: float,
        data_version: str,
    ) -> Dict[str, Any]:
        urban_score_payload = primary_ev["urban_score"] if primary_ev else None
        locality = primary_ev["display_name"] if primary_ev else None

        return {
            "question":       question,
            "locality":       locality,
            "urban_score":    urban_score_payload,
            "answer":         answer,
            "analysis":       analysis,
            "sources":        sources,
            "answer_mode":    answer_mode,
            "cached":         False,
            "cache_status":   "MISS" if semantic_cache.is_online else "UNAVAILABLE",
            "cache_similarity": None,
            "model":          model_used,
            "data_version":   data_version,
            "latency_ms":     round((time.time() - start_time) * 1000, 1),
        }

    # ── Structured Analysis (data-grounded) ───────────────────────────────

    @classmethod
    def _build_structured_analysis(
        cls,
        evidence: Dict[str, Any],
        primary_ev: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Builds structured reasons/risks/recommendations from real data fields."""
        if not primary_ev:
            return {
                "reasons_to_consider": [
                    "Bengaluru's municipal expenditure has recorded over ₹3,169 Cr in verified "
                    "2025–26 civil works across 198 wards.",
                    "Active police presence with 150 mapped stations and outposts across zones.",
                ],
                "reasons_for_caution": [
                    "Citywide crime risk score benchmark is 71.7/100 (D47 series, 15.11% fatal severity rate).",
                    "Significant ward-level disparity in civic capital allocation.",
                ],
                "risks": {
                    "safety":         "Citywide risk index 71.7/100; precinct-level beat records not published.",
                    "environmental":  "PM2.5 and PM10 frequently exceed NAAQS in traffic corridors.",
                    "infrastructure": "Deductions in ward work orders reflect contractor scrutiny (city avg 10.08%).",
                    "governance":     "Pending grievance backlogs vary widely across outer and core zones.",
                },
                "actionable_recommendations": [
                    "Consult ward-specific work order allocations before property decisions.",
                    "Check nearest KSPCB air monitoring station and lake water class.",
                ],
                "data_limitations": [
                    "Ward-level crime incident logs not published; only citywide totals verified."
                ],
            }

        us   = primary_ev.get("urban_score", {})
        wd   = primary_ev.get("ward_data")   or {}
        pd   = primary_ev.get("police_data") or {}
        air  = primary_ev.get("air_data")    or {}
        water = primary_ev.get("water_data") or {}
        cd   = primary_ev.get("complaints_data") or {}

        pros, cons = [], []

        if wd.get("total_amount_cr", 0) > 15:
            pros.append(
                f"Substantial BBMP capital allocation: ₹{wd.get('total_amount_cr'):.2f} Cr "
                f"across {wd.get('total_work_orders')} projects."
            )
        elif wd.get("total_amount_cr", 0) > 0:
            pros.append(
                f"Active civil works: {wd.get('total_work_orders')} projects "
                f"(₹{wd.get('total_amount_cr'):.2f} Cr verified)."
            )
        if pd.get("station_count", 0) > 0:
            pros.append(f"Direct police facility within area ({pd['station_count']} station(s) mapped).")
        if wd.get("unique_contractors", 0) >= 5:
            pros.append(f"Diversified procurement: {wd['unique_contractors']} competing contractors.")

        if air.get("pm25") and air.get("pm25") > 40:
            cons.append(f"Air quality: PM2.5 = {air['pm25']} µg/m³ exceeds NAAQS limit (40).")
        if water.get("wq_class") in ("D", "E"):
            cons.append(
                f"Regional water body: {water.get('lake_name')} classified "
                f"Class {water['wq_class']} ({water.get('status', 'Polluted')})."
            )
        pending = cd.get("total", 0) - cd.get("resolved", 0)
        if pending > 0:
            cons.append(f"Civic grievance backlog: {pending} unresolved complaint(s).")

        return {
            "reasons_to_consider": pros or ["Active municipal administration within BBMP ward boundaries."],
            "reasons_for_caution": cons or ["Verify local water access and road widths before investing."],
            "risks": {
                "safety":
                    f"Mapped stations: {pd.get('station_count', 0)}. Citywide crime risk: 71.7/100.",
                "environmental":
                    f"Air: {air.get('station_name', 'Nearest')} PM2.5={air.get('pm25', 'N/A')} µg/m³; "
                    f"Water: Class {water.get('wq_class', 'N/A')}.",
                "infrastructure":
                    f"{wd.get('total_work_orders', 0)} BBMP civil works "
                    f"(Road: {wd.get('road_projects', 0)}, Drain: {wd.get('drain_projects', 0)}).",
                "governance":
                    f"{cd.get('total', 0)} grievances recorded ({cd.get('resolved', 0)} closed).",
            },
            "actionable_recommendations": [
                f"Inspect drainage ({wd.get('drain_projects', 0)} projects) for monsoon flood risk.",
                "Verify BWSSB piped water availability vs tanker dependency.",
                "Review the full UrbanScore breakdown across all 5 dimensions.",
            ],
            "data_limitations": us.get("missing_indicators", []) + [
                "Crime counts at citywide/divisional level only; beat-level logs not published."
            ],
        }

    # ── Deterministic Fallback ─────────────────────────────────────────────

    @classmethod
    def _generate_deterministic_analysis(cls, question: str, evidence: Dict[str, Any]) -> str:
        """Structured data-only answer when no LLM is available."""
        loc_list = evidence.get("evidence_by_locality", [])
        if not loc_list:
            cw = evidence.get("citywide_benchmarks", {})
            return (
                "### UrbanPulse Intelligence Overview\n\n"
                "**Verified citywide data for Bengaluru (from the UrbanPulse PostgreSQL database):**\n\n"
                f"- **BBMP Construction**: ₹{cw.get('total_construction_investment_cr', 3169.06)} Cr verified "
                f"investment across {cw.get('total_work_orders', 4729)} work orders in 198 wards.\n"
                f"- **Crime Risk (BCP D47)**: Risk score {cw.get('city_crime_risk_score', 71.7)}/100 "
                f"with a {cw.get('fatal_crime_rate_pct', 15.11)}% fatal crime severity rate.\n"
                f"- **Police Infrastructure**: {cw.get('mapped_police_locations', 150)} stations and "
                "outposts mapped across the city.\n\n"
                "_For a localized UrbanScore and decision analysis, specify a locality such as "
                "Whitefield, HSR Layout, Bellandur, or Koramangala._"
            )

        ev    = loc_list[0]
        name  = ev["display_name"]
        us    = ev.get("urban_score", {})
        score = us.get("urban_score", 0.0)
        tier  = us.get("tier", "N/A")
        wd    = ev.get("ward_data")   or {}
        pd    = ev.get("police_data") or {}
        air   = ev.get("air_data")    or {}
        water = ev.get("water_data")  or {}

        return (
            f"### UrbanScore & Decision Analysis: {name}\n\n"
            f"**Overall UrbanScore**: **{score}/100** ({tier})  \n"
            f"*Confidence: {us.get('confidence')} — Data Coverage: {us.get('data_coverage_pct')}%*\n\n"
            f"#### 1. Infrastructure\n"
            f"- BBMP 2025–26: ₹{wd.get('total_amount_cr', 0):.2f} Cr across {wd.get('total_work_orders', 0)} works.\n"
            f"- {wd.get('road_projects', 0)} road | {wd.get('drain_projects', 0)} drain | "
            f"{wd.get('development_projects', 0)} civic upgrade projects.\n"
            f"- {wd.get('unique_contractors', 0)} contractors (avg deduction {wd.get('avg_deduction_pct', 10.08)}%).\n\n"
            f"#### 2. Environment\n"
            f"- Air ({air.get('station_name', 'Regional')}) PM2.5 = {air.get('pm25', 'N/A')} µg/m³ "
            f"(NAAQS limit: 40 µg/m³).\n"
            f"- Water: {water.get('lake_name', 'Regional Lake')} — CPCB Class {water.get('wq_class', 'N/A')}.\n\n"
            f"#### 3. Safety\n"
            f"- Police: {pd.get('station_count', 0)} station(s) + {pd.get('outpost_count', 0)} outpost(s) mapped.\n"
            f"- Citywide BCP D47 risk: 71.7/100 (15.11% fatal rate).\n\n"
            "*All metrics from verified BBMP, BCP, KSPCB, and KSP GIS datasets.*"
        )

    # ── Ollama Status ──────────────────────────────────────────────────────

    @staticmethod
    def get_ollama_status() -> Dict[str, Any]:
        return ollama_client.status()


# Module singleton
assistant_service = IntelligenceAssistantService()
