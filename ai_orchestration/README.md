# AI Orchestration Layer

**Owner:** Punith (Hacker 3)
**Technology:** CrewAI, Anthropic Claude, LangChain

## Files

| File | Purpose |
|------|---------|
| `agents/crew.py` | 3-agent CrewAI pipeline: RiskAgent → ComplianceAgent → FixerAgent |
| `agents/__init__.py` | Package marker |

## Agent Pipeline

```
List[Clause]
    │
    ▼
Pre-scoring engine     ← deterministic regex patterns (no API key needed)
    │
    ▼
Z3 contradiction boost ← from logic/ via memory/bridge.py
    │
    ▼
RiskAgent (Claude)     ← scores each clause 0-100, assigns flags
    │
    ▼
ComplianceAgent (Claude) ← finds GDPR, labour law, IP violations
    │
    ▼
FixerAgent (Claude)    ← rewrites dangerous clauses to balanced language
    │
    ▼
Returns: {compliance_violations, fixed_clauses}
```

## Stub mode (no API key)

When `ANTHROPIC_API_KEY` is not set or is a placeholder, the pipeline
automatically falls back to the deterministic pre-scoring + legal citation
engines. You still get real violations and rewrites — just without LLM refinement.

## How to test standalone

```bash
# From project root
python agents/crew.py
```

## Talks to

- `schemas.py` — imports `Clause` model
- `memory/bridge.py` — uses `contradiction_tool`, `citation_tool`, `rag_index_tool`
- `logic/validator.py` — indirectly via bridge tools
