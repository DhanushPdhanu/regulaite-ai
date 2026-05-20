"""crew.py — RegulAIte CrewAI Agent Pipeline

Hacker 3 (Punith) owns this file.

Interfaces:
- Shashank (Hacker 2): calls analyse(clauses) from server.py
- Ullas    (Hacker 4): imports schemas.py and memory/bridge.py tools here

Pipeline flow:
    List[Clause]
        │
        ▼
    RiskAgent          → scores each clause 0–100, assigns flags
        │
        ▼
    ComplianceAgent    → finds GDPR, labour law, IP violations
        │
        ▼
    FixerAgent         → rewrites flagged clauses to balanced language
        │
        ▼
    analyse() returns  → {compliance_violations, fixed_clauses}
"""

import os
import json
import re
import math
from collections import defaultdict
from difflib import SequenceMatcher
from typing import List, Optional

from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

load_dotenv()

# ══════════════════════════════════════════════════════════════════════════════
# PRE-SCORING ENGINE
# Deterministic pattern-based risk scorer.
# Runs instantly, costs nothing, requires no API key.
# Output is fed to the LLM as context — the LLM refines, not replaces.
# Mirrors Ullas's CLAUSE_PATTERNS in logic/validator.py for consistency.
# ══════════════════════════════════════════════════════════════════════════════

# ── Risk pattern registry ─────────────────────────────────────────────────────
# Each entry: (regex, flag_name, base_score_contribution, risk_reason_template)
PRE_SCORE_PATTERNS: list = [
    # ── Liability ──────────────────────────────────────────────────────────────
    (
        r"\blimit(s|ed)?\s+(liability|damages)\b",
        "ONE_SIDED", 40,
        "Unilateral liability cap detected — verify it is bilateral and covers adequate loss."
    ),
    (
        r"\bno\s+limit\s+on\s+(liability|damages)\b",
        "CONTRADICTION", 75,
        "Unlimited liability clause — contradicts any cap clause present elsewhere."
    ),
    (
        r"\bfull\s+(and\s+)?unlimited\s+liability\b",
        "CONTRADICTION", 78,
        "Full unlimited liability asserted — likely contradicts a liability cap in the same section."
    ),
    # ── Termination ────────────────────────────────────────────────────────────
    (
        r"\bterminate\s+(at\s+will|immediately|without\s+cause)\b",
        "ONE_SIDED", 65,
        "Unilateral immediate termination right with no notice — highly one-sided."
    ),
    (
        r"\b(cannot|may\s+not)\s+terminate\b",
        "CONTRADICTION", 50,
        "Prohibition on termination — may contradict a termination-at-will clause."
    ),
    (
        r"\b(\d+)[- ]day\s+notice\s+(period\s+)?required\b",
        "MISSING_NOTICE", 20,
        lambda m: (
            f"Notice period of {m.group(1)} days required — "
            + ("critically short (industry standard: 30–90 days)."
               if int(m.group(1)) < 15 else
               "verify consistency with any termination-at-will clause.")
        ),
    ),
    (
        r"\bno\s+notice\s+required\b",
        "CONTRADICTION", 60,
        "No-notice termination — contradicts any notice-period clause in the same section."
    ),
    # ── Auto-renewal ───────────────────────────────────────────────────────────
    (
        r"\bauto[- ]renew(al|s|ed)?\b",
        "AUTO_RENEWAL", 55,
        "Auto-renewal clause present — check notice window. Industry standard: 30–90 days."
    ),
    (
        r"\bno\s+auto[- ]renew(al)?\b",
        "CONTRADICTION", 45,
        "Auto-renewal explicitly excluded — verify no other clause implies renewal."
    ),
    (
        r"\b[3-9]\s+day[s]?\s+(notice|prior)",
        "AUTO_RENEWAL", 70,
        "Auto-renewal notice window under 10 days — predatory trap for unsuspecting parties."
    ),
    # ── Exclusivity ────────────────────────────────────────────────────────────
    (
        r"\bexclusive\s+(rights?|license|agreement|distributor|agent)\b",
        "ONE_SIDED", 35,
        "Exclusivity granted — verify territorial scope and whether it is genuinely mutual."
    ),
    (
        r"\bnon[- ]exclusive\b",
        "CONTRADICTION", 30,
        "Non-exclusive arrangement — check for any conflicting exclusivity clause."
    ),
    # ── Confidentiality ────────────────────────────────────────────────────────
    (
        r"\bconfidential(ity)?\s+(obligation|clause|terms?)\b",
        "MISSING_NOTICE", 15,
        "Confidentiality obligation present — verify carve-outs and survival clause."
    ),
    (
        r"\bno\s+confidential(ity)?\s+obligation\b",
        "CONTRADICTION", 50,
        "Confidentiality obligation explicitly waived — contradicts any NDA-type clause present."
    ),
    (
        r"\bpublic\s+disclosure\s+permitted\b",
        "CONTRADICTION", 55,
        "Public disclosure permitted — contradicts any confidentiality obligation clause."
    ),
    # ── Refund / Payment ───────────────────────────────────────────────────────
    (
        r"\bnon[- ]refundable\b",
        "ONE_SIDED", 45,
        "Non-refundable payment clause — verify no conflicting refund right exists."
    ),
    (
        r"\bfully\s+refundable\b",
        "CONTRADICTION", 40,
        "Full refund right asserted — verify no non-refundable clause contradicts this."
    ),
    (
        r"\bpro[- ]rata\s+refund\b",
        "MISSING_NOTICE", 20,
        "Pro-rata refund clause — typically fair; verify calculation methodology is defined."
    ),
    (
        r"\bwithhold\s+(any\s+)?payment\b",
        "ONE_SIDED", 65,
        "Unilateral payment withholding right — no objective threshold or time limit defined."
    ),
    (
        r"\binterest\s+(at|of)\s+(\d+)\s*%",
        "PREDATORY_PAYMENT", 0,
        lambda m: (
            f"Interest rate of {m.group(2)}% per annum — "
            + ("potentially usurious under RBI guidelines (>24% pa flagged)."
               if int(m.group(2)) > 24 else "verify against prevailing market rate.")
        ),
    ),
    # ── Indemnification ────────────────────────────────────────────────────────
    (
        r"\bindemnif(y|ies|ication)\b",
        "ONE_SIDED", 35,
        "Indemnification clause present — verify it is bilateral and capped appropriately."
    ),
    (
        r"\bno\s+indemnif(y|ication)\b",
        "CONTRADICTION", 45,
        "Indemnification explicitly excluded — contradicts any indemnity obligation elsewhere."
    ),
    (
        r"\bhold\s+harmless\b",
        "ONE_SIDED", 30,
        "Hold-harmless clause — verify whether both parties are covered equally."
    ),
    # ── GDPR / Data Privacy ────────────────────────────────────────────────────
    (
        r"\bthird[- ]party\s+(analytics|partner|processor)\b",
        "GDPR_VIOLATION", 80,
        "Data shared with third-party analytics/partners — likely violates GDPR Art. 6 without explicit consent basis."
    ),
    (
        r"\bre[- ]identif(y|ication)\b",
        "GDPR_VIOLATION", 90,
        "Re-identification of de-identified data permitted — critical GDPR Art. 5(1)(e) and DPDP Act violation."
    ),
    (
        r"\bunencrypt(ed)?\b",
        "GDPR_VIOLATION", 85,
        "Unencrypted storage of data — violates GDPR Art. 32 mandatory technical security measures."
    ),
    (
        r"\bretain\s+(personal\s+)?data\s+for\s+(\d+)\s+year",
        "GDPR_VIOLATION", 0,
        lambda m: (
            f"Data retained for {m.group(2)} year(s) post-termination — "
            + ("likely exceeds GDPR data minimisation principle (Art. 5(1)(e))."
               if int(m.group(2)) > 2 else "verify retention basis is documented.")
        ),
    ),
    (
        r"\bno\s+obligation\s+to\s+(facilitate|assist).*(data\s+subject|access|deletion)",
        "GDPR_VIOLATION", 88,
        "Processor disclaims obligation to assist with Data Subject rights — violates GDPR Art. 28(3)(e)."
    ),
    # ── IP / Intellectual Property ─────────────────────────────────────────────
    (
        r"\bworks?\s+made\s+for\s+hire\b",
        "IP_TRAP", 40,
        "Work-for-hire clause — verify payment is complete before IP transfers."
    ),
    (
        r"\bassigns?\s+all\s+(intellectual\s+property|ip|rights?)\b",
        "IP_TRAP", 65,
        "Blanket IP assignment — including personal-time creations likely unenforceable under Indian Copyright Act S.17."
    ),
    (
        r"\bregardless\s+of\s+when.*(created|developed|invented)\b",
        "IP_TRAP", 75,
        "IP assigned regardless of creation time — captures pre-existing and personal-time IP, likely invalid."
    ),
    # ── Non-compete ────────────────────────────────────────────────────────────
    (
        r"\bnon[- ]compete\b",
        "ONE_SIDED", 55,
        "Non-compete clause — Indian courts rarely enforce post-employment non-competes. Verify scope and duration."
    ),
    (
        r"\b(24|36|48)[- ]month\s+non[- ]compete\b",
        "ONE_SIDED", 80,
        "Non-compete exceeding 12 months — almost certainly unenforceable as an unreasonable restraint of trade in India."
    ),
    # ── Governing law / Jurisdiction ───────────────────────────────────────────
    (
        r"\bgoverned\s+by\s+the\s+laws?\s+of\s+(\w[\w\s]+?)[\.,]",
        "VAGUE_TERM", 10,
        lambda m: f"Governing law: {m.group(1).strip()} — verify courts of same jurisdiction are specified."
    ),
    (
        r"\b(courts?\s+of|jurisdiction\s+of)\s+(\w[\w\s]+?)[\.,]",
        "VAGUE_TERM", 10,
        lambda m: f"Jurisdiction: {m.group(2).strip()} — verify governing law matches this jurisdiction."
    ),
    (
        r"\bsingapore\b.{0,60}\b(india|karnataka|mumbai|delhi)\b"
        r"|\b(india|karnataka|mumbai|delhi)\b.{0,60}\bsingapore\b",
        "CONTRADICTION", 70,
        "Governing law and jurisdiction appear to be in different countries — LOGICAL_DEAD_END conflict."
    ),
    # ── Severance / Compensation ───────────────────────────────────────────────
    (
        r"\bno\s+severance\b",
        "ONE_SIDED", 55,
        "Severance explicitly excluded — verify no mandatory severance obligation exists in another clause."
    ),
    (
        r"\bminimum\s+(\d+)\s+month[s]?\s+severance\b",
        "CONTRADICTION", 30,
        lambda m: f"Minimum {m.group(1)}-month severance mandated — verify no clause eliminates this."
    ),
    # ── Unilateral modification ────────────────────────────────────────────────
    (
        r"\bsole\s+(and\s+)?(absolute\s+)?discretion\b",
        "ONE_SIDED", 60,
        "Sole discretion clause — no objective standard or appeal mechanism defined."
    ),
    (
        r"\bwithout\s+(prior\s+)?notice\b",
        "MISSING_NOTICE", 50,
        "Action permitted without notice — verify affected party has adequate protections."
    ),
    (
        r"\bat\s+(its|our|their)\s+sole\s+discretion\b",
        "ONE_SIDED", 58,
        "Unilateral sole-discretion right — creates power imbalance with no recourse for the other party."
    ),
    (
        r"\bfinal\s+and\s+binding\b",
        "ONE_SIDED", 55,
        "Decision stated as final and binding without appeal — removes contractual dispute rights."
    ),
]

# ── Risk reason templates for Z3 contradiction tags ──────────────────────────
# Mirrors Ullas's CONTRADICTION_TYPES dict in logic/validator.py
Z3_TAG_REASONS = {
    "liability_limited":  "Z3 detected MUTUAL_EXCLUSION: liability cap asserted and denied in the same contract.",
    "term_at_will":       "Z3 detected MUTUAL_EXCLUSION: immediate termination and notice-required clauses conflict.",
    "notice_required":    "Z3 detected MUTUAL_EXCLUSION: notice required in one clause, waived in another.",
    "auto_renewal":       "Z3 detected MUTUAL_EXCLUSION: auto-renewal asserted and denied simultaneously.",
    "exclusive":          "Z3 detected MUTUAL_EXCLUSION: exclusive and non-exclusive rights granted in same contract.",
    "confidential":       "Z3 detected MUTUAL_EXCLUSION: confidentiality obligation asserted and waived.",
    "has_governing_law":  "Z3 detected LOGICAL_DEAD_END: governing law jurisdiction conflict — dead letter clause.",
    "indemnification":    "Z3 detected MUTUAL_EXCLUSION: indemnification granted and disclaimed.",
    "refundable":         "Z3 detected MUTUAL_EXCLUSION: refundable and non-refundable payment terms conflict.",
}

# Score boost applied when a Z3 contradiction is confirmed for a clause
Z3_CONTRADICTION_BOOST = 25


def pre_score_clause(text: str) -> dict:
    """
    Runs all PRE_SCORE_PATTERNS against a single clause text.

    Returns:
      {
        "base_score":  int,        # 0–100, capped
        "flags":       List[str],  # deduplicated flag names
        "reasons":     List[str],  # human-readable risk reasons
      }
    """
    text_lower = text.lower()
    total_score = 0
    flags: list = []
    reasons: list = []
    seen_flags: set = set()

    for entry in PRE_SCORE_PATTERNS:
        pattern, flag, score_or_zero, reason_or_fn = entry

        match = re.search(pattern, text_lower, re.IGNORECASE)
        if not match:
            continue

        # Resolve score
        if callable(score_or_zero):
            contribution = 0  # lambdas don't add score, just provide reason
        else:
            contribution = score_or_zero

        total_score += contribution

        # Resolve reason
        if callable(reason_or_fn):
            try:
                reason_text = reason_or_fn(match)
            except Exception:
                reason_text = f"Pattern '{pattern}' matched."
        else:
            reason_text = reason_or_fn

        if flag not in seen_flags:
            flags.append(flag)
            seen_flags.add(flag)

        if reason_text and reason_text not in reasons:
            reasons.append(reason_text)

    # Cap at 95 — leave room for LLM to push to 100 on genuine extremes
    base_score = min(total_score, 95)

    return {
        "base_score": base_score,
        "flags":      flags,
        "reasons":    reasons,
    }


def pre_score_all_clauses(clauses: list) -> dict:
    """
    Pre-scores every clause. Returns a dict keyed by clause_id.
    Also injects a boost for clauses referenced in Ullas's Z3 contradiction output.

    Args:
        clauses: List[Clause] objects
    Returns:
        { clause_id: { base_score, flags, reasons } }
    """
    results = {}
    for clause in clauses:
        pre = pre_score_clause(clause.text)
        results[clause.clause_id] = pre
    return results


def apply_z3_boosts(
    pre_scores: dict,
    contradictions: list,
) -> dict:
    """
    Takes Ullas's contradiction results and boosts the pre-scores
    for every clause involved in a contradiction.

    Args:
        pre_scores:     output of pre_score_all_clauses()
        contradictions: List[ContradictionResult.model_dump()] from bridge
    Returns:
        Updated pre_scores dict with boosts applied
    """
    for c in contradictions:
        for cid in [c.get("clause_id_a"), c.get("clause_id_b")]:
            if not cid or cid not in pre_scores:
                continue
            entry = pre_scores[cid]
            entry["base_score"] = min(
                entry["base_score"] + Z3_CONTRADICTION_BOOST, 100
            )
            ctype  = c.get("contradiction_type", "MUTUAL_EXCLUSION")
            tag    = _infer_z3_tag(c.get("explanation", ""))
            reason = Z3_TAG_REASONS.get(tag, f"Z3 detected {ctype} contradiction.")
            if reason not in entry["reasons"]:
                entry["reasons"].append(reason)
            if "CONTRADICTION" not in entry["flags"]:
                entry["flags"].append("CONTRADICTION")
    return pre_scores


def _infer_z3_tag(explanation: str) -> str:
    """
    Infers the Z3 tag from the contradiction explanation text
    so we can look up the human-readable reason template.
    """
    explanation_lower = explanation.lower()
    if "liabilit" in explanation_lower:
        return "liability_limited"
    if "terminat" in explanation_lower or "at will" in explanation_lower:
        return "term_at_will"
    if "notice" in explanation_lower:
        return "notice_required"
    if "auto" in explanation_lower and "renew" in explanation_lower:
        return "auto_renewal"
    if "exclusiv" in explanation_lower:
        return "exclusive"
    if "confidential" in explanation_lower:
        return "confidential"
    if "governing" in explanation_lower or "jurisdiction" in explanation_lower:
        return "has_governing_law"
    if "indemnif" in explanation_lower:
        return "indemnification"
    if "refund" in explanation_lower:
        return "refundable"
    return "mutual_exclusion"


def merge_scores(
    llm_scores: list,
    pre_scores: dict,
) -> list:
    """
    Merges LLM risk scores with deterministic pre-scores.

    Strategy:
      - If LLM gave a score: take the HIGHER of (LLM score, pre_score)
        LLM may see nuance pre-scoring missed; pre-score may catch
        patterns the LLM was too conservative about.
      - If LLM did not return a score for a clause (parse failure):
        use pre_score as the authoritative score.
      - Merge flags from both sources (deduplicated).
      - Combine reasons: pre_score reason first, LLM reason appended.

    Args:
        llm_scores: list of dicts from _parse_json_output() on RiskAgent output
        pre_scores: dict from pre_score_all_clauses()
    Returns:
        List[dict] with merged clause_id, risk_score, risk_reason, flags
    """
    # Index LLM results by clause_id for O(1) lookup
    llm_map = {item.get("clause_id"): item for item in llm_scores if item.get("clause_id")}

    merged = []

    for clause_id, pre in pre_scores.items():
        llm = llm_map.get(clause_id, {})

        llm_score   = llm.get("risk_score", 0) or 0
        pre_score   = pre.get("base_score", 0) or 0
        final_score = max(llm_score, pre_score)

        # Merge flags
        llm_flags = llm.get("flags", []) or []
        pre_flags = pre.get("flags", []) or []
        all_flags = list(dict.fromkeys(pre_flags + llm_flags))  # preserve order, dedup

        # Build reason: pre reasons first, then LLM reason
        pre_reasons = pre.get("reasons", [])
        llm_reason  = llm.get("risk_reason", "")
        all_reasons = list(pre_reasons)
        if llm_reason and llm_reason not in all_reasons:
            all_reasons.append(llm_reason)

        primary_reason = all_reasons[0] if all_reasons else "No specific risk identified."

        merged.append({
            "clause_id":    clause_id,
            "risk_score":   final_score,
            "risk_reason":  primary_reason,
            "flags":        all_flags,
            "_all_reasons": all_reasons,  # kept for debugging; stripped before API response
        })

    # Also include any clause_ids the LLM returned that pre_score didn't know about
    for clause_id, llm in llm_map.items():
        if clause_id not in pre_scores:
            merged.append({
                "clause_id":    clause_id,
                "risk_score":   llm.get("risk_score", 0) or 0,
                "risk_reason":  llm.get("risk_reason", ""),
                "flags":        llm.get("flags", []) or [],
                "_all_reasons": [llm.get("risk_reason", "")],
            })

    return merged


# ══════════════════════════════════════════════════════════════════════════════
# LEGAL CITATION ENGINE
# Deterministic mapping of clause text patterns to exact law articles.
# Runs before the LLM — costs nothing, hallucinates nothing.
# Output is injected into the ComplianceAgent prompt as verified citations.
# ══════════════════════════════════════════════════════════════════════════════

# ── Legal provision registry ──────────────────────────────────────────────────
# Each entry:
#   (regex, violation_type, severity, legal_ref, description_template)
#
# description_template may be a str or a callable(match) -> str
# severity: CRITICAL > HIGH > MEDIUM > LOW
LEGAL_CITATIONS: list = [
    # ══ GDPR ══════════════════════════════════════════════════════════════════
    (
        r"\bthird[- ]party\s+(analytics|partner|processor|platform)\b",
        "GDPR_VIOLATION", "CRITICAL",
        "GDPR Art. 6(1)",
        "Sharing personal data with third-party analytics providers requires a valid "
        "lawful basis under GDPR Art. 6(1). No consent or legitimate interest basis "
        "is established in this clause.",
    ),
    (
        r"\bwithout\s+(further\s+)?(consent|notice|authoris)",
        "GDPR_VIOLATION", "CRITICAL",
        "GDPR Art. 6(1)(a) & Art. 7",
        "Processing or sharing personal data without consent violates GDPR Art. 6(1)(a). "
        "Where consent is the lawful basis, it must be freely given, specific, informed, "
        "and unambiguous per Art. 7.",
    ),
    (
        r"\bre[- ]identif(y|ication|ied)\b",
        "GDPR_VIOLATION", "CRITICAL",
        "GDPR Art. 5(1)(e) & Art. 25",
        "Re-identification of pseudonymised or anonymised data defeats the purpose of "
        "data minimisation (GDPR Art. 5(1)(e)) and violates data protection by design "
        "obligations (Art. 25).",
    ),
    (
        r"\bunencrypt(ed)?\s+(server|storage|database|system)s?\b",
        "GDPR_VIOLATION", "CRITICAL",
        "GDPR Art. 32(1)(a)",
        "Storing personal data on unencrypted servers fails the mandatory technical "
        "security measure of pseudonymisation and encryption required by GDPR Art. 32(1)(a).",
    ),
    (
        r"\bno\s+obligation\s+to\s+(facilitate|assist|respond|process).{0,50}"
        r"(data\s+subject|access\s+request|deletion|portability|rectif)",
        "GDPR_VIOLATION", "CRITICAL",
        "GDPR Art. 28(3)(e)",
        "A data processor must assist the controller in fulfilling Data Subject rights "
        "obligations (access, erasure, portability, rectification). Disclaiming this "
        "obligation violates GDPR Art. 28(3)(e).",
    ),
    (
        r"\b(sub[- ]?processor)\b.{0,80}"
        r"(without|freely).{0,60}(authoris|consent|notif|approv|inform)",
        "GDPR_VIOLATION", "HIGH",
        "GDPR Art. 28(2)",
        "Engaging sub-processors without prior specific or general written authorisation "
        "from the controller violates GDPR Art. 28(2).",
    ),
    (
        r"\bretain\s+(personal\s+)?data\s+for\s+(\d+)\s+year",
        "GDPR_VIOLATION", "HIGH",
        "GDPR Art. 5(1)(e)",
        lambda m: (
            f"Retaining personal data for {m.group(2)} years post-termination likely "
            "violates the storage limitation principle (GDPR Art. 5(1)(e)) which requires "
            "data to be kept no longer than necessary for the original purpose."
            if int(m.group(2)) > 2 else
            f"Data retained for {m.group(2)} year(s) — verify documented retention basis."
        ),
    ),
    (
        r"\bpersonal\s+data.{0,60}(improve|train|develop|model|AI|analytics)\b",
        "GDPR_VIOLATION", "HIGH",
        "GDPR Art. 5(1)(b)",
        "Using personal data for AI model training or product improvement constitutes "
        "a new purpose beyond the original collection purpose, violating GDPR Art. 5(1)(b) "
        "purpose limitation principle without a documented compatibility assessment.",
    ),
    (
        r"\bno\s+(data\s+breach|breach)\s+notification\b"
        r"|\btakes?\s+no\s+responsibility\s+for\s+(data\s+breaches?|breaches?)\b",
        "GDPR_VIOLATION", "CRITICAL",
        "GDPR Art. 33 & Art. 34",
        "Controllers must notify supervisory authorities of personal data breaches within "
        "72 hours (GDPR Art. 33) and affected data subjects without undue delay (Art. 34). "
        "Disclaiming breach notification obligations is void.",
    ),
    (
        r"\bdata.{0,30}(transfer|store|process).{0,40}"
        r"(outside|third\s+countr|singapore|us|united\s+states|china|russia)\b",
        "GDPR_VIOLATION", "HIGH",
        "GDPR Art. 44–49",
        "Transferring or storing personal data outside the EEA requires an adequacy "
        "decision, Standard Contractual Clauses, or another Art. 44–49 safeguard. "
        "This clause does not specify the transfer mechanism.",
    ),
    # ══ India DPDP Act 2023 ════════════════════════════════════════════════════
    (
        r"\bthird[- ]party\s+(analytics|partner|platform)\b.{0,200}"
        r"\b(india|indian|bengaluru|mumbai|delhi)\b"
        r"|\b(india|indian)\b.{0,200}\bthird[- ]party\s+(analytics|partner)\b",
        "DPDP_VIOLATION", "HIGH",
        "DPDP Act 2023, S.7 & S.8",
        "Under India's Digital Personal Data Protection Act 2023, sharing personal data "
        "with third parties requires a valid consent notice (S.7) and the data fiduciary "
        "must ensure data processors comply with equivalent obligations (S.8).",
    ),
    (
        r"\bno\s+(obligation|duty|requirement)\s+to\s+(delete|erase|destroy)\b",
        "DPDP_VIOLATION", "HIGH",
        "DPDP Act 2023, S.12",
        "The DPDP Act 2023 grants data principals the right to erasure of personal data "
        "(S.12). Disclaiming the obligation to delete personal data is void against Indian "
        "data principals.",
    ),
    # ══ Indian Labour Law ══════════════════════════════════════════════════════
    (
        r"\bnon[- ]compete.{0,100}(india|nationwide|all\s+region|entire\s+countr)\b",
        "LABOUR_LAW_VIOLATION", "HIGH",
        "Indian Contract Act 1872, S.27",
        "Post-employment non-compete clauses with nationwide or all-India scope are void "
        "as an unreasonable restraint of trade under S.27 of the Indian Contract Act 1872. "
        "Indian courts consistently refuse to enforce such clauses.",
    ),
    (
        r"\b(24|36|48|60)[- ]month\s+non[- ]compete\b",
        "LABOUR_LAW_VIOLATION", "HIGH",
        "Indian Contract Act 1872, S.27",
        lambda m: (
            f"A {m.group(1)}-month post-employment non-compete is almost certainly "
            "unenforceable under S.27 of the Indian Contract Act 1872. Indian courts "
            "have consistently held that restraints beyond the employment period are void."
        ),
    ),
    (
        r"\bterminate.{0,60}(immediately|without\s+notice|at\s+will).{0,80}"
        r"(no\s+(severance|compensation)|without\s+(severance|compensation))\b",
        "LABOUR_LAW_VIOLATION", "HIGH",
        "Industrial Disputes Act 1947, S.25F",
        "Immediate termination without notice or severance for employees covered under "
        "the Industrial Disputes Act 1947 violates S.25F mandatory retrenchment "
        "compensation requirements.",
    ),
    (
        r"(unilateral(ly)?.{0,80}(reduc|cut|decreas|revis).{0,40}(salary|compensation|wage|pay))"
        r"|(reduc|cut|decreas|revis).{0,40}(salary|compensation|wage|pay).{0,80}"
        r"(sole\s+discretion|without\s+(prior\s+)?notice|unilateral)",
        "LABOUR_LAW_VIOLATION", "CRITICAL",
        "Indian Contract Act 1872, S.10 & Payment of Wages Act 1936",
        "Unilaterally reducing an employee's agreed salary without consent is a breach of "
        "contract (Indian Contract Act 1872 S.10) and may violate the Payment of Wages Act "
        "1936 which prohibits unauthorised deductions.",
    ),
    # ══ Indian Copyright / IP Law ══════════════════════════════════════════════
    (
        r"\bassigns?\s+all\s+(intellectual\s+property|ip|rights?).{0,80}"
        r"(regardless|irrespective).{0,60}(when|where|how|personal|own\s+time)\b",
        "IP_VIOLATION", "HIGH",
        "Indian Copyright Act 1957, S.17",
        "Blanket IP assignment clauses that capture work created in personal time or "
        "with personal resources are likely unenforceable under S.17 of the Indian "
        "Copyright Act 1957, which vests copyright in the creator absent a valid "
        "contract of service for work done in that capacity.",
    ),
    (
        r"\bmoral\s+rights?.{0,60}(waiv|transfer|assign)\b",
        "IP_VIOLATION", "MEDIUM",
        "Indian Copyright Act 1957, S.57",
        "Moral rights (right of paternity and integrity) under S.57 of the Indian "
        "Copyright Act 1957 cannot be waived or transferred by contract — "
        "any clause purporting to do so is void.",
    ),
    # ══ Predatory Financial Clauses ════════════════════════════════════════════
    (
        r"\binterest\s+(at|of|rate).{0,20}(\d+)\s*%\s*(per\s+annum|p\.a\.|pa)\b",
        "PREDATORY_CLAUSE", "HIGH",
        "RBI Usury Guidelines & Indian Contract Act 1872, S.74",
        lambda m: (
            f"Interest rate of {m.group(2)}% per annum — "
            + ("exceeds RBI's indicative threshold. Courts may strike this down as "
               "a penalty clause under Indian Contract Act 1872 S.74."
               if int(m.group(2)) > 24 else
               f"verify this is consistent with prevailing market rates and RBI guidelines.")
        ),
    ),
    (
        r"\b(invoke|enforce|sell|dispose).{0,60}"
        r"(securit|mortgage|collateral|propert).{0,60}"
        r"(without\s+(prior\s+)?notice|without\s+court|self[- ]help)\b",
        "PREDATORY_CLAUSE", "CRITICAL",
        "Transfer of Property Act 1882, S.69",
        "Self-help enforcement — selling or invoking security without court order or prior "
        "notice — is generally void under S.69 of the Transfer of Property Act 1882. "
        "Lenders require a court decree or SARFAESI Act procedure.",
    ),
    (
        r"\bfinal\s+and\s+binding.{0,60}(without\s+appeal|no\s+recourse|not\s+subject\s+to\s+review)\b",
        "PREDATORY_CLAUSE", "HIGH",
        "Arbitration & Conciliation Act 1996, S.34",
        "Contractual finality clauses that purport to exclude all appeal rights are "
        "void to the extent they conflict with the statutory right to challenge awards "
        "on limited grounds under the Arbitration & Conciliation Act 1996, S.34.",
    ),
    # ══ Jurisdiction / Conflict of Laws ════════════════════════════════════════
    (
        r"\bgoverned\s+by.{0,60}(india|karnataka|maharashtra|delhi)\b"
        r".{0,200}"
        r"\b(courts?\s+of|jurisdiction\s+of)\s+(singapore|london|new\s+york|dubai)\b",
        "CONFLICT_OF_LAW", "HIGH",
        "Private International Law",
        "Governing law (India) conflicts with exclusive jurisdiction (foreign court). "
        "This creates a LOGICAL_DEAD_END — the enforcing court may refuse to apply "
        "foreign law or the Indian court may decline jurisdiction.",
    ),
    (
        r"\b(courts?\s+of|jurisdiction\s+of)\s+(singapore|london|new\s+york|dubai)\b"
        r".{0,200}"
        r"\bgoverned\s+by.{0,60}(india|karnataka|maharashtra|delhi)\b",
        "CONFLICT_OF_LAW", "HIGH",
        "Private International Law",
        "Jurisdiction clause (foreign court) conflicts with governing law (India). "
        "This creates a LOGICAL_DEAD_END — the foreign court applies Indian law it "
        "may not be familiar with, creating enforcement uncertainty.",
    ),
    # ══ Auto-Renewal Traps ═════════════════════════════════════════════════════
    (
        r"\bauto[- ]renew.{0,100}"
        r"(\b[1-9]\b|\bone\b|\btwo\b|\bthree\b|\bfour\b|\bfive\b|\bsix\b|\bseven\b).{0,20}"
        r"(day[s]?\s+(notice|prior|before))\b",
        "AUTO_RENEWAL_TRAP", "HIGH",
        "Indian Contract Act 1872, S.10 (Unconscionable Terms)",
        lambda m: (
            "Auto-renewal with a notice window in single-digit or very short days is "
            "commercially unreasonable. Courts may strike this as unconscionable under "
            "S.10 of the Indian Contract Act 1872 if the window is under 15 days."
        ),
    ),
]

# ── Severity escalation matrix ────────────────────────────────────────────────
# Final severity = max(pattern_severity, risk_score_severity)
# This ensures a clause with a HIGH pattern but a low pre-score is still HIGH.
SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
RANK_SEVERITY = {v: k for k, v in SEVERITY_RANK.items()}


def _escalate_severity(pattern_severity: str, risk_score: int) -> str:
    """Returns the higher of pattern_severity vs score-derived severity.
    Score mapping: <35=LOW, 35–59=MEDIUM, 60–79=HIGH, 80+=CRITICAL"""
    if risk_score >= 80:
        score_sev = "CRITICAL"
    elif risk_score >= 60:
        score_sev = "HIGH"
    elif risk_score >= 35:
        score_sev = "MEDIUM"
    else:
        score_sev = "LOW"

    rank = max(
        SEVERITY_RANK.get(pattern_severity, 0),
        SEVERITY_RANK.get(score_sev, 0),
    )
    return RANK_SEVERITY[rank]


def detect_legal_violations(
    clauses: list,
    pre_scores: dict,
) -> list:
    """Runs LEGAL_CITATIONS patterns against every clause.

    Returns a list of violation dicts ready to be injected into the
    ComplianceAgent prompt — and used as fallback if LLM fails.

    Args:
        clauses:    List[Clause]
        pre_scores: dict from pre_score_all_clauses() — used for severity escalation
    Returns:
        List[dict] with keys:
            clause_id, violation_type, description, severity, legal_ref
    """
    results = []
    seen: set = set()  # deduplicate (clause_id, violation_type) pairs

    for clause in clauses:
        text_lower   = clause.text.lower()
        clause_score = (pre_scores.get(clause.clause_id) or {}).get("base_score", 0)

        for entry in LEGAL_CITATIONS:
            pattern, v_type, base_severity, legal_ref, desc_or_fn = entry

            match = re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL)
            if not match:
                continue

            key = (clause.clause_id, v_type)
            if key in seen:
                continue
            seen.add(key)

            # Resolve description
            if callable(desc_or_fn):
                try:
                    description = desc_or_fn(match)
                except Exception:
                    description = f"{v_type} pattern matched in {clause.clause_id}."
            else:
                description = desc_or_fn

            # Escalate severity based on risk score
            final_severity = _escalate_severity(base_severity, clause_score)

            results.append({
                "clause_id":      clause.clause_id,
                "violation_type": v_type,
                "description":    description,
                "severity":       final_severity,
                "legal_ref":      legal_ref,
            })

    return results


def deduplicate_violations(
    llm_violations: list,
    det_violations: list,
) -> list:
    """Merges LLM-detected violations with deterministic violations.

    Strategy:
    - Deterministic violations are ground truth (never discarded)
    - LLM violations for the same (clause_id, violation_type) pair
      are merged in: the LLM's description replaces the template
      if it is longer and more specific
    - LLM violations for new (clause_id, violation_type) pairs are added

    Args:
        llm_violations: list from _parse_json_output() on ComplianceAgent
        det_violations: list from detect_legal_violations()
    Returns:
        Deduplicated, merged list sorted by severity (CRITICAL first)
    """
    # Index deterministic results
    det_map: dict = {}
    for v in det_violations:
        key = (v["clause_id"], v["violation_type"])
        det_map[key] = dict(v)

    # Merge LLM results
    for v in llm_violations:
        clause_id = v.get("clause_id", "")
        v_type    = v.get("violation_type", "")
        if not clause_id or not v_type:
            continue

        key = (clause_id, v_type)
        if key in det_map:
            # Prefer LLM description if richer
            llm_desc = v.get("description", "")
            if len(llm_desc) > len(det_map[key].get("description", "")):
                det_map[key]["description"] = llm_desc
            # Escalate severity if LLM rates it higher
            llm_sev     = v.get("severity", "LOW")
            current_sev = det_map[key]["severity"]
            if SEVERITY_RANK.get(llm_sev, 0) > SEVERITY_RANK.get(current_sev, 0):
                det_map[key]["severity"] = llm_sev
            # Keep deterministic legal_ref (LLM refs may hallucinate)
        else:
            # New violation from LLM — add it with legal_ref from LLM
            det_map[key] = {
                "clause_id":      clause_id,
                "violation_type": v_type,
                "description":    v.get("description", ""),
                "severity":       v.get("severity", "MEDIUM"),
                "legal_ref":      v.get("legal_ref", "Not specified"),
            }

    # Sort by severity descending
    merged = sorted(
        det_map.values(),
        key=lambda x: SEVERITY_RANK.get(x["severity"], 0),
        reverse=True,
    )
    return merged


# ══════════════════════════════════════════════════════════════════════════════
# REWRITE TEMPLATE ENGINE
# Deterministic clause rewriting templates for the 12 most common risky patterns.
# Runs before the LLM — provides proven balanced language as anchors.
# The LLM refines these templates rather than drafting from scratch,
# which reduces hallucination and improves consistency.
# ══════════════════════════════════════════════════════════════════════════════

# Each entry:
#   (regex, template_fn(match, original_text) -> str, fix_explanation_template)
#
# template_fn receives the regex match AND the full original clause text.
# It returns a rewritten clause string.
# fix_explanation_template may be a str or callable(match) -> str.

REWRITE_TEMPLATES: list = [

    # ── 1. Unilateral liability cap → bilateral cap ────────────────────────
    (
        r"\b(the\s+)?(company|vendor|provider|licensor|employer)"
        r"['\u2019]?s?\s+liabilit(y|ies)\s+(is|are|shall be)?\s*limited\b",
        lambda match, orig: (
            "Each party's total aggregate liability to the other party under this "
            "Agreement, whether in contract, tort (including negligence), breach of "
            "statutory duty, or otherwise, shall not exceed the greater of: "
            "(a) the total fees paid or payable by the Client in the twelve (12) months "
            "immediately preceding the event giving rise to the claim, or "
            "(b) INR 10,00,000 (Indian Rupees Ten Lakh). "
            "This limitation applies to all claims in aggregate, not per incident."
        ),
        "Made liability cap bilateral (applies equally to both parties), extended "
        "lookback period to 12 months (industry standard), and added minimum floor.",
    ),

    # ── 2. Unlimited liability → mutual unlimited carve-outs ──────────────
    (
        r"\bno\s+limit\s+on\s+(liability|damages)\b"
        r"|\bthere\s+is\s+no\s+limit\s+on\s+(liability|damages)\b",
        lambda match, orig: (
            "Neither party excludes or limits its liability to the other party for: "
            "(a) death or personal injury caused by negligence; "
            "(b) fraud or fraudulent misrepresentation; "
            "(c) wilful misconduct or gross negligence; or "
            "(d) any other liability that cannot be excluded or limited by applicable law. "
            "Subject to the foregoing, all other liability is subject to the cap in Clause 3.1."
        ),
        "Converted unlimited liability into a mutual carve-out list for non-excludable "
        "liabilities, then redirected all other liability to the bilateral cap clause.",
    ),

    # ── 3. Termination at will without notice → mutual termination with notice ─
    (
        r"\bterminate\s+(at\s+will|immediately|without\s+cause"
        r"|without\s+notice|without\s+reason)\b",
        lambda match, orig: (
            "Either party may terminate this Agreement for any reason by providing "
            "thirty (30) days' prior written notice to the other party. "
            "During the notice period, both parties shall continue to perform their "
            "obligations under this Agreement. "
            "Upon expiry of the notice period, all accrued rights and liabilities "
            "of both parties shall survive termination."
        ),
        "Converted unilateral immediate termination into mutual 30-day notice "
        "termination right, preserving accrued rights on both sides.",
    ),

    # ── 4. Short/no auto-renewal notice → adequate notice window ──────────
    (
        r"\bauto[- ]renew(al|s|ed)?\b.{0,200}"
        r"(\b[1-9]\b|\bone\b|\btwo\b|\bthree\b|\bfour\b|\bfive\b).{0,20}"
        r"(day[s]?\s+(notice|prior|before))\b",
        lambda match, orig: (
            "This Agreement shall automatically renew for successive periods equal to "
            "the initial term unless either party provides written notice of non-renewal "
            "at least sixty (60) days before the end of the then-current term. "
            "The renewing party shall send a renewal reminder to the other party "
            "ninety (90) days before the renewal date. "
            "Fees for the renewal term shall be communicated at least sixty (60) days "
            "in advance and shall not increase by more than 10% without written consent."
        ),
        "Extended auto-renewal notice window from single digits to 60 days (industry "
        "standard), added renewal reminder obligation, and capped fee increases.",
    ),

    # ── 5. GDPR third-party data sharing without consent → consent-gated sharing ─
    (
        r"\bthird[- ]party\s+(analytics|partner|processor|platform)\b"
        r".{0,150}\bwithout\s+(further\s+)?(consent|notice|authoris)\b",
        lambda match, orig: (
            "Vendor may use aggregated, anonymised, and irreversibly de-identified "
            "Client Data solely for internal product improvement purposes. "
            "Vendor shall not share, sell, license, or transfer any personal data "
            "(as defined under GDPR Art. 4(1) and the DPDP Act 2023) to any "
            "third-party analytics provider, partner, or sub-processor without: "
            "(a) obtaining the prior written consent of Client; "
            "(b) executing a Data Processing Agreement with the sub-processor that "
            "imposes obligations no less protective than those in this Agreement; and "
            "(c) notifying Client of the identity of any new sub-processor at least "
            "30 days in advance, granting Client a right to object."
        ),
        "Restricted data sharing to anonymised data only; prohibited personal data "
        "transfer to third parties without consent, DPA, and advance notice — "
        "GDPR Art. 6(1)(a), Art. 28(2) compliant.",
    ),

    # ── 6. Unencrypted storage → mandatory encryption ─────────────────────
    (
        r"\bunencrypt(ed)?\b",
        lambda match, orig: (
            "Vendor shall store all personal data and Client Confidential Information "
            "using industry-standard encryption both at rest (AES-256 or equivalent) "
            "and in transit (TLS 1.2 or higher). "
            "Vendor shall maintain ISO 27001 certification or equivalent and shall "
            "provide Client with an up-to-date security overview upon request. "
            "In the event of a confirmed or suspected data breach, Vendor shall notify "
            "Client within 24 hours and the relevant supervisory authority within "
            "72 hours as required by GDPR Art. 33."
        ),
        "Mandated AES-256 encryption at rest and TLS 1.2 in transit; added breach "
        "notification timeline (24h to Client, 72h to regulator) — GDPR Art. 32 compliant.",
    ),

    # ── 7. Blanket IP assignment (personal time) → employment-scope assignment ─
    (
        r"\bassigns?\s+all\s+(intellectual\s+property|ip|rights?)\b"
        r".{0,100}(regardless|irrespective).{0,60}(when|where|how|personal|own\s+time)\b",
        lambda match, orig: (
            "Employee assigns to Employer all right, title, and interest in and to "
            "any Intellectual Property created: "
            "(a) during working hours; "
            "(b) using Employer's equipment, facilities, or Confidential Information; or "
            "(c) that directly relates to Employer's current or reasonably anticipated "
            "business activities or research. "
            "For the avoidance of doubt, this assignment does not extend to Intellectual "
            "Property created entirely in Employee's own time, using Employee's own "
            "resources, and unrelated to Employer's business — such IP remains the "
            "exclusive property of Employee. "
            "Employee shall promptly disclose all potentially assignable IP to Employer."
        ),
        "Scoped IP assignment to employment-related work only; carved out personal-time "
        "IP explicitly — enforceable under Indian Copyright Act 1957 S.17.",
    ),

    # ── 8. Non-refundable payment → tiered refund right ───────────────────
    (
        r"\bnon[- ]refundable\b",
        lambda match, orig: (
            "Fees paid in advance for services not yet rendered shall be refunded "
            "on a pro-rata basis upon termination of this Agreement by either party, "
            "calculated from the effective date of termination to the end of the "
            "pre-paid period. "
            "Fees for services already delivered are non-refundable. "
            "Any disputed amounts shall be held in escrow pending resolution "
            "under the dispute resolution clause of this Agreement."
        ),
        "Converted blanket non-refundable clause into pro-rata refund right for "
        "unrendered services; preserved non-refundability for delivered services only.",
    ),

    # ── 9. Unilateral modification right → mutual consent amendment ────────
    (
        r"\b(sole\s+(and\s+)?absolute\s+discretion|at\s+(its|our|their)\s+sole\s+discretion)\b"
        r".{0,100}(amend|modif|chang|revis|updat)\b",
        lambda match, orig: (
            "This Agreement may only be amended or modified by a written instrument "
            "signed by authorised representatives of both parties. "
            "Either party may propose an amendment by providing thirty (30) days' "
            "written notice. If the other party does not object within twenty (20) days "
            "of receiving the proposed amendment, the amendment shall be deemed accepted. "
            "If the other party objects, both parties shall negotiate in good faith for "
            "a period of fifteen (15) days before either party may escalate to the "
            "dispute resolution mechanism in this Agreement."
        ),
        "Replaced unilateral modification right with mutual written consent process; "
        "added deemed-consent mechanism with 20-day review window.",
    ),

    # ── 10. Non-compete (post-employment, broad) → garden leave model ─────
    (
        r"\bnon[- ]compete\b.{0,200}"
        r"(after|post[- ]?(termination|employment)|upon\s+(leaving|resignation|termination))\b",
        lambda match, orig: (
            "During the term of employment only, Employee shall not engage in any "
            "activity that directly competes with Employer's core business activities "
            "as described in Schedule 1. "
            "For a period of six (6) months following termination of employment "
            "('Garden Leave Period'), Employee shall provide Employer with reasonable "
            "assistance in transitioning responsibilities. "
            "In lieu of a post-employment non-compete, Employer may elect to place "
            "Employee on paid garden leave during the notice period. "
            "Employee's confidentiality obligations under Clause 6 shall survive "
            "termination indefinitely."
        ),
        "Replaced unenforceable post-employment non-compete (void under Indian "
        "Contract Act S.27) with a garden-leave model that protects legitimate "
        "interests without restraining trade.",
    ),

    # ── 11. Self-help enforcement → court-order required ─────────────────
    (
        r"\b(invoke|enforce|sell|dispose).{0,60}"
        r"(securit|mortgage|collateral|propert).{0,60}"
        r"(without\s+(prior\s+)?notice|without\s+court|self[- ]help)\b",
        lambda match, orig: (
            "Lender may enforce its security interest over the mortgaged property "
            "only upon: "
            "(a) a continuing Event of Default (as defined herein) that remains "
            "unremedied for thirty (30) days following written notice to Borrower; and "
            "(b) obtaining a court order or following the procedure prescribed under the "
            "SARFAESI Act 2002 or the applicable state Debt Recovery Tribunal process. "
            "Lender shall provide Borrower with a minimum of fifteen (15) days' notice "
            "before filing any enforcement proceeding. "
            "Borrower retains the right to cure the Event of Default within the "
            "notice period."
        ),
        "Replaced void self-help enforcement with court-order / SARFAESI procedure; "
        "added 30-day cure period — compliant with Transfer of Property Act 1882 S.69.",
    ),

    # ── 12. Unilateral salary reduction → mutual consent variation ─────────
    (
        r"\bunilateral(ly)?.{0,60}(reduc|cut|decreas|revis).{0,40}"
        r"(salary|compensation|wage|pay)\b",
        lambda match, orig: (
            "Employee's base compensation, as set out in Schedule A, may not be "
            "reduced without Employee's prior written consent. "
            "Employer may propose a variation to compensation by providing thirty (30) "
            "days' written notice setting out the proposed change and reasons. "
            "Employee shall have twenty (20) days to accept or reject the proposal "
            "in writing. Rejection does not constitute a breach by either party, but "
            "both parties shall negotiate in good faith for a further fifteen (15) days. "
            "Any agreed variation shall be documented in a signed written amendment "
            "to this Agreement."
        ),
        "Prohibited unilateral salary cuts; replaced with mutual consent variation "
        "process — compliant with Indian Contract Act 1872 S.10 and Payment of Wages "
        "Act 1936.",
    ),
]

# ── Fairness keywords for bilateral checker ──────────────────────────────────
# These signal one-sided language that should not appear in a rewritten clause.
UNFAIR_PATTERNS: list = [
    (r"\b(the\s+)?(company|vendor|provider|employer)\s+(may|shall|can|will)\b"
     r".{0,60}\b(client|employee|borrower|user)\s+(may\s+not|shall\s+not|cannot)\b",
     "One party granted right explicitly denied to the other"),
    (r"\bat\s+(its|our|their)\s+sole\s+(and\s+absolute\s+)?discretion\b",
     "Sole discretion without objective standard — one-sided"),
    (r"\bfinal\s+and\s+binding\b.{0,40}\bwithout\s+(appeal|recourse|review)\b",
     "No appeal mechanism — one-sided finality"),
    (r"\bwithout\s+(prior\s+)?notice\b.{0,60}\b(terminat|modif|amend|reduc|withhold)\b",
     "Material action permitted without notice — procedurally one-sided"),
    (r"\bnon[- ]refundable\b.{0,80}\bunder\s+(any|all)\s+(circumstance|condition)\b",
     "Absolute non-refundability — no buyer protection"),
]


def apply_rewrite_template(clause_text: str) -> dict | None:
    """
    Attempts to match a rewrite template against the clause text.

    Returns:
      {
        "fixed_text":       str,   # deterministic rewrite
        "fix_explanation":  str,   # human-readable reason
        "template_matched": str,   # regex that matched (for debug)
      }
    or None if no template matches.
    """
    text_lower = clause_text.lower()
    for pattern, template_fn, explanation in REWRITE_TEMPLATES:
        match = re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL)
        if match:
            try:
                fixed = template_fn(match, clause_text)
                expl  = explanation(match) if callable(explanation) else explanation
                return {
                    "fixed_text":       fixed,
                    "fix_explanation":  expl,
                    "template_matched": pattern[:60],
                }
            except Exception as e:
                print(f"[RewriteTemplate] Error applying template: {e}")
                continue
    return None


def apply_rewrite_templates_all(clauses: list, score_map: dict) -> dict:
    """
    Applies rewrite templates to all HIGH/CRITICAL clauses.
    Returns a dict keyed by clause_id with template rewrites.
    Only processes clauses with risk_score >= 60.

    Args:
        clauses:   List[Clause]
        score_map: dict from merge_scores() — {clause_id: merged_score_dict}

    Returns:
        { clause_id: { fixed_text, fix_explanation, template_matched } }
    """
    results = {}
    for clause in clauses:
        score = (score_map.get(clause.clause_id) or {}).get("risk_score", 0)
        if score < 60:
            continue
        template_result = apply_rewrite_template(clause.text)
        if template_result:
            results[clause.clause_id] = template_result
    return results


def check_bilateral_fairness(fixed_text: str) -> list:
    """
    Scans a rewritten clause for residual one-sided language.
    Returns a list of fairness issues found (empty = clause is fair).

    Args:
        fixed_text: the rewritten clause text

    Returns:
        List[str] — list of fairness issue descriptions
    """
    issues = []
    text_lower = fixed_text.lower()
    for pattern, issue_description in UNFAIR_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL):
            issues.append(issue_description)
    return issues


def score_readability(text: str) -> dict:
    """
    Estimates readability using a simplified Flesch-Kincaid Grade Level proxy.
    Pure Python, no external libraries.

    Returns:
      {
        "grade_level":    float,   # estimated US school grade level
        "word_count":     int,
        "avg_sentence_len": float,
        "avg_syllables":  float,
        "readable":       bool,    # True if grade_level <= 12 (B2 equivalent)
        "verdict":        str,
      }
    """
    # Count sentences
    sentences = re.split(r'[.!?]+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    n_sentences = max(len(sentences), 1)

    # Count words
    words = re.findall(r'\b\w+\b', text)
    n_words = max(len(words), 1)

    # Estimate syllables (vowel-group counting — approximate)
    def count_syllables(word: str) -> int:
        word = word.lower()
        vowels = re.findall(r'[aeiou]+', word)
        count = len(vowels)
        if word.endswith('e') and count > 1:
            count -= 1
        return max(count, 1)

    total_syllables  = sum(count_syllables(w) for w in words)
    avg_sentence_len = n_words / n_sentences
    avg_syllables    = total_syllables / n_words

    # Flesch-Kincaid Grade Level formula
    fk_grade = (0.39 * avg_sentence_len) + (11.8 * avg_syllables) - 15.59
    fk_grade = max(round(fk_grade, 1), 1.0)

    # B2 reading level ≈ Grade 10–12
    readable = fk_grade <= 12.0

    if fk_grade <= 8:
        verdict = "PLAIN (Grade 1–8): Excellent clarity."
    elif fk_grade <= 12:
        verdict = f"STANDARD (Grade {fk_grade}): Acceptable — B2 level."
    elif fk_grade <= 16:
        verdict = f"COMPLEX (Grade {fk_grade}): Legal drafting acceptable but could simplify."
    else:
        verdict = f"DENSE (Grade {fk_grade}): Consider splitting into shorter sentences."

    return {
        "grade_level":      fk_grade,
        "word_count":       n_words,
        "avg_sentence_len": round(avg_sentence_len, 1),
        "avg_syllables":    round(avg_syllables, 2),
        "readable":         readable,
        "verdict":          verdict,
    }


def validate_fixed_clause(
    original_text:   str,
    fixed_text:      str,
    fix_explanation: str,
) -> dict:
    """
    Validates a fixed clause against three criteria:
      1. Fairness     — no residual one-sided language
      2. Readability  — Flesch-Kincaid grade level <= 12
      3. Scope creep  — fixed clause does not introduce
                        major new concepts absent from the original

    Returns:
      {
        "valid":            bool,
        "fairness_issues":  List[str],
        "readability":      dict,
        "scope_warning":    str or None,
      }
    """
    # 1. Fairness check
    fairness_issues = check_bilateral_fairness(fixed_text)

    # 2. Readability
    readability = score_readability(fixed_text)

    # 3. Scope-creep detection
    # Measure how much of the fixed text is "new" vs original
    # using SequenceMatcher similarity. If similarity < 0.15 AND
    # fixed text is >3x longer, flag as potential scope creep.
    similarity = SequenceMatcher(
        None,
        original_text.lower(),
        fixed_text.lower(),
    ).ratio()
    len_ratio = len(fixed_text) / max(len(original_text), 1)

    scope_warning = None
    if similarity < 0.10 and len_ratio > 4.0:
        scope_warning = (
            f"Fixed clause is {len_ratio:.1f}x longer than the original with "
            f"only {similarity:.0%} text similarity — verify no new obligations "
            "were introduced beyond what the original contained."
        )

    valid = (
        len(fairness_issues) == 0
        and readability["readable"]
        and scope_warning is None
    )

    return {
        "valid":           valid,
        "fairness_issues": fairness_issues,
        "readability":     readability,
        "scope_warning":   scope_warning,
    }


def merge_fixed_clauses(
    llm_fixes:         list,
    template_rewrites: dict,
    clauses:           list,
) -> list:
    """
    Merges LLM-generated fixed clauses with deterministic template rewrites.

    Strategy:
      - For each clause_id in template_rewrites:
          * If LLM also fixed it: validate both, prefer the one that passes
            fairness + readability checks. If both pass, prefer LLM (richer).
          * If only template exists: use template, mark source="template"
      - For LLM-only fixes (no template): validate and include if valid.
      - Append _validation metadata (stripped before final API response).

    Args:
        llm_fixes:         list from _parse_json_output() on FixerAgent
        template_rewrites: dict from apply_rewrite_templates_all()
        clauses:           List[Clause] (for original text lookup)

    Returns:
        List[dict] with keys: clause_id, original_text, fixed_text,
                              fix_explanation, _source, _validation
    """
    clause_map = {c.clause_id: c for c in clauses}
    llm_map    = {
        item.get("clause_id"): item
        for item in llm_fixes
        if item.get("clause_id")
    }

    results   = []
    processed = set()

    # ── Template rewrites (ground truth anchors) ──────────────────────────
    for clause_id, tmpl in template_rewrites.items():
        processed.add(clause_id)
        clause       = clause_map.get(clause_id)
        original_txt = clause.text if clause else ""

        tmpl_validation = validate_fixed_clause(
            original_txt,
            tmpl["fixed_text"],
            tmpl["fix_explanation"],
        )

        llm = llm_map.get(clause_id)
        if llm:
            llm_fixed      = llm.get("fixed_text", "")
            llm_expl       = llm.get("fix_explanation", "")
            llm_validation = validate_fixed_clause(
                original_txt, llm_fixed, llm_expl
            )

            # Both valid → prefer LLM for richer language
            if llm_validation["valid"] and tmpl_validation["valid"]:
                chosen_text = llm_fixed
                chosen_expl = llm_expl
                source      = "llm_validated"
                validation  = llm_validation

            # Only template valid → use template
            elif tmpl_validation["valid"] and not llm_validation["valid"]:
                chosen_text = tmpl["fixed_text"]
                chosen_expl = tmpl["fix_explanation"]
                source      = "template_fallback"
                validation  = tmpl_validation

            # Only LLM valid → use LLM
            elif llm_validation["valid"] and not tmpl_validation["valid"]:
                chosen_text = llm_fixed
                chosen_expl = llm_expl
                source      = "llm_only"
                validation  = llm_validation

            # Neither fully valid → use template (deterministic is safer)
            else:
                chosen_text = tmpl["fixed_text"]
                chosen_expl = (
                    tmpl["fix_explanation"] +
                    " [Note: automated validation flagged issues — human review advised.]"
                )
                source     = "template_with_warnings"
                validation = tmpl_validation

        else:
            # No LLM fix for this clause — use template
            chosen_text = tmpl["fixed_text"]
            chosen_expl = tmpl["fix_explanation"]
            source      = "template_only"
            validation  = tmpl_validation

        results.append({
            "clause_id":       clause_id,
            "original_text":   original_txt,
            "fixed_text":      chosen_text,
            "fix_explanation": chosen_expl,
            "_source":         source,
            "_validation":     validation,
        })

    # ── LLM-only fixes (no matching template) ────────────────────────────
    for clause_id, llm in llm_map.items():
        if clause_id in processed:
            continue
        clause       = clause_map.get(clause_id)
        original_txt = clause.text if clause else llm.get("original_text", "")
        llm_fixed    = llm.get("fixed_text", "")
        llm_expl     = llm.get("fix_explanation", "")
        validation   = validate_fixed_clause(original_txt, llm_fixed, llm_expl)

        results.append({
            "clause_id":       clause_id,
            "original_text":   original_txt,
            "fixed_text":      llm_fixed,
            "fix_explanation": llm_expl,
            "_source":         "llm_only",
            "_validation":     validation,
        })

    return results


def strip_internal_metadata(fixed_clauses: list) -> list:
    """
    Removes internal keys (_source, _validation, _all_reasons)
    before returning to Shashank's server — they are not in the API contract.
    """
    clean = []
    for item in fixed_clauses:
        clean.append({
            k: v for k, v in item.items()
            if not k.startswith("_")
        })
    return clean


# ── Import Ullas's schemas and bridge tools ───────────────────────────────────
from schemas import Clause, ComplianceViolation

# Try to import Ullas's bridge tools — fall back gracefully if not ready
try:
    from memory.bridge import (
        contradiction_tool,
        citation_tool,
        rag_index_tool,
    )
    BRIDGE_TOOLS_AVAILABLE = True
except ImportError:
    BRIDGE_TOOLS_AVAILABLE = False
    contradiction_tool = None
    citation_tool      = None
    rag_index_tool     = None

# ── LLM config ────────────────────────────────────────────────────────────────
MODEL       = os.getenv("CREWAI_MODEL",       "claude-sonnet-4-20250514")
TEMPERATURE = float(os.getenv("CREWAI_TEMPERATURE", "0.2"))
MAX_TOKENS  = int(os.getenv("MAX_TOKENS_PER_AGENT", "2000"))


# ══════════════════════════════════════════════════════════════════════════════
# LLM FACTORY
# ══════════════════════════════════════════════════════════════════════════════

def _get_llm():
    """Returns a configured Claude LLM instance for CrewAI."""
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(
        model=MODEL,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )


# ══════════════════════════════════════════════════════════════════════════════
# AGENT DEFINITIONS
# Each agent has a distinct role, backstory, and toolset.
# Tools from Ullas's bridge are attached where relevant.
# ══════════════════════════════════════════════════════════════════════════════

def _make_risk_agent() -> Agent:
    """RiskAgent — reads every clause and assigns a risk score 0–100.
    Uses Ullas's ContradictionTool and CitationTool to ground findings."""
    tools = []
    if BRIDGE_TOOLS_AVAILABLE:
        tools = [contradiction_tool, citation_tool]

    return Agent(
        role="Senior Legal Risk Analyst",
        goal=(
            "Analyse each contract clause and assign a precise risk score from 0 to 100. "
            "Identify one-sided obligations, liability traps, vague language, "
            "auto-renewal clauses, and clauses that contradict each other. "
            "Flag every clause that scores above 35 with a specific reason."
        ),
        backstory=(
            "You are a 15-year veteran of commercial contract review at a Magic Circle law firm. "
            "You have reviewed thousands of SaaS agreements, NDAs, employment contracts, and "
            "vendor agreements. You are known for finding the clause that every other lawyer "
            "missed — the one buried on page 8 that reverses the entire liability structure. "
            "You do not use vague language. Every risk score is justified with a precise clause reference."
        ),
        tools=tools,
        llm=_get_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )


def _make_compliance_agent() -> Agent:
    """ComplianceAgent — finds regulatory violations: GDPR, DPDP Act, labour law, IP law."""
    tools = []
    if BRIDGE_TOOLS_AVAILABLE:
        tools = [citation_tool]

    return Agent(
        role="Regulatory Compliance Specialist",
        goal=(
            "Identify every clause that violates applicable law or regulation. "
            "Focus on: GDPR Articles 5, 6, 7, 12–22, 28, 32; "
            "India DPDP Act 2023; Indian labour law (non-compete enforceability); "
            "IP ownership under Indian Copyright Act; "
            "Predatory lending clauses under RBI guidelines. "
            "Return violation_type, affected clause_id, description, and severity."
        ),
        backstory=(
            "You are a dual-qualified lawyer (UK Solicitor + Indian Advocate) "
            "specialising in data protection and technology law. "
            "You have represented clients in ICO investigations and GDPR audits. "
            "You find compliance violations that generic AI tools miss because you "
            "know the exact article numbers and their practical implications. "
            "You never flag a violation without citing the specific legal provision breached."
        ),
        tools=tools,
        llm=_get_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )


def _make_fixer_agent() -> Agent:
    """FixerAgent — rewrites risky clauses to be fair, balanced, and legally sound.
    Uses RagIndexTool to confirm rewrites are grounded in contract context."""
    tools = []
    if BRIDGE_TOOLS_AVAILABLE:
        tools = [citation_tool, rag_index_tool]

    return Agent(
        role="Contract Drafting Specialist",
        goal=(
            "Rewrite every clause flagged as HIGH or CRITICAL risk. "
            "The rewritten clause must: (1) preserve the commercial intent, "
            "(2) be bilateral and fair to both parties, "
            "(3) use plain English at B2 reading level, "
            "(4) not introduce new legal obligations not present in the original. "
            "For each fixed clause, explain in one sentence what was changed and why."
        ),
        backstory=(
            "You are a senior contract negotiation specialist who has drafted "
            "commercial agreements for FTSE 100 companies and early-stage startups alike. "
            "Your superpower is simplifying dense legal language without losing precision. "
            "You know that the best contract clause is one that both parties understand "
            "without needing a lawyer to interpret it. "
            "You only fix clauses that genuinely need fixing — you never over-engineer."
        ),
        tools=tools,
        llm=_get_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TASK DEFINITIONS
# Each Task maps to one Agent and has a structured output format.
# ══════════════════════════════════════════════════════════════════════════════

def _make_risk_task(
    agent: Agent,
    clauses_summary: str,
    pre_scores: dict,
) -> Task:
    """
    Enriched risk task. Pre-score context is injected into the prompt
    so the LLM focuses on genuinely ambiguous clauses rather than
    recomputing what the regex engine already caught.
    """
    # Build a compact pre-score summary for the LLM
    pre_context_lines = []
    for cid, data in pre_scores.items():
        score   = data.get("base_score", 0)
        flags   = ", ".join(data.get("flags", [])) or "none"
        reasons = data.get("reasons", [])
        r_short = reasons[0][:80] if reasons else "No pattern match."
        pre_context_lines.append(
            f"  {cid}: pre_score={score}, flags=[{flags}], hint={r_short}"
        )

    pre_context = "\n".join(pre_context_lines) if pre_context_lines else "  (none)"

    return Task(
        description=f"""
You are given contract clauses and a preliminary deterministic risk assessment
computed by a pattern engine. Your job is to REFINE these scores using legal
reasoning — do not simply echo the pre-scores. Increase scores where the
full clause context reveals additional risk. Decrease scores where the
pattern engine was overly conservative.

PRE-SCORE CONTEXT (use as starting point, not final answer):
{pre_context}

FULL CLAUSE TEXT:
{clauses_summary}

For each clause, output a precise risk score 0–100 and one clear reason.

Consider:
  - Does this clause contradict any other clause in the document?
  - Is one party given rights the other is denied?
  - Could this clause be weaponised against the weaker party?
  - Does the language leave critical terms undefined?
  - Is the obligation practically impossible to fulfil?

Risk scale:
  0–34   LOW      → minor concern, industry standard language
  35–59  MEDIUM   → needs negotiation, not a dealbreaker
  60–79  HIGH     → material risk, likely to cause dispute
  80–100 CRITICAL → must fix before signing

Flags — use ONLY from this list:
  CONTRADICTION, GDPR_VIOLATION, AUTO_RENEWAL, ONE_SIDED,
  LOOPHOLE, MISSING_NOTICE, VAGUE_TERM, IP_TRAP,
  PREDATORY_PAYMENT, HIGH_RISK

Return ONLY a valid JSON array — no preamble, no markdown backticks:
[
  {{
    "clause_id":    "clause_3_1",
    "risk_score":   82,
    "risk_reason":  "Liability cap (clause 3.1) directly contradicted by unlimited liability clause 3.2 — MUTUAL_EXCLUSION confirmed.",
    "flags":        ["CONTRADICTION", "ONE_SIDED"]
  }}
]
""",
        expected_output=(
            "A JSON array of risk objects, one per clause. "
            "Each object must contain clause_id (str), risk_score (int 0-100), "
            "risk_reason (str, one sentence), and flags (list of str from the allowed list)."
        ),
        agent=agent,
        output_json=True,
    )


def _make_compliance_task(
    agent: Agent,
    clauses_summary: str,
    det_violations: list,
) -> Task:
    """
    Enriched compliance task. Deterministic violations are injected
    as verified citations — the LLM adds legal reasoning depth,
    not raw article lookup (which it may hallucinate).
    """
    # Build compact citation context
    if det_violations:
        det_lines = []
        for v in det_violations:
            det_lines.append(
                f"  [{v['severity']}] {v['clause_id']} | {v['violation_type']} | "
                f"{v['legal_ref']} | {v['description'][:80]}..."
            )
        det_context = "\n".join(det_lines)
    else:
        det_context = "  No pattern-matched violations detected."

    return Task(
        description=f"""You are a dual-qualified data protection and technology lawyer.
A deterministic legal citation engine has already identified potential
violations in this contract. Your job is to:
1. CONFIRM or REJECT each pre-detected violation with legal reasoning
2. ADD any violations the pattern engine missed
3. Ensure every violation references the EXACT law article it breaches

PRE-DETECTED VIOLATIONS (verified by pattern engine — treat as confirmed
unless you have strong reason to reject):
{det_context}

FULL CLAUSE TEXT FOR CONTEXT:
{clauses_summary}

Violation types you MUST check for (beyond what's pre-detected):
  GDPR_VIOLATION         → GDPR Articles 5,6,7,12–22,28,32,33,34,44–49
  DPDP_VIOLATION         → India DPDP Act 2023, Sections 5–17
  LABOUR_LAW_VIOLATION   → Industrial Disputes Act S.25F, Contract Act S.27
  IP_VIOLATION           → Indian Copyright Act S.17, S.57
  PREDATORY_CLAUSE       → Contract Act S.74, Transfer of Property Act S.69
  CONFLICT_OF_LAW        → Governing law vs jurisdiction mismatch
  AUTO_RENEWAL_TRAP      → Unconscionable short notice windows

Severity scale:
  CRITICAL → clause is void or creates immediate regulatory liability
  HIGH     → material risk, regulatory fine or litigation likely
  MEDIUM   → enforceable but one-sided, needs negotiation
  LOW      → minor concern, best practice deviation

Return ONLY a valid JSON array — no preamble, no markdown backticks:
[{{
  "clause_id":      "clause_4_2",
  "violation_type": "GDPR_VIOLATION",
  "description":    "Clause permits sharing of personal data with third-party analytics partners without consent, violating GDPR Art. 6(1)(a). No legitimate interest assessment is documented.",
  "severity":       "CRITICAL",
  "legal_ref":      "GDPR Art. 6(1)(a) & Art. 7"
}}]

If you find no additional violations beyond what was pre-detected, return
only the pre-detected ones in the same format. Do NOT return an empty array
if pre-detected violations exist.""",
        expected_output=(
            "A JSON array of compliance violation objects. "
            "Each must have: clause_id (str), violation_type (str), "
            "description (str — one detailed sentence citing the law), "
            "severity (CRITICAL/HIGH/MEDIUM/LOW), legal_ref (str). "
            "Minimum: all pre-detected violations must appear."
        ),
        agent=agent,
        output_json=True,
    )


def _make_fixer_task(
    agent:             Agent,
    clauses_summary:   str,
    risk_summary:      str,
    template_rewrites: dict,
) -> Task:
    """
    Enriched fixer task. Template rewrites are injected as anchors —
    the LLM refines rather than drafts from scratch, reducing hallucination.
    """
    # Build compact template context
    if template_rewrites:
        tmpl_lines = []
        for cid, tmpl in template_rewrites.items():
            tmpl_lines.append(
                f"  {cid} [TEMPLATE ANCHOR]:\n"
                f"    FIXED : {tmpl['fixed_text'][:120]}...\n"
                f"    REASON: {tmpl['fix_explanation'][:80]}..."
            )
        tmpl_context = "\n".join(tmpl_lines)
    else:
        tmpl_context = "  No template anchors available — draft from scratch."

    return Task(
        description=f"""
You are a senior contract drafting specialist. Your task is to rewrite every
HIGH-RISK or CRITICAL clause into balanced, plain-English language.

TEMPLATE ANCHORS (deterministic rewrites already computed — you may refine
these but should not deviate significantly from their legal intent):
{tmpl_context}

RISK ASSESSMENTS (use these to prioritise):
{risk_summary}

ORIGINAL CLAUSE TEXT:
{clauses_summary}

REWRITING RULES — follow all of these:
1. Only rewrite clauses with risk_score >= 60 (HIGH or CRITICAL)
2. PRESERVE the commercial intent — do not change what the clause is for
3. Make every obligation BILATERAL — both parties must have equal rights
   and equal responsibilities wherever possible
4. Use PLAIN ENGLISH at B2 reading level:
   - Maximum 25 words per sentence
   - No Latin terms (use English equivalents)
   - Spell out abbreviations on first use
5. Do NOT introduce obligations, rights, or concepts not present in the original
6. Do NOT simply copy the template anchor verbatim — adapt it to the
   specific context of this clause
7. Include a specific one-sentence explanation of what changed and why

For each clause you fix, provide:
  - clause_id      : the exact clause_id from the input
  - original_text  : the exact original clause text (do not paraphrase)
  - fixed_text     : your rewritten clause (plain English, bilateral)
  - fix_explanation: one sentence — what changed and the legal reason

Return ONLY a valid JSON array — no preamble, no markdown backticks:
[
  {{
    "clause_id":       "clause_3_1",
    "original_text":   "The Company's liability is limited to fees paid in the preceding one month.",
    "fixed_text":      "Each party's total aggregate liability shall not exceed the greater of: (a) fees paid in the preceding twelve months, or (b) INR 10,00,000.",
    "fix_explanation": "Made bilateral, extended lookback to 12 months (industry standard), added INR floor."
  }}
]

If no clauses require fixing, return: []
""",
        expected_output=(
            "A JSON array of fixed clause objects. "
            "Each must have: clause_id (str), original_text (str), "
            "fixed_text (str — plain English, bilateral), "
            "fix_explanation (str — one sentence). "
            "Return [] if nothing needs fixing."
        ),
        agent=agent,
        output_json=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# CLAUSE SERIALISER
# Converts List[Clause] into a text block the agents can read.
# ══════════════════════════════════════════════════════════════════════════════

def _serialise_clauses(clauses: List[Clause]) -> str:
    """Converts a list of Clause objects into a numbered text summary
    readable by the LLM agents."""
    lines = []
    for c in clauses:
        lines.append(
            f"[{c.clause_id}] §{c.clause_number} ({c.section}, Page {c.page_number}):\n"
            f"  {c.text}\n"
        )
    return "\n".join(lines) if lines else "No clauses provided."


def _parse_json_output(raw: str) -> list:
    """Safely parses the agent's JSON output.
    Strips markdown code fences if the model wraps output in them."""
    if not raw:
        return []
    cleaned = raw.strip()
    # Strip ```json ... ``` fences
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        result = json.loads(cleaned)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        return []


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API — Shashank calls only this function
# ══════════════════════════════════════════════════════════════════════════════

def analyse(clauses: List[Clause]) -> dict:
    """Main entry point called by Shashank's server.py after upload.

    Args:
        clauses: List[Clause] from Ullas's schemas.py

    Returns:
        {
            "compliance_violations": List[dict],
            "fixed_clauses":         List[dict]
        }

    This function is intentionally stub-safe:
    if the LLM call fails (no API key, rate limit, network error),
    it falls back to the deterministic pre-scoring + legal citation engines.
    """
    if not clauses:
        return {"compliance_violations": [], "fixed_clauses": []}

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    stub_mode = not api_key or api_key in ("stub", "your_anthropic_api_key_here", "")

    if stub_mode:
        print("[CrewAI] No valid API key — running deterministic engines only.")
        return _stub_result(clauses)

    clauses_text = _serialise_clauses(clauses)

    try:
        return _run_crew(clauses, clauses_text)
    except Exception as e:
        print(f"[CrewAI] Pipeline error: {e}. Falling back to deterministic result.")
        return _stub_result(clauses)


def _run_crew(clauses: List[Clause], clauses_text: str) -> dict:
    """
    Final 3-agent pipeline with all Task 1–4 enhancements.

    Flow:
      1.  Pre-score all clauses            (Task 2 — deterministic)
      2.  Z3 contradiction boosts          (Task 2 — Ullas's bridge)
      3.  Legal citation detection         (Task 3 — deterministic)
      4.  RiskAgent LLM refinement         (Task 2 — LLM)
      5.  Merge LLM + pre-scores           (Task 2)
      6.  Apply rewrite templates          (Task 4 — deterministic)
      7.  ComplianceAgent LLM enrichment   (Task 3 — LLM)
      8.  Merge LLM + det violations       (Task 3)
      9.  FixerAgent rewrite + refine      (Task 4 — LLM)
      10. Merge LLM fixes + templates      (Task 4)
      11. Validate and strip metadata      (Task 4)
    """
    # ── Step 1: Deterministic pre-scoring ────────────────────────────────────
    pre_scores = pre_score_all_clauses(clauses)

    # ── Step 2: Z3 contradiction boosts ──────────────────────────────────────
    if BRIDGE_TOOLS_AVAILABLE:
        try:
            from memory.bridge import run_full_analysis
            from memory.reset_between_docs import reset_for_new_document
            reset_for_new_document()
            bridge_quick   = run_full_analysis(clauses)
            contradictions = bridge_quick.get("contradictions", [])
            pre_scores     = apply_z3_boosts(pre_scores, contradictions)
        except Exception as e:
            print(f"[PreScore] Z3 boost skipped: {e}")

    # ── Step 3: Legal citation detection ─────────────────────────────────────
    det_violations = detect_legal_violations(clauses, pre_scores)
    print(f"[LegalCite] {len(det_violations)} deterministic violation(s).")

    # ── Step 4: RiskAgent ────────────────────────────────────────────────────
    risk_agent = _make_risk_agent()
    risk_task  = _make_risk_task(risk_agent, clauses_text, pre_scores)
    risk_crew  = Crew(
        agents=[risk_agent], tasks=[risk_task],
        process=Process.sequential, verbose=False,
    )
    risk_output = risk_crew.kickoff()
    llm_scores  = _parse_json_output(str(risk_output) if risk_output else "[]")

    # ── Step 5: Merge scores ─────────────────────────────────────────────────
    merged_scores = merge_scores(llm_scores, pre_scores)
    score_map     = {item["clause_id"]: item for item in merged_scores}
    for clause in clauses:
        if clause.clause_id in score_map:
            m = score_map[clause.clause_id]
            clause.risk_score  = m["risk_score"]
            clause.flags       = m["flags"]
            clause.risk_reason = m["risk_reason"]

    # ── Step 6: Deterministic rewrite templates ───────────────────────────────
    template_rewrites = apply_rewrite_templates_all(clauses, score_map)
    print(f"[Rewrite] {len(template_rewrites)} template rewrite(s) computed.")

    # ── Step 7: ComplianceAgent ───────────────────────────────────────────────
    compliance_agent = _make_compliance_agent()
    compliance_task  = _make_compliance_task(
        compliance_agent, clauses_text, det_violations
    )
    compliance_crew = Crew(
        agents=[compliance_agent], tasks=[compliance_task],
        process=Process.sequential, verbose=False,
    )
    compliance_output = compliance_crew.kickoff()
    llm_violations    = _parse_json_output(
        str(compliance_output) if compliance_output else "[]"
    )

    # ── Step 8: Merge violations ─────────────────────────────────────────────
    final_violations = deduplicate_violations(llm_violations, det_violations)
    print(f"[Compliance] {len(final_violations)} final violation(s).")

    # ── Step 9: FixerAgent ───────────────────────────────────────────────────
    high_risk_clauses = [c for c in clauses if (c.risk_score or 0) >= 60]
    llm_fixes = []
    if high_risk_clauses:
        high_risk_text = _serialise_clauses(high_risk_clauses)
        risk_summary   = json.dumps(
            [score_map[c.clause_id] for c in high_risk_clauses
             if c.clause_id in score_map],
            indent=2,
        )
        fixer_agent = _make_fixer_agent()
        fixer_task  = _make_fixer_task(
            fixer_agent, high_risk_text, risk_summary, template_rewrites
        )
        fixer_crew = Crew(
            agents=[fixer_agent], tasks=[fixer_task],
            process=Process.sequential, verbose=False,
        )
        fixer_output = fixer_crew.kickoff()
        llm_fixes    = _parse_json_output(
            str(fixer_output) if fixer_output else "[]"
        )

    # ── Step 10: Merge LLM fixes with templates ───────────────────────────────
    merged_fixes = merge_fixed_clauses(llm_fixes, template_rewrites, clauses)

    # ── Step 11: Strip internal metadata before returning ────────────────────
    final_fixes = strip_internal_metadata(merged_fixes)

    return {
        "compliance_violations": final_violations,
        "fixed_clauses":         final_fixes,
    }


def _stub_result(clauses: List[Clause]) -> dict:
    """Returns a deterministic result using pre-scoring + legal citation engines.
    Called when the LLM pipeline fails (no API key, rate limit, network error).
    Ensures Shashank's merge and Dhanush's dashboard always get real data."""
    if not clauses:
        return {"compliance_violations": [], "fixed_clauses": []}

    # Run deterministic engines — these never need an API key
    pre_scores = pre_score_all_clauses(clauses)
    det_violations = detect_legal_violations(clauses, pre_scores)
    template_rewrites = apply_rewrite_templates_all(
        clauses,
        {cid: {"risk_score": d["base_score"]} for cid, d in pre_scores.items()}
    )
    final_fixes = strip_internal_metadata(
        merge_fixed_clauses([], template_rewrites, clauses)
    )

    # Format violations to match Shashank's expected schema
    formatted_violations = [
        {
            "clause_id":      v.get("clause_id", ""),
            "violation_type": v.get("violation_type", "UNKNOWN"),
            "description":    v.get("description", ""),
            "severity":       v.get("severity", "MEDIUM"),
        }
        for v in det_violations
    ]

    return {
        "compliance_violations": formatted_violations,
        "fixed_clauses":         final_fixes,
    }


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE SMOKE TEST
# Run: cd regulaite && python agents/crew.py
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from schemas import Clause
    import pprint

    print("=== RegulAIte Task 4 — FixerAgent + Rewrite Engine Smoke Test ===\n")

    test_clauses = [
        Clause(
            clause_id="clause_3_1", page_number=1, clause_number="3.1",
            text="The Company's liability is limited to fees paid in the preceding one month.",
            section="Liability",
        ),
        Clause(
            clause_id="clause_3_2", page_number=2, clause_number="3.2",
            text="There is no limit on liability for any damages arising from this agreement.",
            section="Liability",
        ),
        Clause(
            clause_id="clause_4_2", page_number=3, clause_number="4.2",
            text=(
                "Vendor may use aggregated Client Data for product improvement and may share "
                "such data with third-party analytics partners without further consent."
            ),
            section="Data Privacy",
        ),
        Clause(
            clause_id="clause_4_3", page_number=3, clause_number="4.3",
            text="Vendor stores all personal data on unencrypted servers in Singapore.",
            section="Data Security",
        ),
        Clause(
            clause_id="clause_7_1", page_number=4, clause_number="7.1",
            text="Either party may terminate at will without cause and without notice required.",
            section="Termination",
        ),
        Clause(
            clause_id="clause_12_1", page_number=5, clause_number="12.1",
            text=(
                "Employee assigns all intellectual property rights to Employer "
                "regardless of when, where, or how it was created."
            ),
            section="Intellectual Property",
        ),
        Clause(
            clause_id="clause_2_3", page_number=6, clause_number="2.3",
            text=(
                "Employer may unilaterally reduce Employee's compensation at any time "
                "at its sole discretion without prior notice."
            ),
            section="Compensation",
        ),
        Clause(
            clause_id="clause_5_1", page_number=7, clause_number="5.1",
            text="All fees paid are non-refundable under any circumstances.",
            section="Payment",
        ),
    ]

    # Pre-score to build score_map
    pre = pre_score_all_clauses(test_clauses)
    score_map_test = {
        cid: {"risk_score": data["base_score"], "flags": data["flags"]}
        for cid, data in pre.items()
    }

    # ── Test 1: Rewrite template application ────────────────────────────────
    print("── TEST 1: Rewrite Template Application ──\n")
    template_results = apply_rewrite_templates_all(test_clauses, score_map_test)
    print(f"  Clauses with template rewrites: {len(template_results)}")
    for cid, tmpl in template_results.items():
        print(f"  {cid}: {tmpl['fix_explanation'][:70]}...")

    assert "clause_4_2" in template_results, \
        "FAIL: GDPR data sharing clause should have a template rewrite"
    assert "clause_3_1" in template_results or "clause_3_2" in template_results, \
        "FAIL: Liability clause should have a template rewrite"
    assert "clause_7_1" in template_results, \
        "FAIL: Termination-at-will clause should have a template rewrite"
    print("\n  Template application assertions PASSED\n")

    # ── Test 2: Bilateral fairness checker ──────────────────────────────────
    print("── TEST 2: Bilateral Fairness Checker ──\n")
    unfair_text = (
        "The Company may at its sole discretion terminate this Agreement "
        "without prior notice. The Client may not terminate without cause."
    )
    fair_text = (
        "Either party may terminate this Agreement by providing thirty (30) "
        "days written notice to the other party."
    )
    unfair_issues = check_bilateral_fairness(unfair_text)
    fair_issues   = check_bilateral_fairness(fair_text)

    print(f"  Unfair text issues: {unfair_issues}")
    print(f"  Fair text issues  : {fair_issues}")

    assert len(unfair_issues) > 0, "FAIL: Unfair clause should be flagged"
    assert len(fair_issues)   == 0, "FAIL: Fair clause should pass"
    print("\n  Fairness checker assertions PASSED\n")

    # ── Test 3: Readability scorer ──────────────────────────────────────────
    print("── TEST 3: Readability Scorer ──\n")
    dense_text = (
        "Notwithstanding any other provision herein, the indemnifying party's "
        "obligation to indemnify, defend, and hold harmless the indemnified party "
        "from and against any and all claims, damages, losses, liabilities, costs "
        "and expenses (including reasonable attorneys' fees) arising out of or "
        "relating to any third-party claim alleging infringement of intellectual "
        "property rights shall survive the termination or expiration of this "
        "Agreement indefinitely."
    )
    plain_text = (
        "Either party will defend the other against third-party IP claims. "
        "The defending party will cover all reasonable legal costs. "
        "This obligation continues after the Agreement ends."
    )
    dense_score = score_readability(dense_text)
    plain_score = score_readability(plain_text)

    print(f"  Dense text  grade level: {dense_score['grade_level']} — {dense_score['verdict']}")
    print(f"  Plain text  grade level: {plain_score['grade_level']} — {plain_score['verdict']}")

    assert plain_score["grade_level"] < dense_score["grade_level"], \
        "FAIL: Plain text should score lower grade level than dense text"
    assert plain_score["readable"], \
        f"FAIL: Plain text should be readable, got grade {plain_score['grade_level']}"
    print("\n  Readability assertions PASSED\n")

    # ── Test 4: validate_fixed_clause() ────────────────────────────────────
    print("── TEST 4: Clause Validation ──\n")
    original = "The Company's liability is limited to one month of fees."
    good_fix  = (
        "Each party's total liability shall not exceed fees paid in the "
        "preceding twelve months or INR 10,00,000, whichever is greater."
    )
    bad_fix   = (
        "The Company may at its sole discretion limit liability without "
        "notice to the Client under any circumstances whatsoever."
    )
    good_result = validate_fixed_clause(original, good_fix, "Made bilateral")
    bad_result  = validate_fixed_clause(original, bad_fix,  "Still one-sided")

    print(f"  Good fix valid : {good_result['valid']}")
    print(f"  Bad fix valid  : {bad_result['valid']}")
    print(f"  Bad fix issues : {bad_result['fairness_issues']}")

    assert good_result["valid"],    "FAIL: Good fix should pass validation"
    assert not bad_result["valid"], "FAIL: Bad fix should fail validation"
    print("\n  Validation assertions PASSED\n")

    # ── Test 5: merge_fixed_clauses() ─────────────────────────────────────
    print("── TEST 5: Fixed Clause Merging ──\n")
    mock_llm_fixes = [
        {
            "clause_id":       "clause_4_2",
            "original_text":   test_clauses[2].text,
            "fixed_text":      (
                "Vendor may use only anonymised Client Data for internal product "
                "improvement. Vendor shall not share personal data with any third "
                "party without prior written consent from Client and execution of "
                "a Data Processing Agreement."
            ),
            "fix_explanation": "Restricted to anonymised data; required DPA and consent for sharing.",
        },
        {
            "clause_id":       "clause_6_1",   # Clause not in test_clauses
            "original_text":   "Payments are due within 90 days of invoice.",
            "fixed_text":      "Payments are due within 30 days of invoice.",
            "fix_explanation": "Reduced payment terms to 30 days — industry standard.",
        },
    ]
    merged     = merge_fixed_clauses(mock_llm_fixes, template_results, test_clauses)
    merged_ids = [m["clause_id"] for m in merged]

    # clause_4_2 should appear exactly once
    assert merged_ids.count("clause_4_2") == 1, \
        f"FAIL: clause_4_2 should appear once, got {merged_ids.count('clause_4_2')}"
    # LLM-only clause_6_1 should be included
    assert "clause_6_1" in merged_ids, \
        "FAIL: LLM-only fix clause_6_1 should be included"
    # No _source or _validation keys in final output after stripping
    final = strip_internal_metadata(merged)
    for item in final:
        assert "_source"     not in item, "FAIL: _source key should be stripped"
        assert "_validation" not in item, "FAIL: _validation key should be stripped"

    print(f"  Merged fixes: {len(merged)}")
    print("  Merging and strip assertions PASSED\n")

    # ── Test 6: Full analyse() pipeline ─────────────────────────────────
    print("── TEST 6: Full analyse() Pipeline ──\n")
    result     = analyse(test_clauses)
    violations = result.get("compliance_violations", [])
    fixes      = result.get("fixed_clauses", [])

    print(f"  Violations: {len(violations)}")
    print(f"  Fixes     : {len(fixes)}")

    # Verify no internal metadata leaked into output
    for fix in fixes:
        assert "_source"      not in fix, "FAIL: _source leaked into API response"
        assert "_validation"  not in fix, "FAIL: _validation leaked into API response"
        assert "clause_id"       in fix,  "FAIL: clause_id missing"
        assert "original_text"   in fix,  "FAIL: original_text missing"
        assert "fixed_text"      in fix,  "FAIL: fixed_text missing"
        assert "fix_explanation" in fix,  "FAIL: fix_explanation missing"

    assert isinstance(violations, list) and isinstance(fixes, list), \
        "FAIL: both outputs must be lists"
    print("\n  Full pipeline assertions PASSED\n")

    print("=== Task 4 Smoke Test COMPLETE ===")

    test_clauses = [
        Clause(
            clause_id="clause_4_2", page_number=1, clause_number="4.2",
            text=(
                "Vendor may use aggregated Client Data for product improvement "
                "and may share such data with third-party analytics partners "
                "without further consent."
            ),
            section="Data Privacy",
        ),
        Clause(
            clause_id="clause_4_3", page_number=2, clause_number="4.3",
            text=(
                "Vendor stores all personal data on unencrypted servers "
                "and takes no responsibility for data breaches caused by "
                "third-party attackers."
            ),
            section="Data Security",
        ),
        Clause(
            clause_id="clause_4_4", page_number=2, clause_number="4.4",
            text=(
                "Vendor may re-identify patient data where technically feasible "
                "for improving model accuracy."
            ),
            section="Data Usage",
        ),
        Clause(
            clause_id="clause_5_2", page_number=3, clause_number="5.2",
            text=(
                "Processor may freely engage any sub-processor it deems "
                "appropriate without informing Controller."
            ),
            section="Sub-Processors",
        ),
        Clause(
            clause_id="clause_8_1", page_number=4, clause_number="8.1",
            text=(
                "This Agreement is governed by the laws of Karnataka, India. "
                "Any disputes shall be resolved exclusively in the courts of Singapore."
            ),
            section="Governing Law",
        ),
        Clause(
            clause_id="clause_12_1", page_number=5, clause_number="12.1",
            text=(
                "Employee assigns all intellectual property rights to Employer "
                "regardless of when, where, or how it was created."
            ),
            section="Intellectual Property",
        ),
        Clause(
            clause_id="clause_2_3", page_number=6, clause_number="2.3",
            text=(
                "Employer may revise Employee's compensation downward at any time "
                "at its sole discretion without prior notice."
            ),
            section="Compensation",
        ),
        Clause(
            clause_id="clause_11_2", page_number=7, clause_number="11.2",
            text=(
                "Lender may invoke security and proceed with sale of the "
                "mortgaged property without prior notice to Borrower or court order."
            ),
            section="Security",
        ),
    ]

    # ── Test 1: Legal citation detection ───────────────────────────────────
    print("── TEST 1: Deterministic Legal Citation Detection ──\n")
    pre = pre_score_all_clauses(test_clauses)
    det = detect_legal_violations(test_clauses, pre)
    for v in det:
        print(
            f"  [{v['severity']:8s}] {v['clause_id']:15s} | "
            f"{v['violation_type']:22s} | {v['legal_ref']}"
        )
    print(f"\n  Total deterministic violations: {len(det)}\n")

    # Assertions
    viol_types = [(v["clause_id"], v["violation_type"]) for v in det]
    assert ("clause_4_2", "GDPR_VIOLATION")       in viol_types, \
        "FAIL: Third-party sharing not caught"
    assert ("clause_4_3", "GDPR_VIOLATION")       in viol_types, \
        "FAIL: Unencrypted storage not caught"
    assert ("clause_4_4", "GDPR_VIOLATION")       in viol_types, \
        "FAIL: Re-identification not caught"
    assert ("clause_5_2", "GDPR_VIOLATION")       in viol_types, \
        "FAIL: Sub-processor without auth not caught"
    assert ("clause_8_1", "CONFLICT_OF_LAW")      in viol_types, \
        "FAIL: Jurisdiction conflict not caught"
    assert ("clause_12_1", "IP_VIOLATION")        in viol_types, \
        "FAIL: Blanket IP assignment not caught"
    assert ("clause_2_3", "LABOUR_LAW_VIOLATION") in viol_types, \
        "FAIL: Unilateral salary cut not caught"
    assert ("clause_11_2", "PREDATORY_CLAUSE")    in viol_types, \
        "FAIL: Self-help enforcement not caught"
    print("  All citation detection assertions PASSED\n")

    # ── Test 2: Severity escalation ────────────────────────────────────────
    print("── TEST 2: Severity Escalation Matrix ──\n")
    assert _escalate_severity("HIGH",     90) == "CRITICAL", \
        "FAIL: score=90 should escalate HIGH → CRITICAL"
    assert _escalate_severity("MEDIUM",   65) == "HIGH", \
        "FAIL: score=65 should escalate MEDIUM → HIGH"
    assert _escalate_severity("CRITICAL", 20) == "CRITICAL", \
        "FAIL: CRITICAL pattern should not be downgraded by low score"
    assert _escalate_severity("LOW",      25) == "LOW", \
        "FAIL: LOW pattern + low score should stay LOW"
    print("  All escalation assertions PASSED\n")

    # ── Test 3: Deduplication merging ─────────────────────────────────────
    print("── TEST 3: Violation Deduplication & Merging ──\n")
    mock_llm = [
        {
            "clause_id":      "clause_4_2",
            "violation_type": "GDPR_VIOLATION",
            "description":    "LLM extended description: " + "x" * 120,
            "severity":       "CRITICAL",
            "legal_ref":      "GDPR Art. 6(1)",
        },
        {
            "clause_id":      "clause_4_2",
            "violation_type": "DPDP_VIOLATION",
            "description":    "New LLM violation not in deterministic set.",
            "severity":       "HIGH",
            "legal_ref":      "DPDP Act 2023 S.7",
        },
    ]
    merged = deduplicate_violations(mock_llm, det)

    # GDPR_VIOLATION on clause_4_2 should appear exactly once
    gdpr_42 = [
        v for v in merged
        if v["clause_id"] == "clause_4_2" and v["violation_type"] == "GDPR_VIOLATION"
    ]
    assert len(gdpr_42) == 1, \
        f"FAIL: duplicate GDPR_VIOLATION for clause_4_2 — got {len(gdpr_42)}"
    assert len(gdpr_42[0]["description"]) > 100, \
        "FAIL: LLM richer description should have replaced template"

    # New LLM violation should be added
    dpdp_42 = [
        v for v in merged
        if v["clause_id"] == "clause_4_2" and v["violation_type"] == "DPDP_VIOLATION"
    ]
    assert len(dpdp_42) == 1, "FAIL: New LLM violation not added"

    # Results sorted CRITICAL first
    assert merged[0]["severity"] == "CRITICAL", \
        f"FAIL: First result should be CRITICAL, got {merged[0]['severity']}"

    print(f"  Merged violations: {len(merged)}")
    print("  All deduplication assertions PASSED\n")

    # ── Test 4: Full analyse() pipeline ───────────────────────────────────
    print("── TEST 4: Full analyse() Pipeline ──\n")
    result     = analyse(test_clauses)
    violations = result.get("compliance_violations", [])
    fixes      = result.get("fixed_clauses", [])

    print(f"  Violations returned: {len(violations)}")
    for v in violations:
        print(
            f"    [{v.get('severity', ''):8s}] {v.get('clause_id', ''):15s} "
            f"{v.get('violation_type', ''):22s} | {v.get('legal_ref', '')}"
        )

    print(f"\n  Fixed clauses: {len(fixes)}")

    assert isinstance(violations, list), "FAIL: must be list"
    assert isinstance(fixes, list),      "FAIL: must be list"
    assert len(violations) >= len(det),  \
        "FAIL: final violations must be >= deterministic baseline"

    print("\n  Pipeline assertions PASSED\n")
    print("=== Task 3 Smoke Test COMPLETE ===")
