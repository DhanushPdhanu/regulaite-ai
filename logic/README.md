# Logic Layer

**Owner:** Ullas (Hacker 4)
**Technology:** Z3 SMT Solver, Python regex, itertools

## Files

| File | Purpose |
|------|---------|
| `validator.py` | Z3 formal contradiction detector — proves when two clauses cannot simultaneously hold |
| `__init__.py` | Package marker |

## How it works

1. **Tag extraction** — regex patterns map clause text to logical tags with polarity
   - e.g. "liability is limited" → `{liability_limited: +1}`
   - e.g. "no limit on liability" → `{liability_limited: -1}`

2. **Pairwise Z3 check** — for every pair of clauses, if they assert opposite polarities
   for the same tag, Z3 proves UNSAT (both cannot hold simultaneously)

3. **Circular obligation detection** — DFS on cross-reference graph detects cycles
   like "Clause A subject to Clause B, Clause B subject to Clause A"

## Contradiction types

| Type | Meaning |
|------|---------|
| `MUTUAL_EXCLUSION` | Two clauses assert opposite facts (e.g. liability capped vs uncapped) |
| `LOGICAL_DEAD_END` | Governing law in one country, jurisdiction in another |
| `CIRCULAR_OBLIGATION` | A → B → C → A dependency cycle |

## How to test standalone

```bash
# From project root
python logic/validator.py
```

## Talks to

- `schemas.py` — imports `Clause`, `ContradictionResult`
- Called by `memory/bridge.py` → `validate_clauses(clauses)`
