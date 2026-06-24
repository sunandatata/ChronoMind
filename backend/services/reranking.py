from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import math
import re

import numpy as np

from models.event import EventType, MemoryEvent, SourceType
from services.embedding import cosine_similarity
from services.graph import get_graph_service
from services.query_understanding import QueryProfile, QueryType, TemporalIntent


def rrf_fusion(
    rankings: list[list[dict]],
    k: int = 60,
    source_weights: list[float] | None = None,
    source_names: list[str] | None = None,
) -> list[dict]:
    if source_weights is None:
        source_weights = [1.0] * len(rankings)
    if source_names is None:
        source_names = [f"source_{idx}" for idx in range(len(rankings))]

    scores: dict[str, float] = defaultdict(float)
    all_items: dict[str, dict] = {}
    contributions: dict[str, list[dict]] = defaultdict(list)

    for source_idx, ranking in enumerate(rankings):
        weight = source_weights[source_idx] if source_idx < len(source_weights) else 1.0
        source_name = source_names[source_idx] if source_idx < len(source_names) else f"source_{source_idx}"

        for rank, item in enumerate(ranking):
            item_id = item.get("id", "")
            if not item_id:
                continue

            base_score = weight / (k + rank + 1)
            hop = item.get("_hop")
            hop_bonus = 0.0
            if isinstance(hop, int) and hop <= 3:
                hop_bonus = weight * (3 - hop) / (k * 10)

            contribution = base_score + hop_bonus
            scores[item_id] += contribution
            contributions[item_id].append(
                {
                    "source": source_name,
                    "rank": rank + 1,
                    "score": contribution,
                    "raw_score": item.get("score"),
                    "hop": hop,
                }
            )

            existing = all_items.get(item_id)
            if existing is None:
                all_items[item_id] = dict(item)
            else:
                if not existing.get("embedding") and item.get("embedding"):
                    existing["embedding"] = item["embedding"]
                if not existing.get("payload") and item.get("payload"):
                    existing["payload"] = item["payload"]
                existing.setdefault("_match_type", item.get("_match_type"))

    fused = []
    for item_id in sorted(scores, key=lambda value: -scores[value]):
        item = dict(all_items[item_id])
        item["rrf_score"] = scores[item_id]
        item["_source_contributions"] = contributions[item_id]
        item["_retrieval_sources"] = sorted({c["source"] for c in contributions[item_id]})
        fused.append(item)
    return fused


def _parse_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.utcnow()
    return datetime.utcnow()


def _safe_enum(enum_cls, value, default):
    try:
        return enum_cls(value)
    except Exception:
        return default


def _raw_to_event(candidate: dict) -> MemoryEvent:
    payload = candidate.get("payload", candidate)
    timestamp = _parse_timestamp(payload.get("timestamp", candidate.get("timestamp")))
    return MemoryEvent(
        id=payload.get("id", payload.get("event_id", candidate.get("id", "unknown"))),
        text=payload.get("text", ""),
        timestamp=timestamp,
        source=_safe_enum(SourceType, payload.get("source", "manual"), SourceType.MANUAL),
        event_type=_safe_enum(EventType, payload.get("event_type", "observation"), EventType.OBSERVATION),
        entities=payload.get("entities") or [],
        topics=payload.get("topics") or [],
        sentiment=payload.get("sentiment"),
        confidence=float(payload.get("confidence", 1.0)),
        importance_score=float(payload.get("importance_score", candidate.get("importance_score", 0.5))),
        memory_strength=float(payload.get("memory_strength", candidate.get("memory_strength", 0.5))),
    )


def _event_tokens(text: str) -> set[str]:
    return set(re.sub(r"[^\w\s]", " ", text.lower()).split())


def _query_term_overlap(event: MemoryEvent, profile: QueryProfile) -> float:
    event_tokens = _event_tokens(event.text)
    query_terms = set(profile.topics) | {entity.lower() for entity in profile.entities}
    if not query_terms:
        return 0.5
    overlap = event_tokens & query_terms
    return min(1.0, 0.3 + 0.18 * len(overlap))


def _temporal_distance_score(event: MemoryEvent, profile: QueryProfile) -> float:
    now = datetime.utcnow()
    age_days = max((now - event.timestamp).days, 0)

    if profile.time_window:
        start, end = profile.time_window
        if start <= event.timestamp <= end:
            span_days = max((end - start).days, 1)
            dist_start = abs((event.timestamp - start).days)
            dist_end = abs((end - event.timestamp).days)
            edge_distance = min(dist_start, dist_end)
            return 1.0 / (1.0 + edge_distance / max(span_days, 1))
        return 0.15

    if profile.temporal_intent == TemporalIntent.CURRENT_STATE:
        return float(np.exp(-age_days / 30.0))
    if profile.temporal_intent == TemporalIntent.EVOLUTION_OVER_TIME:
        return 1.0 / (1.0 + np.log1p(age_days / 21.0))
    return 1.0 / (1.0 + np.log1p(age_days / 45.0))


def _recency_score(event: MemoryEvent) -> float:
    age_days = max((datetime.utcnow() - event.timestamp).days, 0)
    return 1.0 / (1.0 + np.log1p(age_days / 30.0))


def _event_type_weight(event: MemoryEvent, profile: QueryProfile) -> float:
    event_type = event.event_type.value
    if profile.query_type == QueryType.DECISION_TRACE:
        weights = {
            "decision": 1.5,
            "action": 1.2,
            "opinion": 1.05,
            "belief": 1.0,
            "learning": 0.95,
            "observation": 0.9,
        }
    elif profile.query_type == QueryType.TEMPORAL_EVOLUTION:
        weights = {
            "belief": 1.35,
            "opinion": 1.3,
            "decision": 1.1,
            "learning": 1.0,
            "action": 0.95,
            "observation": 0.9,
        }
    elif profile.query_type == QueryType.CAUSAL_INFERENCE:
        weights = {
            "decision": 1.4,
            "action": 1.3,
            "belief": 1.05,
            "learning": 1.0,
            "opinion": 0.95,
            "observation": 0.9,
        }
    elif profile.query_type == QueryType.COMPARISON_QUERY:
        weights = {
            "decision": 1.0,
            "action": 1.0,
            "belief": 1.0,
            "opinion": 1.0,
            "learning": 1.0,
            "observation": 1.0,
        }
    else:
        weights = {
            "observation": 1.15,
            "learning": 1.05,
            "decision": 1.0,
            "action": 0.98,
            "belief": 1.0,
            "opinion": 0.95,
        }
    return weights.get(event_type, 1.0)


def _graph_distance_score(candidate: dict) -> float:
    hop = candidate.get("_hop")
    if hop is None:
        hop = candidate.get("graph_hop")
    if hop is None:
        return 0.35
    return 1.0 / (1.0 + float(hop))


def _causal_edge_strength(candidate: dict) -> float:
    match_type = str(candidate.get("_match_type", "")).lower()
    score = 0.1
    if "causal" in match_type:
        score += 0.6
    if "belief" in match_type:
        score += 0.2
    if "contradiction" in match_type:
        score += 0.35
    channels = candidate.get("channels") or {}
    graph_hits = channels.get("graph", {})
    if graph_hits.get("causal_strength"):
        score += min(float(graph_hits["causal_strength"]), 1.0) * 0.35
    return min(score, 1.0)


def _centrality_score(candidate: dict, graph_signals: dict[str, dict[str, float]]) -> float:
    signal = graph_signals.get(candidate.get("id", ""), {})
    if not signal:
        return 0.2
    return float(signal.get("page_rankish", 0.2))


def _vector_similarity(candidate: dict, query_embedding: list[float]) -> float:
    embedding = candidate.get("embedding") or []
    if not embedding:
        return 0.0
    return max(0.0, cosine_similarity(embedding, query_embedding))


def _entity_overlap_score(candidate: dict, profile: QueryProfile) -> float:
    payload = candidate.get("payload", candidate)
    event_entities = {str(item).lower() for item in payload.get("entities") or []}
    event_topics = {str(item).lower() for item in payload.get("topics") or []}
    profile_terms = {str(item).lower() for item in profile.entities + profile.topics}
    overlap = (event_entities | event_topics) & profile_terms
    if not profile_terms:
        return 0.35
    return min(1.0, 0.2 + 0.16 * len(overlap))


def _source_support_score(candidate: dict) -> float:
    channels = candidate.get("channels") or {}
    support = 0.0
    for channel_name, info in channels.items():
        if not info:
            continue
        if isinstance(info, dict):
            support += 0.15
            if channel_name == "vector":
                support += min(float(info.get("score") or 0.0), 1.0) * 0.1
            if channel_name == "bm25":
                support += min(float(info.get("score") or 0.0), 8.0) / 40.0
            if channel_name == "graph":
                support += 0.1
    return min(support, 1.0)


def _importance_score(candidate: dict) -> float:
    payload = candidate.get("payload", candidate)
    return float(payload.get("importance_score") or candidate.get("importance_score") or 0.5)


def _memory_strength(candidate: dict) -> float:
    payload = candidate.get("payload", candidate)
    base = float(payload.get("memory_strength") or candidate.get("memory_strength") or 0.5)
    strength = base
    channels = candidate.get("channels") or {}
    if "graph" in channels:
        strength += 0.08
    if "vector" in channels:
        strength += 0.04
    if "bm25" in channels:
        strength += 0.03
    return min(strength, 1.0)


def _contra_bonus(candidate: dict) -> float:
    match_type = str(candidate.get("_match_type", "")).lower()
    return 0.25 if "contradiction" in match_type else 0.0


def _feature_weights(profile: QueryProfile) -> dict[str, float]:
    if profile.query_type == QueryType.DECISION_TRACE:
        return {
            "vector": 0.16,
            "lexical": 0.10,
            "graph": 0.20,
            "centrality": 0.14,
            "temporal": 0.14,
            "recency": 0.08,
            "event_type": 0.09,
            "causal": 0.17,
            "entity": 0.12,
            "support": 0.08,
            "contra": 0.02,
        }
    if profile.query_type == QueryType.TEMPORAL_EVOLUTION:
        return {
            "vector": 0.13,
            "lexical": 0.07,
            "graph": 0.17,
            "centrality": 0.12,
            "temporal": 0.20,
            "recency": 0.12,
            "event_type": 0.10,
            "causal": 0.08,
            "entity": 0.10,
            "support": 0.08,
            "contra": 0.08,
        }
    if profile.query_type == QueryType.CAUSAL_INFERENCE:
        return {
            "vector": 0.14,
            "lexical": 0.07,
            "graph": 0.18,
            "centrality": 0.12,
            "temporal": 0.12,
            "recency": 0.08,
            "event_type": 0.08,
            "causal": 0.20,
            "entity": 0.12,
            "support": 0.07,
            "contra": 0.12,
        }
    if profile.query_type == QueryType.COMPARISON_QUERY:
        return {
            "vector": 0.16,
            "lexical": 0.13,
            "graph": 0.14,
            "centrality": 0.10,
            "temporal": 0.10,
            "recency": 0.08,
            "event_type": 0.08,
            "causal": 0.05,
            "entity": 0.16,
            "support": 0.10,
            "contra": 0.10,
        }
    return {
        "vector": 0.18,
        "lexical": 0.16,
        "graph": 0.10,
        "centrality": 0.10,
        "temporal": 0.12,
        "recency": 0.10,
        "event_type": 0.09,
        "causal": 0.05,
        "entity": 0.12,
        "support": 0.07,
        "contra": 0.01,
    }


def _score_candidate(
    candidate: dict,
    query_embedding: list[float],
    profile: QueryProfile,
    graph_signals: dict[str, dict[str, float]],
) -> tuple[float, dict]:
    vector_score = _vector_similarity(candidate, query_embedding)
    lexical_score = min(float(candidate.get("_bm25_score") or candidate.get("score") or 0.0) / 5.0, 1.0)
    graph_score = _graph_distance_score(candidate)
    centrality_score = _centrality_score(candidate, graph_signals)
    temporal_score = _temporal_distance_score(_raw_to_event(candidate), profile)
    recency_score = _recency_score(_raw_to_event(candidate))
    event_type_score = _event_type_weight(_raw_to_event(candidate), profile)
    causal_score = _causal_edge_strength(candidate)
    entity_score = _entity_overlap_score(candidate, profile)
    support_score = _source_support_score(candidate)
    contra_score = _contra_bonus(candidate)
    importance_score = _importance_score(candidate)
    memory_strength = _memory_strength(candidate)

    weights = _feature_weights(profile)
    raw_score = (
        weights["vector"] * vector_score
        + weights["lexical"] * lexical_score
        + weights["graph"] * graph_score
        + weights["centrality"] * centrality_score
        + weights["temporal"] * temporal_score
        + weights["recency"] * recency_score
        + weights["event_type"] * event_type_score
        + weights["causal"] * causal_score
        + weights["entity"] * entity_score
        + weights["support"] * support_score
        + weights["contra"] * contra_score
        + 0.10 * importance_score
        + 0.08 * memory_strength
    )

    query_bias = 0.05 if profile.query_type == QueryType.FACTUAL_RECALL else 0.0
    calibrated = 1.0 / (1.0 + math.exp(-7.5 * (raw_score + query_bias - 0.5)))

    features = {
        "vector_similarity_score": vector_score,
        "lexical_score": lexical_score,
        "graph_distance_score": graph_score,
        "graph_centrality_score": centrality_score,
        "temporal_distance_score": temporal_score,
        "recency_score": recency_score,
        "event_type_weight": event_type_score,
        "causal_edge_strength": causal_score,
        "entity_overlap_score": entity_score,
        "source_support_score": support_score,
        "contradiction_score": contra_score,
        "importance_score": importance_score,
        "memory_strength": memory_strength,
        "calibrated_score": calibrated,
    }
    return calibrated, features


def _cluster_key(candidate: dict) -> str:
    payload = candidate.get("payload", candidate)
    topics = payload.get("topics") or []
    entities = payload.get("entities") or []
    if topics:
        return f"topic:{str(topics[0]).lower()}"
    if entities:
        return f"entity:{str(entities[0]).lower()}"
    timestamp = payload.get("timestamp", "")
    if timestamp:
        return f"month:{str(timestamp)[:7]}"
    return "misc"


def _similarity_matrix_item(candidate: dict, other: dict) -> float:
    emb_a = candidate.get("embedding") or []
    emb_b = other.get("embedding") or []
    if emb_a and emb_b:
        return cosine_similarity(emb_a, emb_b)
    tokens_a = _event_tokens((candidate.get("payload", candidate) or {}).get("text", ""))
    tokens_b = _event_tokens((other.get("payload", other) or {}).get("text", ""))
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _quality_filter(candidate: dict, features: dict, selected: list[dict], profile: QueryProfile) -> bool:
    payload = candidate.get("payload", candidate)
    text = payload.get("text", "")
    if not text:
        return False

    if features["vector_similarity_score"] > 0.9:
        if any(_similarity_matrix_item(candidate, kept) > 0.9 for kept in selected):
            return False

    if profile.causal_intent and features["causal_edge_strength"] < 0.22 and features["graph_distance_score"] < 0.34:
        if payload.get("event_type") not in {"decision", "action"}:
            return False

    if len(text.split()) < 6 and len(payload.get("entities") or []) >= 3:
        return False

    if features["calibrated_score"] < 0.18 and features["source_support_score"] < 0.18:
        return False

    return True


def _selected_cluster_counts(selected: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in selected:
        counts[_cluster_key(item)] += 1
    return counts


def _diversified_select(
    scored: list[dict],
    profile: QueryProfile,
    top_k: int,
) -> tuple[list[dict], list[str]]:
    selected: list[dict] = []
    selected_ids: set[str] = set()
    cluster_counts: dict[str, int] = defaultdict(int)
    cluster_targets = max(3, min(top_k, 5))
    max_per_cluster = 2 if profile.query_type != QueryType.FACTUAL_RECALL else 1

    while len(selected) < top_k and scored:
        best_index = None
        best_score = float("-inf")
        for idx, candidate in enumerate(scored):
            item_id = candidate["id"]
            if item_id in selected_ids:
                continue
            cluster = candidate["_cluster"]
            cluster_penalty = 0.0
            if cluster_counts[cluster] >= max_per_cluster:
                cluster_penalty += 0.25
            if len(cluster_counts) < cluster_targets and cluster not in cluster_counts:
                cluster_penalty -= 0.08

            redundancy_penalty = 0.0
            if selected:
                redundancy_penalty = max(
                    _similarity_matrix_item(candidate, kept) for kept in selected
                )

            mmr_score = candidate["_score"] - 0.35 * redundancy_penalty - cluster_penalty
            if mmr_score > best_score:
                best_score = mmr_score
                best_index = idx

        if best_index is None:
            break

        chosen = scored.pop(best_index)
        selected.append(chosen)
        selected_ids.add(chosen["id"])
        cluster_counts[chosen["_cluster"]] += 1

    return selected, list(cluster_counts.keys())


async def rerank(
    candidates: list[dict],
    embeddings: list[list[float]],
    query: str,
    query_embedding: list[float],
    profile: QueryProfile,
    top_k: int = 8,
) -> tuple[list[MemoryEvent], set[str], list[dict]]:
    if not candidates:
        return [], set(), []

    graph_svc = get_graph_service()
    ids = [candidate.get("id", "") for candidate in candidates if candidate.get("id")]
    try:
        graph_signals = await graph_svc.get_graph_signals(ids)
    except Exception:
        graph_signals = {}

    scored: list[dict] = []
    ranking_details: list[dict] = []
    for candidate, embedding in zip(candidates, embeddings):
        candidate = dict(candidate)
        if embedding and not candidate.get("embedding"):
            candidate["embedding"] = embedding
        score, features = _score_candidate(candidate, query_embedding, profile, graph_signals)
        candidate["_score"] = score
        candidate["_features"] = features
        candidate["_cluster"] = _cluster_key(candidate)
        candidate["_event"] = _raw_to_event(candidate)
        ranking_details.append(
            {
                "id": candidate["id"],
                "score": score,
                "cluster": candidate["_cluster"],
                "features": features,
                "source_hits": candidate.get("channels", {}),
                "event_type": candidate["_event"].event_type.value,
                "timestamp": candidate["_event"].timestamp.isoformat(),
                "text": candidate["_event"].text,
            }
        )
        if _quality_filter(candidate, features, scored, profile):
            scored.append(candidate)

    scored.sort(key=lambda item: item["_score"], reverse=True)
    selected, selected_clusters = _diversified_select(scored, profile, top_k)

    selected_events = [item["_event"] for item in selected]
    shift_ids = _detect_belief_shifts(selected_events)
    selected_events.sort(key=lambda event: event.timestamp)
    ranking_details.sort(key=lambda item: item["score"], reverse=True)
    return selected_events, shift_ids, ranking_details


def _detect_belief_shifts(events: list[MemoryEvent]) -> set[str]:
    shift_ids: set[str] = set()
    sorted_events = sorted(events, key=lambda event: event.timestamp)
    for idx in range(1, len(sorted_events)):
        prev = sorted_events[idx - 1]
        curr = sorted_events[idx]
        shared_topics = set(prev.topics or []) & set(curr.topics or [])
        if not shared_topics:
            continue
        prev_sentiment = prev.sentiment if prev.sentiment is not None else 0.0
        curr_sentiment = curr.sentiment if curr.sentiment is not None else 0.0
        if abs(curr_sentiment - prev_sentiment) >= 0.4:
            shift_ids.add(curr.id)
    return shift_ids
