"""
UrbanScore Calculation & Multi-Locality Comparison Engine.
Grounded strictly in verified PostgreSQL records, BBMP work orders, police coverage,
lake water indices, and recorded complaints. Never invents data.
"""

from typing import Any, Dict, List, Optional
from backend.app.services.intelligence.urban_score import (
    UrbanScoreEngine as BaseUrbanScoreEngine,
    calculate_urban_score,
)


class UrbanScoreComparisonEngine:
    """
    Engine for multi-locality comparative analytics and side-by-side benchmarking.
    Decoupled from FastAPI HTTP route handlers.
    """

    @classmethod
    def compare_localities(
        cls,
        evidence_list: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compare two or more localities based on verified evidence dictionaries.
        Returns winning locality, comparative summary, component breakdowns,
        and side-by-side metric tables.
        """
        score_results = [calculate_urban_score(ev) for ev in evidence_list]

        sorted_scores = sorted(score_results, key=lambda s: s["score"], reverse=True)
        winner = sorted_scores[0]["locality"] if sorted_scores else None

        diff = round(sorted_scores[0]["score"] - sorted_scores[-1]["score"], 1) if len(sorted_scores) >= 2 else 0
        summary_parts = [
            f"Compared {len(score_results)} localities: {', '.join(a['locality'] for a in score_results)}.",
            f"{sorted_scores[0]['locality']} leads with an UrbanScore of {sorted_scores[0]['score']}/100 ({sorted_scores[0]['grade']}), "
            f"outperforming {sorted_scores[-1]['locality']} ({sorted_scores[-1]['score']}/100, {sorted_scores[-1]['grade']}) by {diff} points.",
            "Scores reflect verified BBMP 2025-26 capital expenditure, mapped police coverage, lake water quality indices, and recorded public complaints.",
        ]

        metrics_table = [
            {
                "metric": "UrbanScore (Overall)",
                "values": {sc["locality"]: f"{sc['score']}/100 ({sc['grade']})" for sc in score_results},
            },
            {
                "metric": "Safety Score (Weight: 25%)",
                "values": {
                    sc["locality"]: (
                        f"{sc['components']['safety']['score']}/100"
                        if sc["components"]["safety"]["score"] is not None
                        else "Data Unavailable"
                    )
                    for sc in score_results
                },
            },
            {
                "metric": "Infrastructure Score (Weight: 25%)",
                "values": {
                    sc["locality"]: (
                        f"{sc['components']['infrastructure']['score']}/100"
                        if sc["components"]["infrastructure"]["score"] is not None
                        else "Data Unavailable"
                    )
                    for sc in score_results
                },
            },
            {
                "metric": "Environment Score (Weight: 20%)",
                "values": {
                    sc["locality"]: (
                        f"{sc['components']['environment']['score']}/100"
                        if sc["components"]["environment"]["score"] is not None
                        else "Data Unavailable"
                    )
                    for sc in score_results
                },
            },
            {
                "metric": "Social Infrastructure (Weight: 15%)",
                "values": {
                    sc["locality"]: (
                        f"{sc['components']['social_infrastructure']['score']}/100"
                        if sc["components"]["social_infrastructure"]["score"] is not None
                        else "Data Unavailable"
                    )
                    for sc in score_results
                },
            },
            {
                "metric": "Governance & Complaints (Weight: 15%)",
                "values": {
                    sc["locality"]: (
                        f"{sc['components']['governance']['score']}/100"
                        if sc["components"]["governance"]["score"] is not None
                        else "Data Unavailable"
                    )
                    for sc in score_results
                },
            },
        ]

        # Add underlying dataset metrics
        for idx, ev in enumerate(evidence_list):
            loc_name = score_results[idx]["locality"]
            ward_data = ev.get("ward")
            police_data = ev.get("police")

        metrics_table.append({
            "metric": "BBMP Work Orders (2025-26)",
            "values": {
                sc["locality"]: (
                    f"{evidence_list[i].get('ward', {}).get('total_work_orders', 0)} orders"
                    if evidence_list[i].get("ward")
                    else "Ward data unavailable"
                )
                for i, sc in enumerate(score_results)
            },
        })

        metrics_table.append({
            "metric": "BBMP Sanctioned Budget",
            "values": {
                sc["locality"]: (
                    f"₹{evidence_list[i].get('ward', {}).get('total_amount_crores', 0):.2f} Cr"
                    if evidence_list[i].get("ward")
                    else "Ward data unavailable"
                )
                for i, sc in enumerate(score_results)
            },
        })

        metrics_table.append({
            "metric": "Mapped Police Presence",
            "values": {
                sc["locality"]: (
                    f"{evidence_list[i].get('police', {}).get('station_count', 0)} stations, "
                    f"{evidence_list[i].get('police', {}).get('outpost_count', 0)} outposts"
                    if evidence_list[i].get("police")
                    else "GIS coverage unavailable"
                )
                for i, sc in enumerate(score_results)
            },
        })

        data_sources_used = [
            "Bruhat Bengaluru Mahanagara Palike (BBMP) Work Orders 2025-2026",
            "Karnataka State Police GIS Station Registry",
            "CPCB National Air Quality Index (NAQI) Realtime Feed",
            "KSPCB MINARS Lake Water Quality Records",
            "UrbanPulse Public Grievance Audit Logs",
        ]

        return {
            "winner": winner,
            "compared_localities": score_results,
            "summary": " ".join(summary_parts),
            "metrics_table": metrics_table,
            "data_sources_used": data_sources_used,
        }
