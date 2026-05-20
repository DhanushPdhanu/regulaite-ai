"""
redline.py — Redline .docx Generator for RegulAIte
Hacker 2 (Shashank) owns this file.

Called by: server.py → GET /export/{doc_id}
Input:     Full analysis dict (from _analysis_store)
Output:    Path to generated .docx file in /tmp/

generate_redline_docx(analysis: dict, doc_id: str) -> str
Returns the absolute file path of the generated .docx.
"""

import os
import tempfile
from datetime import datetime
from typing import Optional

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ── Color constants ───────────────────────────────────────────────────────────
COLOR_RED   = RGBColor(0xC0, 0x00, 0x00)
COLOR_GREEN = RGBColor(0x00, 0x70, 0x00)
COLOR_AMBER = RGBColor(0xBF, 0x8F, 0x00)
COLOR_NAVY  = RGBColor(0x1E, 0x3A, 0x5F)
COLOR_GRAY  = RGBColor(0x60, 0x60, 0x60)
COLOR_BLACK = RGBColor(0x00, 0x00, 0x00)
COLOR_WHITE = RGBColor(0xFF, 0xFF, 0xFF)

RISK_COLORS = {
    "CRITICAL": COLOR_RED,
    "HIGH":     COLOR_AMBER,
    "MEDIUM":   RGBColor(0x00, 0x70, 0xC0),
    "LOW":      COLOR_GREEN,
}


# ── Document setup helpers ────────────────────────────────────────────────────

def _set_margins(doc: Document):
    """Sets consistent page margins on all sections."""
    for section in doc.sections:
        section.top_margin    = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin   = Cm(3.0)
        section.right_margin  = Cm(2.5)


def _add_horizontal_rule(doc: Document):
    """Adds a thin horizontal line separator between clause blocks."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after  = Pt(2)
    run = p.add_run("─" * 72)
    run.font.size      = Pt(7)
    run.font.color.rgb = COLOR_GRAY


def _add_page_break(doc: Document):
    doc.add_page_break()


def _paragraph_with_spacing(
    doc, text="", bold=False, size=11,
    color=None, italic=False,
    alignment=WD_ALIGN_PARAGRAPH.LEFT,
    space_before=6, space_after=4,
) -> object:
    """Adds a paragraph with controlled styling. Returns the paragraph."""
    p = doc.add_paragraph()
    p.alignment = alignment
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after  = Pt(space_after)
    if text:
        run = p.add_run(text)
        run.bold        = bold
        run.italic      = italic
        run.font.size   = Pt(size)
        if color:
            run.font.color.rgb = color
    return p


def _add_colored_run(
    paragraph, text: str,
    bold=False, italic=False,
    size=10, color=None, strikethrough=False,
):
    """Adds a styled run to an existing paragraph."""
    run = paragraph.add_run(text)
    run.bold        = bold
    run.italic      = italic
    run.font.size   = Pt(size)
    if color:
        run.font.color.rgb = color
    if strikethrough:
        run.font.strike = True
    return run


# ── Table helpers ─────────────────────────────────────────────────────────────

def _add_summary_table(doc: Document, headers: list, rows: list):
    """Adds a styled table with navy header row."""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style     = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.LEFT

    # Header row — navy background, white bold text
    hdr_row = table.rows[0]
    for i, h in enumerate(headers):
        cell = hdr_row.cells[i]
        cell.text = h
        run = cell.paragraphs[0].runs[0]
        run.bold           = True
        run.font.color.rgb = COLOR_WHITE
        run.font.size      = Pt(9)
        tc_pr = cell._tc.get_or_add_tcPr()
        shd   = OxmlElement("w:shd")
        shd.set(qn("w:val"),   "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"),  "1E3A5F")
        tc_pr.append(shd)

    # Data rows — alternating light-blue tint
    for r_idx, row_data in enumerate(rows, start=1):
        row = table.rows[r_idx]
        for c_idx, cell_text in enumerate(row_data):
            cell      = row.cells[c_idx]
            cell.text = str(cell_text)
            run       = cell.paragraphs[0].runs[0]
            run.font.size = Pt(9)
            if r_idx % 2 == 0:
                tc_pr = cell._tc.get_or_add_tcPr()
                shd   = OxmlElement("w:shd")
                shd.set(qn("w:val"),   "clear")
                shd.set(qn("w:color"), "auto")
                shd.set(qn("w:fill"),  "F0F4F8")
                tc_pr.append(shd)

    doc.add_paragraph()


# ── Risk label helper ─────────────────────────────────────────────────────────

def _risk_label(score: int) -> str:
    if score >= 80: return "CRITICAL"
    if score >= 60: return "HIGH"
    if score >= 35: return "MEDIUM"
    return "LOW"


# ── Page 1: Cover ─────────────────────────────────────────────────────────────

def _build_cover_page(doc: Document, analysis: dict):
    """Builds the cover page."""
    doc.add_paragraph()
    doc.add_paragraph()

    # Large scales icon
    p = doc.add_paragraph("⚖")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.runs[0]
    run.font.size      = Pt(48)
    run.font.color.rgb = COLOR_NAVY

    doc.add_paragraph()

    # Main title
    _paragraph_with_spacing(
        doc, "REGULAITE LEGAL ANALYSIS REPORT",
        bold=True, size=24, color=COLOR_NAVY,
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        space_before=12, space_after=8,
    )

    # Date line
    date_str = datetime.now().strftime("%B %d, %Y")
    _paragraph_with_spacing(
        doc, f"Analysed Document  ·  {date_str}",
        size=13, color=COLOR_GRAY,
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        space_before=4, space_after=4,
    )

    # Confidential badge
    _paragraph_with_spacing(
        doc, "CONFIDENTIAL — AI-ASSISTED REVIEW",
        bold=True, size=11, color=COLOR_AMBER,
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        space_before=8, space_after=4,
    )

    doc.add_paragraph()

    # Risk score callout box (1-cell table, centred)
    score       = analysis.get("overall_risk_score", 0)
    label       = _risk_label(score)
    score_color = RISK_COLORS.get(label, COLOR_GRAY)

    tbl       = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell      = tbl.cell(0, 0)
    p         = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after  = Pt(8)
    run       = p.add_run(f"Overall Risk Score:  {score}/100  [{label}]")
    run.bold           = True
    run.font.size      = Pt(14)
    run.font.color.rgb = score_color

    _add_page_break(doc)


# ── Page 2: Executive Summary ─────────────────────────────────────────────────

def _build_executive_summary(doc: Document, analysis: dict):
    """Builds the executive summary page."""
    _paragraph_with_spacing(
        doc, "Executive Summary",
        bold=True, size=16, color=COLOR_NAVY,
        space_before=0, space_after=8,
    )
    _add_horizontal_rule(doc)

    clauses               = analysis.get("clauses", [])
    contradictions        = analysis.get("contradictions", [])
    compliance_violations = analysis.get("compliance_violations", [])
    fixed_clauses         = analysis.get("fixed_clauses", [])
    hallucination_rate    = analysis.get("hallucination_rate", 0.0)
    score                 = analysis.get("overall_risk_score", 0)
    label                 = _risk_label(score)

    # Key metrics
    metrics = [
        ("Overall Risk Score",      f"{score}/100  [{label}]"),
        ("Total Clauses Analysed",  str(len(clauses))),
        ("Contradictions Detected", str(len(contradictions))),
        ("Compliance Violations",   str(len(compliance_violations))),
        ("Clauses Auto-Fixed",      str(len(fixed_clauses))),
        ("Hallucination Rate",      f"{hallucination_rate * 100:.1f}%"),
    ]
    for label_text, value in metrics:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after  = Pt(3)
        _add_colored_run(p, f"  {label_text}:  ", bold=True, size=11, color=COLOR_NAVY)
        _add_colored_run(p, value, size=11, color=COLOR_BLACK)

    doc.add_paragraph()

    # Risk category breakdown table
    _paragraph_with_spacing(
        doc, "Risk Category Breakdown",
        bold=True, size=12, color=COLOR_NAVY,
        space_before=8, space_after=4,
    )

    flag_counts: dict = {}
    max_scores:  dict = {}
    for clause in clauses:
        for flag in clause.get("flags", []):
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
            s = clause.get("risk_score", 0)
            if s > max_scores.get(flag, 0):
                max_scores[flag] = s

    flag_display = {
        "CONTRADICTION":  "Contradictions",
        "GDPR_VIOLATION": "GDPR Violations",
        "ONE_SIDED":      "One-Sided Clauses",
        "AUTO_RENEWAL":   "Auto-Renewal Traps",
        "LOOPHOLE":       "Loopholes",
        "STANDARD":       "Standard Clauses",
    }
    table_rows = [
        (display, str(flag_counts[flag]), _risk_label(max_scores[flag]))
        for flag, display in flag_display.items()
        if flag in flag_counts
    ]
    if table_rows:
        _add_summary_table(doc, ["Category", "Count", "Highest Risk"], table_rows)

    _add_page_break(doc)


# ── Page 3+: Clause-by-Clause Redline ────────────────────────────────────────

def _build_redline_section(doc: Document, analysis: dict):
    """Builds the clause-by-clause redline pages."""
    _paragraph_with_spacing(
        doc, "Clause-by-Clause Redline",
        bold=True, size=16, color=COLOR_NAVY,
        space_before=0, space_after=8,
    )

    fixed_clauses  = analysis.get("fixed_clauses", [])
    all_clauses    = analysis.get("clauses", [])
    contradictions = analysis.get("contradictions", [])

    # Lookup maps
    contradiction_map: dict = {}
    for c in contradictions:
        for cid in [c.get("clause_id_a"), c.get("clause_id_b")]:
            if cid:
                contradiction_map[cid] = c

    fixed_map  = {fc["clause_id"]: fc for fc in fixed_clauses}
    clause_map = {c["clause_id"]: c  for c in all_clauses}

    # ── Section A: Auto-fixed clauses ─────────────────────────────────────────
    if fixed_clauses:
        _paragraph_with_spacing(
            doc, "Auto-Fixed Clauses",
            bold=True, size=13, color=COLOR_GREEN,
            space_before=6, space_after=4,
        )
        for fc in fixed_clauses:
            cid         = fc.get("clause_id", "")
            meta        = clause_map.get(cid, {})
            clause_num  = meta.get(
                "clause_number",
                cid.replace("clause_", "").replace("_", "."),
            )
            section     = meta.get("section", "General")
            score       = meta.get("risk_score", 0)
            risk_lbl    = _risk_label(score)
            risk_color  = RISK_COLORS.get(risk_lbl, COLOR_GRAY)

            # Clause header
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after  = Pt(2)
            _add_colored_run(p, f"CLAUSE {clause_num} — {section}",
                             bold=True, size=12, color=COLOR_NAVY)
            _add_colored_run(p, f"          [{risk_lbl} RISK: {score}/100]",
                             bold=True, size=10, color=risk_color)
            _add_horizontal_rule(doc)

            # Original text
            _paragraph_with_spacing(doc, "ORIGINAL TEXT:",
                                    bold=True, size=9, color=COLOR_RED,
                                    space_before=4, space_after=2)
            p_orig = doc.add_paragraph()
            p_orig.paragraph_format.space_before = Pt(2)
            p_orig.paragraph_format.space_after  = Pt(6)
            p_orig.paragraph_format.left_indent  = Cm(0.5)
            _add_colored_run(p_orig, fc.get("original_text", ""),
                             size=10, color=COLOR_RED, strikethrough=True)

            # Fixed text
            _paragraph_with_spacing(doc, "AI-FIXED VERSION:",
                                    bold=True, size=9, color=COLOR_GREEN,
                                    space_before=4, space_after=2)
            p_fix = doc.add_paragraph()
            p_fix.paragraph_format.space_before = Pt(2)
            p_fix.paragraph_format.space_after  = Pt(6)
            p_fix.paragraph_format.left_indent  = Cm(0.5)
            _add_colored_run(p_fix, fc.get("fixed_text", ""),
                             size=10, color=COLOR_GREEN)

            # Fix explanation
            explanation = fc.get("fix_explanation", "")
            if explanation:
                _paragraph_with_spacing(doc, "FIX EXPLANATION:",
                                        bold=True, size=9, color=COLOR_GRAY,
                                        space_before=4, space_after=2)
                p_exp = doc.add_paragraph()
                p_exp.paragraph_format.space_before = Pt(2)
                p_exp.paragraph_format.space_after  = Pt(4)
                p_exp.paragraph_format.left_indent  = Cm(0.5)
                _add_colored_run(p_exp, explanation,
                                 italic=True, size=9, color=COLOR_GRAY)

            # Z3 proof (if this clause was in a contradiction)
            if cid in contradiction_map:
                proof = contradiction_map[cid].get("z3_proof", "")
                if proof:
                    _paragraph_with_spacing(doc, "Z3 FORMAL PROOF:",
                                            bold=True, size=9, color=COLOR_NAVY,
                                            space_before=4, space_after=2)
                    p_proof = doc.add_paragraph()
                    p_proof.paragraph_format.space_before = Pt(2)
                    p_proof.paragraph_format.space_after  = Pt(4)
                    p_proof.paragraph_format.left_indent  = Cm(0.5)
                    run = p_proof.add_run(proof)
                    run.font.name      = "Courier New"
                    run.font.size      = Pt(8)
                    run.font.color.rgb = COLOR_NAVY

            _add_horizontal_rule(doc)

    # ── Section B: High-risk unfixed clauses ──────────────────────────────────
    high_risk_unfixed = [
        c for c in all_clauses
        if c.get("risk_score", 0) >= 60
        and c.get("clause_id") not in fixed_map
    ]

    if high_risk_unfixed:
        doc.add_paragraph()
        _paragraph_with_spacing(
            doc, "High-Risk Clauses — Require Human Review",
            bold=True, size=13, color=COLOR_AMBER,
            space_before=6, space_after=4,
        )
        for clause in high_risk_unfixed:
            num        = clause.get("clause_number", "?")
            section    = clause.get("section", "General")
            score      = clause.get("risk_score", 0)
            risk_lbl   = _risk_label(score)
            risk_color = RISK_COLORS.get(risk_lbl, COLOR_AMBER)
            flags      = clause.get("flags", [])
            cid        = clause.get("clause_id", "")

            # Clause header
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after  = Pt(2)
            _add_colored_run(p, f"CLAUSE {num} — {section}",
                             bold=True, size=12, color=COLOR_NAVY)
            _add_colored_run(p, f"          [{risk_lbl} RISK: {score}/100]",
                             bold=True, size=10, color=risk_color)
            _add_horizontal_rule(doc)

            # Warning label
            _paragraph_with_spacing(
                doc, "⚠  FLAGGED — NOT AUTO-FIXED (requires human review)",
                bold=True, size=9, color=COLOR_AMBER,
                space_before=4, space_after=2,
            )

            # Clause text in amber
            p_txt = doc.add_paragraph()
            p_txt.paragraph_format.space_before = Pt(2)
            p_txt.paragraph_format.space_after  = Pt(4)
            p_txt.paragraph_format.left_indent  = Cm(0.5)
            _add_colored_run(p_txt, clause.get("text", ""),
                             size=10, color=COLOR_AMBER)

            # Flags
            if flags:
                p_flags = doc.add_paragraph()
                p_flags.paragraph_format.space_before = Pt(2)
                p_flags.paragraph_format.space_after  = Pt(2)
                _add_colored_run(p_flags, "FLAGS:  ",
                                 bold=True, size=9, color=COLOR_GRAY)
                _add_colored_run(p_flags, ",  ".join(flags),
                                 size=9, color=COLOR_RED)

            # Risk reason
            reason = clause.get("risk_reason", "")
            if reason:
                p_reason = doc.add_paragraph()
                p_reason.paragraph_format.space_before = Pt(2)
                p_reason.paragraph_format.space_after  = Pt(4)
                _add_colored_run(p_reason, "REASON:  ",
                                 bold=True, size=9, color=COLOR_GRAY)
                _add_colored_run(p_reason, reason,
                                 italic=True, size=9, color=COLOR_GRAY)

            # Z3 proof if this unfixed clause is in a contradiction
            if cid in contradiction_map:
                proof = contradiction_map[cid].get("z3_proof", "")
                if proof:
                    _paragraph_with_spacing(doc, "Z3 FORMAL PROOF:",
                                            bold=True, size=9, color=COLOR_NAVY,
                                            space_before=4, space_after=2)
                    p_proof = doc.add_paragraph()
                    p_proof.paragraph_format.left_indent = Cm(0.5)
                    run = p_proof.add_run(proof)
                    run.font.name      = "Courier New"
                    run.font.size      = Pt(8)
                    run.font.color.rgb = COLOR_NAVY

            _add_horizontal_rule(doc)

    _add_page_break(doc)


# ── Final Page: Audit Trail ───────────────────────────────────────────────────

def _build_audit_trail(doc: Document, analysis: dict):
    """Builds the final audit trail page."""
    _paragraph_with_spacing(
        doc, "AI Citation Audit Trail",
        bold=True, size=16, color=COLOR_NAVY,
        space_before=0, space_after=8,
    )
    _add_horizontal_rule(doc)

    citation_results = analysis.get("citation_results", [])
    graph_data       = analysis.get("citation_graph", {})
    top_cited        = graph_data.get("top_cited", [])
    hall_rate        = analysis.get("hallucination_rate", 0.0)
    verified_count   = sum(1 for c in citation_results if c.get("verified"))
    unverified_count = len(citation_results) - verified_count

    # Citation metrics
    metrics = [
        ("Total Claims Verified",      str(len(citation_results))),
        ("Verified Citations",          str(verified_count)),
        ("Unverified (Hallucinations)", str(unverified_count)),
        ("Hallucination Rate",          f"{hall_rate * 100:.1f}%"),
    ]
    for label_text, value in metrics:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after  = Pt(3)
        _add_colored_run(p, f"  {label_text}:  ", bold=True, size=11, color=COLOR_NAVY)
        color = COLOR_RED if "Hallucination" in label_text else COLOR_BLACK
        _add_colored_run(p, value, size=11, color=color)

    doc.add_paragraph()

    # Most cited clauses table
    if top_cited:
        _paragraph_with_spacing(
            doc, "Most Referenced Clauses",
            bold=True, size=12, color=COLOR_NAVY,
            space_before=8, space_after=4,
        )
        rows = [
            (
                entry.get("clause_id", "").replace("clause_", "").replace("_", "."),
                entry.get("section", "General"),
                str(entry.get("times_cited", 0)),
            )
            for entry in top_cited
        ]
        _add_summary_table(doc, ["Clause", "Section", "Times Cited"], rows)

    # Unverified claims detail
    unverified = [c for c in citation_results if not c.get("verified")]
    if unverified:
        _paragraph_with_spacing(
            doc, "Unverified Claims (Potential Hallucinations)",
            bold=True, size=12, color=COLOR_RED,
            space_before=8, space_after=4,
        )
        for item in unverified:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after  = Pt(2)
            p.paragraph_format.left_indent  = Cm(0.5)
            _add_colored_run(p, "✗  ", bold=True, size=10, color=COLOR_RED)
            _add_colored_run(p, item.get("claim", ""), size=9, color=COLOR_RED)

            p2 = doc.add_paragraph()
            p2.paragraph_format.space_before = Pt(0)
            p2.paragraph_format.space_after  = Pt(4)
            p2.paragraph_format.left_indent  = Cm(1.0)
            conf = item.get("confidence_score", 0)
            src  = item.get("source_clause_id", "N/A")
            _add_colored_run(
                p2,
                f"Confidence: {conf:.2f}  |  Best match: {src}",
                italic=True, size=8, color=COLOR_GRAY,
            )

    doc.add_paragraph()

    # Disclaimer
    _add_horizontal_rule(doc)
    _paragraph_with_spacing(
        doc,
        "DISCLAIMER: This report was generated by RegulAIte, an AI-powered "
        "legal document analysis system. It is intended for informational "
        "purposes only and does not constitute legal advice. All findings "
        "should be reviewed by a qualified legal professional before any "
        "contractual decisions are made. AI citation verification confirms "
        "grounding in the source document but does not guarantee legal "
        "correctness of the analysis.",
        italic=True, size=8, color=COLOR_GRAY,
        space_before=4, space_after=4,
    )
    _paragraph_with_spacing(
        doc,
        f"Generated by RegulAIte  ·  "
        f"{datetime.now().strftime('%B %d, %Y at %H:%M UTC')}  ·  "
        f"Built at HackIndia 2025  ·  Team Tattvasphere",
        size=8, color=COLOR_GRAY,
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
        space_before=4, space_after=4,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def generate_redline_docx(analysis: dict, doc_id: str) -> str:
    """
    Main entry point called by server.py → GET /export/{doc_id}.

    Args:
        analysis: Full analysis dict from _analysis_store
        doc_id:   UUID string for the document

    Returns:
        Absolute path to generated .docx file in /tmp/
    """
    doc = Document()
    _set_margins(doc)

    # Set default font for Normal style
    style           = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    _build_cover_page(doc, analysis)
    _build_executive_summary(doc, analysis)
    _build_redline_section(doc, analysis)
    _build_audit_trail(doc, analysis)

    output_path = os.path.join(tempfile.gettempdir(), f"redline_{doc_id}.docx")
    doc.save(output_path)
    return output_path


# ── Standalone smoke test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import platform
    import subprocess

    mock_analysis = {
        "doc_id":             "smoke_test_001",
        "overall_risk_score": 74,
        "risk_label":         "HIGH",
        "hallucination_rate": 0.056,
        "clauses": [
            {
                "clause_id":     "clause_3_1",
                "clause_number": "3.1",
                "section":       "Liability",
                "risk_score":    82,
                "risk_reason":   "Liability cap detected — contradicted by 3.2.",
                "flags":         ["CONTRADICTION"],
                "text": (
                    "The Company's liability is limited to the total fees "
                    "paid by Client in the preceding twelve (12) months."
                ),
            },
            {
                "clause_id":     "clause_3_2",
                "clause_number": "3.2",
                "section":       "Liability",
                "risk_score":    88,
                "risk_reason":   "Unlimited liability contradicts 3.1 cap.",
                "flags":         ["CONTRADICTION", "ONE_SIDED"],
                "text": (
                    "There is no limit on liability for any damages arising "
                    "from this agreement."
                ),
            },
            {
                "clause_id":     "clause_7_1",
                "clause_number": "7.1",
                "section":       "Termination",
                "risk_score":    72,
                "risk_reason":   "Unilateral termination without notice.",
                "flags":         ["ONE_SIDED"],
                "text": (
                    "Vendor may terminate this Agreement immediately and "
                    "without notice at its sole discretion for any reason."
                ),
            },
        ],
        "contradictions": [
            {
                "clause_id_a":        "clause_3_1",
                "clause_id_b":        "clause_3_2",
                "contradiction_type": "MUTUAL_EXCLUSION",
                "explanation": (
                    "Clause 3.1 caps liability at 12 months fees. "
                    "Clause 3.2 removes all liability limits. "
                    "Both cannot simultaneously hold."
                ),
                "z3_proof": (
                    "Assert: liability_limited = TRUE  (Clause 3.1)\n"
                    "Assert: liability_limited = FALSE (Clause 3.2)\n"
                    "Z3 Result: UNSAT — both cannot hold simultaneously"
                ),
            }
        ],
        "compliance_violations": [],
        "fixed_clauses": [
            {
                "clause_id":      "clause_3_1",
                "original_text": (
                    "The Company's liability is limited to the total fees "
                    "paid by Client in the preceding twelve (12) months."
                ),
                "fixed_text": (
                    "The Company's total aggregate liability under this Agreement "
                    "shall not exceed the greater of: (a) the total fees paid by "
                    "Client in the preceding twelve (12) months; or (b) INR 5,00,000. "
                    "This cap applies to all claims regardless of the theory of liability."
                ),
                "fix_explanation": (
                    "Added a floor amount to prevent the cap from becoming trivially "
                    "small for low-volume clients. Clarified that the cap applies "
                    "across all claim theories to prevent circumvention."
                ),
            }
        ],
        "citation_results": [
            {
                "claim":               "The vendor's financial exposure is capped.",
                "source_clause_id":    "clause_3_1",
                "source_page":         2,
                "source_text_excerpt": "The Company's liability is limited...",
                "confidence_score":    0.94,
                "verified":            True,
            },
            {
                "claim":               "The vendor can share all client data publicly.",
                "source_clause_id":    "clause_3_1",
                "source_page":         2,
                "source_text_excerpt": "The Company's liability is limited...",
                "confidence_score":    0.31,
                "verified":            False,
            },
        ],
        "citation_graph": {
            "summary": {
                "total_claims_made":    2,
                "verified_citations":   1,
                "unverified_citations": 1,
                "hallucination_rate":   0.5,
            },
            "top_cited": [
                {"clause_id": "clause_3_1", "section": "Liability", "times_cited": 2},
            ],
        },
    }

    output = generate_redline_docx(mock_analysis, "smoke_test_001")
    print(f"Generated: {output}")
    file_size = os.path.getsize(output)
    print(f"File size: {file_size:,} bytes ({file_size // 1024} KB)")

    if platform.system() == "Windows":
        os.startfile(output)
    elif platform.system() == "Darwin":
        subprocess.run(["open", output])
    else:
        subprocess.run(["xdg-open", output])
