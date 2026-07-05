# Ranking System

ChronoMind uses a multi-stage ranking stack.

## Current Design

1. Candidate generation
2. RRF fusion
3. Feature scoring
4. Diversity filtering
5. Timeline-aware context selection

## Offline LTR

A persisted ranker can be trained from retrieval traces and synthetic judgments.

Feature inputs include:

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
- concept overlap
- retrieval source support
- graph depth
- contradiction signal
- refinement signal

## Fallback

If no trained model exists, the system falls back to calibrated feature scoring.

## Model File

- `backend/data/ranker_model.json`

