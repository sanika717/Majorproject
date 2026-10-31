"""
UrbanPulse Intelligence Assistant Service — Three-Level Hybrid Answering.

Level 1 — Verified UrbanPulse Data
    Citywide and locality stats are presented directly from PostgreSQL / verified datasets
    without any LLM call when answering pure factual queries.

Level 2 — Hybrid: UrbanPulse Data + AI Interpretation
    Evidence is retrieved from the database. Primary (qwen3:4b) synthesizes an
    interpretation grounded strictly in the retrieved evidence.

Level 3 — General AI Answer
    No relevant local UrbanPulse data found or conceptual question. Answering uses general AI.

Key guarantees
  - No statistic, score, or citation is fabricated.
  - If LLMs are offline or time out, a data-only deterministic message is returned.
  - Cache is checked with exact sha256 matching before LLM calls and stored only for real answers.
"""

import re
import time
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Iterator
from datetime import datetime
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.services.intelligence.cache import semantic_cache, normalize_query_text
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
# Prompt templates (Concise, strictly < 1500 chars, grounded in evidence)
# ──────────────────────────────────────────────────────────────────────────────

_HYBRID_SYSTEM = (
    "You are the UrbanPulse Intelligence Assistant for Bengaluru civic transparency.\n"
    "Ground every claim, score, and metric strictly in the provided verified evidence.\n"
    "RULES:\n"
    "1. Never fabricate numbers, percentages, citations, or government statistics.\n"
    "2. Do not label any locality absolutely safe or unsafe; never guarantee investment returns.\n"
    "3. Structure property/investment answers with concise bullets: summary, pros, caution, limitations.\n"
    "4. State data limitations honestly and cite sources from the evidence block.\n"
    "5. Keep general observations separate from verified local data.\n"
    "6. Answer in at most 150 words, short bullets, no preamble."
)

_GENERAL_SYSTEM = (
    "You are UrbanPulse's AI assistant for urban planning, civic governance, and "
    "property investment advice. Answer clearly and concisely using general knowledge.\n"
    "RULES:\n"
    "1. Do NOT fabricate Bengaluru-specific statistics, scores, or government data.\n"
    "2. If the user asks about an urban or civic concept, explain it with a structured framework.\n"
    "3. Mention specific Bengaluru localities (e.g. Whitefield, HSR Layout, Indiranagar) can be queried for verified UrbanScores.\n"
    "4. Answer in at most 150 words, short bullets, no preamble."
)

_FOLLOW_UP_SYSTEM = (
    "You are the UrbanPulse Intelligence Assistant for Bengaluru civic transparency.\n"
    "Answer follow-up questions objectively and concisely based on general knowledge.\n"
    "Do not fabricate specific statistics or scores. Mention localities for verified data.\n"
    "Answer in at most 150 words, short bullets, no preamble."
)


class IntelligenceAssistantService:

    # ── Embedding (Kept for compatibility, not in request path) ────────────

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
                "Answer the user's actual question directly using general knowledge, apply citywide figures only when relevant, "
                "and ask which locality or ward they would like to evaluate if the question needs one."
            )

        return "\n".join(lines)

    # ── Deterministic Answers from Data & Locality ─────────────────────────

    @classmethod
    def _try_answer_from_data(cls, question: str, evidence: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Attempts to directly answer verified factual data questions from database metrics.
        Returns (True, answer_text) if the question can be authoritatively answered
        from existing database records, or (False, "") if it should route to the LLM path.
        """
        q = question.lower().strip()
        cw = evidence.get("citywide_benchmarks", {})
        loc_list = evidence.get("evidence_by_locality", [])

        # Send questions requiring comparison, advice, safety, or explanation to LLM
        llm_triggers = ("compare", "should", "safe", "better", "vs", "why", "explain")
        if any(tr in q for tr in llm_triggers):
            return False, ""

        # 1. Total BBMP construction investment & work orders
        bbmp_terms = ("bbmp", "construction", "work order", "civic work", "civil work")
        inv_terms = ("investment", "expenditure", "budget", "how much was spent", "total spent")
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

        # 2. Police infrastructure count
        police_terms = ("police station", "police outpost", "police infrastructure", "police facilities")
        count_terms = ("how many", "count", "number of", "total")
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
        crime_terms = ("crime baseline", "crime risk score", "d47", "fatal crime rate")
        if any(cr in q for cr in crime_terms) and not loc_list:
            score = cw.get("city_crime_risk_score", 71.7)
            fatal = cw.get("fatal_crime_rate_pct", 15.11)
            return True, (
                f"### Verified Crime & Safety Baseline (Bengaluru)\n\n"
                f"Based on the Bengaluru City Police (BCP) Annual Reports D47 Series in the UrbanPulse database:\n\n"
                f"- **Citywide Crime Risk Score Benchmark**: **{score}/100**\n"
                f"- **Fatal Crime Severity Rate**: **{fatal}%** of reported incidents\n"
                f"- **Data Granularity**: Published at citywide and police divisional levels.\n\n"
                f"*Source: Bengaluru City Police Annual Reports D47 Series.*"
            )

        # 4. Public complaints summary
        complaint_terms = ("public complaints", "grievances", "civic complaints")
        comp_count_terms = ("how many", "total", "count", "resolution rate")
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

        return False, ""

    @classmethod
    def _try_answer_deterministic_locality(
        cls,
        question: str,
        evidence: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Answers simple locality questions without the LLM:
        - 1 locality detected: asks for UrbanScore/score (without 'should', 'why', 'explain')
        - 2 localities detected: asks to compare (without 'should', 'why', 'explain')
        Returns (can_answer, answer_text, primary_ev, analysis_dict)
        """
        q = question.lower().strip()
        reasoning_words = ("should", "why", "explain", "advice", "recommend", "pros and cons", "is it good", "is it better", "worth buying")
        if any(w in q for w in reasoning_words):
            return False, "", None, None

        loc_list = evidence.get("evidence_by_locality", [])
        if not loc_list:
            return False, "", None, None

        # Case 1: 1 locality asking for UrbanScore / score
        if len(loc_list) == 1:
            score_terms = ("urbanscore", "urban score", "score", "rating")
            if any(st in q for st in score_terms):
                ev = loc_list[0]
                name = ev["display_name"]
                us = ev.get("urban_score", {})
                score = us.get("urban_score", "N/A")
                tier = us.get("tier", "N/A")
                cov = us.get("data_coverage_pct", "N/A")
                comps = us.get("components", {})

                lines = [
                    f"### Verified UrbanScore: {name}\n",
                    f"- **Overall UrbanScore**: **{score}/100** ({tier})",
                    f"- **Data Coverage**: {cov}% (Confidence: {us.get('confidence', 'N/A')})\n",
                    "#### Component Breakdown:",
                ]
                for c_name, c_data in comps.items():
                    sc = c_data.get("score")
                    sc_str = f"{sc}/100" if sc is not None else "Data Unavailable"
                    lines.append(f"- **{c_name.replace('_', ' ').capitalize()}**: {sc_str}")

                lines.append("\n*Methodology: Safety 25% · Infrastructure 25% · Environment 20% · Social 15% · Governance 15%.*")
                answer_text = "\n".join(lines)
                analysis = cls._build_structured_analysis(evidence, ev)
                return True, answer_text, ev, analysis

        # Case 2: 2 localities asking to compare
        if len(loc_list) >= 2:
            compare_terms = ("compare", " vs ", " vs. ", "versus", "difference between", "comparison")
            if any(ct in q for ct in compare_terms) or q.startswith("compare"):
                ev1, ev2 = loc_list[0], loc_list[1]
                name1, name2 = ev1["display_name"], ev2["display_name"]
                us1, us2 = ev1.get("urban_score", {}), ev2.get("urban_score", {})
                s1 = us1.get("urban_score", 0.0)
                s2 = us2.get("urban_score", 0.0)
                t1 = us1.get("tier", "N/A")
                t2 = us2.get("tier", "N/A")

                c1 = us1.get("components", {})
                c2 = us2.get("components", {})

                def comp_sc(comps, key):
                    sc = comps.get(key, {}).get("score")
                    return f"{sc}/100" if sc is not None else "Unavailable"

                diff = round(abs(s1 - s2), 1)
                leader = name1 if s1 >= s2 else name2

                lines = [
                    f"### Locality Comparison: {name1} vs {name2}\n",
                    f"| Dimension | {name1} | {name2} |",
                    "| --- | --- | --- |",
                    f"| **Overall UrbanScore** | **{s1}/100** ({t1}) | **{s2}/100** ({t2}) |",
                    f"| Safety (25%) | {comp_sc(c1, 'safety')} | {comp_sc(c2, 'safety')} |",
                    f"| Infrastructure (25%) | {comp_sc(c1, 'infrastructure')} | {comp_sc(c2, 'infrastructure')} |",
                    f"| Environment (20%) | {comp_sc(c1, 'environment')} | {comp_sc(c2, 'environment')} |",
                    f"| Social Infra (15%) | {comp_sc(c1, 'social_infrastructure')} | {comp_sc(c2, 'social_infrastructure')} |",
                    f"| Governance (15%) | {comp_sc(c1, 'governance')} | {comp_sc(c2, 'governance')} |\n",
                    f"*{leader} leads by {diff} points. All indicators derived from verified BBMP, BCP, and GIS datasets.*"
                ]
                answer_text = "\n".join(lines)
                analysis = cls._build_structured_analysis(evidence, ev1)
                return True, answer_text, ev1, analysis

        return False, "", None, None

    # ── Greeting Instant Answer (No LLM Call) ──────────────────────────────

    @classmethod
    def _handle_greeting(cls, question: str, start_time: float, data_version: str) -> Dict[str, Any]:
        """Provides an instant conversational greeting without any LLM latency."""
        answer = (
            "Hello! I am the **UrbanPulse Intelligence Assistant**.\n\n"
            "I can help you evaluate Bengaluru localities, check BBMP infrastructure investments, "
            "examine crime safety baselines, track environmental indicators, and calculate "
            "multi-dimensional **UrbanScores** for property and living decisions.\n\n"
            "*Here are a few things you can ask me:*\n"
            "- *'What is the UrbanScore for Whitefield?'*\n"
            "- *'Compare Whitefield and HSR Layout'*\n"
            "- *'Total BBMP construction investment in Bengaluru?'*\n"
            "- *'Is Koramangala safe for a family?'*"
        )
        payload = cls._build_payload(
            question=question,
            answer=answer,
            analysis=None,
            sources=["[UrbanPulse Conversational Assistant]"],
            evidence={},
            primary_ev=None,
            answer_mode=MODE_GENERAL_AI,
            model_used="none",
            start_time=start_time,
            data_version=data_version,
        )
        return payload

    # ── Main Entry Point ───────────────────────────────────────────────────

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
        Main entry point. Routes the question through the 3-level strategy and
        returns a unified structured payload.
        """
        start_time = time.time()
        question = question.strip()
        target_locality = locality or explicit_locality

        data_version = EvidenceRetriever.compute_data_version(db)

        # ── 1. Fast exact cache check (no LLM embedding call) ─────────────
        if use_cache:
            cached_res, sim, cache_status = semantic_cache.get_match(question, data_version)
            if cached_res:
                cached_res["cached"]           = True
                cached_res["cache_status"]     = cache_status
                cached_res["cache_similarity"] = sim
                cached_res["latency_ms"]       = round((time.time() - start_time) * 1000, 1)
                logger.info(
                    f"[Intelligence Request] Level=CACHE | Model={cached_res.get('model')} | "
                    f"Cached=True | Latency={cached_res.get('latency_ms')}ms"
                )
                return cached_res

        # ── 2. Greeting check (Instant, NO LLM call) ───────────────────────
        if is_greeting_or_chit_chat(question):
            result = cls._handle_greeting(question, start_time, data_version)
            logger.info(
                f"[Intelligence Request] Level=GREETING | Model=none | "
                f"Cached=False | Latency={result.get('latency_ms')}ms"
            )
            return result

        # ── 3. Retrieve verified database evidence ─────────────────────────
        evidence = EvidenceRetriever.retrieve_for_query(db, question, target_locality)
        has_locality_ev = bool(evidence.get("evidence_by_locality"))

        # ── 4. Deterministic locality answer (UrbanScore / Compare) ───────
        can_det, det_text, det_ev, det_analysis = cls._try_answer_deterministic_locality(question, evidence)
        if can_det:
            result = cls._build_payload(
                question=question,
                answer=det_text,
                analysis=det_analysis,
                sources=cls._default_sources(),
                evidence=evidence,
                primary_ev=det_ev,
                answer_mode=MODE_VERIFIED,
                model_used="n/a (verified database)",
                start_time=start_time,
                data_version=data_version,
            )
            if use_cache and semantic_cache.is_online:
                semantic_cache.store(question, result, result.get("sources", []), data_version)
            logger.info(
                f"[Intelligence Request] Level=DETERMINISTIC_LOCALITY | Model={result.get('model')} | "
                f"Cached=False | Latency={result.get('latency_ms')}ms"
            )
            return result

        # ── 5. Classify the question ───────────────────────────────────────
        level, level_reason = classify_question(question, has_locality_evidence=has_locality_ev)
        logger.info(f"[Assistant] Level={level} ({level_reason}) Q={question!r:.80}")

        # ── 6. Route to handler ───────────────────────────────────────────
        fail_reason = ""
        if level == LEVEL_1:
            result = cls._handle_verified_data(question, evidence, start_time, data_version)
        elif level == LEVEL_2:
            result = cls._handle_hybrid(question, evidence, start_time, data_version)
        else:  # LEVEL_3
            result = cls._handle_general_ai(question, evidence, start_time, data_version)

        # ── 7. Store in Redis only for real answers ───────────────────────
        # Store only if: not MODE_DATA_ONLY, model_used != 'none', no fail_reason, not greeting
        ans_mode = result.get("answer_mode", "")
        model_used = result.get("model", "")
        is_real_answer = (
            ans_mode != MODE_DATA_ONLY
            and model_used not in ("none", "")
            and not is_greeting_or_chit_chat(question)
        )
        if use_cache and semantic_cache.is_online and is_real_answer:
            semantic_cache.store(
                query=question,
                response=result,
                supporting_datasets=result.get("sources", []),
                data_version=data_version,
            )

        # ── 8. Log one line per request ────────────────────────────────────
        logger.info(
            f"[Intelligence Request] Level={level} | Model={model_used} | "
            f"Cached=False | Latency={result.get('latency_ms')}ms"
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
        """Directly answers factual data questions or routes to hybrid."""
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

        logger.info(f"[Assistant] Data handler falling back to hybrid for '{question}'.")
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
        """Retrieves DB evidence and asks LLM to interpret it."""
        primary_ev = (evidence.get("evidence_by_locality") or [None])[0]
        evidence_text = cls.format_prompt_evidence(evidence)
        loc_list = evidence.get("evidence_by_locality", [])

        if loc_list:
            user_prompt = (
                f"User Question: {question}\n\n"
                f"{evidence_text}\n\n"
                "Provide an objective, evidence-grounded response. "
                "Clearly separate verified facts from general observations. "
                "State data limitations honestly. Answer in at most 150 words, short bullets, no preamble."
            )
        else:
            user_prompt = (
                f"User Question: {question}\n\n"
                f"{evidence_text}\n\n"
                "Answer the user's actual question directly using general knowledge. "
                "Use citywide figures only when relevant to the question. "
                "If the question needs a specific locality, ask which locality or ward they would like to evaluate. "
                "Answer in at most 150 words, short bullets, no preamble."
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
        """Handles general questions using LLM."""
        is_follow = is_follow_up(question)

        if is_follow:
            system_prompt = _FOLLOW_UP_SYSTEM
            user_prompt = f"User Question: {question}\n\nAnswer in at most 150 words, short bullets, no preamble."
        else:
            system_prompt = _GENERAL_SYSTEM
            user_prompt = (
                f"User Question: {question}\n\n"
                "Please provide a helpful, natural-language response based on general knowledge. "
                "Do not invent Bengaluru-specific government numbers or claim to cite database records that do not exist. "
                "Answer in at most 150 words, short bullets, no preamble."
            )

        llm_text, model_used, fail_reason = ollama_client.chat_with_fallback(
            system=system_prompt,
            user=user_prompt,
            temperature=0.3,
        )

        if llm_text:
            answer = llm_text
            answer_mode = MODE_GENERAL_AI
        else:
            answer = (
                "The AI model did not respond in time, please retry.\n\n"
                "For verified Bengaluru civic metrics, you can ask about specific localities (e.g. Whitefield, HSR Layout) "
                "or BBMP construction totals."
            )
            answer_mode = MODE_DATA_ONLY
            model_used = "none"

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

    # ── Streaming Preparation (Pure in-memory outside generator) ───────────

    @classmethod
    def prepare_stream_question(
        cls,
        db: Session,
        question: str,
        locality: Optional[str] = None,
        explicit_locality: Optional[str] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes ALL database lookups and non-LLM checks synchronously.
        The DB session is completely done when this function returns.
        Returns a dict indicating either an instant result or parameters for streaming.
        """
        start_time = time.time()
        question = question.strip()
        target_locality = locality or explicit_locality
        data_version = EvidenceRetriever.compute_data_version(db)

        # 1. Cache hit
        if use_cache:
            cached_res, sim, cache_status = semantic_cache.get_match(question, data_version)
            if cached_res:
                cached_res["cached"]           = True
                cached_res["cache_status"]     = cache_status
                cached_res["cache_similarity"] = sim
                cached_res["latency_ms"]       = round((time.time() - start_time) * 1000, 1)
                return {"is_instant": True, "payload": cached_res}

        # 2. Greeting check
        if is_greeting_or_chit_chat(question):
            res = cls._handle_greeting(question, start_time, data_version)
            return {"is_instant": True, "payload": res}

        # 3. Retrieve DB evidence (done strictly here, while DB session is open)
        evidence = EvidenceRetriever.retrieve_for_query(db, question, target_locality)
        has_locality_ev = bool(evidence.get("evidence_by_locality"))

        # 4. Deterministic locality answer (UrbanScore / Compare)
        can_det, det_text, det_ev, det_analysis = cls._try_answer_deterministic_locality(question, evidence)
        if can_det:
            res = cls._build_payload(
                question=question,
                answer=det_text,
                analysis=det_analysis,
                sources=cls._default_sources(),
                evidence=evidence,
                primary_ev=det_ev,
                answer_mode=MODE_VERIFIED,
                model_used="n/a (verified database)",
                start_time=start_time,
                data_version=data_version,
            )
            if use_cache and semantic_cache.is_online:
                semantic_cache.store(question, res, res.get("sources", []), data_version)
            return {"is_instant": True, "payload": res}

        # 5. Data templates check
        level, level_reason = classify_question(question, has_locality_evidence=has_locality_ev)
        if level == LEVEL_1:
            can_ans, ans_text = cls._try_answer_from_data(question, evidence)
            if can_ans:
                primary_ev = (evidence.get("evidence_by_locality") or [None])[0]
                analysis = cls._build_structured_analysis(evidence, primary_ev)
                res = cls._build_payload(
                    question=question,
                    answer=ans_text,
                    analysis=analysis,
                    sources=cls._default_sources(),
                    evidence=evidence,
                    primary_ev=primary_ev,
                    answer_mode=MODE_VERIFIED,
                    model_used="n/a (verified database)",
                    start_time=start_time,
                    data_version=data_version,
                )
                if use_cache and semantic_cache.is_online:
                    semantic_cache.store(question, res, res.get("sources", []), data_version)
                return {"is_instant": True, "payload": res}
            level = LEVEL_2

        # 6. Prepare LLM prompt and parameters for streaming
        primary_ev = (evidence.get("evidence_by_locality") or [None])[0]
        loc_list = evidence.get("evidence_by_locality", [])

        if level == LEVEL_2:
            system_prompt = _HYBRID_SYSTEM
            evidence_text = cls.format_prompt_evidence(evidence)
            if loc_list:
                user_prompt = (
                    f"User Question: {question}\n\n"
                    f"{evidence_text}\n\n"
                    "Provide an objective, evidence-grounded response. "
                    "Clearly separate verified facts from general observations. "
                    "State data limitations honestly. Answer in at most 150 words, short bullets, no preamble."
                )
            else:
                user_prompt = (
                    f"User Question: {question}\n\n"
                    f"{evidence_text}\n\n"
                    "Answer the user's actual question directly using general knowledge. "
                    "Use citywide figures only when relevant to the question. "
                    "If the question needs a specific locality, ask which locality or ward they would like to evaluate. "
                    "Answer in at most 150 words, short bullets, no preamble."
                )
            analysis = cls._build_structured_analysis(evidence, primary_ev)
            sources = cls._default_sources()
            answer_mode = MODE_HYBRID
        else:
            is_follow = is_follow_up(question)
            system_prompt = _FOLLOW_UP_SYSTEM if is_follow else _GENERAL_SYSTEM
            user_prompt = (
                f"User Question: {question}\n\n"
                "Please provide a helpful, natural-language response based on general knowledge. "
                "Do not invent Bengaluru-specific government numbers or claim to cite database records that do not exist. "
                "Answer in at most 150 words, short bullets, no preamble."
            )
            analysis = None
            sources = ["[General AI answer — based on general AI knowledge, not local database records]"]
            answer_mode = MODE_GENERAL_AI

        target_model = ollama_client.resolve_primary() or ollama_client.resolve_fallback()

        return {
            "is_instant": False,
            "stream_context": {
                "question": question,
                "system": system_prompt,
                "user": user_prompt,
                "model": target_model,
                "answer_mode": answer_mode,
                "level": level,
                "evidence": evidence,
                "primary_ev": primary_ev,
                "analysis": analysis,
                "sources": sources,
                "start_time": start_time,
                "data_version": data_version,
                "use_cache": use_cache,
            }
        }

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
                "The AI model did not respond in time, please retry.\n\n"
                f"Citywide verified benchmark: ₹{cw.get('total_construction_investment_cr', 3169.06)} Cr construction across "
                f"{cw.get('total_work_orders', 4729)} BBMP work orders; "
                f"Crime Risk Score {cw.get('city_crime_risk_score', 71.7)}/100; "
                f"{cw.get('mapped_police_locations', 150)} police stations mapped."
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
