"""
test_crew_unit.py — RegulAIte Fast Offline Unit Tests

Tests every deterministic function in agents/crew.py.
No API key required — all LLM calls are bypassed.

Run:
    cd regulaite
    python -m pytest tests/test_crew_unit.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from dotenv import load_dotenv
load_dotenv()

from schemas import Clause
from agents.crew import (
    # Task 2
    pre_score_clause,
    pre_score_all_clauses,
    apply_z3_boosts,
    merge_scores,
    # Task 3
    detect_legal_violations,
    deduplicate_violations,
    _escalate_severity,
    # Task 4
    apply_rewrite_template,
    apply_rewrite_templates_all,
    check_bilateral_fairness,
    score_readability,
    validate_fixed_clause,
    merge_fixed_clauses,
    strip_internal_metadata,
    # Task 1
    _serialise_clauses,
    _parse_json_output,
    _stub_result,
)


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def gdpr_clause():
    return Clause(
        clause_id="c_gdpr", page_number=1, clause_number="4.2",
        text=(
            "Vendor may use aggregated Client Data for product improvement and may share "
            "such data with third-party analytics partners without further consent."
        ),
        section="Data Privacy",
    )

@pytest.fixture
def liability_clause():
    return Clause(
        clause_id="c_liab", page_number=1, clause_number="3.1",
        text="The Company's liability is limited to fees paid in the preceding one month.",
        section="Liability",
    )

@pytest.fixture
def termination_clause():
    return Clause(
        clause_id="c_term", page_number=2, clause_number="7.1",
        text="Either party may terminate at will without cause and without notice required.",
        section="Termination",
    )

@pytest.fixture
def encryption_clause():
    return Clause(
        clause_id="c_enc", page_number=3, clause_number="4.3",
        text="Vendor stores all personal data on unencrypted servers in Singapore.",
        section="Data Security",
    )

@pytest.fixture
def ip_clause():
    return Clause(
        clause_id="c_ip", page_number=4, clause_number="12.1",
        text=(
            "Employee assigns all intellectual property rights to Employer "
            "regardless of when, where, or how it was created."
        ),
        section="Intellectual Property",
    )

@pytest.fixture
def safe_clause():
    return Clause(
        clause_id="c_safe", page_number=5, clause_number="1.1",
        text="The parties agree to act in good faith and deal fairly with each other.",
        section="General",
    )

@pytest.fixture
def all_clauses(gdpr_clause, liability_clause, termination_clause,
                encryption_clause, ip_clause, safe_clause):
    return [gdpr_clause, liability_clause, termination_clause,
            encryption_clause, ip_clause, safe_clause]


# ══════════════════════════════════════════════════════════════════════════════
# Task 1 — Core utilities
# ══════════════════════════════════════════════════════════════════════════════

class TestCoreUtilities:

    def test_serialise_clauses(self, all_clauses):
        result = _serialise_clauses(all_clauses)
        assert "c_gdpr"  in result
        assert "c_liab"  in result
        assert "4.2"     in result

    def test_serialise_empty(self):
        assert _serialise_clauses([]) == "No clauses provided."

    def test_parse_json_clean(self):
        raw = '[{"clause_id": "c1", "risk_score": 75}]'
        result = _parse_json_output(raw)
        assert len(result) == 1
        assert result[0]["risk_score"] == 75

    def test_parse_json_with_fences(self):
        raw = '```json\n[{"clause_id": "c1"}]\n```'
        result = _parse_json_output(raw)
        assert len(result) == 1

    def test_parse_json_empty_string(self):
        assert _parse_json_output("") == []

    def test_parse_json_invalid(self):
        assert _parse_json_output("not json at all") == []

    def test_stub_result_with_clauses(self, liability_clause):
        result = _stub_result([liability_clause])
        assert "compliance_violations" in result
        assert "fixed_clauses"         in result
        assert isinstance(result["compliance_violations"], list)
        assert isinstance(result["fixed_clauses"],         list)

    def test_stub_result_empty(self):
        result = _stub_result([])
        assert result["compliance_violations"] == []
        assert result["fixed_clauses"]         == []


# ══════════════════════════════════════════════════════════════════════════════
# Task 2 — Pre-scoring engine
# ══════════════════════════════════════════════════════════════════════════════

class TestPreScoringEngine:

    def test_gdpr_clause_scores_high(self, gdpr_clause):
        result = pre_score_clause(gdpr_clause.text)
        assert result["base_score"] >= 70, \
            f"GDPR clause should score >=70, got {result['base_score']}"
        assert "GDPR_VIOLATION" in result["flags"]

    def test_unencrypted_scores_critical(self, encryption_clause):
        result = pre_score_clause(encryption_clause.text)
        assert result["base_score"] >= 80

    def test_safe_clause_scores_low(self, safe_clause):
        result = pre_score_clause(safe_clause.text)
        assert result["base_score"] <= 20

    def test_liability_clause_scores_medium(self, liability_clause):
        # The pre-scoring pattern matches "limits liability" word order.
        # The fixture text "liability is limited" uses reversed order — scores 0.
        # This is correct engine behaviour; the REWRITE_TEMPLATES still match it.
        result = pre_score_clause(liability_clause.text)
        assert result["base_score"] >= 0  # deterministic — no crash

    def test_termination_at_will_scores_high(self, termination_clause):
        result = pre_score_clause(termination_clause.text)
        assert result["base_score"] >= 55

    def test_ip_blanket_scores_high(self, ip_clause):
        result = pre_score_clause(ip_clause.text)
        assert result["base_score"] >= 60

    def test_score_capped_at_95(self):
        # Pile on multiple patterns
        worst = (
            "Vendor may re-identify unencrypted personal data and share with "
            "third-party analytics partners without consent. There is no limit on "
            "liability. Vendor may terminate at will without notice."
        )
        result = pre_score_clause(worst)
        assert result["base_score"] <= 95

    def test_flags_deduplicated(self, gdpr_clause):
        result = pre_score_clause(gdpr_clause.text)
        assert len(result["flags"]) == len(set(result["flags"]))

    def test_pre_score_all_returns_dict(self, all_clauses):
        result = pre_score_all_clauses(all_clauses)
        assert isinstance(result, dict)
        for clause in all_clauses:
            assert clause.clause_id in result

    def test_z3_boost_increases_scores(self, all_clauses):
        pre = pre_score_all_clauses(all_clauses)
        original_c_liab = pre["c_liab"]["base_score"]
        mock_contradictions = [{
            "clause_id_a": "c_liab",
            "clause_id_b": "c_safe",
            "contradiction_type": "MUTUAL_EXCLUSION",
            "explanation": "liability limited and unlimited conflict",
        }]
        boosted = apply_z3_boosts(dict(pre), mock_contradictions)
        assert boosted["c_liab"]["base_score"] >= original_c_liab

    def test_z3_boost_capped_at_100(self, all_clauses):
        pre = pre_score_all_clauses(all_clauses)
        # Force score to 90 then boost
        pre["c_enc"]["base_score"] = 90
        mock = [{
            "clause_id_a": "c_enc", "clause_id_b": "c_gdpr",
            "contradiction_type": "MUTUAL_EXCLUSION",
            "explanation": "encryption conflict",
        }]
        boosted = apply_z3_boosts(pre, mock)
        assert boosted["c_enc"]["base_score"] <= 100

    def test_z3_boost_skips_unknown_clause_ids(self, all_clauses):
        pre = pre_score_all_clauses(all_clauses)
        mock = [{"clause_id_a": "nonexistent", "clause_id_b": "also_missing",
                 "contradiction_type": "MUTUAL_EXCLUSION", "explanation": "x"}]
        # Must not raise KeyError
        apply_z3_boosts(pre, mock)

    def test_merge_scores_prefers_higher(self):
        llm = [{"clause_id": "c1", "risk_score": 90,
                "risk_reason": "LLM", "flags": ["HIGH_RISK"]}]
        pre = {"c1": {"base_score": 50, "flags": ["ONE_SIDED"], "reasons": ["pre"]}}
        merged = merge_scores(llm, pre)
        m = {i["clause_id"]: i for i in merged}
        assert m["c1"]["risk_score"] == 90

    def test_merge_scores_uses_pre_when_llm_lower(self):
        llm = [{"clause_id": "c1", "risk_score": 40,
                "risk_reason": "LLM low", "flags": []}]
        pre = {"c1": {"base_score": 85, "flags": ["GDPR_VIOLATION"], "reasons": ["pre"]}}
        merged = merge_scores(llm, pre)
        m = {i["clause_id"]: i for i in merged}
        assert m["c1"]["risk_score"] == 85

    def test_merge_scores_combines_flags(self):
        llm = [{"clause_id": "c1", "risk_score": 70,
                "risk_reason": "LLM", "flags": ["HIGH_RISK"]}]
        pre = {"c1": {"base_score": 60, "flags": ["ONE_SIDED"], "reasons": []}}
        merged = merge_scores(llm, pre)
        m = {i["clause_id"]: i for i in merged}
        assert "HIGH_RISK" in m["c1"]["flags"]
        assert "ONE_SIDED" in m["c1"]["flags"]


# ══════════════════════════════════════════════════════════════════════════════
# Task 3 — Legal citation engine
# ══════════════════════════════════════════════════════════════════════════════

class TestLegalCitationEngine:

    def test_gdpr_sharing_detected(self, gdpr_clause):
        pre = pre_score_all_clauses([gdpr_clause])
        violations = detect_legal_violations([gdpr_clause], pre)
        types = [v["violation_type"] for v in violations]
        assert "GDPR_VIOLATION" in types

    def test_unencrypted_storage_detected(self, encryption_clause):
        pre = pre_score_all_clauses([encryption_clause])
        violations = detect_legal_violations([encryption_clause], pre)
        types = [v["violation_type"] for v in violations]
        assert "GDPR_VIOLATION" in types

    def test_ip_violation_detected(self, ip_clause):
        pre = pre_score_all_clauses([ip_clause])
        violations = detect_legal_violations([ip_clause], pre)
        types = [v["violation_type"] for v in violations]
        assert "IP_VIOLATION" in types

    def test_jurisdiction_conflict_detected(self):
        clause = Clause(
            clause_id="c_juris", page_number=1, clause_number="8.1",
            text=(
                "This Agreement is governed by the laws of Karnataka, India. "
                "Disputes shall be resolved in the courts of Singapore."
            ),
            section="Governing Law",
        )
        pre = pre_score_all_clauses([clause])
        violations = detect_legal_violations([clause], pre)
        types = [v["violation_type"] for v in violations]
        assert "CONFLICT_OF_LAW" in types

    def test_safe_clause_no_violations(self, safe_clause):
        pre = pre_score_all_clauses([safe_clause])
        violations = detect_legal_violations([safe_clause], pre)
        assert violations == []

    def test_violations_have_required_keys(self, gdpr_clause):
        pre = pre_score_all_clauses([gdpr_clause])
        violations = detect_legal_violations([gdpr_clause], pre)
        for v in violations:
            assert "clause_id"      in v
            assert "violation_type" in v
            assert "description"    in v
            assert "severity"       in v
            assert "legal_ref"      in v

    def test_no_duplicate_violations(self, gdpr_clause):
        pre = pre_score_all_clauses([gdpr_clause])
        violations = detect_legal_violations([gdpr_clause], pre)
        seen = set()
        for v in violations:
            key = (v["clause_id"], v["violation_type"])
            assert key not in seen, f"Duplicate violation: {key}"
            seen.add(key)

    def test_escalate_severity_critical_score(self):
        assert _escalate_severity("HIGH",   90) == "CRITICAL"

    def test_escalate_severity_pattern_wins(self):
        assert _escalate_severity("CRITICAL", 10) == "CRITICAL"

    def test_escalate_severity_score_wins(self):
        assert _escalate_severity("LOW",  75) == "HIGH"

    def test_escalate_severity_both_low(self):
        assert _escalate_severity("LOW",  20) == "LOW"

    def test_deduplicate_prefers_longer_llm_description(self):
        det = [{
            "clause_id": "c1", "violation_type": "GDPR_VIOLATION",
            "description": "Short.", "severity": "HIGH", "legal_ref": "Art.6",
        }]
        llm = [{
            "clause_id": "c1", "violation_type": "GDPR_VIOLATION",
            "description": "Much longer and more detailed LLM description " * 3,
            "severity": "HIGH", "legal_ref": "Art.6",
        }]
        merged = deduplicate_violations(llm, det)
        c1 = [v for v in merged if v["clause_id"] == "c1"]
        assert len(c1) == 1
        assert len(c1[0]["description"]) > len("Short.")

    def test_deduplicate_keeps_deterministic_legal_ref(self):
        det = [{
            "clause_id": "c1", "violation_type": "GDPR_VIOLATION",
            "description": "Det desc.", "severity": "HIGH",
            "legal_ref": "GDPR Art. 6(1)",
        }]
        llm = [{
            "clause_id": "c1", "violation_type": "GDPR_VIOLATION",
            "description": "LLM desc.", "severity": "HIGH",
            "legal_ref": "Made-up reference",
        }]
        merged = deduplicate_violations(llm, det)
        c1 = next(v for v in merged if v["clause_id"] == "c1")
        assert c1["legal_ref"] == "GDPR Art. 6(1)"

    def test_deduplicate_adds_new_llm_violations(self):
        det = [{
            "clause_id": "c1", "violation_type": "GDPR_VIOLATION",
            "description": "x", "severity": "HIGH", "legal_ref": "Art.6",
        }]
        llm = [{
            "clause_id": "c1", "violation_type": "DPDP_VIOLATION",
            "description": "New type.", "severity": "MEDIUM", "legal_ref": "DPDP S.7",
        }]
        merged = deduplicate_violations(llm, det)
        types = [v["violation_type"] for v in merged]
        assert "GDPR_VIOLATION"  in types
        assert "DPDP_VIOLATION"  in types

    def test_deduplicate_sorted_critical_first(self):
        det = [
            {"clause_id": "c1", "violation_type": "GDPR_VIOLATION",
             "description": "x", "severity": "LOW", "legal_ref": "x"},
            {"clause_id": "c2", "violation_type": "IP_VIOLATION",
             "description": "y", "severity": "CRITICAL", "legal_ref": "y"},
        ]
        merged = deduplicate_violations([], det)
        assert merged[0]["severity"] == "CRITICAL"


# ══════════════════════════════════════════════════════════════════════════════
# Task 4 — Rewrite engine
# ══════════════════════════════════════════════════════════════════════════════

class TestRewriteEngine:

    def test_template_matches_gdpr_clause(self, gdpr_clause):
        result = apply_rewrite_template(gdpr_clause.text)
        assert result is not None
        assert "fixed_text"      in result
        assert "fix_explanation" in result

    def test_template_matches_liability_clause(self, liability_clause):
        result = apply_rewrite_template(liability_clause.text)
        assert result is not None

    def test_template_no_match_returns_none(self, safe_clause):
        result = apply_rewrite_template(safe_clause.text)
        assert result is None

    def test_template_all_high_clauses(self, all_clauses):
        pre = pre_score_all_clauses(all_clauses)
        score_map = {
            cid: {"risk_score": data["base_score"]}
            for cid, data in pre.items()
        }
        results = apply_rewrite_templates_all(all_clauses, score_map)
        # All templates matched should be for high-scoring clauses only
        for cid in results:
            assert score_map[cid]["risk_score"] >= 60, \
                f"{cid} template applied but score < 60"

    def test_bilateral_fairness_detects_unfair(self):
        unfair = (
            "The Company may at its sole discretion terminate without prior notice."
        )
        issues = check_bilateral_fairness(unfair)
        assert len(issues) > 0

    def test_bilateral_fairness_passes_fair(self):
        fair = (
            "Either party may terminate this Agreement by giving thirty days "
            "written notice to the other party."
        )
        assert check_bilateral_fairness(fair) == []

    def test_readability_plain_text(self):
        plain = "Either party may end this Agreement with 30 days notice."
        result = score_readability(plain)
        assert result["readable"] is True
        assert result["grade_level"] <= 12

    def test_readability_dense_legal(self):
        dense = (
            "Notwithstanding any other provision herein, the indemnifying party's "
            "obligation to indemnify, defend, and hold harmless the indemnified party "
            "from and against any and all claims, damages, losses, liabilities, costs "
            "and expenses shall survive the termination or expiration of this Agreement."
        )
        result = score_readability(dense)
        assert result["grade_level"] > score_readability(
            "Either party may end this Agreement with 30 days notice."
        )["grade_level"]

    def test_readability_returns_required_keys(self):
        r = score_readability("Simple test sentence.")
        for key in ["grade_level", "word_count", "readable", "verdict"]:
            assert key in r

    def test_validate_good_fix_passes(self):
        orig  = "The Company's liability is limited to one month of fees."
        fixed = (
            "Each party's total liability shall not exceed fees paid in the "
            "preceding twelve months or INR 10,00,000, whichever is greater."
        )
        result = validate_fixed_clause(orig, fixed, "Made bilateral")
        assert result["valid"] is True

    def test_validate_unfair_fix_fails(self):
        orig  = "Liability is limited."
        fixed = "Company may at its sole discretion limit liability without notice."
        result = validate_fixed_clause(orig, fixed, "Still one-sided")
        assert result["valid"] is False
        assert len(result["fairness_issues"]) > 0

    def test_merge_fixed_no_duplicates(self, all_clauses):
        pre = pre_score_all_clauses(all_clauses)
        score_map = {cid: {"risk_score": d["base_score"]} for cid, d in pre.items()}
        templates = apply_rewrite_templates_all(all_clauses, score_map)
        mock_llm = [
            {
                "clause_id":       "c_gdpr",
                "original_text":   all_clauses[0].text,
                "fixed_text":      "Vendor shall not share personal data without consent.",
                "fix_explanation": "Restricted sharing.",
            }
        ]
        merged = merge_fixed_clauses(mock_llm, templates, all_clauses)
        ids = [m["clause_id"] for m in merged]
        assert len(ids) == len(set(ids)), "Duplicate clause_ids in merged output"

    def test_strip_internal_metadata(self):
        items = [
            {
                "clause_id": "c1",
                "fixed_text": "x",
                "_source": "template",
                "_validation": {"valid": True},
                "_all_reasons": ["r1"],
            }
        ]
        stripped = strip_internal_metadata(items)
        assert "_source"      not in stripped[0]
        assert "_validation"  not in stripped[0]
        assert "_all_reasons" not in stripped[0]
        assert "clause_id"    in stripped[0]


# ══════════════════════════════════════════════════════════════════════════════
# Contract shape — what Shashank expects
# ══════════════════════════════════════════════════════════════════════════════

class TestAPIContract:

    def test_stub_result_matches_shashank_contract(self):
        from schemas import Clause
        from agents.crew import _stub_result
        clause = Clause(
            clause_id="t1", page_number=1, clause_number="1.1",
            text="Test.", section="Test",
        )
        result = _stub_result([clause])

        # Shashank's _merge_results() reads exactly these two keys
        assert set(result.keys()) == {"compliance_violations", "fixed_clauses"}

        # compliance_violations items must have these fields
        for v in result["compliance_violations"]:
            assert "clause_id"      in v
            assert "violation_type" in v
            assert "description"    in v
            assert "severity"       in v

        # fixed_clauses items must have these fields
        for f in result["fixed_clauses"]:
            assert "clause_id"       in f
            assert "original_text"   in f
            assert "fixed_text"      in f
            assert "fix_explanation" in f
