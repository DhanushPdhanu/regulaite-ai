"""
handshake_check.py — Cross-hacker integration verification for RegulAIte.
# -*- coding: utf-8 -*-

Run this before every demo to confirm all 4 hackers' modules are
loaded and the full pipeline works end-to-end.

Usage:
    cd regulaite
    python handshake_check.py

All checks must show ✓ before the demo starts.
"""

import sys
import os
import glob
import importlib
from pathlib import Path

# Add repo root to path
ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

PASS_COUNT = 0
FAIL_COUNT = 0
WARN_COUNT = 0


def passed(label: str):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"  \u2713  {label}")


def failed(label: str, detail: str = "", blocker: bool = True):
    global FAIL_COUNT, WARN_COUNT
    if blocker:
        FAIL_COUNT += 1
        print(f"  \u2717  {label}")
    else:
        WARN_COUNT += 1
        print(f"  \u26a0  {label}")
    if detail:
        print(f"       \u2192 {detail}")


def section(title: str):
    line = "\u2500" * (46 - len(title))
    print(f"\n\u2500\u2500 {title} {line}")


# ════════════════════════════════════════════════
# BLOCK 1 — Ullas's modules (Hacker 4)
# ════════════════════════════════════════════════
def check_ullas():
    section("Ullas (Hacker 4) — Schemas + Validator + RAG + Bridge")

    try:
        from schemas import Clause, ContradictionResult, CitationResult
        test_clause = Clause(
            clause_id="clause_1_1",
            clause_number="1.1",
            page_number=1,
            section="Liability",
            text="The Company's liability is limited to fees paid.",
        )
        assert test_clause.clause_id == "clause_1_1"
        passed("schemas.py — Clause, ContradictionResult, CitationResult")
    except Exception as e:
        failed("schemas.py", str(e))

    try:
        from logic.validator import validate_clauses, extract_tags
        tags = extract_tags("Liability is limited to fees paid.")
        assert isinstance(tags, dict)
        passed("logic/validator.py — validate_clauses, extract_tags")
    except Exception as e:
        failed("logic/validator.py", str(e))

    try:
        from memory.rag import InMemoryRAG, citation_graph, get_citation_summary
        rag = InMemoryRAG()
        passed("memory/rag.py — InMemoryRAG, citation_graph")
    except Exception as e:
        failed("memory/rag.py", str(e))

    try:
        from memory.bridge import (
            contradiction_tool,
            citation_tool,
            rag_index_tool,
            run_full_analysis,
            get_graph_for_export,
        )
        from crewai.tools import BaseTool
        assert isinstance(contradiction_tool, BaseTool)
        assert isinstance(citation_tool, BaseTool)
        assert isinstance(rag_index_tool, BaseTool)
        passed("memory/bridge.py — all 3 CrewAI tools + run_full_analysis")
    except Exception as e:
        failed("memory/bridge.py", str(e))

    try:
        from memory.reset_between_docs import reset_for_new_document
        result = reset_for_new_document()
        assert result.get("status") == "reset"
        passed("memory/reset_between_docs.py — reset_for_new_document")
    except Exception as e:
        failed("memory/reset_between_docs.py", str(e))


# ════════════════════════════════════════════════
# BLOCK 2 — Shashank's modules (Hacker 2)
# ════════════════════════════════════════════════
def check_shashank():
    section("Shashank (Hacker 2) — Parser + Server + Redline")

    try:
        from ingestion.parser import extract_clauses, _score_clause
        score, flags = _score_clause(
            "Vendor may terminate immediately and without notice "
            "at its sole discretion."
        )
        assert isinstance(score, int), f"score not int: {type(score)}"
        assert 0 <= score <= 100, f"score out of range: {score}"
        passed(f"ingestion/parser.py — extract_clauses (scored: {score}/100)")
    except Exception as e:
        failed("ingestion/parser.py", str(e))

    try:
        import server
        assert hasattr(server, "app"), "FastAPI app not found in server.py"
        routes = [r.path for r in server.app.routes]
        required_routes = [
            "/health", "/upload", "/analyse",
            "/results/{doc_id}", "/export/{doc_id}", "/status",
        ]
        for route in required_routes:
            assert route in routes, f"Missing route: {route}"
        passed(f"server.py — all {len(required_routes)} required routes present")
    except Exception as e:
        failed("server.py", str(e))

    try:
        from export.redline import generate_redline_docx
        minimal = {
            "doc_id":             "handshake_test",
            "overall_risk_score": 50,
            "risk_label":         "MEDIUM",
            "clauses":            [],
            "contradictions":     [],
            "compliance_violations": [],
            "citation_results":   [],
            "fixed_clauses":      [],
            "hallucination_rate": 0.0,
            "citation_graph":     {
                "nodes": [], "edges": [], "summary": {}, "top_cited": [],
            },
        }
        path = generate_redline_docx(minimal, "handshake_test")
        size = os.path.getsize(path)
        assert size > 1000, f"Generated .docx too small: {size} bytes"
        passed(f"export/redline.py — generated {size:,} byte .docx")
    except Exception as e:
        failed("export/redline.py", str(e))


# ════════════════════════════════════════════════
# BLOCK 3 — Punith's agents (Hacker 3)
# ════════════════════════════════════════════════
def check_punith():
    section("Punith (Hacker 3) — CrewAI Agents")

    try:
        from agents.crew import analyse
        passed("agents/crew.py — analyse() importable")
    except ImportError as e:
        failed("agents/crew.py", str(e), blocker=False)
        print("       (Expected if Punith hasn't pushed yet)")


# ════════════════════════════════════════════════
# BLOCK 4 — Dhanush's frontend (Hacker 1)
# ════════════════════════════════════════════════
def check_dhanush():
    section("Dhanush (Hacker 1) — Streamlit Frontend")

    try:
        import ast
        app_path = ROOT / "app.py"
        assert app_path.exists(), "app.py not found"
        tree = ast.parse(app_path.read_text(encoding="utf-8", errors="replace"))
        funcs = [
            n.name for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
        ]
        required_fns = [
            "page_home", "page_upload", "page_analyse",
            "page_results", "page_redline", "page_graph",
            "page_history", "main",
        ]
        missing = [f for f in required_fns if f not in funcs]
        if missing:
            failed("app.py", f"Missing functions: {missing}", blocker=False)
        else:
            passed(f"app.py — all {len(required_fns)} page functions present")
    except Exception as e:
        failed("app.py", str(e), blocker=False)


# ════════════════════════════════════════════════
# BLOCK 5 — Full pipeline end-to-end (offline)
# ════════════════════════════════════════════════
def check_pipeline():
    section("End-to-End Pipeline (offline, no server needed)")

    # Bridge pipeline
    try:
        from schemas import Clause
        from memory.reset_between_docs import reset_for_new_document
        from memory.bridge import run_full_analysis

        test_clauses = [
            Clause(clause_id="clause_3_1", clause_number="3.1", page_number=1,
                   section="Liability",
                   text="The Company's liability is limited to fees paid in the last 12 months."),
            Clause(clause_id="clause_3_2", clause_number="3.2", page_number=1,
                   section="Liability",
                   text="There is no limit on liability for any damages arising from this agreement."),
            Clause(clause_id="clause_7_1", clause_number="7.1", page_number=2,
                   section="Termination",
                   text="Either party may terminate at will immediately without cause."),
            Clause(clause_id="clause_7_2", clause_number="7.2", page_number=2,
                   section="Termination",
                   text="A 90-day notice period is required before termination of this contract."),
        ]
        reset_for_new_document()
        result = run_full_analysis(test_clauses)
        assert "contradictions_found" in result, "Missing contradictions_found"
        assert "hallucination_rate"   in result, "Missing hallucination_rate"
        assert result["clauses_analysed"] == 4, \
            f"Expected 4, got {result['clauses_analysed']}"
        n = result["contradictions_found"]
        passed(f"Ullas bridge pipeline: 4 clauses → {n} contradiction(s) detected")
    except Exception as e:
        failed("End-to-end bridge pipeline", str(e))

    # Parser risk scoring
    try:
        from ingestion.parser import _score_clause
        risky_clauses = [
            ("auto-renew annually unless cancelled",          "AUTO_RENEWAL",   65),
            ("no limit on liability for any damages",         "CONTRADICTION",  85),
            ("vendor may modify at any time without consent", "ONE_SIDED",      75),
            ("share data with third party without consent",   "GDPR_VIOLATION", 55),
            ("liability is limited to fees paid in 12 months","STANDARD",        5),
        ]
        for text, expected_flag, min_score in risky_clauses:
            score, flags = _score_clause(text)
            assert score >= min_score, \
                f"'{text[:40]}' scored {score}, expected >= {min_score}"
        passed(f"Parser risk scoring: all {len(risky_clauses)} test cases scored correctly")
    except Exception as e:
        failed("Parser risk scoring", str(e))

    # Redline full document
    try:
        from export.redline import generate_redline_docx
        full_mock = {
            "doc_id": "handshake_full",
            "overall_risk_score": 74,
            "risk_label": "HIGH",
            "clauses": [
                {"clause_id": "clause_3_1", "clause_number": "3.1",
                 "section": "Liability", "risk_score": 82,
                 "risk_reason": "Contradicted by clause 3.2.",
                 "flags": ["CONTRADICTION"],
                 "text": "Liability is limited to fees paid."},
            ],
            "contradictions": [
                {"clause_id_a": "clause_3_1", "clause_id_b": "clause_3_2",
                 "contradiction_type": "MUTUAL_EXCLUSION",
                 "explanation": "Cap vs no cap.",
                 "z3_proof": "Z3 Result: UNSAT"},
            ],
            "compliance_violations": [],
            "fixed_clauses": [
                {"clause_id": "clause_3_1",
                 "original_text": "Liability is limited to fees paid.",
                 "fixed_text": "Liability is limited to the greater of fees paid or INR 5,00,000.",
                 "fix_explanation": "Added a floor to prevent trivially small cap."},
            ],
            "citation_results": [
                {"claim": "Vendor liability is capped.",
                 "source_clause_id": "clause_3_1", "source_page": 1,
                 "source_text_excerpt": "Liability is limited...",
                 "confidence_score": 0.94, "verified": True},
            ],
            "hallucination_rate": 0.0,
            "citation_graph": {
                "nodes": [], "edges": [],
                "summary": {"total_claims_made": 1, "verified_citations": 1,
                            "unverified_citations": 0, "hallucination_rate": 0.0},
                "top_cited": [{"clause_id": "clause_3_1",
                               "section": "Liability", "times_cited": 1}],
            },
        }
        path = generate_redline_docx(full_mock, "handshake_full")
        size = os.path.getsize(path)
        assert size > 10_000, f"Full redline too small: {size} bytes"
        passed(f"Redline full doc: {size:,} bytes → {path}")
    except Exception as e:
        failed("Redline full document generation", str(e))


# ════════════════════════════════════════════════
# BLOCK 6 — Demo contracts
# ════════════════════════════════════════════════
def check_contracts():
    section("Demo Contracts (Ullas generated)")

    try:
        pdfs = glob.glob(str(ROOT / "contracts" / "*.pdf"))
        assert len(pdfs) >= 18, f"Expected 18 PDFs, found {len(pdfs)}"
        passed(f"contracts/ — {len(pdfs)} demo PDFs present")
    except Exception as e:
        failed("contracts/", str(e), blocker=False)
        print("       Run: python contracts/generate_contracts.py")


# ════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "=" * 52)
    print("  RegulAIte — Pre-Demo Handshake Check")
    print("=" * 52)

    check_ullas()
    check_shashank()
    check_punith()
    check_dhanush()
    check_pipeline()
    check_contracts()

    print("\n" + "=" * 52)
    print(f"  PASSED:   {PASS_COUNT}")
    print(f"  WARNINGS: {WARN_COUNT}  (non-blocking)")
    print(f"  FAILED:   {FAIL_COUNT}  (must fix before demo)")
    print("=" * 52)

    if FAIL_COUNT == 0:
        print("\n  \u2713  ALL CRITICAL CHECKS PASSED")
        print("  \u2713  RegulAIte is ready to demo.")
        if WARN_COUNT > 0:
            print(f"\n  \u26a0  {WARN_COUNT} warning(s) — check above")
            print("     (Usually means a teammate's module not pushed yet)")
    else:
        print(f"\n  \u2717  {FAIL_COUNT} CRITICAL FAILURE(S)")
        print("  Fix the failures above before the demo.")
        sys.exit(1)
