from pydantic import BaseModel
from typing import Optional, List


class Clause(BaseModel):
    clause_id: str           # e.g. "clause_8_2"
    page_number: int
    clause_number: str       # e.g. "8.2"
    text: str
    section: str             # e.g. "Liability"
    risk_score: Optional[int] = None      # 0-100, filled by Punith's agent
    risk_reason: Optional[str] = None
    fixed_clause: Optional[str] = None   # filled by AutoFixer agent
    source_citation: Optional[str] = None  # filled by your RAG tracker
    flags: List[str] = []   # e.g. ["GDPR_VIOLATION","CONTRADICTION","AUTO_RENEWAL"]


class Obligation(BaseModel):
    event: str
    date_description: str          # e.g. "Day 75 from signing"
    party_responsible: str
    consequence_if_missed: str
    severity: str                  # "critical" | "warning" | "info"


class ContradictionResult(BaseModel):
    clause_id_a: str
    clause_id_b: str
    contradiction_type: str   # "LOGICAL_DEAD_END" | "MUTUAL_EXCLUSION" | "CIRCULAR_OBLIGATION"
    explanation: str
    z3_proof: str             # the Z3 solver output as a string


class CitationResult(BaseModel):
    claim: str
    source_clause_id: str
    source_page: int
    source_text_excerpt: str
    confidence_score: float   # 0.0 to 1.0
    verified: bool


class LoopholeResult(BaseModel):
    clause_id: str
    loophole_description: str
    exploitation_method: str
    verdict: str              # "dangerous" | "acceptable"
    reasoning: str


class ComplianceViolation(BaseModel):
    clause_id: str
    regulation_violated: str
    article_number: str
    violation_description: str
    severity: str             # "critical" | "moderate" | "low"
