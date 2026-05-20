# Memory Layer

**Owner:** Ullas (Hacker 4)
**Technology:** SentenceTransformers, Qdrant, NetworkX, numpy

## Files

| File | Purpose |
|------|---------|
| `rag.py` | RAG vector search — embeds clauses, verifies agent claims, tracks citation graph |
| `bridge.py` | Integration layer — wraps validator + RAG as CrewAI tools + plain functions |
| `reset_between_docs.py` | Clears all in-memory state between document analyses |
| `__init__.py` | Package marker |

## How RAG works

```
Clause text
    │ SentenceTransformer.encode()
    ▼
384-dim vector
    │ stored in Qdrant (or InMemoryRAG fallback)
    ▼
Agent makes a claim: "The vendor liability is capped"
    │ encode claim → cosine similarity search
    ▼
Best matching clause found
    │ score >= 0.55 threshold?
    ▼
verified=True (grounded) or verified=False (hallucination)
    │ recorded in NetworkX citation graph
    ▼
hallucination_rate = unverified / total
```

## Bridge exports

| Export | Type | Used by |
|--------|------|---------|
| `contradiction_tool` | CrewAI BaseTool | Punith's agents |
| `citation_tool` | CrewAI BaseTool | Punith's agents |
| `rag_index_tool` | CrewAI BaseTool | Punith's agents |
| `run_full_analysis()` | plain function | Shashank's server.py |
| `get_graph_for_export()` | plain function | Shashank's redline.py |

## Qdrant vs InMemoryRAG

- **Qdrant** — production vector DB, requires Docker on port 6333
- **InMemoryRAG** — pure numpy fallback, works with no external services, used automatically when Qdrant is unavailable

## How to test standalone

```bash
# From project root
python memory/rag.py      # RAG smoke test
python memory/bridge.py   # Bridge smoke test
python memory/reset_between_docs.py
```

## Talks to

- `schemas.py` — imports `Clause`, `CitationResult`
- `logic/validator.py` — bridge calls `validate_clauses()`
