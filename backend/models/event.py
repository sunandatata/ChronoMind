from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4


class EventType(str, Enum):
    OBSERVATION = "observation"
    DECISION = "decision"
    BELIEF = "belief"
    ACTION = "action"
    OPINION = "opinion"
    LEARNING = "learning"


class SourceType(str, Enum):
    NOTE = "note"
    EMAIL = "email"
    CHAT = "chat"
    DOCUMENT = "document"
    BOOKMARK = "bookmark"
    MANUAL = "manual"


class MemoryEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    timestamp: datetime
    source: SourceType = SourceType.MANUAL
    event_type: EventType = EventType.OBSERVATION
    entities: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    sentiment: Optional[float] = None
    confidence: float = 1.0
    importance_score: float = 0.5
    memory_strength: float = 0.5
    retrieval_count: int = 0
    last_accessed_at: Optional[datetime] = None
    decay_coefficient: float = 0.12
    embedding_id: Optional[str] = None
    version: int = 1
    original_event_id: Optional[str] = None
    source_id: Optional[str] = None


class IngestRequest(BaseModel):
    text: str
    timestamp: Optional[datetime] = None
    source: SourceType = SourceType.MANUAL
    source_id: Optional[str] = None


class IngestResponse(BaseModel):
    events_extracted: int
    event_ids: list[str]
    message: str


class ScoredEvent(BaseModel):
    event: MemoryEvent
    score: float
    embedding: Optional[list[float]] = None
