#!/usr/bin/env python3
"""Seed ChronoMind from a generated benchmark JSONL file."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    records = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        records = records[:args.limit]

    for index, record in enumerate(records, start=1):
        response = requests.post(f"{args.api_url}/api/ingest", json=record, timeout=60)
        response.raise_for_status()
        print(f"[{index}/{len(records)}] ingested")
        time.sleep(0.15)


if __name__ == "__main__":
    main()
