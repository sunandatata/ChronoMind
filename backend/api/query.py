from fastapi import APIRouter, HTTPException
from models.query import QueryRequest, QueryResponse
from services.retrieval import hybrid_retrieve
from services.reranking import rerank
from services.context import assemble_context
from services.reasoning import LLMNotConfiguredError, reason
from services.embedding import embed_text

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_memory(request: QueryRequest) -> QueryResponse:
    candidates, embeddings, query_profile, _, retrieval_trace = await hybrid_retrieve(request, include_trace=True)

    query_embedding = await embed_text(request.query)

    final_events, shift_ids, ranking_details = await rerank(
        candidates,
        embeddings,
        request.query,
        query_embedding,
        profile=query_profile,
        top_k=request.top_k,
    )

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

    try:
        response = await reason(request.query, context, final_events, query_profile.query_type.value)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    debug_trace = {
        **retrieval_trace,
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
    }

    ranking_map = {item["id"]: item for item in ranking_details}
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

    return QueryResponse(
        answer=response.answer,
        source_events=response.source_events,
        query_type=query_profile.query_type.value,
        events_searched=response.events_searched,
        confidence=response.confidence,
        debug_trace=debug_trace,
    )
