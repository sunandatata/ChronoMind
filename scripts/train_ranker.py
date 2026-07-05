#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from services.ranker import RankingExample, save_model, train_linear_ranker
from evaluation.run_eval import QUERIES


API_URL = "http://localhost:8000"


def _label_from_query(item, text: str) -> float:
    score = item.gold_fn(text)
    if score >= 2:
        return 3.0
    if score == 1:
        return 1.5
    return 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("backend/data/ranker_model.json"))
    parser.add_argument("--api-url", type=str, default=API_URL)
    parser.add_argument("--top-k", type=int, default=20)
    args = parser.parse_args()

    examples: list[RankingExample] = []
    with httpx.Client(base_url=args.api_url, timeout=120) as session:
        for item in QUERIES:
            response = session.post("/api/query", json={"query": item.query, "top_k": args.top_k}).json()
            for candidate in response.get("debug_trace", {}).get("ranking_explanations", []):
                features = dict(candidate)
                relevance = _label_from_query(item, candidate.get("text", ""))
                examples.append(
                    RankingExample(
                        features=features,
                        relevance=relevance,
                        query_id=item.name,
                        event_id=candidate.get("id", ""),
                    )
                )

    model = train_linear_ranker(examples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_model(model)
    args.output.write_text(json.dumps(model, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "samples": len(examples), "model_type": model["model_type"]}, indent=2))


if __name__ == "__main__":
    main()
