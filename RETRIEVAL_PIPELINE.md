# Retrieval Pipeline

## Query Planning

The planner classifies intent into retrieval strategies such as:

- Decision Trace
- Temporal Evolution
- Belief Evolution
- Comparison
- Fact Lookup
- Learning History
- Project History
- Relationship Exploration
- Causal Analysis

## Candidate Generation

Each channel runs independently:

- vector search in Qdrant
- graph traversal in Neo4j
- temporal window filtering
- BM25 lexical search

## Ranking

Candidates are scored with a learned or calibrated feature model using:

- vector similarity
- BM25 score
- graph distance
- graph centrality
- temporal relevance
- recency
- importance
- memory strength
- confidence
- entity overlap
- causal strength
- graph depth

## Context Assembly

The final set is:

- deduplicated
- diversity filtered
- ordered chronologically
- compressed into a timeline

## Observability

Every query exposes:

- candidate counts
- pre-fusion rankings
- reranking output
- final context
- latency breakdown
- failure analysis

