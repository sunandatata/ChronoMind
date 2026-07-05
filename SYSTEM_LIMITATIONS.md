# System Limitations

ChronoMind is functional and substantially upgraded, but a few limits remain.

## Current Limits

- Retrieval quality is still bounded by the seeded memory corpus.
- Some graph analytics are approximations over the event subgraph.
- The ranker is trained from retrieval traces and heuristic judgments, not human-labeled relevance data.
- Stress-scale ingestion was prepared, but only the 10k generator artifact was verified in this pass.
- LLM latency remains external to the retrieval stack.

## Known Tradeoffs

- The system prefers explainability and deterministic behavior over opaque learned ranking.
- Session awareness is intentionally lightweight and query-session scoped.
- Consolidation is conservative to avoid losing traceability to source memories.

