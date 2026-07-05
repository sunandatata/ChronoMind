from __future__ import annotations

import math
import os
import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Callable

import httpx


API_URL = os.environ.get("CHRONOMIND_API_URL", "http://localhost:8000")
QUERY_ENDPOINT = f"{API_URL}/api/query"
STATS_ENDPOINT = f"{API_URL}/api/stats"
HISTORY_PATH = Path(__file__).resolve().parents[1] / "backend" / "data" / "evaluation_history.json"


@dataclass
class EvalQuery:
    name: str
    query: str
    gold_fn: Callable[[str], int]
    gold_order: list[str]


def _contains(*needles: str) -> Callable[[str], int]:
    lower_needles = [needle.lower() for needle in needles]

    def scorer(text: str) -> int:
        text_lower = text.lower()
        return 1 if any(needle in text_lower for needle in lower_needles) else 0

    return scorer


def _graded_contains(positive: list[str], support: list[str] | None = None) -> Callable[[str], int]:
    positive_lower = [item.lower() for item in positive]
    support_lower = [item.lower() for item in (support or [])]

    def scorer(text: str) -> int:
        text_lower = text.lower()
        if any(item in text_lower for item in positive_lower):
            return 2
        if any(item in text_lower for item in support_lower):
            return 1
        return 0

    return scorer


QUERIES = [
    EvalQuery(
        name="tech_stack_change",
        query="What led me to change my tech stack?",
        gold_fn=_graded_contains(
            positive=["frustrated with react", "officially switched from react to vue", "started evaluating vue 3"],
            support=["composition api", "typescript integration", "right call", "reactivity system"],
        ),
        gold_order=[
            "frustrated with react",
            "started evaluating vue 3",
            "officially switched from react to vue",
        ],
    ),
    EvalQuery(
        name="react_to_vue",
        query="What led me to switch from React to Vue?",
        gold_fn=_graded_contains(
            positive=["frustrated with react", "officially switched from react to vue", "decision influenced by the june frustrations"],
            support=["composition api", "typescript integration", "colleague recommended"],
        ),
        gold_order=[
            "frustrated with react",
            "started evaluating vue 3",
            "officially switched from react to vue",
        ],
    ),
    EvalQuery(
        name="ml_career",
        query="What led to my ML engineering career?",
        gold_fn=_graded_contains(
            positive=["started learning machine learning", "completed the ml course", "ml will be important", "career conversation with my mentor sarah", "landed my first ml engineering role"],
            support=["postgresql", "fast.ai", "contributing to an open source ml project"],
        ),
        gold_order=[
            "started learning machine learning",
            "completed the ml course",
            "career conversation with my mentor sarah",
            "landed my first ml engineering role",
        ],
    ),
    EvalQuery(
        name="first_ml_learning",
        query="When did I first learn about machine learning?",
        gold_fn=_graded_contains(
            positive=["started learning machine learning from andrew ng"],
            support=["completed the ml course", "built my first neural network"],
        ),
        gold_order=[
            "started learning machine learning from andrew ng",
            "completed the ml course",
        ],
    ),
    EvalQuery(
        name="remote_work_evolution",
        query="How has my opinion on remote work changed?",
        gold_fn=_graded_contains(
            positive=["fully async is the only way i want to work now", "prefer async-first teams"],
            support=["bad experience with daily standups", "opinion on remote work"],
        ),
        gold_order=[
            "prefer async-first teams",
            "fully async is the only way i want to work now",
        ],
    ),
]


def _tokenize(text: str) -> set[str]:
    return set(text.lower().replace(".", " ").replace(",", " ").split())


def recall_at_k(retrieved: list[str], gold_hits: list[int], k: int) -> float:
    relevant_total = sum(1 for score in gold_hits if score > 0)
    if relevant_total == 0:
        return 0.0
    found = sum(1 for idx in range(min(k, len(retrieved))) if gold_hits[idx] > 0)
    return found / relevant_total


def precision_at_k(gold_hits: list[int], k: int) -> float:
    if not gold_hits:
        return 0.0
    limit = min(k, len(gold_hits))
    if limit == 0:
        return 0.0
    found = sum(1 for idx in range(limit) if gold_hits[idx] > 0)
    return found / limit


def mrr(gold_hits: list[int], k: int) -> float:
    for idx, score in enumerate(gold_hits[:k], start=1):
        if score > 0:
            return 1.0 / idx
    return 0.0


def ndcg(gold_hits: list[int], k: int) -> float:
    def dcg(scores: list[int]) -> float:
        total = 0.0
        for idx, rel in enumerate(scores[:k], start=1):
            total += (2**rel - 1) / math.log2(idx + 1)
        return total

    ideal = sorted(gold_hits, reverse=True)
    denom = dcg(ideal)
    return dcg(gold_hits) / denom if denom else 0.0


def temporal_ordering_accuracy(source_events: list[dict], gold_order: list[str]) -> float:
    matches: list[tuple[int, int]] = []
    for idx, event in enumerate(source_events):
        text_lower = event["text"].lower()
        for gold_idx, needle in enumerate(gold_order):
            if needle in text_lower:
                matches.append((idx, gold_idx))
                break

    if len(matches) < 2:
        return 0.0

    correct = 0
    total = 0
    for i in range(len(matches)):
        for j in range(i + 1, len(matches)):
            total += 1
            pred_order = matches[i][0] < matches[j][0]
            gold_order_ok = matches[i][1] < matches[j][1]
            if pred_order == gold_order_ok:
                correct += 1
    return correct / total if total else 0.0


def redundancy_score(source_events: list[dict]) -> float:
    if len(source_events) < 2:
        return 0.0
    duplicate_pairs = 0
    total_pairs = 0
    token_sets = [_tokenize(event["text"]) for event in source_events]
    for i in range(len(token_sets)):
        for j in range(i + 1, len(token_sets)):
            total_pairs += 1
            a = token_sets[i]
            b = token_sets[j]
            if not a or not b:
                continue
            similarity = len(a & b) / len(a | b)
            if similarity >= 0.9:
                duplicate_pairs += 1
    return duplicate_pairs / total_pairs if total_pairs else 0.0


def evaluate_query(session: httpx.Client, item: EvalQuery, k: int = 10) -> dict:
    response = session.post(QUERY_ENDPOINT, json={"query": item.query, "top_k": k}, timeout=120)
    response.raise_for_status()
    payload = response.json()
    source_events = payload.get("source_events", [])
    gold_hits = [item.gold_fn(event.get("text", "")) for event in source_events]

    return {
        "name": item.name,
        "query": item.query,
        "recall@k": recall_at_k([event.get("text", "") for event in source_events], gold_hits, k),
        "precision@k": precision_at_k(gold_hits, k),
        "mrr": mrr(gold_hits, k),
        "ndcg@10": ndcg(gold_hits, 10),
        "temporal_ordering_accuracy": temporal_ordering_accuracy(source_events[:k], item.gold_order),
        "redundancy_score": redundancy_score(source_events[:k]),
        "retrieved": [event.get("text", "") for event in source_events[:k]],
        "debug_trace": payload.get("debug_trace", {}),
    }


def main() -> None:
    results = []
    with httpx.Client() as session:
        stats = session.get(STATS_ENDPOINT, timeout=30).json()
        for item in QUERIES:
            results.append(evaluate_query(session, item))

    aggregate = {
        "recall@k": sum(item["recall@k"] for item in results) / len(results),
        "precision@k": sum(item["precision@k"] for item in results) / len(results),
        "mrr": sum(item["mrr"] for item in results) / len(results),
        "ndcg@10": sum(item["ndcg@10"] for item in results) / len(results),
        "temporal_ordering_accuracy": sum(item["temporal_ordering_accuracy"] for item in results) / len(results),
        "redundancy_score": sum(item["redundancy_score"] for item in results) / len(results),
    }

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if HISTORY_PATH.exists():
        try:
            history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            history = []
    history.append(
        {
            "run_id": datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
            "created_at": datetime.utcnow().isoformat(),
            "dataset_size": int(stats.get("vector_memories") or stats.get("total_memories") or 0),
            "metrics": aggregate,
            "queries": results,
        }
    )
    HISTORY_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")

    print("ChronoMind retrieval evaluation")
    for item in results:
        print(
            f"- {item['name']}: recall@k={item['recall@k']:.3f}, precision@k={item['precision@k']:.3f}, "
            f"mrr={item['mrr']:.3f}, ndcg@10={item['ndcg@10']:.3f}, toa={item['temporal_ordering_accuracy']:.3f}, "
            f"redundancy={item['redundancy_score']:.3f}"
        )
    print("Aggregate")
    print(
        f"- recall@k={aggregate['recall@k']:.3f}, precision@k={aggregate['precision@k']:.3f}, "
        f"mrr={aggregate['mrr']:.3f}, ndcg@10={aggregate['ndcg@10']:.3f}, "
        f"toa={aggregate['temporal_ordering_accuracy']:.3f}, redundancy={aggregate['redundancy_score']:.3f}"
    )


if __name__ == "__main__":
    main()
