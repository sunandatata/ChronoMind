from fastapi import APIRouter, HTTPException
from time import perf_counter
from models.query import QueryRequest, QueryResponse, QueryExplanationResponse, RetrievedEventExplanation
from services.retrieval import hybrid_retrieve
from services.reranking import rerank
from services.context import assemble_context, build_consolidation_summary
from services.reasoning import LLMNotConfiguredError, reason
from services.embedding import embed_text
from services.memory import get_memory_signal_service, MemoryInteraction
from services.session import get_session_service
from services.failure_analysis import analyze_failure

router = APIRouter()


async def _run_query(request: QueryRequest):
    telemetry: dict[str, float] = {}
    session_svc = get_session_service()
    session = session_svc.get(request.session_id) if request.session_id else None

    t0 = perf_counter()
    candidates, embeddings, query_profile, _, retrieval_trace = await hybrid_retrieve(request, include_trace=True)
    telemetry["retrieval_latency_ms"] = (perf_counter() - t0) * 1000.0

    t1 = perf_counter()
    query_embedding = await embed_text(request.query)

    final_events, shift_ids, ranking_details = await rerank(
        candidates,
        embeddings,
        request.query,
        query_embedding,
        profile=query_profile,
        top_k=request.top_k,
    )
    telemetry["reranking_latency_ms"] = (perf_counter() - t1) * 1000.0

    t2 = perf_counter()
    embedding_by_id = {
        candidate["id"]: embedding
        for candidate, embedding in zip(candidates, embeddings)
        if candidate.get("id")
    }
    final_embeddings = [embedding_by_id.get(event.id, []) for event in final_events]

    context = assemble_context(
        final_events, request.query,
        shift_ids=shift_ids,
        embeddings=final_embeddings,
        query_profile=query_profile,
        ranking_details=ranking_details,
    )
    telemetry["context_latency_ms"] = (perf_counter() - t2) * 1000.0

    t3 = perf_counter()
    try:
        response = await reason(request.query, context, final_events, query_profile.query_type.value)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    telemetry["llm_latency_ms"] = (perf_counter() - t3) * 1000.0

    telemetry["total_latency_ms"] = sum(telemetry.values())

    ranking_map = {item["id"]: item for item in ranking_details}
    retrieval_explanations = [
        {
            "id": event.id,
            "rank": idx + 1,
            "text": event.text,
            "event_type": event.event_type.value,
            "final_score": ranking_map[event.id]["score"] if event.id in ranking_map else 0.0,
            "vector_similarity_score": ranking_map[event.id]["features"]["vector_similarity_score"] if event.id in ranking_map else 0.0,
            "bm25_score": ranking_map[event.id]["features"]["lexical_score"] if event.id in ranking_map else 0.0,
            "graph_score": ranking_map[event.id]["features"]["graph_distance_score"] if event.id in ranking_map else 0.0,
            **(ranking_map[event.id]["features"] if event.id in ranking_map else {}),
        }
        for idx, event in enumerate(final_events)
    ]

    debug_trace = {
        **retrieval_trace,
        "ranking_explanations": retrieval_explanations,
        "reranked_top_10": [],
        "final_context_events": [
            {
                "id": event.id,
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type.value,
                "text": event.text,
            }
            for event in final_events
        ],
        "context_text": context,
        "selected_event_ids": [event.id for event in final_events],
        "query_profile": query_profile.to_trace(),
        "telemetry": telemetry,
        "playback_steps": [
            {"step": 1, "title": "Query Classification", "items": [retrieval_trace.get("query_profile", {})]},
            {"step": 2, "title": "Vector Retrieval", "items": retrieval_trace.get("top_20_before_fusion", {}).get("vector", [])},
            {"step": 3, "title": "Graph Retrieval", "items": retrieval_trace.get("top_20_before_fusion", {}).get("graph", [])},
            {"step": 4, "title": "BM25 Retrieval", "items": retrieval_trace.get("top_20_before_fusion", {}).get("bm25", [])},
            {"step": 5, "title": "Fusion", "items": retrieval_trace.get("top_10_after_fusion", [])},
            {"step": 6, "title": "Reranking", "items": retrieval_explanations},
            {"step": 7, "title": "Timeline Reconstruction", "items": [
                {
                    "id": event.id,
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type.value,
                    "text": event.text,
                }
                for event in final_events
            ]},
            {"step": 8, "title": "Final Answer", "items": [{"answer": response.answer, "confidence": response.confidence}]},
        ],
    }
    debug_trace["failure_analysis"] = analyze_failure(debug_trace)
    debug_trace["consolidation_summary"] = build_consolidation_summary(final_events)

    debug_trace["reranked_top_10"] = [
        {
            "id": event.id,
            "score": ranking_map[event.id]["score"] if event.id in ranking_map else None,
            "cluster": ranking_map[event.id]["cluster"] if event.id in ranking_map else None,
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "text": event.text,
            "features": ranking_map[event.id]["features"] if event.id in ranking_map else {},
        }
        for event in final_events[:10]
    ]

    return response, debug_trace, retrieval_explanations, ranking_map, query_profile, final_events


@router.post("/query", response_model=QueryResponse)
async def query_memory(request: QueryRequest) -> QueryResponse:
    response, debug_trace, retrieval_explanations, ranking_map, query_profile, final_events = await _run_query(request)

    memory_svc = get_memory_signal_service()
    session_svc = get_session_service()
    interactions: list[MemoryInteraction] = []
    selected_ids = {event.id for event in final_events}
    selected_lookup = {event.id: event for event in final_events}
    for explanation in retrieval_explanations:
        event_id = explanation["id"]
        selected = event_id in selected_ids
        source_event = selected_lookup.get(event_id)
        interaction = MemoryInteraction(
            event_id=event_id,
            current_strength=float(getattr(source_event, "memory_strength", 0.5) or 0.5),
            event_timestamp=source_event.timestamp.isoformat() if source_event else None,
            retrieved=True,
            selected=selected,
            referenced=selected,
            used_in_answer=selected,
            ignored=not selected,
        )
        interactions.append(interaction)
    try:
        await memory_svc.apply_interactions(interactions, response.answer)
    except Exception:
        pass

    session_id = request.session_id or (debug_trace.get("session") or {}).get("session_id")
    if session_id:
        session_svc.update(
            session_id,
            query=request.query,
            event_ids=[event.id for event in final_events],
            explored_event_ids=[item["id"] for item in retrieval_explanations[:20]],
        )

    return QueryResponse(
        answer=response.answer,
        source_events=response.source_events,
        query_type=query_profile.query_type.value,
        events_searched=response.events_searched,
        confidence=response.confidence,
        session_id=session_id,
        debug_trace=debug_trace,
    )


@router.post("/query/explain", response_model=QueryExplanationResponse)
async def explain_query(request: QueryRequest) -> QueryExplanationResponse:
    response, debug_trace, retrieval_explanations, _, _, _ = await _run_query(request)
    explanations = [RetrievedEventExplanation(**item) for item in retrieval_explanations]
    return QueryExplanationResponse(
        query=request.query,
        query_type=response.query_type,
        explanations=explanations,
        debug_trace=debug_trace,
    )
