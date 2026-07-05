from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from models.query import QueryRequest
from services.embedding import embed_batch, embed_text
from services.graph import get_graph_service
from services.query_understanding import QueryProfile, QueryType, understand_query
from services.reranking import rrf_fusion
from services.session import get_session_service
from services.vector import get_vector_service
from utils.text import get_bm25_index


def _parse_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.utcnow()
    return datetime.utcnow()


def _within_window(candidate: dict, time_window: Optional[tuple[datetime, datetime]]) -> bool:
    if not time_window:
        return True
    payload = candidate.get("payload", candidate)
    ts = _parse_timestamp(payload.get("timestamp"))
    return time_window[0] <= ts <= time_window[1]


def _channel_item(source: str, item: dict, rank: int) -> dict:
    payload = item.get("payload", item)
    candidate_id = item.get("id") or payload.get("id") or payload.get("event_id")
    normalized = {
        "id": candidate_id,
        "payload": payload,
        "embedding": item.get("embedding") or [],
        "timestamp": payload.get("timestamp"),
        "source": source,
        "_channel_rank": rank,
        "_channel_score": float(item.get("score") or 0.0),
        "_match_type": item.get("_match_type") or payload.get("_match_type") or source,
        "_hop": item.get("_hop", payload.get("_hop")),
        "_temporal_distance_days": 0,
        "_temporal_kept": True,
    }
    return normalized


def _bucket_top(items: list[dict], limit: int = 20) -> list[dict]:
    return [
        {
            "id": item["id"],
            "score": item.get("_channel_score", item.get("score")),
            "source": item.get("source"),
            "rank": item.get("_channel_rank"),
            "hop": item.get("_hop"),
            "match_type": item.get("_match_type"),
            "timestamp": item.get("timestamp"),
            "event_type": item.get("payload", {}).get("event_type"),
            "text": (item.get("payload", {}).get("text", "")[:180]),
        }
        for item in items[:limit]
    ]


def _merge_channels(*channels: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for channel in channels:
        for item in channel:
            item_id = item["id"]
            entry = merged.setdefault(
                item_id,
                {
                    "id": item_id,
                    "payload": dict(item.get("payload", {})),
                    "embedding": item.get("embedding") or [],
                    "timestamp": item.get("timestamp"),
                    "channels": {},
                    "_hop": item.get("_hop"),
                    "_match_type": item.get("_match_type"),
                },
            )
            entry["channels"][item["source"]] = {
                "rank": item.get("_channel_rank"),
                "score": item.get("_channel_score"),
                "hop": item.get("_hop"),
                "match_type": item.get("_match_type"),
            }
            if not entry.get("embedding") and item.get("embedding"):
                entry["embedding"] = item["embedding"]
            if item.get("payload"):
                for key, value in item["payload"].items():
                    entry["payload"].setdefault(key, value)
            if item.get("_hop") is not None:
                current_hop = entry.get("_hop")
                if current_hop is None or item["_hop"] < current_hop:
                    entry["_hop"] = item["_hop"]
            if item.get("_match_type"):
                existing = entry.get("_match_type") or ""
                if item["_match_type"] not in existing:
                    entry["_match_type"] = f"{existing},{item['_match_type']}".strip(",")
    return list(merged.values())


async def _ensure_bm25_loaded(vector_svc, bm25) -> None:
    if len(bm25) > 0:
        return
    try:
        records = await vector_svc.get_all_events(limit=2000)
    except Exception:
        return
    bm25.add_documents(
        [
            {
                "id": record.get("id"),
                "text": record.get("payload", {}).get("text", ""),
                "payload": record.get("payload", {}),
            }
            for record in records
            if record.get("payload", {}).get("text")
        ]
    )


async def _hydrate_embeddings(candidates: list[dict], vector_svc) -> list[list[float]]:
    missing_indices = [idx for idx, item in enumerate(candidates) if not item.get("embedding")]
    if not missing_indices:
        return [item.get("embedding") or [] for item in candidates]

    ids = [candidates[idx]["id"] for idx in missing_indices if candidates[idx].get("id")]
    fetched: dict[str, list[float]] = {}
    if ids:
        try:
            vectors = await vector_svc.get_all_events(limit=2000)
            fetched = {
                record["id"]: record["embedding"]
                for record in vectors
                if record.get("id") in ids and record.get("embedding")
            }
        except Exception:
            fetched = {}

    embeddings = []
    missing_texts = []
    missing_slots = []
    for idx, item in enumerate(candidates):
        embedding = item.get("embedding") or fetched.get(item.get("id", ""))
        if embedding:
            embeddings.append(embedding)
        else:
            embeddings.append([])
            missing_slots.append(idx)
            missing_texts.append(item.get("payload", {}).get("text", ""))

    if missing_texts:
        generated = await embed_batch(missing_texts)
        for slot, embedding in zip(missing_slots, generated):
            embeddings[slot] = embedding
    return embeddings


def _pre_fusion_rank(channels: list[list[dict]]) -> list[dict]:
    fused = rrf_fusion(channels, k=60, source_weights=[1.0] * len(channels))
    for item in fused:
        item["fusion_score"] = item.get("rrf_score", 0.0)
    return fused


def _query_channel_counts(channel_map: dict[str, list[dict]]) -> dict[str, int]:
    return {name: len(items) for name, items in channel_map.items()}


async def hybrid_retrieve(request: QueryRequest, include_trace: bool = False):
    profile = understand_query(request.query, request.time_start, request.time_end)
    session_svc = get_session_service()
    session_state = None
    if request.reset_session and request.session_id:
        session_svc.reset(request.session_id)
    if request.session_id:
        session_state = session_svc.get(request.session_id)
    vector_svc = get_vector_service()
    graph_svc = get_graph_service()
    bm25 = get_bm25_index()

    await _ensure_bm25_loaded(vector_svc, bm25)
    query_embedding = await embed_text(request.query)

    vector_task = (
        vector_svc.search_with_time_filter(
            query_embedding,
            profile.time_window[0].isoformat(),
            profile.time_window[1].isoformat(),
            limit=profile.candidate_limits["vector"],
        )
        if profile.time_window
        else vector_svc.search(query_embedding, limit=profile.candidate_limits["vector"])
    )

    graph_task = graph_svc.graph_traversal_retrieve(
        profile.entities,
        profile.topics,
        max_hops=profile.graph_hops,
        min_seed_confidence=0.6 if profile.query_type == QueryType.FACTUAL_RECALL else 0.65,
        seed_limit=profile.candidate_limits["graph"],
        neighbor_confidence_floor=0.5 if profile.query_type == QueryType.FACTUAL_RECALL else 0.6,
        causal_only=False,
        limit=profile.candidate_limits["graph"],
        exclude_event_ids=(session_state.explored_event_ids if session_state else []),
    )

    bm25_results = bm25.search(request.query, limit=profile.candidate_limits["bm25"])

    vector_results, graph_results = await asyncio.gather(vector_task, graph_task)

    causal_results: list[dict] = []
    contradiction_results: list[dict] = []
    belief_results: list[dict] = []
    if profile.causal_intent:
        seed_ids = [item.get("id", "") for item in graph_results[:12] if item.get("id")]
        causal_results = await graph_svc.get_causal_chain(seed_ids)
    if profile.query_type in {QueryType.TEMPORAL_EVOLUTION, QueryType.COMPARISON_QUERY, QueryType.BELIEF_EVOLUTION}:
        seed_ids = [item.get("id", "") for item in graph_results[:12] if item.get("id")]
        belief_results = await graph_svc.get_belief_evolution(seed_ids)
    if profile.query_type in {QueryType.TEMPORAL_EVOLUTION, QueryType.BELIEF_EVOLUTION}:
        seed_ids = [item.get("id", "") for item in graph_results[:12] if item.get("id")]
        contradiction_results = await graph_svc.get_contradiction_events(seed_ids)

    def _attach_time_filter(items: list[dict], source: str) -> list[dict]:
        filtered = []
        excluded_ids = set(session_state.explored_event_ids if session_state else [])
        for rank, item in enumerate(items, start=1):
            normalized = _channel_item(source, item, rank)
            if normalized["id"] in excluded_ids:
                continue
            if _within_window(normalized, profile.time_window):
                filtered.append(normalized)
        return filtered

    vector_channel = _attach_time_filter(vector_results, "vector")
    graph_channel = _attach_time_filter(graph_results + causal_results + contradiction_results, "graph")
    if belief_results:
        graph_channel.extend(_attach_time_filter(belief_results, "graph"))
    bm25_channel = _attach_time_filter(bm25_results, "bm25")

    graph_channel = [
        {**item, "_graph_signal": True, "_source_boost": 1.0}
        for item in graph_channel
    ]

    channel_map = {
        "vector": vector_channel,
        "graph": graph_channel,
        "bm25": bm25_channel,
    }

    top_before_fusion = {
        name: _bucket_top(items, limit=20)
        for name, items in channel_map.items()
    }

    merged = _merge_channels(vector_channel, graph_channel, bm25_channel)
    fusion_rank = _pre_fusion_rank([vector_channel, graph_channel, bm25_channel])
    fused_order_ids = [item["id"] for item in fusion_rank]
    fused_index = {item_id: idx for idx, item_id in enumerate(fused_order_ids)}
    merged.sort(key=lambda item: fused_index.get(item["id"], len(fused_order_ids)))

    embeddings = await _hydrate_embeddings(merged, vector_svc)

    trace = {
        "query_profile": profile.to_trace(),
        "session": session_state.to_dict() if session_state else None,
        "candidate_counts": _query_channel_counts(channel_map),
        "candidate_counts_with_expansion": {
            "vector": len(vector_results),
            "graph": len(graph_results),
            "causal": len(causal_results),
            "belief": len(belief_results),
            "contradiction": len(contradiction_results),
            "bm25": len(bm25_results),
        },
        "top_20_before_fusion": top_before_fusion,
        "top_10_after_fusion": _bucket_top(fusion_rank, limit=10),
        "pre_rerank_fused_candidates": _bucket_top(fusion_rank, limit=20),
    }

    if include_trace:
        return merged, embeddings, profile, query_embedding, trace
    return merged, embeddings, profile


async def hybrid_retrieve_with_trace(request: QueryRequest):
    return await hybrid_retrieve(request, include_trace=True)
