from fastapi import APIRouter
from models.query import GraphResponse, GraphNode, GraphEdge
from services.graph import get_graph_service

router = APIRouter()


@router.get("/graph/explore", response_model=GraphResponse)
async def explore_graph() -> GraphResponse:
    """Return memory graph data for visualization."""
    graph_svc = get_graph_service()
    data = await graph_svc.get_graph_data(limit=80)

    nodes = []
    edges = []
    seen_node_ids = set()

    for event in data.get("events", []):
        node_id = event.get("id", "")
        if node_id and node_id not in seen_node_ids:
            seen_node_ids.add(node_id)
            text_preview = event.get("text", "")[:60] + "..." if len(event.get("text", "")) > 60 else event.get("text", "")
            nodes.append(GraphNode(
                id=node_id,
                label=text_preview,
                node_type="event",
                properties={
                    "event_type": event.get("event_type", ""),
                    "timestamp": str(event.get("timestamp", "")),
                    "topics": event.get("topics", [])
                }
            ))

    for concept in data.get("concepts", []):
        node_id = f"concept_{concept.get('label', '')}"
        if node_id not in seen_node_ids:
            seen_node_ids.add(node_id)
            nodes.append(GraphNode(
                id=node_id,
                label=concept.get("label", ""),
                node_type="concept",
                properties={"event_count": concept.get("event_count", 0)}
            ))

    for edge in data.get("edges", []):
        source = edge.get("source", "")
        target = edge.get("target", "")
        if target and not target.startswith("concept_"):
            target = f"concept_{target}" if edge.get("rel") == "ABOUT" else target
        if source and target and source in seen_node_ids and target in seen_node_ids:
            edges.append(GraphEdge(
                source=source,
                target=target,
                relationship=edge.get("rel", "RELATED")
            ))

    return GraphResponse(nodes=nodes, edges=edges)
