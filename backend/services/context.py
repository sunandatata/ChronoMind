from collections import defaultdict
import re
from typing import Optional

from models.event import MemoryEvent
from services.embedding import cosine_similarity
from services.query_understanding import QueryProfile, QueryType, TemporalIntent


EVENT_TYPE_LABELS = {
    "observation": "Observed",
    "decision": "Decided",
    "belief": "Believed",
    "action": "Acted",
    "opinion": "Opinion",
    "learning": "Learned",
}

CAUSAL_PRIORITY = {
    "observation": 0,
    "learning": 1,
    "belief": 2,
    "opinion": 3,
    "action": 4,
    "decision": 5,
}


def detect_query_type(query: str) -> str:
    q = query.lower()
    if any(w in q for w in ("led", "cause", "why did", "what made", "reason", "decide", "chose", "switch")):
        return "decision_tracing"
    if any(w in q for w in ("changed", "evolved", "different", "shift", "over time", "anymore", "used to")):
        return "belief_evolution"
    if any(w in q for w in ("first", "when did i", "learn", "discover")):
        return "learning_timeline"
    if any(w in q for w in ("related", "connected", "influence", "what else")):
        return "influence_mapping"
    return "general_temporal"


def _sentiment_label(sentiment: Optional[float]) -> str:
    if sentiment is None:
        return ""
    if sentiment >= 0.4:
        return " [positive]"
    if sentiment <= -0.4:
        return " [negative]"
    return " [neutral]"


def _text_tokens(text: str) -> set[str]:
    return set(re.sub(r"[^\w\s]", " ", text.lower()).split())


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _compress_redundant(
    events: list[MemoryEvent],
    embeddings: list[list[float]] | None = None,
    text_threshold: float = 0.78,
    embedding_threshold: float = 0.88,
) -> tuple[list[MemoryEvent], list[list[float]]]:
    aligned_embeddings = embeddings or []
    use_embeddings = len(aligned_embeddings) == len(events)

    kept_events: list[MemoryEvent] = []
    kept_embeddings: list[list[float]] = []
    kept_tokens: list[set[str]] = []

    for idx, event in enumerate(events):
        event_tokens = _text_tokens(event.text)
        event_embedding = aligned_embeddings[idx] if use_embeddings else []
        duplicate_index: int | None = None

        for kept_idx, kept_event in enumerate(kept_events):
            same_month = event.timestamp.strftime("%Y-%m") == kept_event.timestamp.strftime("%Y-%m")
            if not same_month and event.event_type != kept_event.event_type:
                continue

            text_similarity = _jaccard(event_tokens, kept_tokens[kept_idx])
            embedding_similarity = (
                cosine_similarity(event_embedding, kept_embeddings[kept_idx])
                if use_embeddings else 0.0
            )
            if text_similarity >= text_threshold or embedding_similarity >= embedding_threshold:
                duplicate_index = kept_idx
                break

        if duplicate_index is None:
            kept_events.append(event)
            kept_embeddings.append(event_embedding)
            kept_tokens.append(event_tokens)
        elif event.confidence > kept_events[duplicate_index].confidence:
            kept_events[duplicate_index] = event
            kept_embeddings[duplicate_index] = event_embedding
            kept_tokens[duplicate_index] = event_tokens

    return kept_events, kept_embeddings


def _quality_filter(
    events: list[MemoryEvent],
    embeddings: list[list[float]] | None,
    ranking_details: list[dict] | None,
    query_profile: QueryProfile | None,
) -> tuple[list[MemoryEvent], list[list[float]]]:
    if not events:
        return events, embeddings or []

    detail_map = {item["id"]: item for item in (ranking_details or [])}
    kept_events: list[MemoryEvent] = []
    kept_embeddings: list[list[float]] = []
    month_counts: dict[str, int] = defaultdict(int)

    aligned_embeddings = embeddings or []
    use_embeddings = len(aligned_embeddings) == len(events)
    for idx, event in enumerate(events):
        detail = detail_map.get(event.id, {})
        features = detail.get("features", {})
        score = float(detail.get("score") or features.get("calibrated_score") or 0.0)
        support = float(features.get("source_support_score") or 0.0)
        causal = float(features.get("causal_edge_strength") or 0.0)
        cluster = detail.get("cluster") or "misc"
        month = event.timestamp.strftime("%Y-%m")

        if query_profile and query_profile.query_type in {QueryType.DECISION_TRACE, QueryType.CAUSAL_INFERENCE}:
            if score < 0.22 and causal < 0.22 and event.event_type.value not in {"decision", "action"}:
                continue
        if query_profile and query_profile.query_type == QueryType.TEMPORAL_EVOLUTION:
            if score < 0.20 and support < 0.18:
                continue

        if len(event.text.split()) < 6 and len(event.entities) >= 3:
            continue

        event_embedding = aligned_embeddings[idx] if use_embeddings else []
        redundant = False
        for kept_embedding in kept_embeddings:
            if event_embedding and kept_embedding and cosine_similarity(event_embedding, kept_embedding) > 0.9:
                redundant = True
                break
        if redundant:
            continue

        if month_counts[month] >= 3 and score < 0.35:
            continue

        month_counts[month] += 1
        kept_events.append(event)
        kept_embeddings.append(event_embedding)

    return kept_events, kept_embeddings


def _group_timeline(events: list[MemoryEvent]) -> list[tuple[str, list[MemoryEvent]]]:
    buckets: dict[str, list[MemoryEvent]] = defaultdict(list)
    for event in events:
        buckets[event.timestamp.strftime("%Y-%m")].append(event)

    grouped = []
    for bucket in sorted(buckets):
        grouped.append(
            (
                bucket,
                sorted(
                    buckets[bucket],
                    key=lambda event: (
                        event.timestamp,
                        CAUSAL_PRIORITY.get(event.event_type.value, 9),
                        event.text,
                    ),
                ),
            )
        )
    return grouped


def _event_line(event: MemoryEvent, index: int, shift_ids: set[str]) -> str:
    type_value = event.event_type.value
    type_label = EVENT_TYPE_LABELS.get(type_value, type_value.title())
    sentiment = _sentiment_label(event.sentiment) if type_value in {"opinion", "belief"} else ""
    marker = " [BELIEF SHIFT]" if event.id in shift_ids else ""
    date = event.timestamp.strftime("%Y-%m-%d")

    details = []
    if event.entities:
        details.append(f"entities={', '.join(event.entities[:5])}")
    if event.topics:
        details.append(f"topics={', '.join(event.topics[:6])}")
    detail_text = f" ({'; '.join(details)})" if details else ""

    return f"{index}. {date} - {type_label}{sentiment}{marker}: {event.text}{detail_text}"


def assemble_context(
    events: list[MemoryEvent],
    query: str,
    shift_ids: set[str] = None,
    embeddings: list[list[float]] = None,
    query_type: str = None,
    query_profile: QueryProfile | None = None,
    ranking_details: list[dict] | None = None,
) -> str:
    """
    Reconstruct chronological context for reasoning.

    This is intentionally timeline-shaped rather than top-k-shaped: events are
    sorted by time, grouped into monthly buckets, duplicate memories are removed,
    and likely causes are ordered before actions/decisions within each bucket.
    """
    if not events:
        return "No relevant memory events found."

    shift_ids = shift_ids or set()
    query_kind = (
        query_profile.query_type.value
        if query_profile
        else (query_type or detect_query_type(query))
    )
    sorted_events = sorted(
        events,
        key=lambda event: (
            event.timestamp,
            CAUSAL_PRIORITY.get(event.event_type.value, 9),
        ),
    )
    compressed_events, compressed_embeddings = _compress_redundant(sorted_events, embeddings or [])
    filtered_events, filtered_embeddings = _quality_filter(
        compressed_events,
        compressed_embeddings,
        ranking_details,
        query_profile,
    )
    grouped = _group_timeline(filtered_events)

    first = filtered_events[0].timestamp.strftime("%Y-%m-%d")
    last = filtered_events[-1].timestamp.strftime("%Y-%m-%d")
    parts = [
        "CHRONOMIND MEMORY CONTEXT",
        f"Query: {query}",
        f"Query type: {query_kind.replace('_', ' ').title()}",
        f"Timeline span: {first} to {last}",
        f"Compressed events: {len(filtered_events)}",
        "=" * 60,
    ]

    event_index = 1
    for bucket, bucket_events in grouped:
        month_label = bucket_events[0].timestamp.strftime("%B %Y")
        parts.append(f"{month_label}")
        for event in bucket_events:
            parts.append(_event_line(event, event_index, shift_ids))
            event_index += 1

    parts.append("=" * 60)

    instructions = {
        "DECISION_TRACE": (
            "INSTRUCTION: Trace the causal chain from the earliest relevant observations, "
            "beliefs, and experiments to the later decision. Preserve dates and explain "
            "what led to what."
        ),
        "TEMPORAL_EVOLUTION": (
            "INSTRUCTION: Explain how the position changed over the full timeline. "
            "Call out BELIEF SHIFT markers and the events that drove them."
        ),
        "FACTUAL_RECALL": (
            "INSTRUCTION: Identify the first encounter, later learning milestones, "
            "and how understanding deepened over time."
        ),
        "CAUSAL_INFERENCE": (
            "INSTRUCTION: Explain the connected memories and influence paths between them."
        ),
        "COMPARISON_QUERY": (
            "INSTRUCTION: Compare the relevant memories across the requested dimensions, "
            "preserving time and difference markers."
        ),
        "general_temporal": (
            "INSTRUCTION: Reconstruct a coherent narrative in chronological order, "
            "highlighting key developments and causal dependencies."
        ),
    }
    parts.append(instructions.get(query_kind, instructions["general_temporal"]))

    return "\n\n".join(parts)
