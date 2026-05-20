import re
import itertools
import sys
import os
from typing import List, Tuple, Optional

# Ensure the regulaite/ package root is on sys.path so `schemas` is importable
# whether this file is run directly (python logic/validator.py) or imported
# as a module (from logic.validator import validate_clauses).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from z3 import (Solver, Bool, BoolRef, And, Or, Not, Implies,
                sat, unsat, unknown, ArithRef, Int, Real)
from schemas import Clause, ContradictionResult

# ── Pattern registry ──────────────────────────────────────────────────────────
# Each tuple: (regex_pattern, logical_tag, z3_polarity)
# polarity: +1 = clause asserts this tag, -1 = clause negates this tag
CLAUSE_PATTERNS: List[Tuple[str, str, int]] = [
    # Liability
    (r"\blimit(s|ed)?\s+(liability|damages)\b",              "liability_limited",    +1),
    (r"\b(liability|damages)\s+(is\s+)?limit(s|ed)\b",       "liability_limited",    +1),
    (r"\bno\s+limit\s+on\s+(liability|damages)\b",           "liability_limited",    -1),
    (r"\bfull\s+liability\b",                                 "liability_limited",    -1),
    (r"\bunderlimit(ed)?\b",                                   "liability_unlimited",  +1),
    # Termination
    (r"\bterminate\s+(at\s+will|immediately|without\s+cause)\b", "term_at_will",     +1),
    (r"\b(cannot|may\s+not)\s+terminate\b",                  "term_at_will",         -1),
    (r"\b(\d+)[- ]day\s+notice\s+(period\s+)?(is\s+)?required\b", "notice_required", +1),
    (r"\bno\s+notice\s+required\b",                          "notice_required",      -1),
    (r"\bwithout\s+notice\b",                                "notice_required",      -1),
    # "terminate at will / immediately / without cause" also implies no notice required
    (r"\bterminate\s+(at\s+will|immediately|without\s+cause)\b", "notice_required",  -1),
    # Auto-renewal
    (r"\bauto[- ]renew(al|s|ed)?\b",                     "auto_renewal",         +1),
    (r"\bno\s+auto[- ]renew(al)?\b",                     "auto_renewal",         -1),
    (r"\bmanual\s+renew(al)?\s+only\b",                  "auto_renewal",         -1),
    # Exclusivity
    (r"\bexclusive\s+(rights?|license|agreement)\b",     "exclusive",            +1),
    (r"\bnon[- ]exclusive\b",                             "exclusive",            -1),
    # Confidentiality
    (r"\bconfidential(ity)?\s+(obligation|clause|terms?)\b", "confidential",     +1),
    (r"\bno\s+confidential(ity)?\s+obligation\b",        "confidential",         -1),
    (r"\bpublic\s+disclosure\s+permitted\b",              "confidential",         -1),
    # Governing law
    (r"\bgoverned\s+by\s+(the\s+laws?\s+of\s+)?(\w+)",  "has_governing_law",    +1),
    (r"\bno\s+governing\s+law\s+specified\b",            "has_governing_law",    -1),
    # Indemnification
    (r"\bindemnif(y|ies|ication)\b",                     "indemnification",      +1),
    (r"\bno\s+indemnif(y|ication)\b",                    "indemnification",      -1),
    # Payment
    (r"\bpayment\s+(is\s+)?(non[- ]refundable|final)\b","refundable",           -1),
    (r"\bfully\s+refundable\b",                          "refundable",            +1),
    (r"\bpro[- ]rata\s+refund\b",                        "refundable",            +1),
]

CONTRADICTION_TYPES = {
    "liability_limited":   "MUTUAL_EXCLUSION",
    "term_at_will":        "MUTUAL_EXCLUSION",
    "notice_required":     "MUTUAL_EXCLUSION",
    "auto_renewal":        "MUTUAL_EXCLUSION",
    "exclusive":           "MUTUAL_EXCLUSION",
    "confidential":        "MUTUAL_EXCLUSION",
    "has_governing_law":   "LOGICAL_DEAD_END",
    "indemnification":     "MUTUAL_EXCLUSION",
    "refundable":          "MUTUAL_EXCLUSION",
}

# ── Tag extraction ─────────────────────────────────────────────────────────────
def extract_tags(text: str) -> dict[str, int]:
    """Returns {tag: polarity} for every pattern matched in text.
    If same tag matched with conflicting polarities, last match wins."""
    text_lower = text.lower()
    tags: dict[str, int] = {}
    for pattern, tag, polarity in CLAUSE_PATTERNS:
        if re.search(pattern, text_lower):
            tags[tag] = polarity
    return tags


# ── Z3 encoding ───────────────────────────────────────────────────────────────
def _build_z3_assertion(tag: str, polarity: int, var_map: dict) -> BoolRef:
    if tag not in var_map:
        var_map[tag] = Bool(tag)
    var = var_map[tag]
    return var if polarity == +1 else Not(var)


def _check_pair(
    clause_a: Clause,
    clause_b: Clause,
    tags_a: dict[str, int],
    tags_b: dict[str, int],
    var_map: dict,
) -> Optional[ContradictionResult]:
    """For each shared tag, check if clause_a and clause_b assert opposite polarities.
    Uses Z3 to prove UNSAT."""
    shared_tags = set(tags_a.keys()) & set(tags_b.keys())
    if not shared_tags:
        return None

    for tag in shared_tags:
        pol_a = tags_a[tag]
        pol_b = tags_b[tag]
        if pol_a == pol_b:
            continue  # same polarity — no contradiction

        # Opposite polarities found — run Z3
        s = Solver()
        assertion_a = _build_z3_assertion(tag, pol_a, var_map)
        assertion_b = _build_z3_assertion(tag, pol_b, var_map)
        s.add(assertion_a)
        s.add(assertion_b)
        result = s.check()

        if result == unsat:
            z3_proof = (
                f"Assert: {tag} = {'TRUE' if pol_a == 1 else 'FALSE'} (Clause {clause_a.clause_number})\n"
                f"Assert: {tag} = {'TRUE' if pol_b == 1 else 'FALSE'} (Clause {clause_b.clause_number})\n"
                f"Z3 Result: UNSAT — both cannot hold simultaneously"
            )
            ctype = CONTRADICTION_TYPES.get(tag, "MUTUAL_EXCLUSION")
            return ContradictionResult(
                clause_id_a=clause_a.clause_id,
                clause_id_b=clause_b.clause_id,
                contradiction_type=ctype,
                explanation=(
                    f"Clauses {clause_a.clause_number} and {clause_b.clause_number} "
                    f"contradict each other on '{tag}': "
                    f"Clause {clause_a.clause_number} asserts it {'TRUE' if pol_a==1 else 'FALSE'}, "
                    f"Clause {clause_b.clause_number} asserts it {'TRUE' if pol_b==1 else 'FALSE'}."
                ),
                z3_proof=z3_proof,
            )
    return None


# ── Circular obligation detector ──────────────────────────────────────────────
def _detect_circular_obligations(clauses: List[Clause]) -> List[ContradictionResult]:
    """Detects patterns like: A requires B → B requires C → C requires A.
    Uses simple regex to build a dependency graph and detect cycles."""
    results = []

    # Build map: clause_id → list of clause_ids it references
    ref_pattern = re.compile(
        r"(?:subject\s+to|pursuant\s+to|as\s+defined\s+in|see\s+clause|per\s+clause|"
        r"under\s+clause|in\s+accordance\s+with\s+clause)\s+(\d+(?:\.\d+)?)",
        re.IGNORECASE,
    )

    # Map clause_number → clause_id
    num_to_id = {c.clause_number: c.clause_id for c in clauses}
    dep_graph: dict[str, list[str]] = {c.clause_id: [] for c in clauses}

    for clause in clauses:
        matches = ref_pattern.findall(clause.text)
        for ref_num in matches:
            if ref_num in num_to_id and num_to_id[ref_num] != clause.clause_id:
                dep_graph[clause.clause_id].append(num_to_id[ref_num])

    # DFS cycle detection
    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycle_pairs: list[tuple[str, str]] = []

    def dfs(node: str, path: list[str]):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        for neighbor in dep_graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path)
            elif neighbor in rec_stack:
                # Found a cycle — report the entry point pair
                idx = path.index(neighbor)
                cycle_pairs.append((neighbor, node))
        path.pop()
        rec_stack.discard(node)

    for cid in dep_graph:
        if cid not in visited:
            dfs(cid, [])

    # Build results
    reported: set[frozenset] = set()
    for cid_a, cid_b in cycle_pairs:
        key = frozenset([cid_a, cid_b])
        if key in reported:
            continue
        reported.add(key)
        results.append(
            ContradictionResult(
                clause_id_a=cid_a,
                clause_id_b=cid_b,
                contradiction_type="CIRCULAR_OBLIGATION",
                explanation=(
                    f"Clause {cid_a} and {cid_b} form a circular dependency chain. "
                    "Neither obligation can be independently fulfilled."
                ),
                z3_proof="Cycle detected via DFS on clause cross-reference graph.",
            )
        )
    return results


# ── Public API ────────────────────────────────────────────────────────────────
def validate_clauses(clauses: List[Clause]) -> List[ContradictionResult]:
    """Main entry point called by Punith's CrewAI agent.
    Accepts List[Clause], returns List[ContradictionResult]."""
    if not clauses:
        return []

    results: List[ContradictionResult] = []
    var_map: dict = {}

    # Step 1: Extract tags for every clause
    clause_tags = {c.clause_id: extract_tags(c.text) for c in clauses}

    # Step 2: Pairwise Z3 contradiction check
    for clause_a, clause_b in itertools.combinations(clauses, 2):
        tags_a = clause_tags[clause_a.clause_id]
        tags_b = clause_tags[clause_b.clause_id]
        contradiction = _check_pair(clause_a, clause_b, tags_a, tags_b, var_map)
        if contradiction:
            results.append(contradiction)

    # Step 3: Circular obligation check
    circular = _detect_circular_obligations(clauses)
    results.extend(circular)

    return results


# ── Standalone smoke test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    test_clauses = [
        Clause(
            clause_id="clause_3_1", page_number=1, clause_number="3.1",
            text="The Company's liability is limited to the total fees paid in the preceding 12 months.",
            section="Liability",
        ),
        Clause(
            clause_id="clause_3_2", page_number=2, clause_number="3.2",
            text="There is no limit on liability for any damages arising from this agreement.",
            section="Liability",
        ),
        Clause(
            clause_id="clause_7_1", page_number=4, clause_number="7.1",
            text="Either party may terminate at will without cause and without notice required.",
            section="Termination",
        ),
        Clause(
            clause_id="clause_7_2", page_number=4, clause_number="7.2",
            text="A 90-day notice period is required before termination of this contract.",
            section="Termination",
        ),
        Clause(
            clause_id="clause_9_1", page_number=5, clause_number="9.1",
            text="This agreement grants exclusive rights to the licensee for all regions.",
            section="License",
        ),
        Clause(
            clause_id="clause_9_2", page_number=6, clause_number="9.2",
            text="This license is non-exclusive and the licensor may grant similar rights to others.",
            section="License",
        ),
    ]

    print("Running Z3 contradiction detection on 6 test clauses...\n")
    contradictions = validate_clauses(test_clauses)

    if not contradictions:
        print("No contradictions found.")
    else:
        for i, c in enumerate(contradictions, 1):
            print(f"CONTRADICTION {i}:")
            print(f"  Type       : {c.contradiction_type}")
            print(f"  Clauses    : {c.clause_id_a}  ↔  {c.clause_id_b}")
            print(f"  Explanation: {c.explanation}")
            print(f"  Z3 Proof   :\n{c.z3_proof}")
            print()

    print(f"Total contradictions found: {len(contradictions)}")
