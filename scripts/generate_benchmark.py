#!/usr/bin/env python3
"""Generate synthetic ChronoMind benchmark timelines at scale."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


TOPICS = {
    "projects": [
        "the dashboard project",
        "the search refactor",
        "the mobile rewrite",
        "the billing migration",
        "the analytics pipeline",
    ],
    "career": [
        "my career direction",
        "my engineering focus",
        "my management plans",
        "my remote work preferences",
        "my long term role goals",
    ],
    "learning": [
        "machine learning",
        "databases",
        "React",
        "Vue",
        "system design",
    ],
    "books": [
        "Clean Architecture",
        "Designing Data-Intensive Applications",
        "The Pragmatic Programmer",
        "Deep Learning",
        "Refactoring",
    ],
    "meetings": [
        "weekly product review",
        "career conversation",
        "design critique",
        "team retro",
        "planning sync",
    ],
    "opinions": [
        "remote work",
        "monorepos",
        "TypeScript",
        "PostgreSQL",
        "MongoDB",
    ],
    "technology": [
        "React",
        "Vue",
        "PostgreSQL",
        "MongoDB",
        "Redis",
    ],
    "milestones": [
        "launching the feature",
        "shipping the migration",
        "publishing the article",
        "closing the project",
        "starting the new role",
    ],
}


def _ts(start: datetime, idx: int, stride_days: int) -> datetime:
    return start + timedelta(days=idx * stride_days)


def _item(text: str, timestamp: datetime, source: str = "note") -> dict:
    return {
        "text": text,
        "timestamp": timestamp.isoformat(),
        "source": source,
    }


def generate(count: int, seed: int = 42) -> list[dict]:
    random.seed(seed)
    start = datetime(2019, 1, 1)
    outputs: list[dict] = []
    categories = list(TOPICS.keys())

    for idx in range(count):
        category = categories[idx % len(categories)]
        topic = random.choice(TOPICS[category])
        ts = _ts(start, idx, 11)
        phase = idx % 3
        if category == "projects":
            texts = [
                f"I initially believed {topic} should use a simple architecture, but that assumption was too optimistic.",
                f"I refined my view of {topic} after measuring the tradeoffs and comparing implementation approaches.",
                f"I decided to keep {topic} modular because it reduced risk and made future changes easier.",
            ]
        elif category == "career":
            texts = [
                f"My opinion on {topic} shifted after a discussion with a mentor.",
                f"I refined my plan around {topic} after getting more context.",
                f"I decided to change direction because {topic} aligned with my long-term goals.",
            ]
        elif category == "learning":
            texts = [
                f"I started learning {topic} and found the first phase difficult but valuable.",
                f"I reinforced my understanding of {topic} by applying it in a small project.",
                f"I later connected {topic} to a real decision and understood it more deeply.",
            ]
        elif category == "books":
            texts = [
                f"I read {topic} and believed its advice was too strict at first.",
                f"Later I refined my reading of {topic} after applying it to a real project.",
                f"I reinforced the useful parts of {topic} in my own workflow.",
            ]
        elif category == "meetings":
            texts = [
                f"During a {topic}, I heard a concern that contradicted my earlier assumption.",
                f"I refined my approach after the {topic} and wrote down the new plan.",
                f"The {topic} reinforced why the change was worth making.",
            ]
        elif category == "opinions":
            texts = [
                f"In {ts.year}, I believed {topic} was the best option for my current situation.",
                f"Later I contradicted that view after seeing a failure mode that changed my thinking about {topic}.",
                f"By the end of the year, I refined my position and started using {topic} only when it fit the workload.",
            ]
        elif category == "technology":
            texts = [
                f"I thought {topic} would solve the problem, but I later found a limitation.",
                f"I refined my opinion on {topic} after benchmarking it against another option.",
                f"I reinforced that {topic} is a good fit for specific workloads.",
            ]
        else:
            texts = [
                f"I reached a milestone around {topic} and noted the decision that led there.",
                f"I refined my understanding of the milestone after reviewing the outcome.",
                f"The milestone reinforced the broader direction I was already taking.",
            ]

        text = texts[phase]
        source = "chat" if category == "meetings" else "note"
        outputs.append(_item(text, ts + timedelta(days=phase * 4), source=source))

    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, choices=[500, 1000, 5000, 10000, 50000, 100000], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    records = generate(args.count, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")

    manifest = {
        "count": args.count,
        "seed": args.seed,
        "output": str(args.output),
        "generated_at": datetime.utcnow().isoformat(),
    }
    manifest_path = args.output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
