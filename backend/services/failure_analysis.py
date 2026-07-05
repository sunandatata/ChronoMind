from __future__ import annotations

from typing import Any


def analyze_failure(debug_trace: dict[str, Any]) -> list[dict[str, Any]]:
    query_profile = debug_trace.get("query_profile", {})
    candidate_counts = debug_trace.get("candidate_counts", {})
    explanations = debug_trace.get("ranking_explanations", [])

    reasons: list[dict[str, Any]] = []
    if candidate_counts.get("graph", 0) < 3:
        reasons.append({"reason": "sparse_graph", "detail": "Graph expansion returned few candidates."})
    if candidate_counts.get("bm25", 0) < 3:
        reasons.append({"reason": "weak_lexical_match", "detail": "Lexical retrieval produced limited support."})
    if candidate_counts.get("vector", 0) < 3:
        reasons.append({"reason": "weak_semantic_match", "detail": "Vector retrieval returned a small candidate set."})

    if query_profile.get("query_type") in {"TEMPORAL_EVOLUTION", "BELIEF_EVOLUTION"}:
        if not any(item.get("contradiction_score", 0) > 0.2 for item in explanations):
            reasons.append({"reason": "missing_contradiction_signal", "detail": "No strong contradiction evidence surfaced."})

    if not explanations:
        reasons.append({"reason": "insufficient_history", "detail": "No ranking explanations were produced."})
    else:
        top = explanations[0]
        if top.get("final_score", 0) < 0.3:
            reasons.append({"reason": "low_final_confidence", "detail": "Top ranked memory is only weakly supported."})
        if top.get("entity_overlap_score", 0) < 0.2:
            reasons.append({"reason": "missing_entities", "detail": "Query entities do not strongly overlap with retrieved memories."})

    if not reasons:
        reasons.append({"reason": "healthy_retrieval", "detail": "Retrieval signals appear balanced."})
    return reasons[:6]

