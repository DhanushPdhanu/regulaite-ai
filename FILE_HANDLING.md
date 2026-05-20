# RegulAIte — File Handling Guide

> Who owns what, what every file does, and exactly which lines matter.
> Divided by team role so each member knows their domain completely.

---

## Complete File Structure (ELI5 — Explained Like You're 5)

```
regulaite/
│
├── app.py                          ← The website you see in your browser (Dhanush)
├── server.py                       ← The brain that connects everything (Shashank)
├── schemas.py                      ← The rulebook: what a "Clause" looks like (Ullas)
│
├── ingestion/
│   └── parser.py                   ← Reads the PDF, cuts it into clauses (Shashank)
│
├── logic/
│   └── validator.py                ← Math engine that proves contradictions (Ullas)
│
├── memory/
│   ├── rag.py                      ← Finds the right clause for any question (Ullas)
│   ├── bridge.py                   ← Connects the math engine to the AI agents (Ullas)
│   └── reset_between_docs.py       ← Clears memory before a new document (Ullas)
│
├── agents/
│   └── crew.py                     ← The AI agents that read and fix clauses (Punith)
│
├── export/
│   └── redline.py                  ← Writes the Word document with changes (Shashank)
│
├── contracts/
│   ├── generate_contracts.py       ← Makes 18 fake contracts for testing (Ullas)
│   └── *.pdf                       ← The 18 demo contract PDFs
│
├── tests/
│   ├── test_crew_unit.py           ← Unit tests for Punith's agents
│   └── test_integration.py        ← Full pipeline integration tests
│
├── handshake_check.py              ← Pre-demo: checks all 4 modules work together
├── healthcheck.py                  ← Pre-launch: checks env + packages
├── test_integration.py             ← Integration tests (root level copy)
├── start.sh                        ← Starts both server + frontend
├── stop.sh                         ← Stops both services
├── run_local.sh                    ← Alternative local run script
├── requirements.txt                ← All Python packages needed
├── .env.example                    ← Template for environment variables
├── .env                            ← Your actual secrets (never commit this)
├── .gitignore                      ← Files git should ignore
├── README.md                       ← Project overview
├── SETUP.md                        ← How to install and run
└── FILE_HANDLING.md                ← This file
```

---

## How Data Flows Through the Files

```
User uploads PDF
      │
      ▼
[server.py]  POST /upload
      │  calls
      ▼
[ingestion/parser.py]  extract_clauses(pdf_bytes, doc_id)
      │  returns List[dict]  (each dict = one clause)
      │
      ▼
[server.py]  POST /analyse
      │  converts dicts → Clause objects using [schemas.py]
      │  calls
      ├──► [memory/reset_between_docs.py]  reset_for_new_document()
      │
      ├──► [memory/bridge.py]  run_full_analysis(clauses)
      │         │  calls
      │         ├──► [memory/rag.py]  InMemoryRAG.index(clauses)
      │         └──► [logic/validator.py]  validate_clauses(clauses)
      │
      └──► [agents/crew.py]  analyse(clauses)
                │  uses tools from [memory/bridge.py]
                └──► RiskAgent → ComplianceAgent → FixerAgent
      │
      ▼
[server.py]  _merge_results()  →  unified AnalysisResult dict
      │
      ├──► GET /results/{doc_id}  →  [app.py] displays dashboard
      └──► GET /export/{doc_id}   →  [export/redline.py] generates .docx
```

---

---

# DHANUSH (Hacker 1) — Frontend

**Role:** Builds the interactive web UI that users see and click.
**Primary file:** `app.py`
**Technology:** Streamlit, Plotly, Pandas, NetworkX

---

## `app.py` — The Entire Frontend

**What it is:** A single-file Streamlit application. Streamlit turns Python functions into web pages automatically — no HTML/CSS/JS needed (though custom CSS is injected here for the dark theme).

**ELI5:** Think of this as the "face" of the app. Everything the user sees — the upload button, the risk charts, the contradiction list, the download button — is rendered by this file. It talks to `server.py` over HTTP to get data.

### Key Concepts Used

**Streamlit session state** (lines ~340–360)
```python
st.session_state["doc_id"]      # stores the current document's UUID
st.session_state["analysis"]    # stores the full analysis result dict
st.session_state["server_online"]  # True/False — is the backend up?
```
Session state is like a dictionary that persists across page rerenders. Without it, every button click would reset all variables.

**CSS injection** (lines ~30–280)
```python
GLOBAL_CSS = """<style> ... </style>"""
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
```
Streamlit doesn't have a built-in dark theme as rich as this. The entire design system (colors, fonts, card styles, animations) is injected as raw CSS into the page. The CSS variables like `--primary`, `--accent-red` are defined at the top and reused everywhere.

**API calls** (lines ~300–330)
```python
def api_get(endpoint: str) -> Optional[dict]:
    r = requests.get(f"{API_BASE}{endpoint}", timeout=10)
    return r.json() if r.status_code == 200 else None

def api_post(endpoint: str, **kwargs) -> Optional[dict]:
    r = requests.post(f"{API_BASE}{endpoint}", timeout=120, **kwargs)
    return r.json() if r.status_code == 200 else None
```
These two helpers wrap all HTTP calls to the backend. `API_BASE` comes from the `.env` file (`API_BASE_URL=http://localhost:8000`).

**Module sync check** (lines ~370–430)
```python
def _sync_check() -> dict:
    # Tries to import each of Ullas's modules
    # Returns {"schemas": True, "validator": True, "rag": True, ...}
```
On startup, the frontend tries to import all backend modules directly. This lets it show a status banner telling the user which modules are loaded. It only runs once per session (cached in `session_state`).

**Status banner** (lines ~432–490)
```python
def render_status_banner():
    # Shows: "● API Online  ✓ All modules synced  📄 filename.pdf"
```
The top bar that shows API health + module status. Reads from `_sync_check()` and `st.session_state.server_online`.

### Page Functions

Each page is a separate Python function:

| Function | Page | What it renders |
|----------|------|-----------------|
| `page_home()` | Home | Hero section, feature cards, CTA button |
| `page_upload()` | Upload Document | File uploader, clause table after upload |
| `page_analyse()` | Agent Analysis | Progress timeline, agent log stream |
| `page_results()` | Risk Dashboard | Risk score gauge, clause cards, metrics |
| `page_redline()` | Redline View | Original vs fixed clause side-by-side |
| `page_graph()` | Citation Graph | NetworkX graph rendered with Plotly |
| `page_history()` | Document History | List of previously analysed documents |
| `main()` | Router | Reads `session_state.page`, calls the right function |

### Risk Scoring Helpers

```python
def risk_color(score: int) -> str:   # returns hex color string
def risk_label(score: int) -> str:   # returns "critical"/"high"/"medium"/"low"
def risk_badge_html(score: int) -> str:  # returns HTML badge span
```
These are used throughout the UI to color-code clauses. Score thresholds: 80+ = critical (red), 60+ = high (orange), 35+ = medium (amber), below 35 = low (green).

### What Dhanush Should NOT Touch

- `schemas.py` — Ullas owns this
- `server.py` — Shashank owns this
- Anything in `memory/`, `logic/`, `agents/`, `ingestion/`, `export/`

---

---

# SHASHANK (Hacker 2) — Backend

**Role:** Builds the REST API server, PDF parser, and Word document exporter.
**Primary files:** `server.py`, `ingestion/parser.py`, `export/redline.py`
**Technology:** FastAPI, PyMuPDF, python-docx, uvicorn

---

## `server.py` — The FastAPI Backend

**What it is:** The central REST API server. Every request from the frontend goes through here. It orchestrates all the other modules — calling Shashank's parser, Ullas's bridge, and Punith's agents in sequence.

**ELI5:** Think of this as the "manager" of the whole system. When the frontend says "analyse this document", the server is the one that calls the parser, then calls the AI tools, then calls the agents, then combines all the results and sends them back.

### Key Concepts Used

**FastAPI lifespan** (lines ~60–100)
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs ONCE at startup
    # Tries to import each teammate's module
    # Sets _PARSER_AVAILABLE, _BRIDGE_AVAILABLE, etc.
    yield
    # Runs at shutdown
```
The lifespan context manager runs startup code before the server accepts requests. It probes every teammate's module with a try/except. If a module fails to import, the flag stays `False` and the server uses stub results instead — it never crashes.

**Module availability flags** (lines ~45–55)
```python
_PARSER_AVAILABLE  = False   # set True if ingestion/parser.py imports OK
_BRIDGE_AVAILABLE  = False   # set True if memory/bridge.py imports OK
_AGENTS_AVAILABLE  = False   # set True if agents/crew.py imports OK
_REDLINE_AVAILABLE = False   # set True if export/redline.py imports OK
```
These four booleans control which real code runs vs which stub code runs. This is the "graceful degradation" design — the server always returns a valid response even if half the team's code isn't ready yet.

**In-memory stores** (lines ~40–43)
```python
_doc_store:      dict = {}   # doc_id → upload result (clauses)
_analysis_store: dict = {}   # doc_id → full analysis result
```
Documents and analyses are stored in Python dicts in RAM. No database needed for the demo. The doc_id is a UUID generated at upload time.

**POST /upload** (lines ~115–165)
```python
async def upload_document(file: UploadFile = File(...)):
    pdf_bytes = await file.read()
    doc_id = str(uuid.uuid4())
    clauses = extract_clauses(pdf_bytes, doc_id)  # calls parser.py
    _doc_store[doc_id] = {"doc_id": doc_id, "clauses": clauses, ...}
    return result
```
Reads the PDF bytes, generates a UUID, calls the parser, stores the result, returns it. Falls back to `_stub_clauses()` if the parser isn't available.

**POST /analyse** (lines ~170–250)
```python
async def analyse_document(body: dict):
    # Step 1: Convert raw dicts → Clause objects (schemas.py)
    # Step 2: Run Ullas's bridge (Z3 + RAG)
    # Step 3: Run Punith's agents (LLM scoring + compliance + fixing)
    # Step 4: Merge all results with _merge_results()
    # Step 5: Cache in _analysis_store and return
```
The most important endpoint. Each step is wrapped in try/except so one failing module never blocks the others.

**`_merge_results()`** (lines ~310–390)
```python
def _merge_results(doc_id, doc, bridge_result, agent_result) -> dict:
    # Normalises output from Ullas's bridge and Punith's agents
    # Handles both dict-style and Pydantic model_dump() output
    # Computes overall_risk_score as average of all clause scores
    # Returns the unified AnalysisResult dict
```
This is the "glue" function. Ullas's bridge returns Pydantic objects. Punith's agents return dicts. This function normalises both into a single consistent dict that Dhanush's frontend can read.

**Stub functions** (lines ~395–420)
```python
def _stub_clauses(doc_id) -> list:       # 2 fake clauses
def _stub_bridge_result(clauses) -> dict: # empty contradictions/citations
def _stub_agent_result(clauses) -> dict:  # empty violations/fixes
```
These are fallbacks used when a teammate's module isn't ready. They return the correct schema shape so the frontend never crashes.

---

## `ingestion/parser.py` — PDF Clause Extractor

**What it is:** Takes raw PDF bytes and returns a list of clause dicts. This is the first step in the pipeline.

**ELI5:** Imagine you have a 20-page contract. This file reads every line, figures out where each numbered clause starts and ends, scores how risky each clause sounds, and hands back a neat list like "Clause 3.1 — Liability — risk score 82 — flags: CONTRADICTION".

### Key Concepts Used

**PyMuPDF text extraction** (lines ~95–105)
```python
def _extract_pages(pdf_bytes: bytes) -> List[dict]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text")   # extracts plain text from PDF page
```
`fitz` is the PyMuPDF library. `get_text("text")` extracts all text from a page as a plain string, preserving line breaks. This is much more reliable than OCR for text-based PDFs.

**Clause segmentation regex** (lines ~115–125)
```python
CLAUSE_NUM_RE = re.compile(
    r"^[\s]*(\d{1,2}(?:\.\d{1,2}){0,2})\.?\s{1,6}(.+)",
    re.MULTILINE,
)
```
This regex matches lines that start with a clause number like `3.1`, `3.1.2`, `10.4`. Group 1 captures the number, Group 2 captures the clause text. The `{0,2}` means it handles up to 3 levels deep (e.g. `3.1.2`).

**Section heading regex** (lines ~127–133)
```python
HEADING_RE = re.compile(
    r"^[\s]*(?:(?:SECTION\s+)?\d{1,2}[\s.:\-—]+)?([A-Z][A-Z\s&,\-/]{3,60})\s*$",
    re.MULTILINE,
)
```
Matches lines that look like section headings: `LIABILITY`, `SECTION 3 — TERMINATION`, `DATA & PRIVACY`. Used to infer which section a clause belongs to.

**Multi-line clause accumulation** (`_segment_clauses`, lines ~140–210)
```python
j = i + 1
while j < len(lines):
    next_line = lines[j].strip()
    if CLAUSE_NUM_RE.match(lines[j]) or HEADING_RE.match(lines[j]):
        break   # next clause starts here
    if next_line:
        clause_text = clause_text + " " + next_line
    j += 1
```
A clause often spans multiple lines. This loop accumulates continuation lines until it hits the next clause number or heading. This is how "Clause 3.1" that spans 4 lines gets joined into one string.

**RISK_RULES scoring** (lines ~50–90)
```python
RISK_RULES = [
    (90, "CONTRADICTION", [[r"unlimited\s+liability"], ...]),
    (80, "ONE_SIDED",     [[r"at\s+its\s+sole\s+discretion"], ...]),
    (70, "AUTO_RENEWAL",  [[r"auto[\s-]?renew", r"unless\s+cancelled"], ...]),
    ...
]
```
Each rule is `(score, flag_name, list_of_pattern_groups)`. A pattern group is a list of regexes that ALL must match. Any one group matching is enough to apply the flag and score. The highest matching score wins. Multi-flag boost: each extra flag adds 3 points.

**Stable clause ID** (lines ~220–228)
```python
def _make_clause_id(doc_id: str, clause_number: str) -> str:
    sanitised = clause_number.replace(".", "_")
    return f"clause_{sanitised}"   # e.g. "clause_3_1"
```
IDs are derived from clause numbers, not random UUIDs. This means re-uploading the same document produces the same IDs — important for Ullas's RAG indexer which uses these IDs as vector store keys.

**Paragraph fallback** (`_paragraph_fallback`, lines ~212–235)
```python
# Used when no numbered clauses are found (e.g. some NDAs)
# Splits on double newlines, treats each paragraph as a clause
```
Some contracts don't use numbered clauses. This fallback handles them by treating each paragraph as a separate clause.

---

## `export/redline.py` — Word Document Generator

**What it is:** Takes the full analysis result dict and generates a professional `.docx` file with tracked changes, risk scores, Z3 proofs, and an audit trail.

**ELI5:** After all the AI analysis is done, this file creates a Word document that looks like what a lawyer would hand you — original clause in red with strikethrough, AI-fixed version in green, Z3 proof in monospace, and a summary table at the front.

### Key Concepts Used

**python-docx Document model** (lines ~1–30)
```python
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
```
`python-docx` builds Word documents programmatically. A `Document` contains `Paragraph` objects. Each `Paragraph` contains `Run` objects. A `Run` is a contiguous piece of text with the same formatting.

**Color constants** (lines ~32–45)
```python
COLOR_RED   = RGBColor(0xC0, 0x00, 0x00)
COLOR_GREEN = RGBColor(0x00, 0x70, 0x00)
COLOR_AMBER = RGBColor(0xBF, 0x8F, 0x00)
COLOR_NAVY  = RGBColor(0x1E, 0x3A, 0x5F)
```
These match the app's design system colors. Red = original/dangerous text. Green = fixed text. Amber = flagged but not fixed. Navy = headers.

**Strikethrough for original text** (lines ~95–105)
```python
def _add_colored_run(paragraph, text, strikethrough=False, ...):
    run = paragraph.add_run(text)
    if strikethrough:
        run.font.strike = True   # Word's tracked-deletion style
```
The "redline" effect: original dangerous clause text is shown in red with strikethrough, mimicking Word's "Track Changes" deletion style.

**Table with XML shading** (lines ~110–145)
```python
tc_pr = cell._tc.get_or_add_tcPr()
shd   = OxmlElement("w:shd")
shd.set(qn("w:fill"), "1E3A5F")   # navy background
tc_pr.append(shd)
```
`python-docx` doesn't expose table cell background color through its high-level API. This drops down to raw OOXML (Office Open XML) to set the cell shading. `qn()` converts `"w:fill"` to the proper XML namespace prefix.

**Document structure** (4 pages):
1. `_build_cover_page()` — title, date, overall risk score callout box
2. `_build_executive_summary()` — key metrics table, risk category breakdown
3. `_build_redline_section()` — clause-by-clause: auto-fixed (green) + high-risk unfixed (amber)
4. `_build_audit_trail()` — citation verification stats, hallucination list, disclaimer

**Output path** (lines ~310–320)
```python
output_path = os.path.join(tempfile.gettempdir(), f"redline_{doc_id}.docx")
doc.save(output_path)
return output_path
```
The `.docx` is saved to the system temp directory (`/tmp/` on Linux/Mac, `C:\Users\...\AppData\Local\Temp\` on Windows). The server then serves it as a `FileResponse` download.

---

---

# PUNITH (Hacker 3) — AI Agents

**Role:** Builds the CrewAI multi-agent pipeline that scores risk, finds compliance violations, and rewrites dangerous clauses using Claude LLM.
**Primary file:** `agents/crew.py`
**Technology:** CrewAI, Anthropic Claude, Pydantic, regex

---

## `agents/crew.py` — The CrewAI Agent Pipeline

**What it is:** A multi-agent system built with CrewAI. Three AI agents work in sequence: RiskAgent scores each clause, ComplianceAgent finds law violations, FixerAgent rewrites dangerous clauses. Before any LLM call, a deterministic pre-scoring engine runs to give the LLM context.

**ELI5:** Think of this as three lawyers working in a chain. The first lawyer reads every clause and gives it a danger score. The second lawyer checks if any clause breaks GDPR, Indian labour law, or IP law. The third lawyer rewrites the dangerous ones. But before any of them start, a paralegal (the pre-scoring engine) has already highlighted the obvious problems so the lawyers don't miss anything.

### Key Concepts Used

**PRE_SCORE_PATTERNS** (lines ~50–250)
```python
PRE_SCORE_PATTERNS: list = [
    (r"\blimit(s|ed)?\s+(liability|damages)\b", "ONE_SIDED", 40,
     "Unilateral liability cap detected..."),
    (r"\bno\s+limit\s+on\s+(liability|damages)\b", "CONTRADICTION", 75,
     "Unlimited liability clause..."),
    ...
]
```
Each entry is a 4-tuple: `(regex_pattern, flag_name, score_contribution, reason_text)`. The reason can be a string or a `lambda(match)` that uses the regex match groups to build a dynamic message (e.g. "Interest rate of 28% per annum — exceeds RBI threshold").

This runs entirely in Python with no API calls. It costs nothing and runs in milliseconds. Its output is fed to the LLM as context so the LLM can refine rather than start from scratch.

**`pre_score_clause(text)`** (lines ~255–295)
```python
def pre_score_clause(text: str) -> dict:
    # Runs all PRE_SCORE_PATTERNS against one clause
    # Returns {"base_score": int, "flags": [...], "reasons": [...]}
    base_score = min(total_score, 95)  # cap at 95, leave room for LLM
```
Scores are additive — multiple matching patterns add up. Capped at 95 so the LLM can push to 100 on genuinely extreme clauses.

**`apply_z3_boosts(pre_scores, contradictions)`** (lines ~310–340)
```python
# Takes Ullas's Z3 contradiction results
# Adds Z3_CONTRADICTION_BOOST (25 points) to every clause in a contradiction
# Appends the Z3 reason to the clause's reason list
```
This is the integration point between Ullas's Z3 engine and Punith's scoring. If Z3 proved clause 3.1 and 3.2 contradict each other, both get +25 points on top of their pre-score.

**`merge_scores(llm_scores, pre_scores)`** (lines ~360–410)
```python
# Strategy: take the HIGHER of (LLM score, pre_score)
# Merge flags from both sources (deduplicated)
# Combine reasons: pre_score reasons first, LLM reason appended
final_score = max(llm_score, pre_score)
```
The LLM may see nuance the regex missed. The regex may catch patterns the LLM was too conservative about. Taking the max of both ensures nothing is under-scored.

**LEGAL_CITATIONS** (lines ~430–650)
```python
LEGAL_CITATIONS: list = [
    (r"\bthird[- ]party\s+(analytics|partner|processor)\b",
     "GDPR_VIOLATION", "CRITICAL",
     "GDPR Art. 6(1)",
     "Sharing personal data with third-party analytics providers..."),
    ...
]
```
A registry of 25+ legal provisions mapped to regex patterns. Covers GDPR Articles 5, 6, 7, 25, 28, 32, 33, 34, 44–49; India DPDP Act 2023 S.7, S.8, S.12; Indian Contract Act 1872 S.27, S.74; Industrial Disputes Act 1947 S.25F; Indian Copyright Act 1957 S.17, S.57; Transfer of Property Act 1882 S.69; RBI usury guidelines.

This runs before the LLM. The ComplianceAgent receives these pre-computed citations as verified facts, so it never has to guess which law applies.

**Three CrewAI Agents**

```python
# RiskAgent — scores each clause 0-100
risk_agent = Agent(
    role="Senior Legal Risk Analyst",
    goal="Score each clause for legal risk on a scale of 0-100",
    tools=[contradiction_tool, citation_tool],  # Ullas's tools
    llm=claude_llm,
)

# ComplianceAgent — finds law violations
compliance_agent = Agent(
    role="Regulatory Compliance Specialist",
    goal="Identify GDPR, Indian labour law, and IP violations",
    tools=[citation_tool],
    llm=claude_llm,
)

# FixerAgent — rewrites dangerous clauses
fixer_agent = Agent(
    role="Contract Drafting Specialist",
    goal="Rewrite flagged clauses to be balanced and legally sound",
    tools=[citation_tool],
    llm=claude_llm,
)
```

**`analyse(clauses)` — the public API** (called by `server.py`)
```python
def analyse(clauses: List[Clause]) -> dict:
    # 1. Pre-score all clauses (deterministic, free)
    # 2. Get Z3 contradictions from Ullas's bridge
    # 3. Apply Z3 boosts to pre-scores
    # 4. Run CrewAI pipeline (LLM calls)
    # 5. Merge LLM scores with pre-scores
    # 6. Return {"compliance_violations": [...], "fixed_clauses": [...]}
```

**`_stub_result(clauses)` — fallback when no API key**
```python
def _stub_result(clauses: list) -> dict:
    # Returns pre-scored results without any LLM calls
    # Used when ANTHROPIC_API_KEY is not set
    # Produces realistic-looking output for demo purposes
```

### What Punith Should NOT Touch

- `schemas.py` — Ullas owns this (but Punith imports from it)
- `memory/bridge.py` — Ullas owns this (but Punith uses the tools it exports)
- `server.py` — Shashank owns this (but Punith's `analyse()` is called from it)

---

---

# ULLAS (Hacker 4) — AI Core

**Role:** Builds the data schemas, Z3 formal logic contradiction detector, RAG vector search system, and the bridge that connects them to the agent pipeline.
**Primary files:** `schemas.py`, `logic/validator.py`, `memory/rag.py`, `memory/bridge.py`, `memory/reset_between_docs.py`, `contracts/generate_contracts.py`
**Technology:** Pydantic, Z3 SMT Solver, SentenceTransformers, Qdrant, NetworkX, numpy

---

## `schemas.py` — The Data Contract

**What it is:** Pydantic models that define the shape of every data object in the system. Every other file imports from here.

**ELI5:** This is the "rulebook" that says what a Clause looks like, what a ContradictionResult looks like, etc. If Shashank's parser returns a clause without a `clause_id`, Pydantic will throw an error immediately. This prevents silent bugs where data is missing a field.

### Models Defined

**`Clause`** (lines ~4–14)
```python
class Clause(BaseModel):
    clause_id: str        # e.g. "clause_3_1" — stable, derived from clause number
    page_number: int      # which page in the PDF
    clause_number: str    # e.g. "3.1"
    text: str             # the full clause text
    section: str          # e.g. "Liability"
    risk_score: Optional[int] = None    # 0-100, filled by Punith's agent
    risk_reason: Optional[str] = None  # human-readable explanation
    fixed_clause: Optional[str] = None # AI-rewritten version
    source_citation: Optional[str] = None  # which clause the RAG matched
    flags: List[str] = []  # e.g. ["GDPR_VIOLATION", "CONTRADICTION"]
```
The central data object. Every module passes `Clause` objects around. The `Optional` fields start as `None` and get filled in as the pipeline progresses.

**`ContradictionResult`** (lines ~24–30)
```python
class ContradictionResult(BaseModel):
    clause_id_a: str          # first clause in the contradiction pair
    clause_id_b: str          # second clause
    contradiction_type: str   # "MUTUAL_EXCLUSION" | "LOGICAL_DEAD_END" | "CIRCULAR_OBLIGATION"
    explanation: str          # human-readable description
    z3_proof: str             # the Z3 solver output as a string
```
Returned by `logic/validator.py`. The `z3_proof` field contains the actual Z3 assertion output — this is what makes the contradiction detection formally verifiable, not just pattern-matched.

**`CitationResult`** (lines ~32–39)
```python
class CitationResult(BaseModel):
    claim: str                  # the agent's claim being verified
    source_clause_id: str       # which clause supports this claim
    source_page: int
    source_text_excerpt: str    # first 200 chars of the matching clause
    confidence_score: float     # 0.0 to 1.0 cosine similarity
    verified: bool              # True if score >= 0.55 threshold
```
Returned by `memory/rag.py`. The `verified` field is the anti-hallucination gate — if `False`, the claim is flagged as a potential hallucination.

**`ComplianceViolation`** (lines ~48–55)
```python
class ComplianceViolation(BaseModel):
    clause_id: str
    regulation_violated: str   # e.g. "GDPR"
    article_number: str        # e.g. "Art. 6(1)"
    violation_description: str
    severity: str              # "critical" | "moderate" | "low"
```
Note: `server.py`'s `_merge_results()` uses a slightly different dict shape (`violation_type`, `description`) for the API response. This Pydantic model is used internally by Punith's agents.

---

## `logic/validator.py` — Z3 Contradiction Detector

**What it is:** Uses the Z3 SMT (Satisfiability Modulo Theories) solver to formally prove when two clauses cannot both be true at the same time.

**ELI5:** Imagine Clause 3.1 says "the speed limit is 60 km/h" and Clause 3.2 says "there is no speed limit." A human can see these contradict. Z3 is a math engine that can *prove* they contradict — not just guess. It works by saying "assume both are true at the same time" and then proving that's impossible (UNSAT = unsatisfiable).

### Key Concepts Used

**CLAUSE_PATTERNS** (lines ~20–60)
```python
CLAUSE_PATTERNS: List[Tuple[str, str, int]] = [
    (r"\blimit(s|ed)?\s+(liability|damages)\b", "liability_limited", +1),
    (r"\bno\s+limit\s+on\s+(liability|damages)\b", "liability_limited", -1),
    ...
]
```
Each pattern is `(regex, logical_tag, polarity)`. Polarity `+1` means "this clause asserts the tag is TRUE". Polarity `-1` means "this clause asserts the tag is FALSE". The same tag with opposite polarities in two different clauses = contradiction.

**`extract_tags(text)`** (lines ~65–75)
```python
def extract_tags(text: str) -> dict[str, int]:
    # Returns {tag: polarity} for every pattern matched
    # e.g. {"liability_limited": +1, "notice_required": -1}
```
Runs all patterns against one clause's text. Returns a dict mapping each matched tag to its polarity.

**Z3 Boolean encoding** (lines ~78–90)
```python
def _build_z3_assertion(tag, polarity, var_map) -> BoolRef:
    if tag not in var_map:
        var_map[tag] = Bool(tag)   # create a Z3 Boolean variable
    var = var_map[tag]
    return var if polarity == +1 else Not(var)
```
Each logical tag becomes a Z3 Boolean variable. `Bool("liability_limited")` creates a variable. `Not(var)` negates it. The `var_map` dict reuses the same Z3 variable for the same tag across all clauses.

**`_check_pair()` — the core Z3 check** (lines ~92–130)
```python
def _check_pair(clause_a, clause_b, tags_a, tags_b, var_map):
    shared_tags = set(tags_a.keys()) & set(tags_b.keys())
    for tag in shared_tags:
        if tags_a[tag] == tags_b[tag]:
            continue   # same polarity — no contradiction
        # Opposite polarities — run Z3
        s = Solver()
        s.add(_build_z3_assertion(tag, tags_a[tag], var_map))
        s.add(_build_z3_assertion(tag, tags_b[tag], var_map))
        result = s.check()
        if result == unsat:
            # PROVED: both cannot hold simultaneously
            return ContradictionResult(...)
```
For each pair of clauses, find tags they share. If they assert opposite polarities for the same tag, add both assertions to a Z3 Solver and call `s.check()`. If Z3 returns `unsat`, the contradiction is formally proved.

**Circular obligation detection** (lines ~135–185)
```python
def _detect_circular_obligations(clauses):
    # Builds a dependency graph from cross-references
    # e.g. "subject to clause 3.1" → edge from current clause to 3.1
    # Runs DFS to find cycles
    # A cycle = CIRCULAR_OBLIGATION contradiction
```
Uses regex to find cross-references between clauses (`"subject to clause 3.1"`, `"pursuant to clause 7.2"`). Builds a directed graph and runs depth-first search to find cycles. A cycle means neither obligation can be independently fulfilled.

**`validate_clauses(clauses)`** (lines ~190–210) — the public API
```python
def validate_clauses(clauses: List[Clause]) -> List[ContradictionResult]:
    # Step 1: extract_tags() for every clause
    # Step 2: pairwise _check_pair() for all combinations
    # Step 3: _detect_circular_obligations()
    # Returns combined list of all contradictions found
```
Called by `memory/bridge.py`. Complexity is O(n²) for the pairwise check — fine for contracts (typically 20–100 clauses).

---

## `memory/rag.py` — Retrieval-Augmented Generation

**What it is:** A vector search system that can find the most semantically similar clause to any natural language query. Used to verify that agent claims are grounded in the actual contract text.

**ELI5:** Imagine you have 50 clauses and an agent says "the vendor's liability is capped." RAG converts that claim into a mathematical vector (a list of 384 numbers that represents its meaning), then finds the clause whose vector is closest. If the closest clause actually says something about liability caps, the claim is verified. If the closest clause is about something completely different, the claim is flagged as a hallucination.

### Key Concepts Used

**SentenceTransformer embedding** (lines ~30–40)
```python
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
VECTOR_DIM = 384   # this model outputs 384-dimensional vectors

_embedder = SentenceTransformer(EMBEDDING_MODEL)
vec = _embedder.encode(text, normalize_embeddings=True)
```
`all-MiniLM-L6-v2` is a small, fast sentence embedding model. It converts any text into a 384-dimensional vector where semantically similar texts have vectors that point in similar directions. `normalize_embeddings=True` makes all vectors unit length so cosine similarity = dot product.

**Qdrant vector database** (lines ~45–80)
```python
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
client.create_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
)
client.upsert(collection_name=COLLECTION_NAME, points=points)
results = client.search(query_vector=query_vector, limit=5)
```
Qdrant is a vector database optimised for similarity search. Each clause is stored as a `PointStruct` with its embedding vector and metadata payload. `client.search()` returns the top-K most similar clauses to a query vector.

**Stable UUID for clause IDs** (lines ~55–60)
```python
def _clause_uuid(clause_id: str) -> str:
    hex_digest = hashlib.md5(clause_id.encode()).hexdigest()
    return str(uuid.UUID(hex_digest))
```
Qdrant requires UUID point IDs. This converts the string clause_id (e.g. `"clause_3_1"`) to a deterministic UUID using MD5. Re-indexing the same clause always produces the same UUID, so upsert overwrites cleanly.

**Negation-aware verification** (lines ~115–135)
```python
_NEGATION_PAIRS = [
    ({"publicly", "freely share", "no limit"},
     {"confidential", "must not", "restricted"}),
    ...
]
# If claim says "can share publicly" but matched clause says "must not disclose"
# → downgrade to unverified even if cosine similarity is high
```
Cosine similarity measures topic similarity, not semantic agreement. A claim saying "data can be shared freely" and a clause saying "data must not be shared" are about the same topic (high similarity) but mean opposite things. This negation check catches that case.

**`InMemoryRAG` class** (lines ~195–265)
```python
class InMemoryRAG:
    # Fallback when Qdrant is not running
    # Uses numpy dot product instead of Qdrant search
    # Identical logic to the Qdrant path
    def index(self, clauses): ...
    def verify(self, claim_text): ...
```
The in-memory fallback stores vectors in a Python list and uses `numpy.dot()` for similarity search. No Docker, no external services needed. Used automatically when Qdrant is unavailable.

**Citation graph** (lines ~170–195)
```python
citation_graph: nx.DiGraph = nx.DiGraph()   # module-level singleton

# When a claim is verified:
claim_node = f"claim::{hash[:8]}"
citation_graph.add_node(claim_node, type="claim", text=claim_text[:80])
citation_graph.add_edge(claim_node, used_clause_id, weight=score, verified=verified)
```
Every verification call adds an edge to a NetworkX directed graph: `claim_node → clause_node`. This builds an audit trail of which claims cited which clauses. Dhanush's frontend renders this as an interactive graph. Shashank's redline exporter includes it in the Word document.

**`get_citation_summary()`** (lines ~270–290)
```python
# Returns:
{
    "total_claims_made": 50,
    "verified_citations": 47,
    "unverified_citations": 3,
    "hallucination_rate": 0.06,   # 3/50
    "graph_nodes": 55,
    "graph_edges": 50,
}
```
The hallucination rate is the fraction of agent claims that couldn't be grounded in the contract. A rate of 0% means every claim the AI made was backed by actual contract text.

---

## `memory/bridge.py` — The Integration Layer

**What it is:** Wraps Ullas's validator and RAG into CrewAI `BaseTool` objects that Punith's agents can call, plus plain functions that Shashank's server can call directly.

**ELI5:** Punith's AI agents need to use Ullas's tools, but CrewAI agents can only use tools that follow a specific interface (`BaseTool`). This file wraps the tools in that interface. It also provides a simple `run_full_analysis()` function that Shashank's server can call without knowing anything about CrewAI.

### Three CrewAI Tools

**`ContradictionTool`** (lines ~55–80)
```python
class ContradictionTool(BaseTool):
    name = "ContradictionDetector"
    # Input: JSON string of List[Clause]
    # Output: JSON string of List[ContradictionResult]
    def _run(self, clauses_json: str) -> str:
        clauses = [Clause(**c) for c in json.loads(clauses_json)]
        results = validate_clauses(clauses)   # calls logic/validator.py
        return json.dumps([r.model_dump() for r in results])
```

**`CitationTool`** (lines ~83–105)
```python
class CitationTool(BaseTool):
    name = "CitationVerifier"
    # Input: claim_text string
    # Output: JSON CitationResult with verified=True/False
    def _run(self, claim_text: str) -> str:
        result = _get_rag().verify(claim_text)   # calls memory/rag.py
        return json.dumps(result.model_dump())
```

**`RagIndexTool`** (lines ~108–130)
```python
class RagIndexTool(BaseTool):
    name = "RagIndexTool"
    # Input: JSON string of List[Clause]
    # Output: confirmation message
    def _run(self, clauses_json: str) -> str:
        _rag_instance = InMemoryRAG()
        count = _rag_instance.index(clauses)
        return json.dumps({"status": "indexed", "clauses_indexed": count})
```

### Two Plain Functions

**`run_full_analysis(clauses)`** (lines ~155–185) — called by `server.py`
```python
def run_full_analysis(clauses: List[Clause]) -> Dict:
    # 1. Index clauses into RAG
    # 2. Run Z3 contradiction detection
    # 3. Auto-verify one claim per clause
    # 4. Export citation graph
    # Returns combined dict with all results
```

**`get_graph_for_export()`** (lines ~140–155) — called by `export/redline.py`
```python
def get_graph_for_export() -> Dict:
    # Serialises the NetworkX citation graph to JSON
    # Returns {"nodes": [...], "edges": [...], "summary": {...}, "top_cited": [...]}
```

---

## `memory/reset_between_docs.py` — State Reset

**What it is:** A single function that clears all in-memory state between document analyses.

**ELI5:** After analysing Document A, the RAG store has Document A's clauses and the citation graph has Document A's edges. Before analysing Document B, everything must be cleared. This file does that clearing.

```python
def reset_for_new_document() -> dict:
    bridge_module._rag_instance = None      # clear RAG instance
    bridge_module._indexed_clauses = []     # clear indexed clause list
    rag_module.citation_graph.clear()       # clear NetworkX graph
    bridge_module.citation_graph = rag_module.citation_graph  # re-sync reference
    return {"status": "reset", "message": "..."}
```

Called by `server.py` at the start of every `POST /analyse` request (line ~195 in server.py):
```python
reset_for_new_document()
bridge_result = run_full_analysis(clause_objects)
```

---

---

# SHARED / UTILITY FILES

These files are owned by the team collectively. No single person should modify them without coordinating.

---

## `handshake_check.py` — Pre-Demo Integration Verifier

**What it is:** A standalone script that imports every module, runs smoke tests, and reports pass/fail for each teammate's code. Run this before every demo.

**ELI5:** Before a demo, you want to know "does everything work together?" This script checks all 4 hackers' modules in sequence, runs the full pipeline offline (no server needed), and prints a clear pass/fail report.

```bash
python handshake_check.py
```

**What it checks:**
- Ullas: `schemas.py`, `logic/validator.py`, `memory/rag.py`, `memory/bridge.py`, `memory/reset_between_docs.py`
- Shashank: `ingestion/parser.py` (with a real risk score test), `server.py` (all 6 routes present), `export/redline.py` (generates a real .docx)
- Punith: `agents/crew.py` (importable)
- Dhanush: `app.py` (all 8 page functions present, checked via AST parsing)
- Pipeline: runs `run_full_analysis()` on 4 test clauses, verifies 2 contradictions detected
- Contracts: verifies 18 PDFs exist in `contracts/`

---

## `healthcheck.py` — Pre-Launch Environment Validator

**What it is:** Checks Python version, environment variables, installed packages, and each module's importability. Run this before `start.sh`.

```bash
python healthcheck.py
```

**What it checks:**
1. Python 3.10+
2. `ANTHROPIC_API_KEY` set (warns if missing, doesn't block)
3. All packages from `requirements.txt` importable
4. Ullas's modules importable
5. Punith's `analyse()` has correct signature `(clauses)`
6. Shashank's `server.py` syntax valid
7. Dhanush's `app.py` syntax valid
8. At least 1 PDF in `contracts/`

---

## `requirements.txt` — Python Dependencies

Pinned to exact versions to ensure reproducibility across all 4 machines.

| Package | Version | Owner | Purpose |
|---------|---------|-------|---------|
| `fastapi` | 0.115.0 | Shashank | REST API framework |
| `uvicorn` | 0.30.6 | Shashank | ASGI server for FastAPI |
| `python-multipart` | 0.0.9 | Shashank | File upload support |
| `PyMuPDF` | 1.24.11 | Shashank | PDF text extraction |
| `python-docx` | 1.1.2 | Shashank | Word document generation |
| `streamlit` | 1.33.0 | Dhanush | Web UI framework |
| `plotly` | 5.21.0 | Dhanush | Interactive charts |
| `pandas` | 2.2.2 | Dhanush | Data manipulation for charts |
| `pydantic` | ≥2.4.2 | Ullas | Data validation / schemas |
| `z3-solver` | 4.13.0 | Ullas | SMT formal logic solver |
| `sentence-transformers` | 2.7.0 | Ullas | Text embedding for RAG |
| `qdrant-client` | 1.9.0 | Ullas | Vector database client |
| `networkx` | 3.3 | Ullas | Citation graph |
| `numpy` | 1.26.4 | Ullas | Vector math for InMemoryRAG |
| `crewai` | 0.80.0 | Punith | Multi-agent orchestration |
| `anthropic` | 0.40.0 | Punith | Claude API client |
| `langchain-anthropic` | 0.3.0 | Punith | LangChain Claude integration |

---

## `.env.example` — Environment Variable Template

Safe to commit to git (contains no real secrets). Copy to `.env` and fill in real values.

```dotenv
ANTHROPIC_API_KEY=your_anthropic_api_key_here   # ← only real secret needed
SERVER_PORT=8000
STREAMLIT_PORT=8501
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

---

## `start.sh` — Full Stack Startup Script

Starts both services in the correct order with health checks between steps.

**Steps it performs:**
1. Loads `.env` (copies from `.env.example` if missing)
2. Checks Python version
3. Checks core dependencies are importable
4. Checks all teammate modules
5. Generates demo contracts if fewer than 18 PDFs exist
6. Kills any existing processes on ports 8000 and 8501
7. Starts `python server.py` in background, waits up to 15s for `/health` to respond
8. Starts `streamlit run app.py` in background
9. Traps `Ctrl+C` for clean shutdown of both processes

---

## `contracts/generate_contracts.py` — Demo PDF Generator

**Owner:** Ullas
**What it does:** Generates 18 realistic contract PDFs using `fpdf2`. Each contract has numbered clauses with intentional risk patterns (contradictions, GDPR violations, auto-renewal traps) so the demo always has interesting results.

**Contract types generated:**
1. SaaS Subscription Agreement
2. Vendor Services Agreement
3. NDA (Bilateral)
4. Employment Contract
5. Software License Agreement
6. Data Processing Agreement
7. Freelance Consulting Agreement
8. Commercial Lease Agreement
9. Partnership Agreement
10. Agency Agreement
11. Loan Agreement
12. Reseller Agreement
13. Marketing Services Agreement
14. Subscription Content Agreement
15. Construction Contract
16. API Integration Agreement
17. Healthcare Services Agreement
18. Joint Venture Agreement

---

## `tests/` — Test Suite

| File | Owner | What it tests |
|------|-------|---------------|
| `tests/test_crew_unit.py` | Punith | Unit tests for `pre_score_clause()`, `merge_scores()`, `apply_z3_boosts()` |
| `tests/test_integration.py` | Shashank | Full pipeline with a running server: upload → analyse → results → export |
| `test_integration.py` (root) | Shashank | Same as above, root-level copy for convenience |

Run unit tests:
```bash
pytest tests/test_crew_unit.py -v
```

Run integration tests (server must be running):
```bash
python test_integration.py
```

---

# Cross-Module Interface Contract

This section defines exactly what each module must accept and return. If you change these interfaces, you must coordinate with the affected teammates.

## `ingestion/parser.py` → `server.py`

```python
# extract_clauses(pdf_bytes: bytes, doc_id: str) → List[dict]
# Each dict must have these keys (matches schemas.Clause fields):
{
    "clause_id":     str,   # e.g. "clause_3_1"
    "clause_number": str,   # e.g. "3.1"
    "page_number":   int,
    "section":       str,
    "text":          str,
    "risk_score":    int,   # 0-100
    "risk_reason":   str | None,
    "flags":         list,  # e.g. ["CONTRADICTION"]
}
```

## `memory/bridge.py` → `server.py`

```python
# run_full_analysis(clauses: List[Clause]) → dict
{
    "clauses_analysed":     int,
    "contradictions_found": int,
    "contradictions":       List[dict],   # ContradictionResult.model_dump()
    "citation_results":     List[dict],   # CitationResult.model_dump()
    "citation_graph":       dict,         # {nodes, edges, summary, top_cited}
    "hallucination_rate":   float,        # 0.0 to 1.0
}
```

## `agents/crew.py` → `server.py`

```python
# analyse(clauses: List[Clause]) → dict
{
    "compliance_violations": List[dict],  # {clause_id, violation_type, description, severity}
    "fixed_clauses":         List[dict],  # {clause_id, original_text, fixed_text, fix_explanation}
}
```

## `export/redline.py` → `server.py`

```python
# generate_redline_docx(analysis: dict, doc_id: str) → str
# Returns absolute path to generated .docx file
# analysis dict must have: doc_id, overall_risk_score, risk_label, clauses,
#   contradictions, compliance_violations, citation_results, fixed_clauses,
#   hallucination_rate, citation_graph
```

---

# Git Workflow

## Branch naming

```
main          ← stable, demo-ready code only
dev           ← integration branch
feature/dhanush-*   ← Dhanush's feature branches
feature/shashank-*  ← Shashank's feature branches
feature/punith-*    ← Punith's feature branches
feature/ullas-*     ← Ullas's feature branches
```

## Before pushing

```bash
# 1. Run handshake check
python handshake_check.py

# 2. Run your module's smoke test
python <your_module>.py

# 3. Run unit tests
pytest tests/ -v

# 4. Commit only your files
git add <your_files>
git commit -m "feat(your-name): description"
git push origin feature/your-name-description
```

## Never commit

- `.env` (contains your API key)
- `*.docx` output files
- `__pycache__/` directories
- `.venv/` or any virtual environment folder

All of these are in `.gitignore`.

---

*RegulAIte — Because every contract has a landmine.*
