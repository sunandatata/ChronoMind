import logging

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from config import get_settings
from models.event import MemoryEvent
from models.query import QueryResponse
from services.embedding import has_openai_api_key

settings = get_settings()
logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are ChronoMind, a temporal memory reasoning system. You reconstruct the user's knowledge history, decision timelines, and belief evolution from their personal memory events.

When answering:
- Preserve temporal ordering explicitly; reference specific time periods
- Identify causal relationships: what led to what, what influenced what
- Note belief shifts or contradictions between events over time
- Be specific about when key events happened
- Synthesize a coherent narrative, not just a list of events
- For decision tracing queries: identify the sequence of events that culminated in the decision
- For opinion evolution queries: show how the position changed and what drove each shift

The memory events are already sorted chronologically. Reason across them to answer the query with depth and specificity."""


class LLMNotConfiguredError(RuntimeError):
    pass


def _has_anthropic_key() -> bool:
    key = settings.anthropic_api_key or ""
    return bool(key and not key.startswith("your_") and len(key) >= 20)


async def reason_with_claude(query: str, context: str, events: list[MemoryEvent], query_type: str) -> QueryResponse:
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"{context}\n\nAnswer this query based on the memory events above:\n{query}",
            }
        ],
    )

    return QueryResponse(
        answer=response.content[0].text,
        source_events=events,
        query_type=query_type,
        events_searched=len(events),
        confidence=min(0.45 + 0.05 * min(len(events), 10), 0.95),
    )


async def reason_with_openai(query: str, context: str, events: list[MemoryEvent], query_type: str) -> QueryResponse:
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{context}\n\nAnswer this query:\n{query}"},
        ],
        max_tokens=1500,
    )

    return QueryResponse(
        answer=response.choices[0].message.content,
        source_events=events,
        query_type=query_type,
        events_searched=len(events),
        confidence=min(0.45 + 0.05 * min(len(events), 10), 0.95),
    )


async def reason(query: str, context: str, events: list[MemoryEvent], query_type: str) -> QueryResponse:
    if _has_anthropic_key():
        try:
            return await reason_with_claude(query, context, events, query_type)
        except Exception as exc:
            logger.warning("Claude reasoning failed; trying OpenAI if configured: %s", exc)

    if has_openai_api_key():
        return await reason_with_openai(query, context, events, query_type)

    return _local_reason(query, events, query_type, context)


def _local_reason(query: str, events: list[MemoryEvent], query_type: str, context: str) -> QueryResponse:
    timeline = sorted(events, key=lambda event: event.timestamp)
    if not timeline:
        answer = "No relevant memory events were found."
    elif query_type == "DECISION_TRACE":
        lines = [
            f"{event.timestamp.strftime('%Y-%m-%d')}: {event.text}"
            for event in timeline[:8]
        ]
        answer = (
            "The decision appears to have been driven by a sequence of earlier observations and experiments.\n"
            + "\n".join(f"- {line}" for line in lines)
        )
    elif query_type == "TEMPORAL_EVOLUTION":
        lines = [
            f"{event.timestamp.strftime('%Y-%m-%d')}: {event.text}"
            for event in timeline[:8]
        ]
        answer = (
            "The memory shows a shift over time:\n"
            + "\n".join(f"- {line}" for line in lines)
        )
    else:
        lines = [
            f"{event.timestamp.strftime('%Y-%m-%d')}: {event.text}"
            for event in timeline[:6]
        ]
        answer = "Relevant memories:\n" + "\n".join(f"- {line}" for line in lines)

    if context:
        answer += "\n\nContext grounded from the ranked timeline above."

    confidence = 0.25
    if timeline:
        confidence = min(0.35 + 0.08 * min(len(timeline), 8), 0.95)

    return QueryResponse(
        answer=answer,
        source_events=events,
        query_type=query_type,
        events_searched=len(events),
        confidence=confidence,
        debug_trace={},
    )
