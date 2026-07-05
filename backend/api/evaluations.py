from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from models.query import EvaluationHistoryResponse, EvaluationRun

router = APIRouter()

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "evaluation_history.json"


@router.get("/evaluations/history", response_model=EvaluationHistoryResponse)
async def evaluation_history() -> EvaluationHistoryResponse:
    if not DATA_PATH.exists():
        return EvaluationHistoryResponse(runs=[])

    try:
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return EvaluationHistoryResponse(runs=[])

    runs = []
    for item in payload if isinstance(payload, list) else payload.get("runs", []):
        try:
            runs.append(EvaluationRun(**item))
        except Exception:
            continue
    runs.sort(key=lambda run: run.created_at, reverse=True)
    return EvaluationHistoryResponse(runs=runs)
