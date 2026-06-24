#!/usr/bin/env python3
"""Seed ChronoMind with demo data for testing."""

import requests
import time
from datetime import datetime

API_URL = "http://localhost:8000"

demo_entries = [
    {
        "text": "March 2021: Started learning machine learning from Andrew Ng's course on Coursera. Found the math intimidating at first but pushed through. I believe ML will be important for my career. Decided to dedicate 2 hours every morning to studying.",
        "timestamp": "2021-03-15T08:00:00",
        "source": "note"
    },
    {
        "text": "September 2021: Completed the ML course. Built my first neural network from scratch in NumPy. The backpropagation implementation finally clicked after reading the cs231n notes three times. I now feel confident enough to apply ML to real problems. Started exploring NLP specifically.",
        "timestamp": "2021-09-20T14:00:00",
        "source": "note"
    },
    {
        "text": "January 2022: Chose PostgreSQL over MongoDB for my new project's database. MongoDB felt like a good fit initially but after profiling, the JOIN-heavy queries performed 10x better in PostgreSQL. Also the ACID guarantees matter for financial data. This was a tough decision — spent 3 days benchmarking both.",
        "timestamp": "2022-01-10T10:00:00",
        "source": "note"
    },
    {
        "text": "June 2022: I'm frustrated with React. Bundle sizes are getting out of hand and the hooks mental model still feels unnatural to me after 2 years. Started evaluating Vue 3 Composition API as an alternative. A colleague recommended it and the reactivity system looks more intuitive.",
        "timestamp": "2022-06-05T16:00:00",
        "source": "note"
    },
    {
        "text": "October 2022: Officially switched from React to Vue 3 for all new projects. The Composition API is much cleaner. TypeScript integration feels more natural. Bundle sizes are 30% smaller. This was the right call. Decision influenced by the June frustrations and 3 months of Vue prototyping.",
        "timestamp": "2022-10-18T09:00:00",
        "source": "note"
    },
    {
        "text": "April 2023: Had a career conversation with my mentor Sarah. She suggested I should move from full-stack web dev into ML engineering given my background. I'm seriously considering this pivot. The ML skills I built in 2021 could be leveraged. Feeling uncertain but excited about the possibility.",
        "timestamp": "2023-04-22T15:00:00",
        "source": "chat"
    },
    {
        "text": "August 2023: Enrolled in fast.ai course to deepen ML engineering skills. Also started contributing to an open source ML project on GitHub. The career pivot decision is becoming more concrete. My opinion on remote work has shifted — I now prefer async-first teams over synchronous remote work after a bad experience with daily standups.",
        "timestamp": "2023-08-10T11:00:00",
        "source": "note"
    },
    {
        "text": "February 2024: Landed my first ML engineering role! The journey from web developer to ML engineer took exactly 3 years. Key inflection points: Andrew Ng course (2021), PostgreSQL project gave me data confidence (2022), Sarah's career advice (2023), fast.ai course (2023). Remote work opinion: fully async is the only way I want to work now.",
        "timestamp": "2024-02-15T13:00:00",
        "source": "note"
    }
]


def seed():
    print(f"Seeding ChronoMind at {API_URL}...\n")

    # Check health
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        print(f"Health check: {r.json()}\n")
    except Exception as e:
        print(f"Cannot reach backend at {API_URL}: {e}")
        print("Make sure 'docker-compose up' is running first.")
        return

    for i, entry in enumerate(demo_entries, 1):
        print(f"[{i}/{len(demo_entries)}] Ingesting: {entry['text'][:60]}...")
        try:
            r = requests.post(f"{API_URL}/api/ingest", json=entry, timeout=30)
            if r.status_code == 200:
                data = r.json()
                print(f"  -> Extracted {data['events_extracted']} events")
            else:
                print(f"  -> Error {r.status_code}: {r.text[:100]}")
        except Exception as e:
            print(f"  -> Request failed: {e}")

        time.sleep(2)  # Rate limit OpenAI calls

    print("\nDemo data seeded successfully!")
    print("\nTry these queries:")
    print("  - What led me to switch from React to Vue?")
    print("  - How has my opinion on remote work changed?")
    print("  - What led to my ML engineering career?")
    print("  - When did I first learn about machine learning?")


if __name__ == "__main__":
    seed()
