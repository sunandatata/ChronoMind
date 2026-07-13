from datetime import datetime
from typing import Optional

import networkx as nx
from neo4j import AsyncGraphDatabase

from config import get_settings
from models.event import MemoryEvent

settings = get_settings()

EVENT_EDGE_TYPES = {
    "RELATED_TO",
    "INFLUENCED_BY",
    "CAUSED_BY",
    "CONTRADICTS",
    "REFINES",
    "REINFORCES",
    "PREVIOUS_VERSION",
    "VERSION_OF",
    "SUMMARIZES",
}

# Edges are written from the later/effect event to the earlier/influencing event.
_EDGE_TYPE_MATRIX: dict[tuple[str, str], str] = {
    ("decision", "opinion"): "INFLUENCED_BY",
    ("decision", "belief"): "INFLUENCED_BY",
    ("decision", "observation"): "INFLUENCED_BY",
    ("decision", "learning"): "INFLUENCED_BY",
    ("decision", "action"): "CAUSED_BY",
    ("action", "decision"): "CAUSED_BY",
    ("action", "observation"): "INFLUENCED_BY",
    ("action", "learning"): "INFLUENCED_BY",
    ("belief", "belief"): "CONTRADICTS",
    ("opinion", "opinion"): "CONTRADICTS",
    ("opinion", "belief"): "CONTRADICTS",
    ("belief", "opinion"): "CONTRADICTS",
    ("learning", "observation"): "INFLUENCED_BY",
    ("learning", "learning"): "RELATED_TO",
    ("observation", "observation"): "RELATED_TO",
}


def _resolve_edge_type(from_type: str, to_type: str, sentiment_delta: float = 0.0) -> str:
    edge_type = _EDGE_TYPE_MATRIX.get((from_type, to_type), "RELATED_TO")
    if edge_type == "CONTRADICTS" and abs(sentiment_delta) < 0.4:
        return "RELATED_TO"
    return edge_type


def _resolve_belief_edge_type(event: MemoryEvent, candidate: dict) -> str:
    payload = candidate.get("payload") or {}
    candidate_type = str(payload.get("event_type") or "").lower()
    if event.event_type.value not in {"belief", "opinion"} and candidate_type not in {"belief", "opinion"}:
        return "RELATED_TO"

    event_sentiment = float(event.sentiment or 0.0)
    candidate_sentiment = float(payload.get("sentiment") or 0.0)
    delta = abs(event_sentiment - candidate_sentiment)
    if delta >= 0.55:
        return "CONTRADICTS"
    if delta >= 0.2:
        return "REFINES"
    return "REINFORCES"


def _parse_ts(value, default: datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return default
    return default


class GraphService:
    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    async def close(self):
        await self.driver.close()

    async def init_schema(self):
        async with self.driver.session() as session:
            await session.run(
                "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT concept_label IF NOT EXISTS FOR (c:Concept) REQUIRE c.label IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (en:Entity) REQUIRE en.name IS UNIQUE"
            )
            await session.run(
                "CREATE INDEX event_timestamp IF NOT EXISTS FOR (e:Event) ON (e.timestamp)"
            )
            await session.run(
                "CREATE INDEX event_type_idx IF NOT EXISTS FOR (e:Event) ON (e.event_type)"
            )

    async def create_event_node(self, event: MemoryEvent, is_demo: bool = False) -> str:
        ts = event.timestamp.isoformat()
        async with self.driver.session() as session:
            await session.run(
                """
                MERGE (e:Event {id: $id})
                SET e.text       = $text,
                    e.timestamp  = $timestamp,
                    e.source     = $source,
                    e.event_type = $event_type,
                    e.entities   = $entities,
                    e.topics     = $topics,
                    e.sentiment  = $sentiment,
                    e.confidence = $confidence,
                    e.importance_score = $importance_score,
                    e.memory_strength  = $memory_strength,
                    e.retrieval_count  = $retrieval_count,
                    e.last_accessed_at = $last_accessed_at,
                    e.decay_coefficient = $decay_coefficient,
                    e.version   = $version,
                    e.original_event_id = $original_event_id,
                    e.source_id = $source_id,
                    e.is_demo    = $is_demo
                """,
                id=event.id,
                text=event.text,
                timestamp=ts,
                source=event.source.value,
                event_type=event.event_type.value,
                entities=event.entities,
                topics=event.topics,
                sentiment=event.sentiment if event.sentiment is not None else 0.0,
                confidence=event.confidence,
                importance_score=event.importance_score,
                memory_strength=event.memory_strength,
                retrieval_count=event.retrieval_count,
                last_accessed_at=event.last_accessed_at.isoformat() if event.last_accessed_at else None,
                decay_coefficient=event.decay_coefficient,
                version=event.version,
                original_event_id=event.original_event_id,
                source_id=event.source_id,
                is_demo=is_demo,
            )
            for topic in event.topics:
                await session.run(
                    """
                    MERGE (c:Concept {label: $label})
                    ON CREATE SET c.first_seen = $ts, c.event_count = 1, c.last_seen = $ts
                    ON MATCH  SET c.event_count = coalesce(c.event_count, 0) + 1, c.last_seen = $ts
                    WITH c
                    MATCH (e:Event {id: $eid})
                    MERGE (e)-[:ABOUT]->(c)
                    """,
                    label=topic.lower(),
                    ts=ts,
                    eid=event.id,
                )
            for entity in event.entities:
                await session.run(
                    """
                    MERGE (en:Entity {name: $name})
                    ON CREATE SET en.first_mention = $ts
                    ON MATCH  SET en.last_mention = $ts
                    WITH en
                    MATCH (e:Event {id: $eid})
                    MERGE (e)-[:MENTIONS]->(en)
                    """,
                    name=entity,
                    ts=ts,
                    eid=event.id,
                )
        return event.id

    async def create_semantic_edges(
        self,
        new_event: MemoryEvent,
        candidate_events: list[dict],
    ) -> None:
        new_ts = new_event.timestamp
        new_type = new_event.event_type.value
        new_sentiment = new_event.sentiment or 0.0

        for candidate in candidate_events[:8]:
            candidate_id = candidate.get("event_id") or candidate.get("id", "")
            if not candidate_id or candidate_id == new_event.id:
                continue

            candidate_ts = _parse_ts(candidate.get("timestamp"), new_ts)
            candidate_type = candidate.get("event_type", "observation")
            candidate_sentiment = float(candidate.get("sentiment") or 0.0)
            candidate_belief_edge = candidate.get("_belief_edge_type")

            if candidate_ts > new_ts:
                from_id = candidate_id
                to_id = new_event.id
                from_type = candidate_type
                to_type = new_type
                sentiment_delta = candidate_sentiment - new_sentiment
            else:
                from_id = new_event.id
                to_id = candidate_id
                from_type = new_type
                to_type = candidate_type
                sentiment_delta = new_sentiment - candidate_sentiment

            edge_type = candidate_belief_edge or _resolve_belief_edge_type(new_event, candidate) or _resolve_edge_type(from_type, to_type, sentiment_delta)
            async with self.driver.session() as session:
                await session.run(
                    f"""
                    MATCH (a:Event {{id: $from_id}})
                    MATCH (b:Event {{id: $to_id}})
                    MERGE (a)-[r:{edge_type}]->(b)
                    SET r.auto_linked     = true,
                        r.sentiment_delta = $sd,
                        r.created_at      = $ts
                    """,
                    from_id=from_id,
                    to_id=to_id,
                    sd=sentiment_delta,
                    ts=datetime.utcnow().isoformat(),
                )

    async def create_edge(
        self, from_id: str, to_id: str, rel_type: str, properties: dict = None
    ):
        rel_type = rel_type.upper()
        if rel_type not in EVENT_EDGE_TYPES:
            raise ValueError(f"Unsupported event relationship type: {rel_type}")

        async with self.driver.session() as session:
            await session.run(
                f"""
                MATCH (a:Event {{id: $from_id}})
                MATCH (b:Event {{id: $to_id}})
                MERGE (a)-[r:{rel_type}]->(b)
                SET r += $props
                """,
                from_id=from_id,
                to_id=to_id,
                props=properties or {},
            )

    async def update_event_properties(self, event_id: str, properties: dict) -> None:
        if not properties:
            return
        assignments = ", ".join([f"e.{key} = ${key}" for key in properties.keys()])
        params = dict(properties)
        params["event_id"] = event_id
        async with self.driver.session() as session:
            await session.run(
                f"""
                MATCH (e:Event {{id: $event_id}})
                SET {assignments}
                """,
                **params,
            )

    async def get_event_properties(self, event_id: str) -> dict:
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (e:Event {id: $event_id})
                RETURN e.id AS id,
                       e.memory_strength AS memory_strength,
                       e.retrieval_count AS retrieval_count,
                       e.last_accessed_at AS last_accessed_at,
                       e.importance_score AS importance_score,
                       e.confidence AS confidence
                """,
                event_id=event_id,
            )
            records = await result.data()
        return dict(records[0]) if records else {}

    async def graph_traversal_retrieve(
        self,
        entities: list[str],
        topics: list[str],
        max_hops: int = 3,
        min_seed_confidence: float = 0.65,
        seed_limit: int = 30,
        neighbor_confidence_floor: float = 0.5,
        causal_only: bool = False,
        limit: int = 30,
        exclude_event_ids: list[str] | None = None,
    ) -> list[dict]:
        entity_terms = [entity.lower() for entity in entities]
        topic_terms = [topic.lower() for topic in topics]
        hop_pattern = f"1..{max(1, min(max_hops, 3))}"
        excluded_ids = exclude_event_ids or []

        if not entity_terms and not topic_terms:
            return []

        async with self.driver.session() as session:
            seed_result = await session.run(
                """
                MATCH (seed:Event)
                WHERE coalesce(seed.is_demo, false) = false
                  AND coalesce(seed.confidence, 0.0) >= $min_seed_confidence
                  AND NOT seed.id IN $excluded_ids
                  AND (
                    EXISTS {
                      MATCH (seed)-[:MENTIONS]->(en:Entity)
                      WHERE toLower(en.name) IN $entities
                    }
                    OR EXISTS {
                      MATCH (seed)-[:ABOUT]->(c:Concept)
                      WHERE c.label IN $topics
                    }
                  )
                RETURN DISTINCT seed
                ORDER BY coalesce(seed.confidence, 0.0) DESC, seed.timestamp DESC
                LIMIT $seed_limit
                """,
                entities=entity_terms,
                topics=topic_terms,
                seed_limit=max(seed_limit, 12),
                min_seed_confidence=min_seed_confidence,
                excluded_ids=excluded_ids,
            )
            seed_records = await seed_result.data()
            seed_ids = [
                record["seed"]["id"]
                for record in seed_records
                if record.get("seed") and record["seed"].get("id")
            ]

            if not seed_ids:
                return []

            traversal_result = await session.run(
                f"""
                UNWIND $seed_ids AS sid
                MATCH (seed:Event {{id: sid}})
                CALL {{
                  WITH seed
                  RETURN seed AS ev, 0 AS hop, 'graph_seed' AS match_type

                  UNION

                  WITH seed
                  MATCH path = (seed)-[:RELATED_TO|INFLUENCED_BY|CAUSED_BY|CONTRADICTS*{hop_pattern}]-(linked:Event)
                  WHERE coalesce(linked.is_demo, false) = false
                    AND coalesce(linked.confidence, 0.0) >= $neighbor_confidence_floor
                  RETURN linked AS ev,
                         length(path) AS hop,
                         CASE
                           WHEN any(r IN relationships(path) WHERE type(r) IN ['INFLUENCED_BY', 'CAUSED_BY'])
                           THEN 'causal_graph_traversal'
                           ELSE 'graph_traversal'
                         END AS match_type

                  UNION

                  WITH seed
                  MATCH (seed)-[:ABOUT]->(:Concept)<-[:ABOUT]-(peer:Event)
                  WHERE peer.id <> seed.id AND coalesce(peer.is_demo, false) = false
                  RETURN peer AS ev, 2 AS hop, 'shared_concept_traversal' AS match_type
                }}
                WITH ev, min(hop) AS hop, collect(DISTINCT match_type) AS match_types
                WHERE $causal_only = false OR any(label IN match_types WHERE label CONTAINS 'causal')
                  AND NOT ev.id IN $excluded_ids
                RETURN ev, hop, match_types
                ORDER BY hop ASC, ev.timestamp DESC
                LIMIT $limit
                """,
                seed_ids=seed_ids,
                neighbor_confidence_floor=neighbor_confidence_floor,
                causal_only=causal_only,
                limit=limit,
                excluded_ids=excluded_ids,
            )
            records = await traversal_result.data()
            return [
                {
                    **record["ev"],
                    "_hop": record["hop"],
                    "_match_type": ",".join(record["match_types"]),
                }
                for record in records
                if record.get("ev")
            ]

    async def get_causal_chain(self, event_ids: list[str]) -> list[dict]:
        if not event_ids:
            return []

        queries = [
            """
            UNWIND $event_ids AS eid
            MATCH (effect:Event {id: eid})
            WHERE effect.event_type IN ['decision', 'action']
              AND coalesce(effect.is_demo, false) = false
            MATCH path = (effect)-[:INFLUENCED_BY|CAUSED_BY*1..3]->(cause:Event)
            WHERE coalesce(cause.is_demo, false) = false
            RETURN DISTINCT cause AS ev, length(path) AS chain_depth, effect.id AS effect_id
            ORDER BY cause.timestamp ASC
            LIMIT 20
            """,
            """
            UNWIND $event_ids AS eid
            MATCH (effect:Event {id: eid})
            WHERE effect.event_type IN ['decision', 'action']
              AND coalesce(effect.is_demo, false) = false
            MATCH path = (cause:Event)-[:INFLUENCED_BY|CAUSED_BY*1..3]->(effect)
            WHERE coalesce(cause.is_demo, false) = false
            RETURN DISTINCT cause AS ev, length(path) AS chain_depth, effect.id AS effect_id
            ORDER BY cause.timestamp ASC
            LIMIT 20
            """,
        ]

        seen: set[str] = set()
        chain: list[dict] = []
        async with self.driver.session() as session:
            for query in queries:
                result = await session.run(query, event_ids=event_ids)
                records = await result.data()
                for record in records:
                    ev = record.get("ev")
                    if not ev or ev.get("id") in seen:
                        continue
                    seen.add(ev.get("id"))
                    chain.append(
                        {
                            **ev,
                            "_chain_depth": record["chain_depth"],
                            "_causes": record["effect_id"],
                            "_match_type": "causal_chain",
                        }
                    )

        chain.sort(key=lambda item: (item.get("timestamp", ""), -item.get("_chain_depth", 0)))
        return chain[:20]

    async def get_event_versions(self, event_id: str) -> list[dict]:
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH path = (latest:Event {id: $event_id})-[:PREVIOUS_VERSION*0..5]->(previous:Event)
                WITH nodes(path) AS nodes
                UNWIND nodes AS node
                RETURN DISTINCT node AS ev
                ORDER BY ev.version ASC, ev.timestamp ASC
                """,
                event_id=event_id,
            )
            records = await result.data()
        return [record["ev"] for record in records if record.get("ev")]

    async def get_belief_evolution(self, event_ids: list[str]) -> list[dict]:
        if not event_ids:
            return []

        async with self.driver.session() as session:
            result = await session.run(
                """
                UNWIND $event_ids AS eid
                MATCH (seed:Event {id: eid})
                WHERE seed.event_type IN ['belief', 'opinion']
                MATCH path = (seed)-[:REFINES|REINFORCES|CONTRADICTS*1..3]-(related:Event)
                WHERE coalesce(related.is_demo, false) = false
                RETURN DISTINCT related AS ev, length(path) AS depth, seed.id AS seed_id
                ORDER BY related.timestamp ASC
                LIMIT 20
                """,
                event_ids=event_ids,
            )
            records = await result.data()

        seen: set[str] = set()
        chain: list[dict] = []
        for record in records:
            ev = record.get("ev")
            if not ev or ev.get("id") in seen:
                continue
            seen.add(ev.get("id"))
            chain.append(
                {
                    **ev,
                    "_belief_depth": record.get("depth", 0),
                    "_belief_seed": record.get("seed_id"),
                    "_match_type": "belief_evolution",
                }
            )
        return chain

    async def get_belief_evolution_by_concept(self, concept: str) -> dict:
        concept_key = concept.lower().strip()
        if not concept_key:
            return {"concept": concept, "events": [], "links": []}

        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (seed:Event)
                WHERE coalesce(seed.is_demo, false) = false
                  AND (
                    EXISTS {
                      MATCH (seed)-[:ABOUT]->(c:Concept)
                      WHERE toLower(c.label) CONTAINS $concept
                    }
                    OR toLower(seed.text) CONTAINS $concept
                  )
                  AND seed.event_type IN ['belief', 'opinion', 'decision', 'learning', 'action']
                OPTIONAL MATCH path = (seed)-[:CONTRADICTS|REFINES|REINFORCES|INFLUENCED_BY|CAUSED_BY*1..3]-(related:Event)
                WHERE coalesce(related.is_demo, false) = false
                WITH seed, collect(DISTINCT related) AS related_events
                RETURN seed, related_events
                ORDER BY seed.timestamp ASC
                LIMIT 25
                """,
                concept=concept_key,
            )
            records = await result.data()

        seen: set[str] = set()
        events: list[dict] = []
        for record in records:
            seed = record.get("seed")
            if seed and seed.get("id") and seed["id"] not in seen:
                seen.add(seed["id"])
                events.append({**seed, "_role": "seed"})
            for related in record.get("related_events") or []:
                if not related or not related.get("id") or related["id"] in seen:
                    continue
                seen.add(related["id"])
                events.append({**related, "_role": "related"})

        events.sort(key=lambda item: item.get("timestamp", ""))
        links = []
        for idx in range(1, len(events)):
            prev = events[idx - 1]
            curr = events[idx]
            if prev.get("id") and curr.get("id"):
                links.append(
                    {
                        "source": prev["id"],
                        "target": curr["id"],
                        "relationship": curr.get("_match_type", "evolution"),
                    }
                )

        return {"concept": concept, "events": events, "links": links}

    async def get_centrality_scores(self, event_ids: list[str]) -> dict[str, float]:
        if not event_ids:
            return {}

        async with self.driver.session() as session:
            result = await session.run(
                """
                UNWIND $event_ids AS eid
                MATCH (e:Event {id: eid})
                OPTIONAL MATCH (e)-[r:RELATED_TO|INFLUENCED_BY|CAUSED_BY|CONTRADICTS]-(:Event)
                RETURN e.id AS event_id, count(r) AS degree
                """,
                event_ids=event_ids,
            )
            records = await result.data()

        raw = {record["event_id"]: float(record["degree"]) for record in records if record["event_id"]}
        if not raw:
            return {}

        max_degree = max(raw.values()) or 1.0
        return {
            event_id: (degree / max_degree) * 0.9 + 0.1
            for event_id, degree in raw.items()
        }

    async def get_graph_stats(self) -> dict[str, float]:
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (e:Event)
                WHERE coalesce(e.is_demo, false) = false
                OPTIONAL MATCH (e)-[r]->()
                WITH count(DISTINCT e) AS events, count(DISTINCT r) AS rels
                OPTIONAL MATCH (c:Concept)
                WITH events, rels, count(DISTINCT c) AS concepts
                OPTIONAL MATCH (en:Entity)
                WITH events, rels, concepts, count(DISTINCT en) AS entities
                RETURN events, rels, concepts, entities
                """
            )
            records = await result.data()
        if not records:
            return {"total_memories": 0, "total_concepts": 0, "total_entities": 0, "graph_edges": 0, "graph_density": 0.0}
        record = records[0]
        total_memories = int(record.get("events") or 0)
        total_concepts = int(record.get("concepts") or 0)
        total_entities = int(record.get("entities") or 0)
        graph_edges = int(record.get("rels") or 0)
        possible = max(total_memories * max(total_memories - 1, 1), 1)
        density = min(graph_edges / possible, 1.0)
        return {
            "total_memories": total_memories,
            "total_concepts": total_concepts,
            "total_entities": total_entities,
            "graph_edges": graph_edges,
            "graph_density": round(density, 6),
        }

    async def get_belief_stats(self) -> dict[str, int]:
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH ()-[r:CONTRADICTS|REFINES|REINFORCES]->()
                RETURN type(r) AS relationship, count(*) AS count
                """
            )
            records = await result.data()
        output = {"CONTRADICTS": 0, "REFINES": 0, "REINFORCES": 0}
        for record in records:
            rel = record.get("relationship")
            if rel in output:
                output[rel] = int(record.get("count") or 0)
        return output

    async def get_graph_signals(self, event_ids: list[str]) -> dict[str, dict[str, float]]:
        if not event_ids:
            return {}

        async with self.driver.session() as session:
            result = await session.run(
                """
                UNWIND $event_ids AS eid
                MATCH (e:Event {id: eid})
                OPTIONAL MATCH (:Event)-[in_rel:RELATED_TO|INFLUENCED_BY|CAUSED_BY|CONTRADICTS]->(e)
                OPTIONAL MATCH (e)-[out_rel:RELATED_TO|INFLUENCED_BY|CAUSED_BY|CONTRADICTS]->(:Event)
                RETURN e.id AS event_id,
                       count(DISTINCT in_rel) AS inbound,
                       count(DISTINCT out_rel) AS outbound,
                       sum(
                         CASE
                           WHEN in_rel IS NULL THEN 0
                           WHEN type(in_rel) IN ['CAUSED_BY', 'INFLUENCED_BY'] THEN 2
                           ELSE 1
                         END
                       ) AS causal_inbound
                """,
                event_ids=event_ids,
            )
            records = await result.data()

        if not records:
            return {}

        signals: dict[str, dict[str, float]] = {}
        for record in records:
            event_id = record.get("event_id")
            if not event_id:
                continue
            inbound = float(record.get("inbound") or 0.0)
            outbound = float(record.get("outbound") or 0.0)
            causal_inbound = float(record.get("causal_inbound") or 0.0)
            signals[event_id] = {
                "page_rankish": inbound + 0.5 * outbound + 0.5,
                "degree": inbound + outbound,
                "causal_strength": causal_inbound + inbound * 0.25,
            }

        max_page = max(item["page_rankish"] for item in signals.values()) or 1.0
        max_degree = max(item["degree"] for item in signals.values()) or 1.0
        max_causal = max(item["causal_strength"] for item in signals.values()) or 1.0
        for item in signals.values():
            item["page_rankish"] = item["page_rankish"] / max_page
            item["degree"] = item["degree"] / max_degree
            item["causal_strength"] = item["causal_strength"] / max_causal
        return signals

    async def get_contradiction_events(self, event_ids: list[str]) -> list[dict]:
        if not event_ids:
            return []

        async with self.driver.session() as session:
            result = await session.run(
                """
                UNWIND $event_ids AS eid
                MATCH (e:Event {id: eid})-[:CONTRADICTS]-(contra:Event)
                WHERE coalesce(contra.is_demo, false) = false
                RETURN DISTINCT contra AS ev, e.id AS contradicts_event_id
                ORDER BY contra.timestamp ASC LIMIT 12
                """,
                event_ids=event_ids,
            )
            records = await result.data()
            return [
                {
                    **record["ev"],
                    "_contradicts": record["contradicts_event_id"],
                    "_match_type": "contradiction",
                }
                for record in records
                if record.get("ev")
            ]

    async def get_timeline(
        self,
        concept: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> list[dict]:
        async with self.driver.session() as session:
            query = """
                MATCH (e:Event)-[:ABOUT]->(c:Concept)
                WHERE toLower(c.label) CONTAINS toLower($concept)
                  AND coalesce(e.is_demo, false) = false
                """
            if start:
                query += " AND e.timestamp >= $start"
            if end:
                query += " AND e.timestamp <= $end"
            query += " RETURN e ORDER BY e.timestamp ASC LIMIT 50"

            params: dict = {"concept": concept}
            if start:
                params["start"] = start
            if end:
                params["end"] = end

            result = await session.run(query, **params)
            records = await result.data()
            return [record["e"] for record in records]

    async def get_all_events(self, limit: int = 200) -> list[dict]:
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (e:Event)
                WHERE coalesce(e.is_demo, false) = false
                RETURN e ORDER BY e.timestamp DESC LIMIT $limit
                """,
                limit=limit,
            )
            records = await result.data()
            return [record["e"] for record in records]

    async def get_graph_data(self, limit: int = 100) -> dict:
        async with self.driver.session() as session:
            event_result = await session.run(
                """
                MATCH (e:Event)
                WHERE coalesce(e.is_demo, false) = false
                RETURN e LIMIT $limit
                """,
                limit=limit,
            )
            events = await event_result.data()

            concept_result = await session.run(
                "MATCH (c:Concept) RETURN c LIMIT 50"
            )
            concepts = await concept_result.data()

            edge_result = await session.run(
                """
                MATCH (e:Event)-[r:ABOUT]->(c:Concept)
                WHERE coalesce(e.is_demo, false) = false
                RETURN e.id AS source, c.label AS target, type(r) AS rel LIMIT 200
                """
            )
            edges = await edge_result.data()

            event_edge_result = await session.run(
                """
                MATCH (a:Event)-[r]->(b:Event)
                WHERE coalesce(a.is_demo, false) = false
                  AND coalesce(b.is_demo, false) = false
                RETURN a.id AS source, b.id AS target, type(r) AS rel LIMIT 150
                """
            )
            event_edges = await event_edge_result.data()

            return {
                "events": [record["e"] for record in events],
                "concepts": [record["c"] for record in concepts],
                "edges": edges + event_edges,
            }

    async def get_graph_analytics(self, limit: int = 120) -> dict:
        graph_data = await self.get_graph_data(limit=limit)
        graph = nx.DiGraph()
        for event in graph_data.get("events", []):
            if event.get("id"):
                graph.add_node(event["id"], **event)
        for edge in graph_data.get("edges", []):
            src = edge.get("source")
            dst = edge.get("target")
            if src and dst and src in graph and dst in graph:
                graph.add_edge(src, dst, relationship=edge.get("rel"))

        undirected = graph.to_undirected()
        components = [sorted(list(component)) for component in nx.connected_components(undirected)] if len(undirected) else []
        betweenness = nx.betweenness_centrality(undirected, normalized=True) if len(undirected) else {}
        pagerank = self._pagerank(graph) if len(graph) else {}
        try:
            from networkx.algorithms.community import greedy_modularity_communities

            communities = [sorted(list(comm)) for comm in greedy_modularity_communities(undirected)] if len(undirected) else []
        except Exception:
            communities = []

        shortest_paths = []
        event_ids = [event.get("id") for event in graph_data.get("events", []) if event.get("id")]
        if len(event_ids) >= 2:
            source = event_ids[0]
            target = event_ids[min(len(event_ids) - 1, 4)]
            try:
                path = nx.shortest_path(undirected, source=source, target=target)
                shortest_paths.append({"source": source, "target": target, "path": path, "length": max(len(path) - 1, 0)})
            except Exception:
                pass

        return {
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
            "connected_components": components[:10],
            "communities": communities[:10],
            "pagerank": dict(sorted(pagerank.items(), key=lambda item: item[1], reverse=True)[:20]),
            "betweenness": dict(sorted(betweenness.items(), key=lambda item: item[1], reverse=True)[:20]),
            "shortest_paths": shortest_paths,
        }

    def _pagerank(self, graph: nx.DiGraph, alpha: float = 0.85, max_iter: int = 100, tol: float = 1.0e-6) -> dict[str, float]:
        nodes = list(graph.nodes())
        if not nodes:
            return {}
        n = len(nodes)
        ranks = {node: 1.0 / n for node in nodes}
        out_degree = {node: graph.out_degree(node) for node in nodes}

        for _ in range(max_iter):
            prev = ranks.copy()
            dangling_sum = sum(prev[node] for node in nodes if out_degree[node] == 0)
            for node in nodes:
                rank = (1.0 - alpha) / n
                rank += alpha * dangling_sum / n
                for pred in graph.predecessors(node):
                    degree = out_degree.get(pred, 0)
                    if degree:
                        rank += alpha * prev[pred] / degree
                ranks[node] = rank
            delta = sum(abs(ranks[node] - prev[node]) for node in nodes)
            if delta < tol:
                break
        total = sum(ranks.values()) or 1.0
        return {node: value / total for node, value in ranks.items()}


_graph_service: Optional[GraphService] = None


def get_graph_service() -> GraphService:
    global _graph_service
    if _graph_service is None:
        _graph_service = GraphService()
    return _graph_service
