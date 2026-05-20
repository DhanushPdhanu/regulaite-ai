"""
parser.py — PDF Clause Extractor for RegulAIte
Hacker 2 (Shashank) owns this file.

Called by:  server.py → POST /upload
Output fed to: Dhanush's clause display, Ullas's RAG indexer,
               Punith's CrewAI agents

extract_clauses(pdf_bytes, doc_id) → List[dict]
Each dict is Clause-schema compatible (matches schemas.py).
"""

import re
import hashlib
from typing import List, Optional

import fitz  # PyMuPDF


# ── Section inference from clause number ──────────────────────────────────────

SECTION_MAP = {
    "1": "Definitions",
    "2": "Payment",
    "3": "Liability",
    "4": "Data & Privacy",
    "5": "Termination",
    "6": "Confidentiality",
    "7": "Governing Law",
    "8": "Indemnification",
    "9": "Renewal",
}


def _infer_section(clause_number: str, nearest_heading: Optional[str]) -> str:
    if nearest_heading:
        h = nearest_heading.strip().title()
        if len(h) > 2 and not h[0].isdigit():
            return h[:40]
    top = clause_number.split(".")[0] if "." in clause_number else clause_number
    return SECTION_MAP.get(top, "General")


# ── Risk scoring ──────────────────────────────────────────────────────────────

# Each rule: (score, flag, list_of_pattern_groups)
# A pattern_group is a list of regex strings — ALL must match for the group to fire.
# Any one group firing is enough to apply the flag + score.
RISK_RULES = [
    (90, "CONTRADICTION", [
        [r"(full\s+and\s+)?unlimited\s+liability"],
        [r"no\s+limit\s+on\s+(liability|damages)"],
        [r"immediately", r"without\s+notice"],
        [r"at\s+its\s+sole\s+discretion", r"without\s+cause"],
    ]),
    (80, "ONE_SIDED", [
        # "may revise/modify" without mutual consent — check absence of "mutual" or "consent" nearby
        [r"may\s+revise|may\s+modify"],
        [r"at\s+any\s+time", r"without\b"],
        [r"final\s+and\s+binding", r"no\s+appeal"],
        [r"waives?\s+all\s+rights?"],
        [r"at\s+its\s+sole\s+discretion"],
        [r"without\s+(?:employee|client|tenant|party).{0,20}consent"],
        [r"regardless\s+of\s+(?:when|where|how|cause)"],
    ]),
    (70, "AUTO_RENEWAL", [
        # Must contain auto-renew language but NOT a negation ("no auto-renewal", "shall not")
        [r"(?<!no\s)(?<!not\s)auto[\s-]?renew|automatically\s+renew(?!\s+applies)"],
        [r"unless\s+cancelled|unless\s+terminated"],
        [r"successive", r"term|period"],
    ]),
    (60, "GDPR_VIOLATION", [
        [r"shar(e|ing)", r"third[\s-]?part(y|ies)", r"data|information"],
        [r"without\s+(further\s+)?consent", r"data|personal"],
        [r"re[\s-]?identif"],
        [r"unencrypted", r"stor(e|ing)|data"],
    ]),
    (50, "LOOPHOLE", [
        [r"subject\s+to", r"sole\s+discretion"],
        [r"as\s+determined\s+by"],
        [r"\breasonable\b"],
    ]),
    (25, "STANDARD", [
        [r"governed\s+by\s+the\s+laws?"],
        [r"\d+\s+days?\s+(written\s+)?notice"],
        [r"means?\s+and\s+includes?|\"[\w\s]+\"\s+means?"],
    ]),
]


def _score_clause(text: str) -> tuple:
    """Returns (risk_score, flags) for a clause text using pure heuristics."""
    text_lower = text.lower()
    matched_flags: List[str] = []
    highest_score = 10

    for score, flag, pattern_groups in RISK_RULES:
        for group in pattern_groups:
            if all(re.search(p, text_lower) for p in group):
                # Negation guard for AUTO_RENEWAL:
                # clauses that explicitly say "no auto-renewal" or "shall not auto-renew"
                # are CONTRADICTIONS, not AUTO_RENEWAL
                if flag == "AUTO_RENEWAL":
                    if re.search(r"\bno\s+auto[\s-]?renew|\bshall\s+not\s+auto[\s-]?renew", text_lower):
                        # Reclassify as CONTRADICTION instead
                        if "CONTRADICTION" not in matched_flags:
                            matched_flags.append("CONTRADICTION")
                        if 80 > highest_score:
                            highest_score = 80
                        break
                if flag not in matched_flags:
                    matched_flags.append(flag)
                if score > highest_score:
                    highest_score = score
                break  # one matching group per flag is enough

    # Multi-flag boost: each extra flag adds 3 points (capped at 100)
    if len(matched_flags) > 1:
        highest_score = min(100, highest_score + (len(matched_flags) - 1) * 3)

    return highest_score, matched_flags


def _risk_reason(score: int, flags: list, text: str) -> Optional[str]:
    """Generates a human-readable risk reason string."""
    if not flags:
        return None
    flag_descriptions = {
        "CONTRADICTION":  "Contradicts another clause in this section.",
        "ONE_SIDED":      "Gives one party unilateral power without consent requirement.",
        "AUTO_RENEWAL":   "Auto-renewal trap — short cancellation window likely.",
        "GDPR_VIOLATION": "Personal data handling may violate GDPR / DPDP Act.",
        "LOOPHOLE":       "Vague language creates exploitable ambiguity.",
        "STANDARD":       "Standard boilerplate — low risk.",
    }
    reasons = [flag_descriptions.get(f, f) for f in flags]
    return " ".join(reasons)


# ── PDF text extraction ───────────────────────────────────────────────────────

def _extract_pages(pdf_bytes: bytes) -> List[dict]:
    """Returns list of {page_number, text} dicts using PyMuPDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text")
        pages.append({"page_number": i, "text": text})
    doc.close()
    return pages


# ── Clause segmentation ───────────────────────────────────────────────────────

# Matches: "3.1", "3.1.2", "1", "10.4" at start of line with clause text after
# Handles both "3.1   text" and "3.1 text" spacing, and "7.   text" (trailing dot)
CLAUSE_NUM_RE = re.compile(
    r"^[\s]*(\d{1,2}(?:\.\d{1,2}){0,2})\.?\s{1,6}(.+)",
    re.MULTILINE,
)

# Matches section headings:
#   "1  DEFINITIONS"  →  top-level numbered heading (no dot in number)
#   "SECTION 3 — LIABILITY"
#   "ALL CAPS HEADING" (2+ words)
HEADING_RE = re.compile(
    r"^[\s]*(?:(?:SECTION\s+)?\d{1,2}[\s.:\-—]+)?([A-Z][A-Z\s&,\-/]{3,60})\s*$",
    re.MULTILINE,
)


def _segment_clauses(pages: List[dict]) -> List[dict]:
    """
    Segments all page text into individual clauses.
    Returns list of raw clause dicts before risk scoring.

    Strategy:
    1. Walk every line across all pages tracking the current section heading.
    2. When a numbered clause line is found, capture it.
    3. Multi-line clauses: accumulate continuation lines until the next
       clause number or heading is hit.
    4. Fall back to paragraph segmentation if no numbered clauses found.
    """
    raw_clauses: List[dict] = []
    current_heading: Optional[str] = None
    seen_numbers: set = set()

    # Build a single combined text with page markers so we can track page numbers
    # Process page by page to keep page_number accurate
    for page in pages:
        text = page["text"]
        page_num = page["page_number"]
        lines = text.splitlines()

        i = 0
        while i < len(lines):
            line = lines[i]

            # ── Check for section heading ──────────────────────────────────
            h_match = HEADING_RE.match(line)
            if h_match:
                heading_text = h_match.group(1).strip()
                # Filter false positives: must be 2+ words OR 8+ chars
                words = heading_text.split()
                if len(words) >= 2 or len(heading_text) >= 8:
                    # Exclude lines that are just the document title repeated
                    if not any(skip in heading_text for skip in
                               ["CONFIDENTIAL", "FOR REVIEW", "PURPOSES ONLY"]):
                        current_heading = heading_text.title()
                i += 1
                continue

            # ── Check for numbered clause ──────────────────────────────────
            c_match = CLAUSE_NUM_RE.match(line)
            if c_match:
                num = c_match.group(1).strip()
                clause_text = c_match.group(2).strip()

                # Skip top-level section headers like "1  DEFINITIONS"
                # (single integer, no dot, all-caps text)
                if "." not in num and clause_text.isupper():
                    # This is a section heading, not a clause
                    current_heading = clause_text.title()
                    i += 1
                    continue

                # Skip duplicate clause numbers (same clause split across pages)
                if num in seen_numbers:
                    i += 1
                    continue

                # Accumulate continuation lines (indented or non-empty non-clause lines)
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    # Stop if next line is a new clause number or heading
                    if CLAUSE_NUM_RE.match(lines[j]) or HEADING_RE.match(lines[j]):
                        break
                    # Stop on page footer patterns
                    if re.match(r"^Page\s+\d+$", next_line, re.IGNORECASE):
                        break
                    if next_line:
                        clause_text = clause_text + " " + next_line
                    j += 1

                clause_text = clause_text.strip()

                # Skip very short entries (likely TOC or page headers)
                if len(clause_text) < 20:
                    i += 1
                    continue

                seen_numbers.add(num)
                raw_clauses.append({
                    "clause_number":   num,
                    "page_number":     page_num,
                    "nearest_heading": current_heading,
                    "text":            clause_text,
                })
                i = j
                continue

            i += 1

    # Fallback: no numbered clauses found → paragraph segmentation
    if not raw_clauses:
        raw_clauses = _paragraph_fallback(pages)

    return raw_clauses


def _paragraph_fallback(pages: List[dict]) -> List[dict]:
    """
    Fallback for PDFs with no clause numbers (e.g. some NDAs).
    Splits on double newlines and treats each paragraph as a clause.
    """
    raw: List[dict] = []
    counter = 1
    current_heading: Optional[str] = None

    for page in pages:
        paragraphs = re.split(r"\n{2,}", page["text"].strip())
        for para in paragraphs:
            para = para.strip()
            if len(para) < 30:
                continue
            # Check if this looks like a heading (short, all-caps)
            if para.isupper() and len(para.split()) <= 6:
                current_heading = para.title()
                continue
            raw.append({
                "clause_number":   str(counter),
                "page_number":     page["page_number"],
                "nearest_heading": current_heading,
                "text":            para,
            })
            counter += 1

    return raw


# ── Stable clause ID ──────────────────────────────────────────────────────────

def _make_clause_id(doc_id: str, clause_number: str) -> str:
    """
    Generates a stable clause_id from clause_number.
    Format: clause_{section}_{sub}  e.g. clause_3_1
    Matches the format Ullas's RAG indexer expects.
    """
    sanitised = clause_number.replace(".", "_")
    return f"clause_{sanitised}"


# ── Public API ────────────────────────────────────────────────────────────────

def extract_clauses(pdf_bytes: bytes, doc_id: str) -> List[dict]:
    """
    Main entry point called by server.py → POST /upload.

    Args:
        pdf_bytes: Raw PDF file bytes
        doc_id:    UUID string for the uploaded document

    Returns:
        List of clause dicts, each matching schemas.Clause field names:
        clause_id, clause_number, page_number, section, text,
        risk_score, risk_reason, flags
    """
    pages = _extract_pages(pdf_bytes)
    raw_clauses = _segment_clauses(pages)

    result = []
    for raw in raw_clauses:
        score, flags = _score_clause(raw["text"])
        reason = _risk_reason(score, flags, raw["text"])
        section = _infer_section(
            raw["clause_number"],
            raw.get("nearest_heading"),
        )
        result.append({
            "clause_id":     _make_clause_id(doc_id, raw["clause_number"]),
            "clause_number": raw["clause_number"],
            "page_number":   raw["page_number"],
            "section":       section,
            "text":          raw["text"],
            "risk_score":    score,
            "risk_reason":   reason,
            "flags":         flags,
        })

    return result


# ── Standalone smoke test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python ingestion/parser.py <path-to-pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    clauses = extract_clauses(pdf_bytes, "smoke_test_doc")
    print(f"\nExtracted {len(clauses)} clauses from {pdf_path}\n")
    for c in clauses[:10]:
        print(f"  [{c['clause_number']}] {c['section']} | "
              f"risk={c['risk_score']} | flags={c['flags']}")
        print(f"    {c['text'][:90]}...")
        print()

    high_risk = sum(1 for c in clauses if c['risk_score'] >= 60)
    print(f"Total: {len(clauses)} clauses. High risk (>=60): {high_risk}")
