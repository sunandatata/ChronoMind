import json
import logging
import re
from datetime import datetime

from openai import AsyncOpenAI

from config import get_settings
from models.event import EventType, IngestRequest, IngestResponse, MemoryEvent
from services.embedding import embed_text, has_openai_api_key
from services.graph import get_graph_service
from services.vector import get_vector_service
from utils.text import get_bm25_index, tokenize

logger = logging.getLogger(__name__)
settings = get_settings()

EXTRACTION_PROMPT = """Extract all distinct memory events from this text. Each event is an atomic unit representing one observation, decision, belief, action, opinion, or learning moment.

Return a JSON array of events, each with:
- "text": the event description (1-3 sentences, self-contained, written in first person)
- "event_type": one of ["observation", "decision", "belief", "action", "opinion", "learning"]
- "entities": list of named entities (people, orgs, technologies, projects, places) - max 5
- "topics": list of topic keywords (lowercase) - max 5
- "sentiment": float from -1.0 (very negative) to 1.0 (very positive)

Rules:
- Each event must be self-contained and independently meaningful
- Do not merge distinct events; do not split single events
- Focus on personal experiences, decisions, and evolving beliefs

Text:
{text}

Return ONLY valid JSON array. No markdown, no explanation."""

TECH_TERMS = {
    "react": {"react", "frontend", "javascript", "tech", "stack"},
    "vue": {"vue", "frontend", "javascript", "tech", "stack"},
    "vue 3": {"vue", "frontend", "javascript", "tech", "stack"},
    "composition api": {"vue", "frontend", "javascript", "tech", "stack"},
    "typescript": {"typescript", "frontend", "tech", "stack"},
    "postgresql": {"postgresql", "database", "tech", "stack"},
    "postgres": {"postgresql", "database", "tech", "stack"},
    "mongodb": {"mongodb", "database", "tech", "stack"},
    "numpy": {"numpy", "machine learning", "ml"},
    "nlp": {"nlp", "machine learning", "ml"},
    "machine learning": {"machine learning", "ml"},
    "ml": {"machine learning", "ml"},
    "fast.ai": {"fast.ai", "machine learning", "ml"},
    "github": {"github", "open source"},
}

STOP_TOPICS = {
    "about", "after", "also", "and", "are", "but", "for", "from", "had",
    "has", "have", "into", "just", "now", "over", "the", "then", "this",
    "that", "was", "were", "will", "with", "years", "feel", "feels",
    "felt", "first", "every", "both", "given", "could", "should",
}

POSITIVE_WORDS = {
    "confident", "cleaner", "natural", "intuitive", "right", "excited",
    "important", "completed", "landed", "better", "prefer", "good",
}

NEGATIVE_WORDS = {
    "frustrated", "intimidating", "uncertain", "bad", "tough", "out of hand",
    "unnatural", "smaller", "profiling",
}

DECISION_WORDS = {"decided", "decision", "chose", "switched", "moved", "pivot", "picked", "selected"}
REFINEMENT_WORDS = {"refined", "better", "improved", "adjusted", "optimized", "clarified", "deeper", "deepen"}
REINFORCEMENT_WORDS = {"confident", "confirmed", "reinforced", "strengthened", "solidified", "validated"}
CONTRADICTION_WORDS = {"however", "but", "instead", "though", "contrary", "yet", "frustrated", "uncertain"}


async def _extract_with_llm(text: str, timestamp: datetime, source) -> list[MemoryEvent]:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": EXTRACTION_PROMPT.format(text=text)}],
        max_tokens=2000,
        temperature=0.3,
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    extracted = json.loads(raw)

    events = []
    for item in extracted:
        try:
            event_type = EventType(item.get("event_type", "observation").lower())
        except ValueError:
            event_type = EventType.OBSERVATION

        text_value = str(item.get("text", "")).strip()
        if not text_value:
            continue

        events.append(
            MemoryEvent(
                text=text_value,
                timestamp=timestamp,
                source=source,
                event_type=event_type,
                entities=_dedupe_strings(item.get("entities", []), limit=5),
                topics=_dedupe_strings(
                    [str(t).lower() for t in item.get("topics", [])],
                    limit=8,
                ),
                sentiment=float(item.get("sentiment", 0.0)),
                confidence=0.9,
            )
        )
    return events


def _dedupe_strings(values: list, limit: int = 8) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _split_atomic_text(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    normalized = re.sub(r"^\s*[A-Z][a-z]+\s+\d{4}:\s*", "", normalized)
    pieces = re.split(r"(?<=[.!?])\s+", normalized)

    events: list[str] = []
    carry = ""
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        candidate = f"{carry} {piece}".strip() if carry else piece
        if len(candidate.split()) < 5:
            carry = candidate
            continue
        events.append(candidate)
        carry = ""

    if carry:
        if events:
            events[-1] = f"{events[-1]} {carry}".strip()
        else:
            events.append(carry)

    return events or [normalized]


def _classify_event_type(text: str) -> EventType:
    q = text.lower()
    if any(term in q for term in ("decided", "decision", "chose", "switched", "right call", "pivot decision")):
        return EventType.DECISION
    if any(term in q for term in ("learned", "learning", "course", "studying", "reading", "clicked", "understanding")):
        return EventType.LEARNING
    if any(term in q for term in ("believe", "belief", "opinion", "prefer", "think", "considering")):
        return EventType.BELIEF
    if any(term in q for term in ("started", "built", "completed", "enrolled", "contributing", "evaluating", "dedicate")):
        return EventType.ACTION
    if any(term in q for term in ("frustrated", "feel", "feeling", "looks", "seems")):
        return EventType.OPINION
    return EventType.OBSERVATION


def _extract_entities(text: str) -> list[str]:
    entities: list[str] = []
    lower = text.lower()

    canonical = {
        "andrew ng": "Andrew Ng",
        "coursera": "Coursera",
        "postgresql": "PostgreSQL",
        "postgres": "PostgreSQL",
        "mongodb": "MongoDB",
        "react": "React",
        "vue 3": "Vue 3",
        "vue": "Vue",
        "composition api": "Composition API",
        "typescript": "TypeScript",
        "sarah": "Sarah",
        "fast.ai": "fast.ai",
        "github": "GitHub",
        "numpy": "NumPy",
        "nlp": "NLP",
    }
    for term, label in canonical.items():
        if term in lower:
            entities.append(label)

    entities.extend(re.findall(r"\b[A-Z][a-zA-Z0-9.+#-]*(?:\s+[A-Z][a-zA-Z0-9.+#-]*){0,2}\b", text))
    return _dedupe_strings(entities, limit=6)


def _extract_topics(text: str) -> list[str]:
    lower = text.lower()
    topics: list[str] = []

    for term, mapped_topics in TECH_TERMS.items():
        if term in lower:
            topics.extend(sorted(mapped_topics))

    for token in tokenize(lower):
        if len(token) <= 3 or token in STOP_TOPICS:
            continue
        topics.append(token)

    return _dedupe_strings(topics, limit=10)


def _sentiment(text: str) -> float:
    lower = text.lower()
    score = 0
    for word in POSITIVE_WORDS:
        if word in lower:
            score += 1
    for word in NEGATIVE_WORDS:
        if word in lower:
            score -= 1
    if score == 0:
        return 0.0
    return max(min(score / 3.0, 1.0), -1.0)


def _importance_score(event: MemoryEvent) -> float:
    text = event.text.lower()
    score = 0.2
    if event.event_type in {EventType.DECISION, EventType.ACTION}:
        score += 0.28
    if event.event_type in {EventType.BELIEF, EventType.OPINION}:
        score += 0.14
    if any(word in text for word in DECISION_WORDS):
        score += 0.22
    if any(word in text for word in REFINEMENT_WORDS):
        score += 0.12
    if any(word in text for word in REINFORCEMENT_WORDS):
        score += 0.12
    if len(event.topics) >= 2:
        score += 0.08
    if len(event.entities) >= 2:
        score += 0.08
    if abs(event.sentiment or 0.0) >= 0.5:
        score += 0.05
    return max(0.0, min(score, 1.0))


def _memory_strength(event: MemoryEvent) -> float:
    text = event.text.lower()
    score = 0.28 + 0.5 * _importance_score(event)
    if event.event_type in {EventType.DECISION, EventType.BELIEF}:
        score += 0.1
    if any(word in text for word in REINFORCEMENT_WORDS):
        score += 0.12
    if any(word in text for word in CONTRADICTION_WORDS):
        score += 0.05
    score += min(len(event.topics), 4) * 0.03
    score += min(len(event.entities), 4) * 0.02
    return max(0.0, min(score, 1.0))


def _extract_locally(text: str, timestamp: datetime, source) -> list[MemoryEvent]:
    events: list[MemoryEvent] = []
    for sentence in _split_atomic_text(text):
        cleaned = sentence.strip()
        if not cleaned:
            continue
        events.append(
            MemoryEvent(
                text=cleaned,
                timestamp=timestamp,
                source=source,
                event_type=_classify_event_type(cleaned),
                entities=_extract_entities(cleaned),
                topics=_extract_topics(cleaned),
                sentiment=_sentiment(cleaned),
                confidence=0.72,
            )
        )
    return events


def _payload(event: MemoryEvent) -> dict:
    return {
        "id": event.id,
        "text": event.text,
        "timestamp": event.timestamp.isoformat(),
        "source": event.source.value,
        "event_type": event.event_type.value,
        "entities": event.entities,
        "topics": event.topics,
        "sentiment": event.sentiment,
        "confidence": event.confidence,
        "importance_score": event.importance_score,
        "memory_strength": event.memory_strength,
        "is_demo": False,
    }


def _should_link_neighbor(event: MemoryEvent, neighbor: dict) -> bool:
    payload = neighbor.get("payload") or {}
    score = float(neighbor.get("score") or 0.0)
    shared_topics = set(event.topics or []) & set(payload.get("topics") or [])
    shared_entities = {entity.lower() for entity in event.entities or []} & {
        entity.lower() for entity in payload.get("entities") or []
    }
    return bool(shared_topics or shared_entities or score >= 0.08)


def _belief_edge_hint(event: MemoryEvent, neighbor: dict) -> str | None:
    payload = neighbor.get("payload") or {}
    neighbor_type = str(payload.get("event_type") or "").lower()
    if event.event_type.value not in {"belief", "opinion"} and neighbor_type not in {"belief", "opinion"}:
        return None

    shared_topics = set(event.topics or []) & set(payload.get("topics") or [])
    shared_entities = {entity.lower() for entity in event.entities or []} & {
        entity.lower() for entity in payload.get("entities") or []
    }
    if not shared_topics and not shared_entities:
        return None

    sentiment_delta = abs((event.sentiment or 0.0) - float(payload.get("sentiment") or 0.0))
    if sentiment_delta >= 0.55:
        return "CONTRADICTS"
    if sentiment_delta >= 0.2:
        return "REFINES"
    return "REINFORCES"


async def ingest(request: IngestRequest) -> IngestResponse:
    """
    Full ingestion pipeline:
      1. Atomic event extraction
      2. Embedding generation
      3. Qdrant upsert
      4. Neo4j node creation
      5. BM25 index update
      6. Semantic edge creation using typed graph relationships
    """
    timestamp = request.timestamp or datetime.utcnow()

    if has_openai_api_key():
        try:
            events = await _extract_with_llm(request.text, timestamp, request.source)
        except Exception as exc:
            logger.warning("LLM extraction failed; using local extraction: %s", exc)
            events = _extract_locally(request.text, timestamp, request.source)
    else:
        events = _extract_locally(request.text, timestamp, request.source)

    if not events:
        return IngestResponse(events_extracted=0, event_ids=[], message="No events extracted")

    graph_svc = get_graph_service()
    vector_svc = get_vector_service()
    bm25 = get_bm25_index()

    event_ids: list[str] = []
    all_events_with_embeddings: list[tuple[MemoryEvent, list[float]]] = []

    for event in events:
        if not event.text.strip():
            continue

        event.importance_score = _importance_score(event)
        event.memory_strength = _memory_strength(event)
        embedding = await embed_text(event.text)
        payload = _payload(event)

        try:
            await vector_svc.upsert_event(event.id, embedding, payload)
            await graph_svc.create_event_node(event, is_demo=False)
        except Exception as exc:
            logger.error("Failed to persist event %s: %s", event.id, exc)
            continue

        bm25.add_document(event.id, event.text, payload)
        all_events_with_embeddings.append((event, embedding))
        event_ids.append(event.id)

    for event, embedding in all_events_with_embeddings:
        try:
            neighbors = await vector_svc.search(embedding, limit=8)
            candidate_payloads = []
            for neighbor in neighbors:
                if neighbor.get("id") == event.id or not neighbor.get("payload"):
                    continue
                if not _should_link_neighbor(event, neighbor):
                    continue
                payload = neighbor["payload"]
                belief_edge = _belief_edge_hint(event, neighbor)
                if belief_edge:
                    payload = {**payload, "_belief_edge_type": belief_edge}
                candidate_payloads.append(payload)
            await graph_svc.create_semantic_edges(event, candidate_payloads)
        except Exception as exc:
            logger.error("Semantic edge creation failed for %s: %s", event.id, exc)

    return IngestResponse(
        events_extracted=len(event_ids),
        event_ids=event_ids,
        message=f"Ingested {len(event_ids)} events",
    )
