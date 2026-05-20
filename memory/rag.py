import os
import uuid
import hashlib
import sys

# Force HuggingFace to use local cache — prevents SSL errors on corporate networks
# The model (all-MiniLM-L6-v2) is cached in ~/.cache/huggingface/hub/
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Ensure regulaite/ root is on sys.path for `from schemas import ...`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Optional
from dotenv import load_dotenv
import networkx as nx
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
)
from schemas import Clause, CitationResult

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
QDRANT_HOST       = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT       = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME   = os.getenv("QDRANT_COLLECTION", "lexai_clauses")
EMBEDDING_MODEL   = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
VECTOR_DIM        = 384          # all-MiniLM-L6-v2 output dimension
SIMILARITY_THRESH = 0.55         # min cosine score to accept as a valid citation
TOP_K             = 5            # number of candidates to retrieve per query

# ── Singleton helpers ─────────────────────────────────────────────────────────
_embedder: Optional[SentenceTransformer] = None
_qdrant:   Optional[QdrantClient]        = None
citation_graph: nx.DiGraph = nx.DiGraph()   # shared graph — imported by redline.py


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def _get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _qdrant


# ── Collection bootstrap ──────────────────────────────────────────────────────
def _ensure_collection() -> None:
    """Create Qdrant collection if it does not exist."""
    client = _get_qdrant()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )


# ── Stable UUID from clause_id ────────────────────────────────────────────────
def _clause_uuid(clause_id: str) -> str:
    """Deterministic UUID so re-indexing the same clause overwrites cleanly."""
    hex_digest = hashlib.md5(clause_id.encode()).hexdigest()
    return str(uuid.UUID(hex_digest))


# ── Indexing ──────────────────────────────────────────────────────────────────
def index_clauses(clauses: List[Clause]) -> int:
    """Embed all clauses and upsert into Qdrant.
    Returns the number of clauses successfully indexed.
    Called by Shashank's ingestion pipeline after parsing."""
    if not clauses:
        return 0

    _ensure_collection()
    embedder = _get_embedder()
    client   = _get_qdrant()

    texts   = [c.text for c in clauses]
    vectors = embedder.encode(texts, show_progress_bar=False, normalize_embeddings=True)

    points = []
    for clause, vector in zip(clauses, vectors):
        points.append(PointStruct(
            id=_clause_uuid(clause.clause_id),
            vector=vector.tolist(),
            payload={
                "clause_id":     clause.clause_id,
                "clause_number": clause.clause_number,
                "page_number":   clause.page_number,
                "section":       clause.section,
                "text":          clause.text,
                "risk_score":    clause.risk_score,
                "flags":         clause.flags,
            },
        ))

    client.upsert(collection_name=COLLECTION_NAME, points=points)

    # Add nodes to the citation graph (edges added during verify_claim)
    for clause in clauses:
        citation_graph.add_node(
            clause.clause_id,
            clause_number=clause.clause_number,
            section=clause.section,
            page=clause.page_number,
        )

    return len(points)


# ── Verification ──────────────────────────────────────────────────────────────
def verify_claim(
    claim_text: str,
    source_clause_id: Optional[str] = None,
) -> CitationResult:
    """Given an agent's claim (natural language), find the best-matching clause
    in Qdrant and decide if the claim is grounded (verified=True) or hallucinated.

    source_clause_id: if provided, this is the clause the agent says it is citing.
    We verify BOTH similarity AND that it matches the retrieved top hit."""
    _ensure_collection()
    embedder = _get_embedder()
    client   = _get_qdrant()

    # Embed the claim
    query_vector = embedder.encode(claim_text, normalize_embeddings=True).tolist()

    # Search Qdrant
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=TOP_K,
        with_payload=True,
    )

    if not results:
        return CitationResult(
            claim=claim_text,
            source_clause_id=source_clause_id or "UNKNOWN",
            source_page=0,
            source_text_excerpt="[No clauses indexed]",
            confidence_score=0.0,
            verified=False,
        )

    top      = results[0]
    score    = float(top.score)
    payload  = top.payload
    verified = score >= SIMILARITY_THRESH

    # Negation-aware check: if the claim semantically contradicts the matched clause
    # (e.g. claim says "can share publicly" but clause says "must not disclose"),
    # downgrade to unverified.
    _NEGATION_PAIRS = [
        ({"no restriction", "publicly", "freely share", "no limit", "unlimited"},
         {"confidential", "must not", "prohibited", "restricted", "limited"}),
        ({"no liability", "unlimited liability", "full liability"},
         {"limited", "capped", "maximum"}),
    ]
    claim_lower  = claim_text.lower()
    clause_lower = payload["text"].lower()
    for claim_keywords, clause_keywords in _NEGATION_PAIRS:
        claim_hit  = any(kw in claim_lower  for kw in claim_keywords)
        clause_hit = any(kw in clause_lower for kw in clause_keywords)
        if claim_hit and clause_hit:
            verified = False
            score    = score * 0.5
            break

    # If agent cited a specific clause, cross-check
    if source_clause_id and payload["clause_id"] != source_clause_id:
        # Agent cited a different clause than the best semantic match
        # Downgrade confidence if the stated clause is not in top-K results
        stated_ids = [r.payload["clause_id"] for r in results]
        if source_clause_id not in stated_ids:
            verified = False
            score    = score * 0.5   # penalise: stated clause not found nearby

    # Build excerpt (first 200 chars)
    excerpt = payload["text"][:200] + ("..." if len(payload["text"]) > 200 else "")

    # Record in citation graph
    used_clause_id = payload["clause_id"]
    claim_node     = f"claim::{hashlib.md5(claim_text.encode()).hexdigest()[:8]}"
    citation_graph.add_node(claim_node, type="claim", text=claim_text[:80])
    citation_graph.add_edge(
        claim_node,
        used_clause_id,
        weight=score,
        verified=verified,
    )

    return CitationResult(
        claim=claim_text,
        source_clause_id=used_clause_id,
        source_page=payload["page_number"],
        source_text_excerpt=excerpt,
        confidence_score=round(score, 4),
        verified=verified,
    )


# ── Batch verification ────────────────────────────────────────────────────────
def verify_claims_batch(claims: List[str]) -> List[CitationResult]:
    """Verify a list of claims. Used by Punith's agent after analysis."""
    return [verify_claim(c) for c in claims]


# ── Citation graph utilities ──────────────────────────────────────────────────
def get_citation_summary() -> dict:
    """Returns a summary of the citation graph.
    Called by Shashank's redline.py for the audit trail section."""
    total_claims     = sum(1 for n, d in citation_graph.nodes(data=True) if "claim" in str(d.get("type", "")))
    total_clauses    = sum(1 for n in citation_graph.nodes if not str(n).startswith("claim::"))
    verified_edges   = sum(1 for _, _, d in citation_graph.edges(data=True) if d.get("verified"))
    unverified_edges = sum(1 for _, _, d in citation_graph.edges(data=True) if not d.get("verified"))

    return {
        "total_claims_made":     total_claims,
        "total_clauses_indexed": total_clauses,
        "verified_citations":    verified_edges,
        "unverified_citations":  unverified_edges,
        "hallucination_rate":    (
            round(unverified_edges / (verified_edges + unverified_edges), 4)
            if (verified_edges + unverified_edges) > 0 else 0.0
        ),
        "graph_nodes": citation_graph.number_of_nodes(),
        "graph_edges": citation_graph.number_of_edges(),
    }


def get_most_cited_clauses(top_n: int = 5) -> List[dict]:
    """Returns the top N clauses referenced most by agent claims."""
    clause_nodes = [
        n for n in citation_graph.nodes
        if not str(n).startswith("claim::")
    ]
    ranked = sorted(
        clause_nodes,
        key=lambda n: citation_graph.in_degree(n),
        reverse=True,
    )[:top_n]

    return [
        {
            "clause_id":    n,
            "times_cited":  citation_graph.in_degree(n),
            "section":      citation_graph.nodes[n].get("section", ""),
            "page":         citation_graph.nodes[n].get("page", 0),
        }
        for n in ranked
    ]


def reset_collection() -> None:
    """Wipe and recreate the Qdrant collection. Use between documents."""
    global citation_graph
    client = _get_qdrant()
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        client.delete_collection(COLLECTION_NAME)
    _ensure_collection()
    citation_graph = nx.DiGraph()


# ── In-memory fallback (if Qdrant is not running) ─────────────────────────────
class InMemoryRAG:
    """Fallback RAG using pure numpy cosine similarity.
    Activated automatically if Qdrant connection fails.
    Used during demo if Docker is not available."""

    def __init__(self):
        self.embedder = _get_embedder()
        self.store: List[dict] = []

    def index(self, clauses: List[Clause]) -> int:
        import numpy as np
        for clause in clauses:
            vec = self.embedder.encode(clause.text, normalize_embeddings=True)
            self.store.append({"clause": clause, "vector": vec})
            citation_graph.add_node(
                clause.clause_id,
                clause_number=clause.clause_number,
                section=clause.section,
                page=clause.page_number,
            )
        return len(clauses)

    def verify(self, claim_text: str) -> CitationResult:
        import numpy as np
        if not self.store:
            return CitationResult(
                claim=claim_text, source_clause_id="UNKNOWN",
                source_page=0, source_text_excerpt="[empty store]",
                confidence_score=0.0, verified=False,
            )

        q      = self.embedder.encode(claim_text, normalize_embeddings=True)
        scores = [float(np.dot(q, item["vector"])) for item in self.store]
        best_idx    = int(np.argmax(scores))
        best_score  = scores[best_idx]
        best_clause = self.store[best_idx]["clause"]
        verified    = best_score >= SIMILARITY_THRESH

        # Negation-aware check (mirrors verify_claim logic)
        _NEGATION_PAIRS = [
            ({"no restriction", "publicly", "freely share", "no limit", "unlimited"},
             {"confidential", "must not", "prohibited", "restricted", "limited"}),
            ({"no liability", "unlimited liability", "full liability"},
             {"limited", "capped", "maximum"}),
        ]
        claim_lower  = claim_text.lower()
        clause_lower = best_clause.text.lower()
        for claim_keywords, clause_keywords in _NEGATION_PAIRS:
            claim_hit  = any(kw in claim_lower  for kw in claim_keywords)
            clause_hit = any(kw in clause_lower for kw in clause_keywords)
            if claim_hit and clause_hit:
                verified   = False
                best_score = best_score * 0.5
                break

        excerpt     = best_clause.text[:200] + ("..." if len(best_clause.text) > 200 else "")

        # Record in citation graph
        claim_node = f"claim::{hashlib.md5(claim_text.encode()).hexdigest()[:8]}"
        citation_graph.add_node(claim_node, type="claim", text=claim_text[:80])
        citation_graph.add_edge(
            claim_node,
            best_clause.clause_id,
            weight=best_score,
            verified=verified,
        )

        return CitationResult(
            claim=claim_text,
            source_clause_id=best_clause.clause_id,
            source_page=best_clause.page_number,
            source_text_excerpt=excerpt,
            confidence_score=round(best_score, 4),
            verified=verified,
        )


def get_rag_backend(clauses: Optional[List[Clause]] = None):
    """Returns (index_fn, verify_fn).
    Tries Qdrant first; falls back to InMemoryRAG silently.
    Punith's agents call this — they don't need to know which backend is used."""
    try:
        client = _get_qdrant()
        client.get_collections()   # ping
        if clauses:
            index_clauses(clauses)
        return index_clauses, verify_claim
    except Exception:
        mem = InMemoryRAG()
        if clauses:
            mem.index(clauses)
        return mem.index, mem.verify


# ── Standalone smoke test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    from schemas import Clause

    test_clauses = [
        Clause(
            clause_id="clause_3_1", page_number=1, clause_number="3.1",
            text="The Company's liability is strictly limited to fees paid in the last 12 months.",
            section="Liability"
        ),
        Clause(
            clause_id="clause_5_1", page_number=2, clause_number="5.1",
            text="Either party may terminate this agreement with 90 days written notice.",
            section="Termination"
        ),
        Clause(
            clause_id="clause_7_1", page_number=3, clause_number="7.1",
            text="All data shared under this agreement is strictly confidential and must not be disclosed.",
            section="Confidentiality"
        ),
        Clause(
            clause_id="clause_9_1", page_number=4, clause_number="9.1",
            text="This agreement auto-renews annually unless cancelled 30 days before expiry.",
            section="Renewal"
        ),
        Clause(
            clause_id="clause_11_1", page_number=5, clause_number="11.1",
            text="Vendor indemnifies the client against all third-party claims arising from negligence.",
            section="Indemnification"
        ),
    ]

    print("=== RegulAIte RAG Smoke Test ===\n")

    # Use in-memory fallback (no Docker needed for smoke test)
    mem_rag = InMemoryRAG()
    indexed = mem_rag.index(test_clauses)
    print(f"Indexed {indexed} clauses into InMemoryRAG\n")

    test_claims = [
        "The company's liability is limited to fees paid in the last 12 months.",   # close paraphrase
        "Either side can exit this contract by giving advance notice.",
        "Sensitive information cannot be shared with outside parties.",
        "This agreement auto-renews annually unless cancelled before expiry.",       # close paraphrase
        "The vendor is responsible for protecting the client from lawsuits.",
        "The vendor can share all data publicly with no restrictions.",              # hallucination
    ]

    print("Verifying claims:\n")
    for claim in test_claims:
        result = mem_rag.verify(claim)
        status = "✓ VERIFIED" if result.verified else "✗ HALLUCINATION"
        print(f"  {status}  (score={result.confidence_score})")
        print(f"  Claim  : {claim}")
        print(f"  Matched: Clause {result.source_clause_id} — {result.source_text_excerpt[:80]}...")
        print()

    summary = get_citation_summary()
    print("Citation Graph Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    top = get_most_cited_clauses(3)
    print("\nMost Cited Clauses:")
    for entry in top:
        print(f"  {entry['clause_id']} — cited {entry['times_cited']} time(s)")
