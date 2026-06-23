# ChronoMind

ChronoMind is a temporal memory retrieval system for personal knowledge. It treats memories as an evolving event graph and answers questions by combining semantic retrieval, graph traversal, lexical matching, temporal ranking, and timeline reconstruction.

This is not a chatbot. It is a search-and-reasoning engine for personal history.

## What it does

- stores atomic memory events
- indexes memories in Qdrant for semantic search
- links events in Neo4j for causal and temporal traversal
- supports BM25 lexical retrieval for exact matches
- understands query intent before retrieval
- ranks results with temporal, causal, graph, and importance signals
- reconstructs a chronological context timeline
- generates an answer grounded in retrieved memory events

## Core capabilities

- decision tracing
- belief evolution
- causal inference
- temporal evolution search
- comparison queries
- retrieval debugging and evaluation

## Architecture

| Layer | Role |
|---|---|
| Frontend | Next.js UI for query, timeline, graph, and debug inspection |
| Backend | FastAPI API for ingestion, retrieval, ranking, and reasoning |
| Vector search | Qdrant semantic retrieval |
| Graph search | Neo4j multi-hop traversal |
| Lexical search | BM25 exact-term matching |
| Ranking | Hybrid fusion, reranking, diversity filtering, temporal weighting |
| Context | Chronological reconstruction for LLM input |

## Repository layout

```text
backend/       FastAPI app, retrieval pipeline, graph, vector, ingestion
frontend/      Next.js application and API routes
scripts/       Demo seeding utilities
evaluation/    Retrieval evaluation harness
docker-compose.yml  Full local stack
```

## Quick start

### 1. Configure environment

```bash
cp .env.example .env
```

Fill in API keys if you want hosted embeddings or LLM reasoning:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`

### 2. Start the stack

```bash
docker compose up -d --build
```

### 3. Seed demo data

```bash
python scripts/seed_demo.py
```

### 4. Open the app

- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/health
- API docs: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474

## Example queries

- What led me to change my tech stack?
- How has my opinion on remote work changed?
- What led to my ML engineering career?
- When did I first learn about machine learning?

## API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/ingest` | POST | Ingest raw text and extract atomic memory events |
| `/api/query` | POST | Run hybrid retrieval and answer a memory query |
| `/api/timeline/{concept}` | GET | Fetch a chronological timeline for a concept |
| `/api/graph/explore` | GET | Inspect the memory graph |
| `/api/stats` | GET | View corpus and graph statistics |
| `/health` | GET | Health check |

## Evaluation

Run the evaluation harness against the live API:

```bash
python evaluation/run_eval.py
```

It reports:

- Recall@K
- MRR
- NDCG@10
- Temporal Ordering Accuracy
- Redundancy Score

## Demo focus

The seeded dataset is designed to show:

- learning a topic over time
- changing an opinion
- making a decision
- causal chains across events
- knowledge evolution through beliefs and refinements

## Development notes

- The system runs fully in Docker Compose.
- The backend uses real retrieval logic end to end.
- The frontend exposes the retrieval trace for debugging and interview demos.

## License

No license has been specified yet.
