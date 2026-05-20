"""
test_integration.py — Full integration smoke test for Shashank's server.
Run: cd regulaite && python test_integration.py

Tests every endpoint and confirms the API contract is correct.
All 4 hackers can run this to verify their modules integrate cleanly.
"""

import sys
import json
import time
import os
import tempfile

import requests

BASE = "http://localhost:8000"
PDF  = "contracts/01_saas_subscription_agreement.pdf"


def ok(label: str):
    print(f"  \u2713  {label}")


def fail(label: str, detail: str = ""):
    print(f"  \u2717  {label}")
    if detail:
        print(f"       {detail}")
    sys.exit(1)


def test_health():
    print("\n\u2500\u2500 /health \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    r = requests.get(f"{BASE}/health", timeout=5)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert data.get("status") == "ok", f"status != ok: {data}"
    assert "modules" in data, "Missing 'modules' key in /health response"
    ok(f"status=ok  modules={data.get('modules', {})}")


def test_upload():
    print("\n\u2500\u2500 POST /upload \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    with open(PDF, "rb") as f:
        r = requests.post(
            f"{BASE}/upload",
            files={"file": (PDF, f, "application/pdf")},
            timeout=30,
        )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()

    required = ["doc_id", "filename", "clause_count", "clauses"]
    for k in required:
        assert k in data, f"Missing key: {k}"

    assert data["clause_count"] > 0, "clause_count must be > 0"
    assert len(data["clauses"]) > 0, "clauses array must not be empty"

    clause = data["clauses"][0]
    clause_keys = [
        "clause_id", "clause_number", "page_number",
        "section", "text", "risk_score", "flags",
    ]
    for k in clause_keys:
        assert k in clause, f"Clause missing key: {k}"

    ok(f"doc_id={data['doc_id'][:8]}...  clauses={data['clause_count']}")
    return data["doc_id"]


def test_analyse(doc_id: str):
    print("\n\u2500\u2500 POST /analyse \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    r = requests.post(
        f"{BASE}/analyse",
        json={"doc_id": doc_id},
        timeout=120,
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()

    required = [
        "doc_id", "overall_risk_score", "risk_label",
        "clauses", "contradictions", "compliance_violations",
        "citation_results", "fixed_clauses",
        "hallucination_rate", "citation_graph",
    ]
    for k in required:
        assert k in data, f"Missing analysis key: {k}"

    assert isinstance(data["overall_risk_score"], int), \
        "overall_risk_score must be int"
    assert data["risk_label"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"], \
        f"Unexpected risk_label: {data['risk_label']}"
    assert 0.0 <= data["hallucination_rate"] <= 1.0, \
        f"hallucination_rate out of range: {data['hallucination_rate']}"

    ok(
        f"score={data['overall_risk_score']}  "
        f"label={data['risk_label']}  "
        f"contradictions={len(data['contradictions'])}  "
        f"fixes={len(data['fixed_clauses'])}"
    )
    return data


def test_results(doc_id: str):
    print("\n\u2500\u2500 GET /results/{doc_id} \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    r = requests.get(f"{BASE}/results/{doc_id}", timeout=10)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert data["doc_id"] == doc_id, "doc_id mismatch in results"
    ok("Cached result returned correctly")


def test_export(doc_id: str):
    print("\n\u2500\u2500 GET /export/{doc_id} \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    r = requests.get(f"{BASE}/export/{doc_id}", timeout=30)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    ct = r.headers.get("content-type", "")
    assert "wordprocessingml" in ct, f"Wrong content-type: {ct}"
    assert len(r.content) > 5000, f"File too small: {len(r.content)} bytes"

    out = os.path.join(tempfile.gettempdir(), "integration_test_redline.docx")
    with open(out, "wb") as f:
        f.write(r.content)
    ok(f"Downloaded {len(r.content):,} bytes -> {out}")


def test_404_handling():
    print("\n\u2500\u2500 Error handling \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    r = requests.get(f"{BASE}/results/nonexistent-doc-id", timeout=5)
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"
    ok("GET /results/bad-id -> 404 correct")

    r = requests.post(
        f"{BASE}/analyse",
        json={"doc_id": "nonexistent"},
        timeout=5,
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"
    ok("POST /analyse bad doc_id -> 404 correct")

    r = requests.post(
        f"{BASE}/upload",
        files={"file": ("test.txt", b"not a pdf", "text/plain")},
        timeout=5,
    )
    assert r.status_code == 400, f"Expected 400, got {r.status_code}"
    ok("POST /upload non-PDF -> 400 correct")


def test_status():
    print("\n\u2500\u2500 GET /status \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
    r = requests.get(f"{BASE}/status", timeout=5)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert "modules" in data, "Missing 'modules' key"
    for m in ["parser", "bridge", "agents", "redline"]:
        assert m in data["modules"], f"Missing module: {m}"
        assert "available" in data["modules"][m], \
            f"Module {m} missing 'available' field"
    ok(f"All 4 module statuses present")
    for m, info in data["modules"].items():
        status = "AVAILABLE" if info["available"] else "MISSING"
        print(f"       {m:10s} {status:12s} ({info['owner']})")


if __name__ == "__main__":
    print("=" * 52)
    print("RegulAIte Integration Test")
    print("=" * 52)
    print(f"Target: {BASE}")
    print(f"PDF:    {PDF}")

    try:
        test_health()
        doc_id = test_upload()
        test_analyse(doc_id)
        test_results(doc_id)
        test_export(doc_id)
        test_404_handling()
        test_status()

        print("\n" + "=" * 52)
        print("ALL INTEGRATION TESTS PASSED")
        print("=" * 52)
        print("\nShashank's server is fully wired. Safe to proceed to Task 5.")

    except AssertionError as e:
        print(f"\n  FAIL: {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"\n  ERROR: Cannot connect to {BASE}")
        print("  Start the server first: python server.py")
        sys.exit(1)
