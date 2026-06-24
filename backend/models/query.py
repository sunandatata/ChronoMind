from pydantic import BaseModel, Field
from typing import Optional
from .event import MemoryEvent


class QueryRequest(BaseModel):
    query: str
    top_k: int = 8
    time_start: Optional[str] = None
    time_end: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    source_events: list[MemoryEvent]
    query_type: str
    events_searched: int
    confidence: float = 0.0
    debug_trace: dict = Field(default_factory=dict)


class TimelineResponse(BaseModel):
    concept: str
    events: list[MemoryEvent]
    total: int


class GraphNode(BaseModel):
    id: str
    label: str
    node_type: str
    properties: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
