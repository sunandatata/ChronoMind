from pydantic import BaseModel, Field
from typing import Optional, Any
from .event import MemoryEvent


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=8, ge=1, le=25)
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    session_id: Optional[str] = None
    reset_session: bool = False


class QueryResponse(BaseModel):
    answer: str
    source_events: list[MemoryEvent]
    query_type: str
    events_searched: int
    confidence: float = 0.0
    session_id: Optional[str] = None
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


class RetrievedEventExplanation(BaseModel):
    id: str
    rank: int
    text: str
    event_type: str
    final_score: float
    vector_similarity_score: float = 0.0
    bm25_score: float = 0.0
    graph_distance_score: float = 0.0
    temporal_distance_score: float = 0.0
    importance_score: float = 0.0
    memory_strength: float = 0.0
    graph_centrality_score: float = 0.0
    causal_edge_strength: float = 0.0
    entity_overlap_score: float = 0.0
    source_support_score: float = 0.0
    contradiction_score: float = 0.0


class QueryExplanationResponse(BaseModel):
    query: str
    query_type: str
    explanations: list[RetrievedEventExplanation]
    debug_trace: dict[str, Any] = Field(default_factory=dict)


class BeliefEvent(BaseModel):
    id: str
    text: str
    timestamp: str
    event_type: str
    relationship: str = ""
    role: str = ""
    sentiment: Optional[float] = None
    importance_score: Optional[float] = None
    memory_strength: Optional[float] = None


class BeliefEvolutionResponse(BaseModel):
    concept: str
    timeline: list[BeliefEvent]
    links: list[dict[str, Any]]
    belief_edges: dict[str, int] = Field(default_factory=dict)


class EvaluationRun(BaseModel):
    run_id: str
    created_at: str
    dataset_size: int
    metrics: dict[str, float]
    queries: list[dict[str, Any]] = Field(default_factory=list)


class EvaluationHistoryResponse(BaseModel):
    runs: list[EvaluationRun]
