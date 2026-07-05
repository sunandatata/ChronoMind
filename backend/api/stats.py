from fastapi import APIRouter

from services.graph import get_graph_service
from services.vector import get_vector_service

router = APIRouter()


@router.get("/stats")
async def get_stats() -> dict:
    graph_svc = get_graph_service()
    vector_svc = get_vector_service()

    graph_stats = await graph_svc.get_graph_stats()
    belief_stats = await graph_svc.get_belief_stats()
    try:
        vector_count = len(await vector_svc.get_all_events(limit=5000))
    except Exception:
        vector_count = 0

    return {
        **graph_stats,
        "belief_edges": belief_stats,
        "vector_memories": vector_count,
    }
