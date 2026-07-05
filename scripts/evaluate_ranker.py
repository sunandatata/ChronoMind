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

from services.ranker import load_model, predict_score
from evaluation.run_eval import QUERIES, ndcg


API_URL = "http://localhost:8000"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", type=str, default=API_URL)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    model = load_model()
    if model is None:
        print(json.dumps({"status": "no_model_found"}, indent=2))
        return

    rows = []
    with httpx.Client(base_url=args.api_url, timeout=120) as session:
        for item in QUERIES:
            response = session.post("/api/query/explain", json={"query": item.query, "top_k": args.top_k}).json()
            explanations = response.get("explanations", [])
            scores = []
            for explanation in explanations:
                features = {
                    "vector_similarity_score": explanation.get("vector_similarity_score", 0.0),
                    "lexical_score": explanation.get("bm25_score", 0.0),
                    "graph_distance_score": explanation.get("graph_distance_score", 0.0),
                    "graph_centrality_score": explanation.get("graph_centrality_score", 0.0),
                    "temporal_distance_score": explanation.get("temporal_distance_score", 0.0),
                    "recency_score": explanation.get("temporal_distance_score", 0.0),
                    "event_type_weight": 0.5,
                    "causal_edge_strength": explanation.get("causal_edge_strength", 0.0),
                    "entity_overlap_score": explanation.get("entity_overlap_score", 0.0),
                    "source_support_score": explanation.get("source_support_score", 0.0),
                    "contradiction_score": explanation.get("contradiction_score", 0.0),
                    "importance_score": explanation.get("importance_score", 0.0),
                    "memory_strength": explanation.get("memory_strength", 0.0),
                    "confidence_score": 0.8,
                    "retrieval_source_score": 0.5,
                    "graph_depth_score": 0.5,
                }
                scores.append(predict_score(features, model))
            rows.append({"query": item.name, "ndcg@10": ndcg(scores, 10), "top_k": args.top_k})

    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
