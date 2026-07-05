from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from config import get_settings


settings = get_settings()
SESSION_PATH = Path(__file__).resolve().parents[1] / "data" / "search_sessions.json"


@dataclass
class RetrievalSession:
    session_id: str
    created_at: str
    last_active_at: str
    last_query: str = ""
    last_event_ids: list[str] = None
    explored_event_ids: list[str] = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["last_event_ids"] = self.last_event_ids or []
        data["explored_event_ids"] = self.explored_event_ids or []
        return data


class SessionService:
    def __init__(self):
        self._sessions: dict[str, RetrievalSession] = {}
        self._load()

    def _load(self) -> None:
        if not SESSION_PATH.exists():
            return
        try:
            raw = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
        except Exception:
            return
        for key, item in raw.items():
            self._sessions[key] = RetrievalSession(
                session_id=item.get("session_id", key),
                created_at=item.get("created_at") or datetime.utcnow().isoformat(),
                last_active_at=item.get("last_active_at") or datetime.utcnow().isoformat(),
                last_query=item.get("last_query", ""),
                last_event_ids=item.get("last_event_ids", []) or [],
                explored_event_ids=item.get("explored_event_ids", []) or [],
            )

    def _persist(self) -> None:
        SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {key: session.to_dict() for key, session in self._sessions.items()}
        SESSION_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get(self, session_id: str | None) -> RetrievalSession:
        now = datetime.utcnow()
        if not session_id:
            session_id = str(uuid4())
        session = self._sessions.get(session_id)
        if session is None:
            session = RetrievalSession(
                session_id=session_id,
                created_at=now.isoformat(),
                last_active_at=now.isoformat(),
                last_event_ids=[],
                explored_event_ids=[],
            )
            self._sessions[session_id] = session
            self._persist()
            return session

        try:
            last_active = datetime.fromisoformat(session.last_active_at)
        except Exception:
            last_active = now
        if now - last_active > timedelta(hours=settings.session_expiry_hours):
            session = RetrievalSession(
                session_id=session_id,
                created_at=now.isoformat(),
                last_active_at=now.isoformat(),
                last_event_ids=[],
                explored_event_ids=[],
            )
            self._sessions[session_id] = session
            self._persist()
        return session

    def update(self, session_id: str, *, query: str, event_ids: list[str], explored_event_ids: list[str] | None = None) -> RetrievalSession:
        session = self.get(session_id)
        session.last_query = query
        session.last_event_ids = list(dict.fromkeys(event_ids))[:20]
        if explored_event_ids:
            combined = list(dict.fromkeys((session.explored_event_ids or []) + explored_event_ids))
            session.explored_event_ids = combined[:100]
        session.last_active_at = datetime.utcnow().isoformat()
        self._sessions[session.session_id] = session
        self._persist()
        return session

    def reset(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._persist()


_session_service: SessionService | None = None


def get_session_service() -> SessionService:
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service
