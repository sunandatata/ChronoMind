from fastapi import APIRouter

from services.graph import get_graph_service


router = APIRouter()


@router.get("/graph/analytics")
async def graph_analytics() -> dict:
    graph_svc = get_graph_service()
    return await graph_svc.get_graph_analytics()


@router.get("/graph/communities")
async def graph_communities() -> dict:
    graph_svc = get_graph_service()
    analytics = await graph_svc.get_graph_analytics()
    return {
        "connected_components": analytics.get("connected_components", []),
        "communities": analytics.get("communities", []),
    }


@router.get("/graph/versions/{event_id}")
async def event_versions(event_id: str) -> dict:
    graph_svc = get_graph_service()
    versions = await graph_svc.get_event_versions(event_id)
    return {"event_id": event_id, "versions": versions}

