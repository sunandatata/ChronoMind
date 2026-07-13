from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

config_stub = types.ModuleType("config")

class _Settings:
    ranker_model_path = str(ROOT / "backend" / "data" / "ranker_model.json")
    memory_decay_floor = 0.15
    memory_decay_ceiling = 1.0

def get_settings():
    return _Settings()

config_stub.get_settings = get_settings
sys.modules.setdefault("config", config_stub)

embedding_stub = types.ModuleType("services.embedding")
embedding_stub.cosine_similarity = lambda a, b: 0.0
sys.modules.setdefault("services.embedding", embedding_stub)

from models.event import EventType, MemoryEvent, SourceType
from services.context import assemble_context, build_consolidation_summary
from services.query_understanding import QueryType, understand_query
from services.ranker import predict_score


class QueryUnderstandingTests(unittest.TestCase):
    def test_decision_trace_query(self) -> None:
        profile = understand_query("What led me to switch from React to Vue?")
        self.assertEqual(profile.query_type, QueryType.DECISION_TRACE)
        self.assertTrue(profile.causal_intent)
        self.assertGreaterEqual(profile.graph_hops, 3)

    def test_belief_evolution_query(self) -> None:
        profile = understand_query("How has my opinion on remote work changed?")
        self.assertEqual(profile.query_type, QueryType.BELIEF_EVOLUTION)
        self.assertEqual(profile.temporal_intent.value, "EVOLUTION_OVER_TIME")


class ContextAssemblyTests(unittest.TestCase):
    def test_context_orders_chronologically_and_compresses_duplicates(self) -> None:
        events = [
            MemoryEvent(
                id="1",
                text="I started learning machine learning from Andrew Ng.",
                timestamp=datetime.fromisoformat("2021-01-01T12:00:00"),
                source=SourceType.NOTE,
                event_type=EventType.LEARNING,
                entities=["Andrew Ng"],
                topics=["machine learning"],
                confidence=0.8,
            ),
            MemoryEvent(
                id="2",
                text="I started learning machine learning from Andrew Ng.",
                timestamp=datetime.fromisoformat("2021-01-01T12:00:00"),
                source=SourceType.NOTE,
                event_type=EventType.LEARNING,
                entities=["Andrew Ng"],
                topics=["machine learning"],
                confidence=0.9,
            ),
            MemoryEvent(
                id="3",
                text="I decided to keep the stack modular.",
                timestamp=datetime.fromisoformat("2022-01-01T12:00:00"),
                source=SourceType.NOTE,
                event_type=EventType.DECISION,
                entities=[],
                topics=["stack"],
                confidence=0.8,
            ),
        ]
        context = assemble_context(events, "What led me to change my stack?")
        self.assertIn("2021-01-01", context)
        self.assertIn("2022-01-01", context)
        self.assertIn("Compressed events: 2", context)

    def test_consolidation_summary(self) -> None:
        events = [
            MemoryEvent(
                id="1",
                text="I believed React was the best tool.",
                timestamp=datetime.fromisoformat("2023-01-01T12:00:00"),
                source=SourceType.NOTE,
                event_type=EventType.OPINION,
                topics=["react"],
            ),
            MemoryEvent(
                id="2",
                text="I refined my opinion on React after benchmarking it.",
                timestamp=datetime.fromisoformat("2023-01-02T12:00:00"),
                source=SourceType.NOTE,
                event_type=EventType.BELIEF,
                topics=["react"],
            ),
        ]
        summaries = build_consolidation_summary(events)
        self.assertEqual(len(summaries), 1)
        self.assertIn("summarizes 2 related events", summaries[0]["summary"])


class RankerTests(unittest.TestCase):
    def test_predict_score_is_bounded(self) -> None:
        score = predict_score(
            {
                "vector_similarity_score": 1.0,
                "lexical_score": 1.0,
                "graph_distance_score": 1.0,
                "graph_centrality_score": 1.0,
                "temporal_distance_score": 1.0,
                "recency_score": 1.0,
                "event_type_weight": 1.0,
                "causal_edge_strength": 1.0,
                "entity_overlap_score": 1.0,
                "source_support_score": 1.0,
                "contradiction_score": 1.0,
                "importance_score": 1.0,
                "memory_strength": 1.0,
                "confidence_score": 1.0,
                "retrieval_source_score": 1.0,
                "graph_depth_score": 1.0,
            }
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


if __name__ == "__main__":
    unittest.main()
