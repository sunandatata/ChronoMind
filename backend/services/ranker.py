from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from config import get_settings


settings = get_settings()

FEATURE_ORDER = [
    "vector_similarity_score",
    "lexical_score",
    "graph_distance_score",
    "graph_centrality_score",
    "temporal_distance_score",
    "recency_score",
    "event_type_weight",
    "causal_edge_strength",
    "entity_overlap_score",
    "source_support_score",
    "contradiction_score",
    "importance_score",
    "memory_strength",
    "confidence_score",
    "retrieval_source_score",
    "graph_depth_score",
]


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(value, upper))


def _default_model() -> dict[str, Any]:
    weights = {
        "vector_similarity_score": 0.18,
        "lexical_score": 0.14,
        "graph_distance_score": 0.10,
        "graph_centrality_score": 0.08,
        "temporal_distance_score": 0.12,
        "recency_score": 0.08,
        "event_type_weight": 0.08,
        "causal_edge_strength": 0.10,
        "entity_overlap_score": 0.10,
        "source_support_score": 0.05,
        "contradiction_score": 0.04,
        "importance_score": 0.10,
        "memory_strength": 0.10,
        "confidence_score": 0.08,
        "retrieval_source_score": 0.04,
        "graph_depth_score": 0.06,
    }
    return {
        "feature_order": FEATURE_ORDER,
        "weights": weights,
        "bias": -0.15,
        "model_type": "feature_calibrated",
        "trained_at": None,
        "training_samples": 0,
    }


def model_path() -> Path:
    base = Path(__file__).resolve().parents[1] / "data"
    configured = Path(settings.ranker_model_path)
    return configured if configured.is_absolute() else base / configured.name


def load_model() -> dict[str, Any] | None:
    path = model_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_model(model: dict[str, Any]) -> Path:
    path = model_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model, indent=2), encoding="utf-8")
    return path


def vectorize(features: dict[str, float]) -> np.ndarray:
    values = [float(features.get(name, 0.0)) for name in FEATURE_ORDER]
    return np.array(values, dtype=float)


def predict_score(features: dict[str, float], model: dict[str, Any] | None = None) -> float:
    model = model or load_model() or _default_model()
    weights = model.get("weights") or {}
    bias = float(model.get("bias") or 0.0)
    score = bias
    for name in FEATURE_ORDER:
        score += float(weights.get(name, 0.0)) * float(features.get(name, 0.0))
    return _clamp(_sigmoid(score))


@dataclass
class RankingExample:
    features: dict[str, float]
    relevance: float
    query_id: str = ""
    event_id: str = ""


def train_linear_ranker(
    examples: list[RankingExample],
    epochs: int = 200,
    learning_rate: float = 0.06,
    l2: float = 0.02,
) -> dict[str, Any]:
    if not examples:
        return _default_model()

    x = np.stack([vectorize(example.features) for example in examples], axis=0)
    y = np.array([float(example.relevance) for example in examples], dtype=float)
    y = np.clip(y, 0.0, 3.0) / 3.0

    weights = np.zeros(x.shape[1], dtype=float)
    bias = 0.0
    for _ in range(epochs):
        logits = x @ weights + bias
        preds = 1.0 / (1.0 + np.exp(-np.clip(logits, -20, 20)))
        errors = preds - y
        grad_w = (x.T @ errors) / len(x) + l2 * weights
        grad_b = float(errors.mean())
        weights -= learning_rate * grad_w
        bias -= learning_rate * grad_b

    model = {
        "feature_order": FEATURE_ORDER,
        "weights": {name: float(weights[idx]) for idx, name in enumerate(FEATURE_ORDER)},
        "bias": float(bias),
        "model_type": "logistic_ranker",
        "trained_at": datetime.utcnow().isoformat(),
        "training_samples": len(examples),
    }
    return model


def calibrate_feature_score(features: dict[str, float]) -> float:
    model = load_model()
    if model is None:
        model = _default_model()
    return predict_score(features, model)
