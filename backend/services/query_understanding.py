from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import re


class QueryType(str, Enum):
    FACTUAL_RECALL = "FACTUAL_RECALL"
    DECISION_TRACE = "DECISION_TRACE"
    TEMPORAL_EVOLUTION = "TEMPORAL_EVOLUTION"
    CAUSAL_INFERENCE = "CAUSAL_INFERENCE"
    COMPARISON_QUERY = "COMPARISON_QUERY"


class TemporalIntent(str, Enum):
    PAST_STATE = "PAST_STATE"
    EVOLUTION_OVER_TIME = "EVOLUTION_OVER_TIME"
    CURRENT_STATE = "CURRENT_STATE"


@dataclass(slots=True)
class QueryProfile:
    query: str
    query_type: QueryType
    temporal_intent: TemporalIntent
    causal_intent: bool
    entities: list[str]
    topics: list[str]
    time_window: tuple[datetime, datetime] | None
    graph_hops: int
    candidate_limits: dict[str, int]

    def to_trace(self) -> dict:
        return {
            "query": self.query,
            "query_type": self.query_type.value,
            "temporal_intent": self.temporal_intent.value,
            "causal_intent": self.causal_intent,
            "entities": self.entities,
            "topics": self.topics,
            "time_window": [self.time_window[0].isoformat(), self.time_window[1].isoformat()]
            if self.time_window else None,
            "graph_hops": self.graph_hops,
            "candidate_limits": self.candidate_limits,
        }


_DECISION_SIGNALS = {"led", "cause", "why did", "what made", "reason", "decide", "chose", "switch"}
_EVOLUTION_SIGNALS = {"changed", "evolved", "different", "shift", "over time", "anymore", "used to", "evolve"}
_COMPARE_SIGNALS = {"compare", "versus", "vs", "better than", "worse than", "difference between", "difference"}
_FACTUAL_SIGNALS = {"when", "what", "who", "where", "which", "did i", "have i", "was i"}
_CURRENT_SIGNALS = {"current", "now", "today", "these days", "right now", "currently", "present"}


def _extract_entities(query: str) -> list[str]:
    stopwords = {
        "What", "When", "How", "Why", "Who", "Where", "Did", "The", "My", "I",
        "Is", "Was", "Were", "Are", "Do", "Does", "Have", "Has", "Had", "Will",
        "Can", "Could", "Should", "Would", "Which", "That", "This", "These", "Those",
    }
    words = re.findall(r"\b[A-Z][a-zA-Z0-9.+#-]+\b", query)
    entities = [word for word in words if word not in stopwords]

    lower = query.lower()
    known_entities = {
        "react": "React",
        "vue": "Vue",
        "postgresql": "PostgreSQL",
        "postgres": "PostgreSQL",
        "mongodb": "MongoDB",
        "typescript": "TypeScript",
        "github": "GitHub",
        "fast.ai": "fast.ai",
    }
    for term, label in known_entities.items():
        if term in lower and label not in entities:
            entities.append(label)
    return entities


def _extract_topics(query: str) -> list[str]:
    stop = {
        "what", "when", "how", "why", "who", "where", "did", "the", "my", "i",
        "a", "an", "led", "me", "to", "about", "changed", "change", "over",
        "time", "first", "learn", "think", "feel", "believe", "have", "has",
        "had", "is", "was", "were", "be", "been", "this", "that", "these",
        "those", "do", "does", "make", "made", "get", "got", "just", "also",
        "more", "some", "any", "did", "was", "from", "into", "than", "then",
    }
    q = query.lower()
    words = re.sub(r"[^\w\s]", "", q).split()
    topics = [word for word in words if word not in stop and len(word) > 2]
    if "tech stack" in q or "stack" in q:
        topics.extend(["tech", "stack", "frontend", "database"])

    seen: set[str] = set()
    ordered: list[str] = []
    for topic in topics:
        if topic not in seen:
            seen.add(topic)
            ordered.append(topic)
    return ordered


def _temporal_window(query: str) -> tuple[datetime, datetime] | None:
    q = query.lower()
    now = datetime.utcnow()
    year_match = re.search(r"\b(20\d{2})\b", query)
    if year_match:
        year = int(year_match.group(1))
        return datetime(year, 1, 1), datetime(year, 12, 31, 23, 59, 59)
    if any(signal in q for signal in ("recently", "lately", "these days", "now", "current", "today")):
        return now - timedelta(days=90), now
    if "last year" in q:
        return datetime(now.year - 1, 1, 1), datetime(now.year - 1, 12, 31, 23, 59, 59)
    if "this year" in q:
        return datetime(now.year, 1, 1), now
    if "last month" in q:
        return now - timedelta(days=30), now
    return None


def understand_query(query: str, time_start: str | None = None, time_end: str | None = None) -> QueryProfile:
    q = query.lower()
    entities = _extract_entities(query)
    topics = _extract_topics(query)
    temporal_window = _temporal_window(query)

    if time_start or time_end:
        start = datetime.fromisoformat(time_start) if time_start else datetime.min
        end = datetime.fromisoformat(time_end) if time_end else datetime.max
        temporal_window = (start, end)

    if any(signal in q for signal in _COMPARE_SIGNALS):
        query_type = QueryType.COMPARISON_QUERY
        temporal_intent = TemporalIntent.EVOLUTION_OVER_TIME
        graph_hops = 2
    elif any(signal in q for signal in _DECISION_SIGNALS):
        query_type = QueryType.DECISION_TRACE
        temporal_intent = TemporalIntent.EVOLUTION_OVER_TIME
        graph_hops = 3
    elif any(signal in q for signal in _EVOLUTION_SIGNALS):
        query_type = QueryType.TEMPORAL_EVOLUTION
        temporal_intent = TemporalIntent.EVOLUTION_OVER_TIME
        graph_hops = 3
    elif any(signal in q for signal in ("cause", "caused", "influence", "influenced", "why")):
        query_type = QueryType.CAUSAL_INFERENCE
        temporal_intent = TemporalIntent.PAST_STATE
        graph_hops = 3
    else:
        query_type = QueryType.FACTUAL_RECALL
        temporal_intent = TemporalIntent.CURRENT_STATE if any(signal in q for signal in _CURRENT_SIGNALS) else TemporalIntent.PAST_STATE
        graph_hops = 2

    causal_intent = query_type in {QueryType.DECISION_TRACE, QueryType.CAUSAL_INFERENCE}

    candidate_limits = {
        "vector": 30 if query_type != QueryType.FACTUAL_RECALL else 20,
        "graph": 30 if causal_intent or query_type == QueryType.TEMPORAL_EVOLUTION else 20,
        "bm25": 30,
        "rerank": 12 if query_type in {QueryType.DECISION_TRACE, QueryType.CAUSAL_INFERENCE} else 10,
    }

    return QueryProfile(
        query=query,
        query_type=query_type,
        temporal_intent=temporal_intent,
        causal_intent=causal_intent,
        entities=entities,
        topics=topics,
        time_window=temporal_window,
        graph_hops=graph_hops,
        candidate_limits=candidate_limits,
    )
