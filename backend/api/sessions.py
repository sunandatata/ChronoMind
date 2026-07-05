from fastapi import APIRouter

from services.session import get_session_service


router = APIRouter()


@router.delete("/sessions/{session_id}")
async def reset_session(session_id: str) -> dict:
    session_svc = get_session_service()
    session_svc.reset(session_id)
    return {"status": "reset", "session_id": session_id}

