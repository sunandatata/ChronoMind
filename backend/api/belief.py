from fastapi import APIRouter

from models.query import BeliefEvolutionResponse, BeliefEvent
from services.graph import get_graph_service

router = APIRouter()


@router.get("/belief/{concept}", response_model=BeliefEvolutionResponse)
async def belief_evolution(concept: str) -> BeliefEvolutionResponse:
    graph_svc = get_graph_service()
    data = await graph_svc.get_belief_evolution_by_concept(concept)
    belief_edges = await graph_svc.get_belief_stats()
    timeline = [
        BeliefEvent(
            id=item.get("id", ""),
            text=item.get("text", ""),
            timestamp=str(item.get("timestamp", "")),
            event_type=item.get("event_type", "observation"),
            relationship=item.get("_match_type", item.get("relationship", "")),
            role=item.get("_role", ""),
            sentiment=item.get("sentiment"),
            importance_score=item.get("importance_score"),
            memory_strength=item.get("memory_strength"),
        )
        for item in data.get("events", [])
    ]
    return BeliefEvolutionResponse(
        concept=data.get("concept", concept),
        timeline=timeline,
        links=data.get("links", []),
        belief_edges=belief_edges,
    )
