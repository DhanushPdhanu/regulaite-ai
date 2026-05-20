"""
test_integration.py — RegulAIte End-to-End Integration Test

Tests the full stack: PDF upload → FastAPI → CrewAI → Streamlit response shape.

Requires:
  - Server running at http://localhost:8000
  - At least one PDF in regulaite/contracts/

Run AFTER starting the server:
    cd regulaite
    uvicorn server:app --reload &
    python -m pytest tests/test_integration.py -v --timeout=120
"""

import os
import sys
import glob
import time
import json

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.getenv("REGULAITE_BASE_URL", "http://localhost:8000")
TIMEOUT  = int(os.getenv("REGULAITE_TEST_TIMEOUT", "120"))


# ── Skip all tests if server is not running ───────────────────────────────────
def server_running() -> bool:
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not server_running(),
    reason=f"Server not running at {BASE_URL} — start with: uvicorn server:app --reload",
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_demo_pdf() -> str | None:
    pdfs = glob.glob(
        os.path.join(os.path.dirname(__file__), "..", "contracts", "*.pdf")
    )
    return pdfs[0] if pdfs else None


# ══════════════════════════════════════════════════════════════════════════════
# Integration Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestServerHealth:

    def test_health_endpoint(self):
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert data["status"] in ("ok", "healthy", "running")

    def test_docs_endpoint_reachable(self):
        r = requests.get(f"{BASE_URL}/docs", timeout=5)
        assert r.status_code == 200


class TestAnalyseEndpoint:

    def test_analyse_with_demo_pdf(self):
        pdf_path = get_demo_pdf()
        if not pdf_path:
            pytest.skip("No PDF found in contracts/ — add a PDF to test upload")

        with open(pdf_path, "rb") as f:
            r = requests.post(
                f"{BASE_URL}/analyse",
                files={"file": (os.path.basename(pdf_path), f, "application/pdf")},
                timeout=TIMEOUT,
            )

        assert r.status_code == 200, \
            f"Expected 200, got {r.status_code}: {r.text[:200]}"

        data = r.json()

        # Top-level structure
        assert "compliance_violations" in data, \
            "Missing key: compliance_violations"
        assert "fixed_clauses" in data, \
            "Missing key: fixed_clauses"
        assert isinstance(data["compliance_violations"], list)
        assert isinstance(data["fixed_clauses"],         list)

    def test_analyse_response_violation_schema(self):
        pdf_path = get_demo_pdf()
        if not pdf_path:
            pytest.skip("No PDF in contracts/")

        with open(pdf_path, "rb") as f:
            r = requests.post(
                f"{BASE_URL}/analyse",
                files={"file": (os.path.basename(pdf_path), f, "application/pdf")},
                timeout=TIMEOUT,
            )

        data = r.json()
        for v in data.get("compliance_violations", []):
            assert "clause_id"      in v, f"Missing clause_id in {v}"
            assert "violation_type" in v, f"Missing violation_type in {v}"
            assert "description"    in v, f"Missing description in {v}"
            assert "severity"       in v, f"Missing severity in {v}"
            assert v["severity"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW"), \
                f"Invalid severity: {v['severity']}"

    def test_analyse_response_fix_schema(self):
        pdf_path = get_demo_pdf()
        if not pdf_path:
            pytest.skip("No PDF in contracts/")

        with open(pdf_path, "rb") as f:
            r = requests.post(
                f"{BASE_URL}/analyse",
                files={"file": (os.path.basename(pdf_path), f, "application/pdf")},
                timeout=TIMEOUT,
            )

        data = r.json()
        for fix in data.get("fixed_clauses", []):
            assert "clause_id"       in fix, f"Missing clause_id in {fix}"
            assert "original_text"   in fix, f"Missing original_text in {fix}"
            assert "fixed_text"      in fix, f"Missing fixed_text in {fix}"
            assert "fix_explanation" in fix, f"Missing fix_explanation in {fix}"
            # Internal metadata must not leak
            assert "_source"     not in fix, "_source key leaked into response"
            assert "_validation" not in fix, "_validation key leaked into response"

    def test_analyse_no_internal_metadata_leaks(self):
        pdf_path = get_demo_pdf()
        if not pdf_path:
            pytest.skip("No PDF in contracts/")

        with open(pdf_path, "rb") as f:
            r = requests.post(
                f"{BASE_URL}/analyse",
                files={"file": (os.path.basename(pdf_path), f, "application/pdf")},
                timeout=TIMEOUT,
            )

        raw = r.text
        # Check raw JSON string for internal keys
        assert "_source"      not in raw, "_source leaked in raw JSON response"
        assert "_validation"  not in raw, "_validation leaked in raw JSON response"
        assert "_all_reasons" not in raw, "_all_reasons leaked in raw JSON response"

    def test_analyse_invalid_file_type_rejected(self):
        r = requests.post(
            f"{BASE_URL}/analyse",
            files={"file": ("test.txt", b"This is not a PDF", "text/plain")},
            timeout=10,
        )
        # Should return 400 or 422 — not 500
        assert r.status_code in (400, 422), \
            f"Expected 400/422 for invalid file, got {r.status_code}"

    def test_analyse_empty_file_handled(self):
        r = requests.post(
            f"{BASE_URL}/analyse",
            files={"file": ("empty.pdf", b"", "application/pdf")},
            timeout=10,
        )
        # Must not 500
        assert r.status_code != 500, \
            f"Server crashed on empty file (500). Must handle gracefully."

    def test_analyse_returns_within_timeout(self):
        pdf_path = get_demo_pdf()
        if not pdf_path:
            pytest.skip("No PDF in contracts/")

        start = time.time()
        with open(pdf_path, "rb") as f:
            r = requests.post(
                f"{BASE_URL}/analyse",
                files={"file": (os.path.basename(pdf_path), f, "application/pdf")},
                timeout=TIMEOUT,
            )
        elapsed = time.time() - start
        assert r.status_code == 200
        print(f"\n  Response time: {elapsed:.1f}s")
        # Warn (not fail) if slow — LLM calls can be slow
        if elapsed > 60:
            print(f"  WARNING: Response took {elapsed:.1f}s — consider caching")


class TestAgentDirectly:
    """
    Tests Punith's analyse() directly (no HTTP) — fast sanity check
    that the full pipeline returns the correct shape.
    """

    def test_analyse_stub_mode(self):
        """Works without a valid API key — stub fallback must return correct shape."""
        from schemas import Clause
        from agents.crew import analyse

        clauses = [
            Clause(
                clause_id="it_1", page_number=1, clause_number="1.1",
                text=(
                    "Vendor may share personal data with third-party analytics "
                    "partners without consent. Vendor stores data on unencrypted servers."
                ),
                section="Data Privacy",
            ),
            Clause(
                clause_id="it_2", page_number=2, clause_number="2.1",
                text="The Company's liability is limited to one month of fees.",
                section="Liability",
            ),
        ]

        result = analyse(clauses)

        assert isinstance(result, dict)
        assert "compliance_violations" in result
        assert "fixed_clauses"         in result
        assert isinstance(result["compliance_violations"], list)
        assert isinstance(result["fixed_clauses"],         list)

        # Even in stub mode, deterministic engine should find violations
        assert len(result["compliance_violations"]) >= 1, \
            "At least 1 violation expected even in stub mode"

    def test_analyse_empty_input(self):
        from agents.crew import analyse
        result = analyse([])
        assert result == {"compliance_violations": [], "fixed_clauses": []}
