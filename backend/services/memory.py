from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from config import get_settings
from services.graph import get_graph_service
from services.vector import get_vector_service


settings = get_settings()


def _clamp(value: float, floor: float | None = None, ceiling: float | None = None) -> float:
    if floor is not None:
        value = max(value, floor)
    if ceiling is not None:
        value = min(value, ceiling)
    return value


@dataclass(slots=True)
class MemoryInteraction:
    event_id: str
    current_strength: float = 0.5
    event_timestamp: str | None = None
    retrieved: bool = False
    selected: bool = False
    referenced: bool = False
    used_in_answer: bool = False
    ignored: bool = False


class MemorySignalService:
    async def update_event_strength(self, event_id: str, current_strength: float, *, boost: float = 0.0, decay: float = 0.0, importance: float | None = None) -> float:
        updated = current_strength
        updated += boost
        updated -= decay
        if importance is not None:
            updated += max(0.0, importance - 0.5) * 0.03
        updated = _clamp(updated, settings.memory_decay_floor, settings.memory_decay_ceiling)

        graph_svc = get_graph_service()
        vector_svc = get_vector_service()
        payload = {
            "memory_strength": updated,
            "retrieval_count": int(max(0, round((updated - settings.memory_decay_floor) * 10))),
            "last_accessed_at": datetime.now(timezone.utc).isoformat(),
            "last_signal_update": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await graph_svc.update_event_properties(event_id, payload)
        except Exception:
            pass
        try:
            await vector_svc.update_event_payload(event_id, payload)
        except Exception:
            pass
        return updated

    async def apply_interactions(self, interactions: Iterable[MemoryInteraction], answer_text: str = "") -> dict[str, float]:
        answer_lower = answer_text.lower()
        updated: dict[str, float] = {}
        for interaction in interactions:
            base = interaction.current_strength
            boost = 0.0
            decay = 0.0
            if interaction.retrieved:
                boost += settings.memory_retrieval_boost
            if interaction.selected:
                boost += settings.memory_selection_boost
            if interaction.used_in_answer:
                boost += settings.memory_answer_boost
            if interaction.referenced:
                boost += settings.memory_reference_boost
            if interaction.ignored:
                decay += settings.memory_ignored_decay
            if interaction.event_timestamp:
                try:
                    event_time = datetime.fromisoformat(interaction.event_timestamp.replace("Z", "+00:00"))
                    if event_time.tzinfo is None:
                        event_time = event_time.replace(tzinfo=timezone.utc)
                    age_days = max((datetime.now(timezone.utc) - event_time).days, 0)
                    decay += min(age_days / 365.0, 3.0) * settings.memory_age_decay
                except Exception:
                    pass
            if interaction.event_id and interaction.event_id in answer_lower:
                boost += settings.memory_reference_boost
            updated_strength = await self.update_event_strength(interaction.event_id, base, boost=boost, decay=decay)
            updated[interaction.event_id] = updated_strength
        return updated


_memory_signal_service: MemorySignalService | None = None


def get_memory_signal_service() -> MemorySignalService:
    global _memory_signal_service
    if _memory_signal_service is None:
        _memory_signal_service = MemorySignalService()
    return _memory_signal_service
