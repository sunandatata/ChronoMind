# Graph Model

ChronoMind stores memories as a temporal event graph.

## Nodes

- `Event`: atomic memory record
- `Concept`: topic-level anchor
- `Entity`: named person, place, system, or technology

## Relationships

- `ABOUT`: event to concept
- `MENTIONS`: event to entity
- `RELATED_TO`: generic adjacency
- `INFLUENCED_BY`: causal influence
- `CAUSED_BY`: downstream cause relation
- `CONTRADICTS`: belief or opinion reversal
- `REFINES`: refinement of a prior belief
- `REINFORCES`: reinforcement of a prior belief
- `PREVIOUS_VERSION`: immutable version chain

## Graph Algorithms

Implemented analytics include:

- connected components
- community detection
- shortest path search
- PageRank-style centrality
- betweenness centrality

## Retrieval Usage

Graph traversal uses:

- 2-3 hop expansion
- confidence thresholds
- causal edge preference
- session-aware exclusion of already explored events

