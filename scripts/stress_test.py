#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx


API_URL = "http://localhost:8000"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--sample-queries", type=int, default=12)
    args = parser.parse_args()

    lines = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    with httpx.Client(base_url=API_URL, timeout=240) as session:
        start = time.perf_counter()
        for item in lines:
            session.post("/api/ingest", json=item)
        ingest_ms = (time.perf_counter() - start) * 1000.0

        sample_queries = [
            "What led me to change my tech stack?",
            "How has my opinion on remote work changed?",
            "What did I used to believe about MongoDB?",
            "How did my understanding of machine learning evolve?",
        ]
        query_latencies = []
        for query in sample_queries[: args.sample_queries]:
            q_start = time.perf_counter()
            session.post("/api/query", json={"query": query, "top_k": 8})
            query_latencies.append((time.perf_counter() - q_start) * 1000.0)

    report = {
        "records": len(lines),
        "ingest_latency_ms": ingest_ms,
        "avg_query_latency_ms": sum(query_latencies) / len(query_latencies) if query_latencies else 0.0,
        "max_query_latency_ms": max(query_latencies) if query_latencies else 0.0,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

