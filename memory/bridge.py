"""bridge.py — CrewAI Tool wrappers for Ullas's validator + RAG modules.

Exports:
    contradiction_tool   → CrewAI Tool  (used by Punith's ContradictionAgent)
    citation_tool        → CrewAI Tool  (used by Punith's CitationVerifierAgent)
    rag_index_tool       → CrewAI Tool  (used by Punith's pipeline setup)
    get_graph_for_export → plain fn     (used by Shashank's redline.py)
    run_full_analysis    → plain fn     (used by Shashank's server.py endpoint)
"""

import os
import sys

# Ensure regulaite/ root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from typing import List, Dict, Any, Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from schemas import Clause, ContradictionResult, CitationResult
from logic.validator import validate_clauses
from memory.rag import (
    InMemoryRAG,
    get_rag_backend,
    citation_graph,
    get_citation_summary,
    get_most_cited_clauses,
)

# ── Module-level RAG instance (shared across tools in one run) ─────────────────
_rag_instance: Optional[InMemoryRAG] = None
_indexed_clauses: List[Clause] = []


def _get_rag() -> InMemoryRAG:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = InMemoryRAG()
    return _rag_instance


# ── Tool Input Schemas ─────────────────────────────────────────────────────────
class ClausesInput(BaseModel):
    clauses_json: str = Field(
        description="JSON string of a list of Clause objects serialized with .model_dump()"
    )


class ClaimInput(BaseModel):
    claim_text: str = Field(
        description="A natural language claim made by an agent about the contract"
    )
    source_clause_id: Optional[str] = Field(
        default=None,
        description="Optional clause_id the agent believes supports this claim",
    )


class ClaimsListInput(BaseModel):
    claims_json: str = Field(
        description="JSON string of a list of claim strings to verify in batch"
    )


# ── Tool 1: Contradiction Detector ────────────────────────────────────────────
class ContradictionTool(BaseTool):
    name: str = "ContradictionDetector"
    description: str = (
        "Detects logical contradictions between contract clauses using the Z3 SMT solver. "
        "Input: JSON list of Clause objects. "
        "Output: JSON list of ContradictionResult objects with clause pairs, "
        "contradiction type (MUTUAL_EXCLUSION / LOGICAL_DEAD_END / CIRCULAR_OBLIGATION), "
        "and formal Z3 proof. Use this after all clauses are extracted from a document."
    )
    args_schema: type[BaseModel] = ClausesInput

    def _run(self, clauses_json: str) -> str:
        try:
            raw = json.loads(clauses_json)
            clauses = [Clause(**c) for c in raw]
            results: List[ContradictionResult] = validate_clauses(clauses)
            return json.dumps(
                [r.model_dump() for r in results],
                indent=2,
                default=str,
            )
        except Exception as e:
            return json.dumps({"error": str(e), "contradictions": []})


# ── Tool 2: Claim Citation Verifier ───────────────────────────────────────────
class CitationTool(BaseTool):
    name: str = "CitationVerifier"
    description: str = (
        "Verifies whether an agent's claim about a contract is grounded in an actual clause. "
        "Uses semantic similarity search (RAG) to find the best-matching clause. "
        "Returns a CitationResult with verified=True if the claim is supported, "
        "verified=False if it appears to be a hallucination. "
        "ALWAYS call this before reporting any finding about a specific clause."
    )
    args_schema: type[BaseModel] = ClaimInput

    def _run(self, claim_text: str, source_clause_id: Optional[str] = None) -> str:
        try:
            rag = _get_rag()
            if not rag.store:
                return json.dumps({
                    "error": "RAG store is empty. Call RagIndexTool first.",
                    "verified": False,
                })
            result: CitationResult = rag.verify(claim_text)
            return json.dumps(result.model_dump(), indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e), "verified": False})


# ── Tool 3: RAG Indexer ───────────────────────────────────────────────────────
class RagIndexTool(BaseTool):
    name: str = "RagIndexTool"
    description: str = (
        "Indexes contract clauses into the RAG vector store so CitationVerifier can work. "
        "Must be called ONCE at the start of each document analysis, before any other tools. "
        "Input: JSON list of Clause objects. "
        "Output: Confirmation message with count of indexed clauses."
    )
    args_schema: type[BaseModel] = ClausesInput

    def _run(self, clauses_json: str) -> str:
        global _rag_instance, _indexed_clauses
        try:
            raw = json.loads(clauses_json)
            clauses = [Clause(**c) for c in raw]
            # Fresh instance per document
            _rag_instance = InMemoryRAG()
            count = _rag_instance.index(clauses)
            _indexed_clauses = clauses
            return json.dumps({
                "status": "indexed",
                "clauses_indexed": count,
                "message": f"RAG store ready. {count} clauses indexed. CitationVerifier is now active.",
            })
        except Exception as e:
            return json.dumps({"error": str(e), "status": "failed"})


# ── Instantiate tools for import ──────────────────────────────────────────────
contradiction_tool = ContradictionTool()
citation_tool      = CitationTool()
rag_index_tool     = RagIndexTool()


# ── Plain function: used by Shashank's redline.py ─────────────────────────────
def get_graph_for_export() -> Dict[str, Any]:
    """Returns citation graph data serialized for the audit trail in redline exports.
    Shashank imports this directly — not a CrewAI tool."""
    nodes = [
        {
            "id":      n,
            "type":    "claim" if str(n).startswith("claim::") else "clause",
            "section": citation_graph.nodes[n].get("section", ""),
            "page":    citation_graph.nodes[n].get("page", 0),
            "text":    citation_graph.nodes[n].get("text", ""),
        }
        for n in citation_graph.nodes
    ]
    edges = [
        {
            "from":     u,
            "to":       v,
            "weight":   round(d.get("weight", 0), 4),
            "verified": d.get("verified", False),
        }
        for u, v, d in citation_graph.edges(data=True)
    ]
    summary   = get_citation_summary()
    top_cited = get_most_cited_clauses(5)
    return {
        "nodes":     nodes,
        "edges":     edges,
        "summary":   summary,
        "top_cited": top_cited,
    }


# ── Plain function: used by Shashank's server.py POST /analyse endpoint ───────
def run_full_analysis(clauses: List[Clause]) -> Dict[str, Any]:
    """One-shot analysis combining contradiction detection + RAG indexing.
    server.py calls this after Shashank's parser returns clauses.
    Returns a combined result dict ready to be serialised as the API response."""
    global _rag_instance, _indexed_clauses

    # Step 1: Index into RAG
    _rag_instance = InMemoryRAG()
    indexed_count = _rag_instance.index(clauses)
    _indexed_clauses = clauses

    # Step 2: Contradiction detection
    contradictions = validate_clauses(clauses)

    # Step 3: Auto-verify one claim per clause (proof of concept)
    citation_results = []
    for clause in clauses:
        claim = f"The contract states: {clause.text[:120]}"
        result = _rag_instance.verify(claim)
        citation_results.append(result.model_dump())

    # Step 4: Graph export
    graph_data = get_graph_for_export()

    return {
        "clauses_analysed":    indexed_count,
        "contradictions_found": len(contradictions),
        "contradictions":      [c.model_dump() for c in contradictions],
        "citation_results":    citation_results,
        "citation_graph":      graph_data,
        "hallucination_rate":  graph_data["summary"].get("hallucination_rate", 0.0),
    }


# ── Standalone smoke test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    from schemas import Clause

    print("=== Bridge Smoke Test ===\n")

    test_clauses = [
        Clause(clause_id="c1", page_number=1, clause_number="3.1",
               text="Liability is limited to fees paid in the last 12 months.",
               section="Liability"),
        Clause(clause_id="c2", page_number=2, clause_number="3.2",
               text="There is no limit on liability for any damages under this agreement.",
               section="Liability"),
        Clause(clause_id="c3", page_number=3, clause_number="7.1",
               text="Either party may terminate at will without cause immediately.",
               section="Termination"),
        Clause(clause_id="c4", page_number=4, clause_number="7.2",
               text="A 90-day notice period is required before termination.",
               section="Termination"),
        Clause(clause_id="c5", page_number=5, clause_number="9.1",
               text="All data shared is strictly confidential and must not be disclosed.",
               section="Confidentiality"),
    ]

    clauses_json = json.dumps([c.model_dump() for c in test_clauses])

    # Test Tool 1: RAG Index
    print("-- RagIndexTool --")
    result = rag_index_tool._run(clauses_json=clauses_json)
    print(result)

    # Test Tool 2: Contradiction detection
    print("\n-- ContradictionTool --")
    result = contradiction_tool._run(clauses_json=clauses_json)
    parsed = json.loads(result)
    print(f"Contradictions found: {len(parsed)}")
    for c in parsed:
        print(f"  {c['clause_id_a']} ↔ {c['clause_id_b']} : {c['contradiction_type']}")

    # Test Tool 3: Citation verification
    print("\n-- CitationTool (verified claim) --")
    result = citation_tool._run(claim_text="The vendor financial liability is capped under this contract.")
    print(json.loads(result))

    print("\n-- CitationTool (hallucination attempt) --")
    result = citation_tool._run(claim_text="The vendor can publicly share all client data with anyone.")
    r = json.loads(result)
    print(f"verified: {r['verified']}, score: {r['confidence_score']}")

    # Test run_full_analysis
    print("\n-- run_full_analysis --")
    analysis = run_full_analysis(test_clauses)
    print(f"Clauses analysed    : {analysis['clauses_analysed']}")
    print(f"Contradictions found: {analysis['contradictions_found']}")
    print(f"Hallucination rate  : {analysis['hallucination_rate']}")
    print(f"Graph nodes         : {analysis['citation_graph']['summary']['graph_nodes']}")

    # Test get_graph_for_export
    print("\n-- get_graph_for_export --")
    graph = get_graph_for_export()
    print(f"Nodes: {len(graph['nodes'])}, Edges: {len(graph['edges'])}")
    print(f"Summary: {graph['summary']}")

    print("\n=== Bridge Smoke Test COMPLETE ===")
