# Performance Report

## Validation Snapshot

Live query:

- `What led me to change my tech stack?`

Telemetry:

- retrieval latency: ~2900 ms
- reranking latency: ~559 ms
- context assembly latency: ~7 ms
- LLM latency: ~0.2 ms
- total query latency: ~3466 ms

## Graph Analytics

The event graph analytics endpoint returns:

- node count: 66
- edge count: 150
- connected components
- communities
- PageRank-style scores
- betweenness scores
- shortest paths

## Build Verification

- backend compile: passed
- frontend build: passed
- Docker Compose rebuild: passed

