# ChronoMind Final Architecture

ChronoMind is a temporal memory retrieval system, not a chatbot.

## Core Stack

- FastAPI backend
- Neo4j graph store
- Qdrant vector store
- BM25 lexical index
- Next.js frontend

## Retrieval Flow

1. Query understanding classifies the request.
2. Candidate generation runs independently across vector, graph, temporal, and BM25 channels.
3. A learned ranker or calibrated fallback scores candidates.
4. Diversity and quality filters prune redundant noise.
5. Context reconstruction orders memories chronologically.
6. The reasoning layer generates the final response.

## Explainability

Each query exposes:

- retrieval traces
- ranking explanations
- timeline context
- failure analysis
- telemetry
- session reuse state

## Graph Model

The graph stores:

- `Event`
- `Concept`
- `Entity`

Relationships include:

- `ABOUT`
- `MENTIONS`
- `RELATED_TO`
- `INFLUENCED_BY`
- `CAUSED_BY`
- `CONTRADICTS`
- `REFINES`
- `REINFORCES`
- `PREVIOUS_VERSION`

## Model Selection

The ranker loads `backend/data/ranker_model.json` when present and falls back to calibrated feature scoring otherwise.

