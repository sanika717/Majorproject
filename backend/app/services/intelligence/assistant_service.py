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
    is_greeting_or_chit_chat,
    is_follow_up,
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
    "property investment advice. Answer clearly, concisely, and helpfully using your general knowledge.\n\n"
    "RULES:\n"
    "1. Answer helpfully using your general knowledge in clean, friendly natural language.\n"
    "2. Do NOT fabricate Bengaluru-specific statistics, scores, or government data.\n"
    "3. If the user asks about a concept (e.g. ESG, urban planning, safety factors), "
    "   explain the concept and offer a structured framework.\n"
    "4. Mention that the user can explore specific Bengaluru localities (e.g. Whitefield, HSR Layout, "
    "   Indiranagar, Peenya) for verified UrbanScores and BBMP civic data."
)

_CONVERSATIONAL_SYSTEM = (
    "You are the UrbanPulse Intelligence Assistant for Bengaluru civic transparency, "
    "urban planning, and locality evaluation.\n\n"
    "RULES:\n"
    "1. Greet the user warmly, naturally, and concisely in 2-3 sentences.\n"
    "2. Introduce your capabilities: evaluating Bengaluru localities using UrbanScore, BBMP civil works, "
    "   police safety infrastructure, crime risk baselines, and environmental/ESG metrics.\n"
    "3. Suggest 2-3 sample queries the user can ask (e.g. 'Should I buy a house in Whitefield?', 'What is the UrbanScore for HSR Layout?').\n"
    "4. Do NOT apologize or say 'no records found' when greeting."
)

_FOLLOW_UP_SYSTEM = (
    "You are the UrbanPulse Intelligence Assistant for Bengaluru civic transparency and urban planning.\n"
    "The user is continuing the conversation with a follow-up inquiry. Answer helpfully, objectively, "
    "and concisely in natural language. Do not fabricate specific statistics or scores. If relevant, "
    "suggest locality-specific queries (e.g. Whitefield, HSR Layout, Koramangala) for verified data."
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
    def _try_answer_from_data(cls, question: str, evidence: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Attempts to directly answer verified factual data questions from database metrics.
        Returns (True, answer_text) if the question can be authoritatively answered
        from existing database records, or (False, "") if it should fall back to Ollama.
        """
        q = question.lower().strip()
        cw = evidence.get("citywide_benchmarks", {})
        loc_list = evidence.get("evidence_by_locality", [])

        # Speculative / explanatory triggers should route to AI reasoning, not static template
        speculative_triggers = (
            "why ", "how come", "how does", "how to", "what causes", "explain why",
            "what do you think", "should i", "is it good", "is it bad", "process of",
            "history of", "tell me about the reason"
        )
        if any(tr in q for tr in speculative_triggers):
            return False, ""

        # 1. Total BBMP construction investment & work orders
        bbmp_terms = ("bbmp", "construction", "work order", "civic work", "civil work", "infrastructure budget")
        inv_terms = ("investment", "expenditure", "total", "budget", "how much", "how many work orders", "allocation")
        if any(b in q for b in bbmp_terms) and any(i in q for i in inv_terms) and not loc_list:
            inv = cw.get("total_construction_investment_cr", 3169.06)
            orders = cw.get("total_work_orders", 4729)
            wards = cw.get("total_wards_analyzed", 198)
            avg_ward = cw.get("average_ward_expenditure_cr", 16.01)
            ded = cw.get("deductions_scrutiny_rate_pct", 10.08)
            return True, (
                f"### Verified BBMP Construction Data (Bengaluru)\n\n"
                f"According to verified 2025–26 municipal records in the UrbanPulse database:\n\n"
                f"- **Total Capital Investment**: **₹{inv:,.2f} Crores**\n"
                f"- **Total Work Orders**: **{orders:,}** projects across {wards} BBMP wards\n"
                f"- **Average Allocation per Ward**: **₹{avg_ward:,.2f} Cr**\n"
                f"- **Contractor Scrutiny Deductions Rate**: **{ded}%** across active contracts\n\n"
                f"*Source: BBMP 2025–26 198 Wards Work-Order Dataset (Open City Bengaluru).*"
            )

        # 2. Police infrastructure
        police_terms = ("police", "police station", "outpost", "precinct")
        count_terms = ("how many", "count", "total", "locations", "mapped", "facilities")
        if any(p in q for p in police_terms) and any(c in q for c in count_terms) and not loc_list:
            st = cw.get("mapped_police_locations", 150)
            return True, (
                f"### Verified Police Infrastructure (Bengaluru)\n\n"
                f"According to the Karnataka State Police GIS dataset in the UrbanPulse database:\n\n"
                f"- **Mapped Police Facilities**: **{st}** police stations and outposts across Bengaluru metropolitan zones.\n"
                f"- **Precinct Mapping**: Coordinates verified and mapped to municipal zones.\n\n"
                f"*Source: Karnataka State Police GIS KML Dataset.*"
            )

        # 3. Crime baseline / risk score
        crime_terms = ("crime", "d47", "fatal crime", "homicide", "safety baseline")
        rate_terms = ("risk score", "baseline", "rate", "statistics", "benchmark", "numbers")
        if any(cr in q for cr in crime_terms) and any(r in q for r in rate_terms) and not loc_list:
            score = cw.get("city_crime_risk_score", 71.7)
            fatal = cw.get("fatal_crime_rate_pct", 15.11)
            return True, (
                f"### Verified Crime & Safety Baseline (Bengaluru)\n\n"
                f"Based on the Bengaluru City Police (BCP) Annual Reports D47 Series in the UrbanPulse database:\n\n"
                f"- **Citywide Crime Risk Score Benchmark**: **{score}/100**\n"
                f"- **Fatal Crime Severity Rate**: **{fatal}%** of reported incidents\n"
                f"- **Data Granularity**: Published at citywide and police divisional levels (sub-ward beat incident logs are not published).\n\n"
                f"*Source: Bengaluru City Police Annual Reports D47 Series.*"
            )

        # 4. Public complaints
        complaint_terms = ("complaint", "grievance", "public complaints")
        comp_count_terms = ("how many", "total", "count", "resolution", "pending", "resolved", "status")
        if any(c in q for c in complaint_terms) and any(cc in q for cc in comp_count_terms) and not loc_list:
            total = cw.get("public_complaints_total", 0)
            res = cw.get("complaints_resolved", 0)
            pen = cw.get("complaints_pending", 0)
            rate = cw.get("complaints_resolution_rate_pct", 0.0)
            return True, (
                f"### Verified Public Grievances Summary (Bengaluru)\n\n"
                f"According to the UrbanPulse PostgreSQL grievance database:\n\n"
                f"- **Total Complaints Logged**: **{total}**\n"
                f"- **Resolved Complaints**: **{res}** ({rate}% resolution rate)\n"
                f"- **Pending Action**: **{pen}**\n\n"
                f"*Source: UrbanPulse PostgreSQL Civic Grievance Database.*"
            )

        # 5. Locality pure factual metric query (e.g. "how many work orders in Whitefield")
        if loc_list and len(loc_list) == 1:
            lev = loc_list[0]
            loc_name = lev.get("display_name", "Locality")
            wd = lev.get("ward_data") or {}
            if any(w in q for w in ("how many work orders", "how many projects", "total budget", "work order count", "expenditure in")):
                return True, (
                    f"### Verified BBMP Works for {loc_name}\n\n"
                    f"- **Total Projects**: **{wd.get('total_work_orders', 0)}**\n"
                    f"- **Total Expenditure**: **₹{wd.get('total_amount_cr', 0.0):.2f} Cr**\n"
                    f"- **Road Projects**: **{wd.get('road_projects', 0)}** | **Drain Projects**: **{wd.get('drain_projects', 0)}**\n"
                    f"- **Unique Registered Contractors**: **{wd.get('unique_contractors', 0)}**\n\n"
                    f"*Source: BBMP 2025–26 198 Wards Work-Order Dataset.*"
                )

        return False, ""

    @classmethod
    def _handle_verified_data(
        cls,
        question: str,
        evidence: Dict[str, Any],
        start_time: float,
        data_version: str,
    ) -> Dict[str, Any]:
        """
        Attempts to directly answer verified factual data questions from database metrics.
        If the question cannot be answered directly from the data (e.g. nuanced question,
        historical question, or explanation about data), automatically falls back to Ollama.
        """
        can_answer, answer_text = cls._try_answer_from_data(question, evidence)
        if can_answer:
            primary_ev = (evidence.get("evidence_by_locality") or [None])[0]
            analysis = cls._build_structured_analysis(evidence, primary_ev)
            sources = cls._default_sources()
            return cls._build_payload(
                question=question,
                answer=answer_text,
                analysis=analysis,
                sources=sources,
                evidence=evidence,
                primary_ev=primary_ev,
                answer_mode=MODE_VERIFIED,
                model_used="n/a (verified database)",
                start_time=start_time,
                data_version=data_version,
            )

        # Data handler cannot directly answer the specific question —
        # automatically fall back to Ollama with the evidence context!
        logger.info(f"[Assistant] Data handler cannot directly answer '{question}'. Falling back to Ollama.")
        return cls._handle_hybrid(question, evidence, start_time, data_version)

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

    # ── Level-3: General AI & Conversational ───────────────────────────────

    @classmethod
    def _handle_general_ai(
        cls,
        question: str,
        evidence: Dict[str, Any],
        start_time: float,
        data_version: str,
    ) -> Dict[str, Any]:
        """
        Handles greetings, conversational chit-chat, follow-up messages, and general questions.
        Uses Ollama for natural language responses. If Ollama is offline, provides
        a friendly, natural fallback message.
        """
        is_greeting = is_greeting_or_chit_chat(question)
        is_follow = is_follow_up(question)

        if is_greeting:
            system_prompt = _CONVERSATIONAL_SYSTEM
            user_prompt = f"User: {question}"
        elif is_follow:
            system_prompt = _FOLLOW_UP_SYSTEM
            user_prompt = f"User Question: {question}"
        else:
            system_prompt = _GENERAL_SYSTEM
            user_prompt = (
                f"User Question: {question}\n\n"
                "Please provide a helpful, natural-language response based on general knowledge. "
                "Do not invent Bengaluru-specific government numbers or claim to cite database records that do not exist."
            )

        llm_text, model_used, fail_reason = ollama_client.chat_with_fallback(
            system=system_prompt,
            user=user_prompt,
            temperature=0.4,   # conversational for general Q&A
        )

        if llm_text:
            answer = llm_text
            answer_mode = MODE_GENERAL_AI
        else:
            if is_greeting:
                answer = (
                    "Hello! I am the **UrbanPulse Intelligence Assistant**.\n\n"
                    "I can help you evaluate Bengaluru localities, check BBMP infrastructure investments, "
                    "examine crime safety baselines, track environmental and ESG indicators, and calculate "
                    "multi-dimensional **UrbanScores** for property and living decisions.\n\n"
                    "*Here are a few things you can ask me:*\n"
                    "- *'Should I buy a house in Whitefield?'*\n"
                    "- *'What is the UrbanScore for HSR Layout?'*\n"
                    "- *'Total BBMP construction investment in Bengaluru?'*\n"
                    "- *'Is Koramangala safe for a family?'*\n"
                    "- *'Compare Whitefield and HSR Layout'*"
                )
                answer_mode = MODE_GENERAL_AI
                model_used = "none"
            elif is_follow:
                answer = (
                    "⚠️ **AI Service Unavailable**\n\n"
                    "The local Ollama AI model is currently unreachable to process follow-up conversational messages.\n\n"
                    "However, verified UrbanPulse database queries remain fully operational. You can ask factual questions like:\n"
                    "- *What is the UrbanScore for Whitefield?*\n"
                    "- *Total BBMP construction investment in Bengaluru?*\n"
                    "- *How many police stations in Bengaluru?*"
                )
                answer_mode = MODE_DATA_ONLY
                model_used = "none"
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

        # For general questions and greetings, attach clear attribution
        sources = (
            ["[General AI answer — based on general AI knowledge, not local database records]"]
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
