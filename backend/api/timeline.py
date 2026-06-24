from fastapi import APIRouter, Query
from typing import Optional
from models.query import TimelineResponse
from models.event import MemoryEvent, EventType, SourceType
from services.graph import get_graph_service
from datetime import datetime

router = APIRouter()


@router.get("/timeline/{concept}", response_model=TimelineResponse)
async def get_timeline(
    concept: str,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None)
) -> TimelineResponse:
    """Get chronological timeline of events related to a concept."""
    graph_svc = get_graph_service()
    raw_events = await graph_svc.get_timeline(concept, start, end)

    events = []
    for r in raw_events:
        ts = r.get("timestamp", datetime.utcnow().isoformat())
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except Exception:
                ts = datetime.utcnow()

        try:
            event_type = EventType(r.get("event_type", "observation"))
        except ValueError:
            event_type = EventType.OBSERVATION

        try:
            source = SourceType(r.get("source", "manual"))
        except ValueError:
            source = SourceType.MANUAL

        events.append(MemoryEvent(
            id=r.get("id", ""),
            text=r.get("text", ""),
            timestamp=ts,
            source=source,
            event_type=event_type,
            entities=r.get("entities", []),
            topics=r.get("topics", []),
            sentiment=r.get("sentiment"),
            confidence=r.get("confidence", 1.0)
        ))

    return TimelineResponse(concept=concept, events=events, total=len(events))
