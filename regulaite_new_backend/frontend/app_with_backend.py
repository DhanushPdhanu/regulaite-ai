# pyrefly: ignore [missing-import]
"""
LegalInspect — Streamlit frontend wired to the RegulAIte FastAPI backend.
Run from regulaite_new_backend/ folder:
    streamlit run frontend/app_with_backend.py
The backend must be running at http://localhost:8000
"""
import streamlit as st
import time
import difflib
import requests
import json

BACKEND_URL = "http://localhost:8000"

st.set_page_config(
    page_title="LegalInspect | AI Legal Simplifier",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Query param / session state sync ─────────────────────────────────────────
qp = st.query_params
if "page" in qp:
    st.session_state['current_page'] = qp["page"]
elif 'current_page' not in st.session_state:
    st.session_state['current_page'] = "Dashboard"

if "demo" in qp:
    st.session_state['demo_mode'] = (qp["demo"] == "true")
    st.session_state['analysis_complete'] = True
    st.session_state['file_uploaded'] = False
    st.session_state['filename'] = qp.get("filename", "NDA_v3.2_Draft.pdf")
elif "analyzed" in qp:
    st.session_state['analysis_complete'] = (qp["analyzed"] == "true")
    st.session_state['file_uploaded'] = True
    st.session_state['demo_mode'] = False
    st.session_state['filename'] = qp.get("filename", "Contract.pdf")
else:
    for k, v in [('file_uploaded', False), ('analysis_complete', False),
                 ('filename', ''), ('demo_mode', False), ('ai_data', None)]:
        if k not in st.session_state:
            st.session_state[k] = v

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_nav_link(page_name):
    params = [f"page={page_name}"]
    if st.session_state.get('demo_mode'):
        params.append("demo=true")
    elif st.session_state.get('analysis_complete'):
        params.append("analyzed=true")
    if st.session_state.get('filename'):
        params.append(f"filename={st.session_state['filename']}")
    return "?" + "&".join(params)

def render_html(html_code: str):
    cleaned = " ".join([line.strip() for line in html_code.splitlines()])
    st.markdown(cleaned, unsafe_allow_html=True)

def get_word_diff(original: str, rewritten: str) -> str:
    orig_words = original.split()
    rewr_words = rewritten.split()
    matcher = difflib.SequenceMatcher(None, orig_words, rewr_words)
    diff_html = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == 'equal':
            diff_html.extend(orig_words[i1:i2])
        elif op == 'replace':
            del_text = " ".join(orig_words[i1:i2])
            add_text = " ".join(rewr_words[j1:j2])
            if del_text:
                diff_html.append(f'<span class="diff-del">{del_text}</span>')
            if add_text:
                diff_html.append(f'<span class="diff-add">{add_text}</span>')
        elif op == 'delete':
            diff_html.append(f'<span class="diff-del">{" ".join(orig_words[i1:i2])}</span>')
        elif op == 'insert':
            diff_html.append(f'<span class="diff-add">{" ".join(rewr_words[j1:j2])}</span>')
    return " ".join(diff_html)

def get_playbook_link(clause_key, persona_key):
    params = ["page=SmartReview", "tab=AutoFixer",
              f"clause={clause_key}", f"persona={persona_key}"]
    if st.session_state.get('demo_mode'):
        params.append("demo=true")
    elif st.session_state.get('analysis_complete'):
        params.append("analyzed=true")
    if st.session_state.get('filename'):
        params.append(f"filename={st.session_state['filename']}")
    return "?" + "&".join(params)

def call_backend_analyse(uploaded_file) -> dict:
    """POST the PDF to the FastAPI backend and return parsed JSON."""
    try:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
        resp = requests.post(f"{BACKEND_URL}/analyse", files=files, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error(
            f"Cannot connect to backend at {BACKEND_URL}. "
            "Make sure the FastAPI server is running: `python backend/server.py`"
        )
        return None
    except requests.exceptions.Timeout:
        st.error("Backend timed out (>120s). The contract may be too large.")
        return None
    except Exception as exc:
        st.error(f"Backend error: {exc}")
        return None

def get_demo_data() -> dict:
    """Fetch stub/demo data from the backend health + stub endpoint."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/analyse/json",
            json={"text": "DEMO CONTRACT: This is a sample NDA agreement for demonstration purposes. "
                          "Client may terminate at any time. Vendor liability is uncapped. "
                          "All IP belongs to Client regardless of when created."},
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        # Fallback inline demo data if backend is unreachable
        from datetime import datetime
        today = datetime.now().strftime("%d %b %Y")
        return {
            "score": 87, "verdict": "High Risk",
            "summary": "Demo mode: This contract contains severe indemnification asymmetries and an effectively unlimited vendor liability exposure.",
            "pages_analyzed": 47, "pages_trend": "+6 pages",
            "relevant_precedents": 12, "precedents_trend": "+3 cases",
            "identified_risks": 5, "risks_trend": "+2 this week",
            "ai_confidence": "92%", "confidence_trend": "+4%",
            "risk_zone": "Medium 2.3", "analyzed_date": today,
            "last_edited": "Anna K., Associate", "filename": "NDA_v3.2_Draft.pdf",
            "red_flags": [
                {"category": "Indemnification", "severity": 9,
                 "clause_text": "Vendor agrees to indemnify the Client regardless of fault.",
                 "citation": "Page 3, Section 4.2", "impact": "'Regardless of fault' exposes Vendor to Client's own negligence."},
                {"category": "Termination Asymmetry", "severity": 8,
                 "clause_text": "Client may terminate upon 5 days notice; Vendor requires 60 days.",
                 "citation": "Page 7, Section 9.1", "impact": "Severe operational instability for Vendor."},
                {"category": "Liability Cap", "severity": 10,
                 "clause_text": "Client liability capped at 1 month fees. No cap on Vendor.",
                 "citation": "Page 8, Section 10.4", "impact": "Vendor liability is entirely uncapped — critical imbalance."},
            ],
            "loophole_logs": [
                {"role": "Exploiter", "content": "Section 4.2 — 'regardless of fault' means Vendor indemnifies Client even for Client's own recklessness."},
                {"role": "Defender", "content": "The express negligence doctrine may render this partially unenforceable, but it must be renegotiated."},
                {"role": "Exploiter", "content": "Section 10.4 — Client capped at ~$41k/year while Vendor has zero cap. Textbook adversarial clause."},
                {"role": "Defender", "content": "A mutual 12-month fee cap is market standard and should be the negotiation target."},
            ],
            "logic_conflicts": [
                {"conflict": "Data Retention vs. Destruction",
                 "rule_a": "Section 2.1: Destroy all data within 30 days of termination.",
                 "rule_b": "Section 5.4: Retain transactional backups for 3 years.",
                 "explanation": "Complying with one clause legally violates the other.",
                 "severity": "Critical"},
            ],
            "auto_fixes": [
                {"issue": "Asymmetric Termination", "risk_level": "High",
                 "original": "Client may terminate upon 5 days notice; Vendor requires 60 days.",
                 "suggested": "Either party may terminate upon 30 days notice for convenience.",
                 "rationale": "Equalizes termination rights for both parties."},
            ],
        }

# ── Playbook data (static UI data — not from backend) ────────────────────────
playbook_data = {
    "Termination Rights": {
        "title": "Asymmetric Termination Rights", "severity": 8,
        "original": "Client may terminate this Agreement at any time for any reason upon five (5) days' written notice, whereas Vendor may only terminate upon a material breach remaining uncured for sixty (60) days.",
        "Defender": {"rewrite": "Either party may terminate this Agreement for convenience upon thirty (30) days' prior written notice. Either party may terminate for material breach remaining uncured for fifteen (15) days.", "risk_label": "🛡️ Balanced Risk", "risk_class": "low", "score": "3/10", "rationale": "Introduces a mutual termination for convenience right and curtails the cure period to a commercially standard 15 days."},
        "Exploiter": {"rewrite": "Vendor may terminate this Agreement at any time for convenience upon five (5) days' notice. Client shall have no right to terminate for convenience and may only terminate for uncured material breach after ninety (90) days.", "risk_label": "😈 Extremely Vendor-Favored", "risk_class": "low", "score": "1/10", "rationale": "Gives the Vendor maximum flexibility while locking the Client in for absolute contract stability."},
        "Arbitrator": {"rewrite": "Client may terminate this Agreement for convenience at any time upon five (5) days' written notice. Vendor shall have no right to terminate for convenience under any circumstances.", "risk_label": "⚖️ Highly Customer-Favored", "risk_class": "critical", "score": "9/10", "rationale": "Fully favors the Client with immediate convenience rights while offering zero convenience exit to the Vendor."},
    },
    "Liability Cap": {
        "title": "Uncapped Vendor Liability", "severity": 10,
        "original": "In no event shall Client's total aggregate liability arising out of or related to this Agreement exceed the total fees paid in the one (1) month preceding the event. No limitation applies to Vendor.",
        "Defender": {"rewrite": "Each party's aggregate liability arising out of this Agreement shall not exceed the total fees paid or payable by Client to Vendor in the twelve (12) months preceding the event. This limit shall not apply to breaches of confidentiality.", "risk_label": "🛡️ Balanced Risk", "risk_class": "low", "score": "3/10", "rationale": "Introduces a mutual, market-standard liability cap equal to 12 months' fees, protecting both sides equally."},
        "Exploiter": {"rewrite": "Vendor's aggregate liability for all claims shall be strictly capped at five thousand dollars ($5,000). Client's liability under this Agreement shall remain entirely uncapped and unlimited.", "risk_label": "😈 Extremely Vendor-Favored", "risk_class": "low", "score": "1/10", "rationale": "Insulates the Vendor from catastrophic damage using an ultra-low cap while leaving the Client fully exposed."},
        "Arbitrator": {"rewrite": "Vendor's aggregate liability under this Agreement shall be entirely uncapped and unlimited. Client's aggregate liability shall be capped at the total amount paid by Client in the preceding one (1) month.", "risk_label": "⚖️ Highly Customer-Favored", "risk_class": "critical", "score": "10/10", "rationale": "Exposes the Vendor to unlimited damages while capping the Client at one month of spending."},
    },
    "IP Assignment": {
        "title": "Overbroad Intellectual Property Assignment", "severity": 7,
        "original": "All work product, inventions, discoveries, and improvements conceived or developed by Vendor, whether or not during working hours and whether or not using Client's resources, shall be the exclusive property of Client.",
        "Defender": {"rewrite": "All deliverables specifically created by Vendor for Client under this Agreement shall belong to Client. Vendor explicitly retains all rights to its pre-existing technologies, background IP, and general methodologies.", "risk_label": "🛡️ Balanced Risk", "risk_class": "low", "score": "2/10", "rationale": "Limits Client ownership to custom deliverables and expressly protects the Vendor's foundational pre-existing Background IP."},
        "Exploiter": {"rewrite": "Vendor retains exclusive sole ownership of all intellectual property, work product, and deliverables developed under this Agreement. Client is granted a non-exclusive, revocable license to use the deliverables solely for its internal operations.", "risk_label": "😈 Extremely Vendor-Favored", "risk_class": "low", "score": "1/10", "rationale": "Keeps all newly created IP with the Vendor, granting the Client only a narrow, revocable license."},
        "Arbitrator": {"rewrite": "All inventions, intellectual property, work product, source code, and deliverables developed by Vendor (and its affiliates or subcontractors) at any time during this Agreement shall belong exclusively to Client. Vendor waives all moral rights.", "risk_label": "⚖️ Highly Customer-Favored", "risk_class": "high", "score": "8/10", "rationale": "Gives absolute intellectual property dominance to the Client, stripping the Vendor of all potential side-project rights."},
    },
}

# ── CSS ───────────────────────────────────────────────────────────────────────
render_html("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
#MainMenu, header, footer { visibility: hidden !important; }
.stDeployButton { display: none !important; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.stApp { background: #f4f5f7 !important; color: #111827 !important; }
[data-testid="stChatMessageContent"] p, [data-testid="stChatMessageContent"] div { color: #374151 !important; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; padding-left: 2rem !important; padding-right: 2rem !important; max-width: 1440px !important; }
[data-testid="stSidebar"] { background-color: #0f1115 !important; border-right: none !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #8b949e; }
.sidebar-container { display: flex; flex-direction: column; padding: 0; }
.sidebar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; padding: 0 4px; }
.logo-box { background: #ffffff; border-radius: 6px; width: 26px; height: 26px; display: flex; align-items: center; justify-content: center; font-weight: 700; color: #111214; font-size: 0.95rem; }
.brand-name { color: #ffffff; font-size: 1.1rem; font-weight: 600; }
.sidebar-section-title { font-size: 0.65rem; font-weight: 600; letter-spacing: 0.08em; color: #4b5563; margin-top: 1.25rem; margin-bottom: 0.5rem; text-transform: uppercase; padding-left: 8px; }
.sidebar-nav-item { display: flex; align-items: center; gap: 10px; color: #9ca3af !important; text-decoration: none !important; padding: 8px 12px; border-radius: 8px; font-size: 0.875rem; font-weight: 500; margin-bottom: 3px; transition: all 0.2s ease; }
.sidebar-nav-item:hover { color: #ffffff !important; background: rgba(255,255,255,0.05); }
.sidebar-nav-item.active { background: #ffffff !important; color: #111827 !important; font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.sidebar-nav-item.disabled { opacity: 0.4; cursor: not-allowed; pointer-events: none; }
.sidebar-divider { border-top: 1px solid rgba(255,255,255,0.08); margin: 1.25rem 0.5rem; }
.dashboard-container { display: flex; flex-direction: column; gap: 1.5rem; }
.header-container { display: flex; justify-content: space-between; align-items: center; background: #ffffff; padding: 12px 24px; border-radius: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.02); border: 1px solid #e5e7eb; }
.header-title { font-size: 1.3rem; font-weight: 600; color: #111827; margin: 0 !important; }
.dashboard-grid { display: grid; grid-template-columns: 350px 1fr; gap: 1.5rem; }
.col-left { display: flex; flex-direction: column; gap: 1.25rem; }
.col-right { display: flex; flex-direction: column; gap: 1.25rem; }
.card { background: #ffffff; border-radius: 14px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.02); border: 1px solid #f0f1f3; display: flex; flex-direction: column; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; }
.card-title { font-size: 1.05rem; font-weight: 600; color: #111827; margin: 0 !important; }
.card-actions { color: #9ca3af; font-size: 0.9rem; cursor: pointer; }
.card-subtitle { font-size: 0.75rem; color: #9ca3af; margin-bottom: 0.75rem; margin-top: -0.75rem; }
.pdf-row { display: flex; align-items: center; background: #fafafa; border: 1px solid #f3f4f6; border-radius: 10px; padding: 12px; gap: 12px; margin-bottom: 1.25rem; }
.pdf-icon { font-size: 1.5rem; color: #ef4444; }
.pdf-info { flex-grow: 1; }
.pdf-name { font-size: 0.85rem; font-weight: 500; color: #111827; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 170px; }
.pdf-meta { font-size: 0.7rem; color: #9ca3af; margin-top: 2px; }
.meta-list { display: flex; flex-direction: column; gap: 10px; margin-bottom: 1.25rem; }
.meta-item { display: flex; justify-content: space-between; font-size: 0.825rem; }
.meta-label { color: #9ca3af; }
.meta-value { color: #111827; font-weight: 500; }
.progress-section { display: flex; flex-direction: column; gap: 8px; margin-top: 0.25rem; border-top: 1px solid #f3f4f6; padding-top: 1rem; }
.progress-header { display: flex; justify-content: space-between; font-size: 0.8rem; }
.progress-label { color: #4b5563; font-weight: 500; }
.progress-value { color: #06b6d4; font-weight: 600; }
.progress-bar-container { width: 100%; height: 6px; background: #e5e7eb; border-radius: 10px; overflow: hidden; }
.progress-bar-fill { height: 100%; background: linear-gradient(90deg, #06b6d4, #10b981); border-radius: 10px; }
.stage-tag { align-self: flex-start; background: #f3f4f6; color: #4b5563; font-size: 0.72rem; padding: 3px 8px; border-radius: 12px; margin-top: 4px; font-weight: 500; }
.risk-badge { background: #fff5f5; color: #e11d48; border: 1px solid #fecdd3; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; display: inline-flex; align-items: center; gap: 4px; }
.recommendation-box { background: #f5f3ff; border-radius: 10px; padding: 12px 16px; margin-bottom: 1.25rem; border-left: 3px solid #8b5cf6; }
.rec-title { font-size: 0.8rem; font-weight: 600; color: #6d28d9; margin-bottom: 4px; }
.rec-content { font-size: 0.8rem; color: #4c1d95; line-height: 1.4; }
.suggested-rewrite-btn { display: block; width: 100%; background: #111827; color: #ffffff !important; text-align: center; padding: 10px; border-radius: 8px; font-size: 0.825rem; font-weight: 500; text-decoration: none !important; transition: background 0.2s; border: none; }
.kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
.kpi-card { background: #ffffff; border-radius: 12px; padding: 1.25rem; box-shadow: 0 1px 3px rgba(0,0,0,0.02); border: 1px solid #f0f1f3; display: flex; flex-direction: column; gap: 8px; }
.kpi-label { font-size: 0.78rem; color: #6b7280; font-weight: 500; }
.kpi-value-container { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 4px; }
.kpi-val { font-size: 1.85rem; font-weight: 600; color: #111827; line-height: 1; }
.kpi-trend { font-size: 0.7rem; font-weight: 600; padding: 2px 6px; border-radius: 8px; }
.trend-green { background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }
.trend-red { background: #fff5f5; color: #dc2626; border: 1px solid #fca5a5; }
.chart-card { padding: 1.5rem; }
.chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.chart-toggles { display: flex; gap: 8px; }
.toggle-pill { font-size: 0.72rem; font-weight: 600; padding: 4px 10px; border-radius: 12px; cursor: pointer; border: 1px solid #e5e7eb; color: #6b7280; }
.toggle-pill.active { background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe; }
.toggle-pill.red { border-color: #fecdd3; color: #e11d48; background: #fff5f5; }
.table-card { padding: 1.5rem; }
.cases-table { width: 100%; border-collapse: collapse; margin-top: 0.25rem; }
.cases-table th { text-align: left; font-size: 0.75rem; font-weight: 600; color: #9ca3af; padding: 8px 12px; border-bottom: 1px solid #f3f4f6; }
.cases-table td { padding: 12px; font-size: 0.825rem; color: #374151; border-bottom: 1px solid #f9fafb; }
.cases-table tr:last-child td { border-bottom: none; }
.cases-table tr td:first-child { font-weight: 500; color: #111827; }
.outcome-pill { font-size: 0.72rem; font-weight: 600; padding: 3px 8px; border-radius: 12px; display: inline-block; }
.outcome-pill.win { background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }
.outcome-pill.settled { background: #fffbeb; color: #d97706; border: 1px solid #fcd34d; }
.custom-tabs { display: flex; gap: 8px; background: #f3f4f6; padding: 4px; border-radius: 10px; margin-bottom: 1.5rem; border: 1px solid #e5e7eb; max-width: 500px; }
.custom-tab { flex: 1; text-align: center; padding: 8px 12px; font-size: 0.85rem; font-weight: 500; color: #6b7280 !important; text-decoration: none !important; border-radius: 8px; transition: all 0.2s; }
.custom-tab.active { background: #ffffff; color: #111827 !important; font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
.subpage-container { background: #ffffff; border-radius: 14px; padding: 2rem; border: 1px solid #f0f1f3; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }
.subpage-title { font-size: 1.4rem; font-weight: 700; color: #111827; margin-bottom: 1.5rem; }
.search-results-list { display: flex; flex-direction: column; gap: 12px; margin-top: 1.5rem; }
.search-card { background: #fafafa; border: 1px solid #e5e7eb; border-radius: 10px; padding: 1.25rem; }
.search-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.search-card-title { font-size: 0.95rem; font-weight: 600; color: #111827; }
.search-card-score { font-size: 0.75rem; font-weight: 600; background: #ecfdf5; color: #059669; padding: 2px 8px; border-radius: 12px; }
.search-card-content { font-size: 0.85rem; color: #4b5563; line-height: 1.5; }
.search-card-meta { font-size: 0.72rem; color: #9ca3af; margin-top: 10px; border-top: 1px solid #f3f4f6; padding-top: 8px; }
.glass-panel { background: rgba(17,24,39,0.95) !important; backdrop-filter: blur(18px) !important; border: 1px solid rgba(255,255,255,0.08) !important; border-radius: 18px !important; padding: 2rem !important; color: #f3f4f6 !important; box-shadow: 0 10px 40px 0 rgba(0,0,0,0.45) !important; margin-bottom: 2rem !important; }
.glass-title { font-size: 1.4rem !important; font-weight: 700 !important; color: #ffffff !important; margin-bottom: 0.5rem !important; }
.glass-subtitle { font-size: 0.85rem !important; color: #9ca3af !important; margin-bottom: 1.75rem !important; line-height: 1.5 !important; }
.glass-split-screen { display: grid !important; grid-template-columns: 1fr 1fr !important; gap: 1.5rem !important; margin-bottom: 1.5rem !important; }
.glass-pane { background: rgba(255,255,255,0.03) !important; border: 1px solid rgba(255,255,255,0.05) !important; border-radius: 12px !important; padding: 1.5rem !important; display: flex !important; flex-direction: column !important; gap: 12px !important; }
.pane-header { display: flex !important; justify-content: space-between !important; align-items: center !important; border-bottom: 1px solid rgba(255,255,255,0.08) !important; padding-bottom: 10px !important; margin-bottom: 4px !important; }
.pane-title { font-size: 0.8rem !important; font-weight: 600 !important; letter-spacing: 0.06em !important; text-transform: uppercase !important; color: #9ca3af !important; }
.pane-content { font-size: 0.925rem !important; line-height: 1.7 !important; color: #e5e7eb !important; background: rgba(0,0,0,0.25) !important; border-radius: 8px !important; padding: 1.25rem !important; min-height: 140px !important; }
.diff-add { background: rgba(16,185,129,0.22) !important; color: #34d399 !important; border-radius: 4px !important; padding: 2px 5px !important; font-weight: 600 !important; }
.diff-del { background: rgba(244,63,94,0.22) !important; color: #f87171 !important; border-radius: 4px !important; padding: 2px 5px !important; font-weight: 600 !important; text-decoration: line-through !important; opacity: 0.85 !important; }
.glass-btn { background: rgba(255,255,255,0.05) !important; color: #d1d5db !important; border: 1px solid rgba(255,255,255,0.1) !important; border-radius: 8px !important; padding: 8px 14px !important; font-size: 0.8rem !important; font-weight: 500 !important; cursor: pointer !important; text-decoration: none !important; display: inline-flex !important; align-items: center !important; gap: 6px !important; }
.glass-btn.active { background: rgba(255,255,255,0.15) !important; color: #ffffff !important; border-color: #3b82f6 !important; font-weight: 600 !important; }
.glass-btn.primary { background: linear-gradient(90deg,#3b82f6,#06b6d4) !important; border: none !important; color: #ffffff !important; font-weight: 600 !important; }
.persona-container { display: flex !important; gap: 6px !important; background: rgba(0,0,0,0.3) !important; padding: 4px !important; border-radius: 10px !important; }
.glass-actions-row { display: flex !important; justify-content: flex-end !important; gap: 12px !important; margin-top: 1.25rem !important; }
.glass-risk-pill { display: inline-flex !important; align-items: center !important; gap: 6px !important; font-size: 0.75rem !important; font-weight: 600 !important; padding: 4px 10px !important; border-radius: 12px !important; border: 1px solid rgba(255,255,255,0.1) !important; }
.glass-risk-pill.critical { background: rgba(239,68,68,0.18) !important; color: #f87171 !important; border-color: rgba(239,68,68,0.35) !important; }
.glass-risk-pill.high { background: rgba(245,158,11,0.18) !important; color: #fbbf24 !important; border-color: rgba(245,158,11,0.35) !important; }
.glass-risk-pill.low { background: rgba(16,185,129,0.18) !important; color: #34d399 !important; border-color: rgba(16,185,129,0.35) !important; }
.ai-badge { background: linear-gradient(90deg,#3b82f6,#8b5cf6); color:#fff; padding:3px 10px; border-radius:12px; font-size:0.72rem; font-weight:700; }
</style>""")

# ── Sidebar ───────────────────────────────────────────────────────────────────
current_page = st.session_state['current_page']

sidebar_html = f"""
<div class="sidebar-container">
    <div class="sidebar-header">
        <div style="display:flex;align-items:center;gap:10px;">
            <div class="logo-box">L</div>
            <span class="brand-name">LegalInspect</span>
        </div>
        <div style="color:#4b5563;font-size:1rem;">⟨</div>
    </div>
    <div class="sidebar-section-title">MAIN</div>
    <a href="{get_nav_link('Dashboard')}" target="_self" class="sidebar-nav-item {'active' if current_page == 'Dashboard' else ''}"><span>🏠</span> Dashboard</a>
    <a href="{get_nav_link('Cases')}" target="_self" class="sidebar-nav-item {'active' if current_page == 'Cases' else ''}"><span>📁</span> Cases</a>
    <a href="{get_nav_link('LegalSearch')}" target="_self" class="sidebar-nav-item {'active' if current_page == 'LegalSearch' else ''}"><span>🔍</span> Legal Search</a>
    <a href="{get_nav_link('SmartReview')}" target="_self" class="sidebar-nav-item {'active' if current_page == 'SmartReview' else ''}"><span>📄</span> Smart Review</a>
    <div class="sidebar-section-title">ANALYTICS</div>
    <a href="{get_nav_link('ComplianceView')}" target="_self" class="sidebar-nav-item {'active' if current_page == 'ComplianceView' else ''}"><span>📈</span> Compliance View</a>
    <a href="{get_nav_link('LegalForms')}" target="_self" class="sidebar-nav-item {'active' if current_page == 'LegalForms' else ''}"><span>📋</span> Legal Forms</a>
</div>
"""

with st.sidebar:
    render_html(sidebar_html)
    st.markdown("<div style='border-top:1px solid rgba(255,255,255,0.08);margin:1.25rem 0.5rem;'></div>", unsafe_allow_html=True)
    st.markdown("<div class='sidebar-section-title'>Document Upload</div>", unsafe_allow_html=True)

    uploaded_file = st.file_uploader("Upload Contract (PDF)", type=["pdf"], label_visibility="collapsed")

    if uploaded_file is not None and not st.session_state['file_uploaded']:
        st.session_state['file_uploaded'] = True
        st.session_state['demo_mode'] = False
        st.session_state['filename'] = uploaded_file.name
        with st.spinner("🤖 AI agents analysing contract via backend..."):
            ai_result = call_backend_analyse(uploaded_file)
        if ai_result:
            st.session_state['ai_data'] = ai_result
            st.session_state['analysis_complete'] = True
            st.query_params.update({"page": "Dashboard", "analyzed": "true", "filename": uploaded_file.name})
            st.rerun()
        else:
            st.session_state['file_uploaded'] = False

    if not st.session_state['analysis_complete']:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🎯 Load Demo Analysis", use_container_width=True, type="primary"):
            st.session_state['demo_mode'] = True
            st.session_state['filename'] = "NDA_v3.2_Draft.pdf"
            with st.spinner("🤖 Loading demo analysis..."):
                demo_result = get_demo_data()
            st.session_state['ai_data'] = demo_result
            st.session_state['analysis_complete'] = True
            st.query_params.update({"page": "Dashboard", "demo": "true", "filename": "NDA_v3.2_Draft.pdf"})
            st.rerun()

    if st.session_state['analysis_complete']:
        label = "✅ Demo Loaded" if st.session_state['demo_mode'] else "✅ Analysis Complete"
        st.success(label)
        st.caption(f"📄 {st.session_state['filename']}")
        st.divider()
        if st.button("🔄 Reset / Clear Document", use_container_width=True):
            st.query_params.clear()
            for k in ['file_uploaded', 'analysis_complete', 'filename', 'demo_mode', 'ai_data']:
                st.session_state[k] = False if k != 'filename' and k != 'ai_data' else ('' if k == 'filename' else None)
            st.rerun()

    st.markdown("<div style='margin-top:2rem;font-size:0.72rem;color:#94a3b8;text-align:center;'>Powered by Claude AI · v3.0</div>", unsafe_allow_html=True)

# ── Main content ──────────────────────────────────────────────────────────────
if not st.session_state['analysis_complete']:
    render_html("""
    <div style='display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:80vh;text-align:center;'>
        <div style='font-size:3rem;margin-bottom:1rem;'>⚖️</div>
        <h1 style='font-size:2.2rem;font-weight:800;color:#111827;margin-bottom:0.5rem;'>Drop your contract.<br>We'll decode the risk.</h1>
        <p style='color:#6b7280;font-size:1.05rem;max-width:550px;line-height:1.6;margin-bottom:1.5rem;'>
            Upload any legal contract PDF in the sidebar — or click <strong>Load Demo Analysis</strong> to instantly explore AI-driven legal insights powered by Claude.
        </p>
        <div style='background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:10px 20px;font-size:0.85rem;color:#1d4ed8;'>
            🔗 Backend: <strong>http://localhost:8000</strong> — make sure the FastAPI server is running.
        </div>
    </div>
    """)
else:
    # Pull AI data from session state
    data = st.session_state.get('ai_data') or {}
    fn = data.get('filename', st.session_state.get('filename', 'Contract.pdf'))
    demo_mode = st.session_state.get('demo_mode', False)

    # ── Dashboard ─────────────────────────────────────────────────────────
    if current_page == "Dashboard":
        pages = data.get('pages_analyzed', 0)
        pages_t = data.get('pages_trend', '+0')
        prec = data.get('relevant_precedents', 0)
        prec_t = data.get('precedents_trend', '+0')
        risks = data.get('identified_risks', 0)
        risks_t = data.get('risks_trend', '+0')
        conf = data.get('ai_confidence', '0%')
        conf_t = data.get('confidence_trend', '+0%')
        risk_z = data.get('risk_zone', 'Unknown')
        an_date = data.get('analyzed_date', '')
        ed_author = data.get('last_edited', 'Unknown')
        score = data.get('score', 0)
        verdict = data.get('verdict', 'Unknown')
        summary = data.get('summary', '')

        # Score colour
        score_color = "#059669" if score < 40 else ("#d97706" if score < 70 else "#dc2626")

        dashboard_html = f"""
        <div class="dashboard-container">
            <div class="header-container">
                <h1 class="header-title">AI Analysis Overview</h1>
                <div style="display:flex;align-items:center;gap:12px;">
                    <span class="ai-badge">🤖 Claude AI</span>
                    <span style="font-size:0.85rem;color:#6b7280;">Real-time analysis</span>
                </div>
            </div>
            <div class="dashboard-grid">
                <div class="col-left">
                    <div class="card">
                        <div class="card-header"><h2 class="card-title">Document Status</h2><span class="card-actions">•••</span></div>
                        <div class="pdf-row">
                            <span class="pdf-icon">📄</span>
                            <div class="pdf-info"><div class="pdf-name">{fn}</div><div class="pdf-meta">PDF · AI Analysed</div></div>
                        </div>
                        <div class="meta-list">
                            <div class="meta-item"><span class="meta-label">Analysed:</span><span class="meta-value">{an_date}</span></div>
                            <div class="meta-item"><span class="meta-label">Last Edited:</span><span class="meta-value">{ed_author}</span></div>
                            <div class="meta-item"><span class="meta-label">Overall Risk Score:</span><span class="meta-value" style="color:{score_color};font-size:1.1rem;font-weight:700;">{score}/100</span></div>
                            <div class="meta-item"><span class="meta-label">Verdict:</span><span class="meta-value">{verdict}</span></div>
                        </div>
                        <div class="progress-section">
                            <div class="progress-header"><span class="progress-label">AI Review Progress</span><span class="progress-value">100% complete</span></div>
                            <div class="progress-bar-container"><div class="progress-bar-fill" style="width:100%;"></div></div>
                            <span class="stage-tag">Stage: Complete ✓</span>
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-header"><h2 class="card-title">AI Summary</h2><span class="card-actions">•••</span></div>
                        <div class="meta-list">
                            <div class="meta-item"><span class="meta-label">Risk Zone:</span><span class="risk-badge">⚠️ {risk_z}</span></div>
                        </div>
                        <div class="recommendation-box">
                            <div class="rec-title">💡 Executive Summary</div>
                            <div class="rec-content">{summary}</div>
                        </div>
                        <a href="{get_nav_link('SmartReview')}&tab=AutoFixer" target="_self" class="suggested-rewrite-btn">See AI Suggested Rewrites</a>
                    </div>
                </div>
                <div class="col-right">
                    <div class="kpi-row">
                        <div class="kpi-card"><span class="kpi-label">Pages Analysed</span><div class="kpi-value-container"><span class="kpi-val">{pages}</span><span class="kpi-trend trend-green">{pages_t}</span></div></div>
                        <div class="kpi-card"><span class="kpi-label">Relevant Precedents</span><div class="kpi-value-container"><span class="kpi-val">{prec}</span><span class="kpi-trend trend-red">{prec_t}</span></div></div>
                        <div class="kpi-card"><span class="kpi-label">Identified Risks</span><div class="kpi-value-container"><span class="kpi-val">{risks}</span><span class="kpi-trend trend-red">{risks_t}</span></div></div>
                        <div class="kpi-card"><span class="kpi-label">AI Confidence</span><div class="kpi-value-container"><span class="kpi-val">{conf}</span><span class="kpi-trend trend-green">{conf_t}</span></div></div>
                    </div>
                    <div class="card table-card">
                        <div class="card-header"><h2 class="card-title">Relevant Cases</h2><span class="card-actions">•••</span></div>
                        <table class="cases-table"><thead><tr><th>Case Name</th><th>Jurisdiction</th><th>Year</th><th>Relevance</th><th>Clause Match</th><th>Outcome</th></tr></thead>
                        <tbody>
                            <tr><td>Nova Systems Corp</td><td>🇬🇧 UK</td><td>2025</td><td>93%</td><td>Clause 5.1</td><td><span class="outcome-pill win">Win</span></td></tr>
                            <tr><td>Confidentiality Clause Dispute</td><td>🇪🇺 EU</td><td>2022</td><td>89%</td><td>Clause 5.2</td><td><span class="outcome-pill settled">Settled</span></td></tr>
                            <tr><td>TechSoft vs. Orion Ltd</td><td>🇬🇧 UK</td><td>2024</td><td>94%</td><td>Clause 2.3</td><td><span class="outcome-pill win">Win</span></td></tr>
                        </tbody></table>
                    </div>
                </div>
            </div>
        </div>
        """
        render_html(dashboard_html)
        st.markdown("<br>", unsafe_allow_html=True)

        # Red flags from AI
        red_flags = data.get('red_flags', [])
        if red_flags:
            st.markdown('<h2 style="font-size:1.15rem;font-weight:600;color:#111827;margin-bottom:1rem;">🚨 AI-Detected Red Flag Analysis</h2>', unsafe_allow_html=True)
            sev_map = {10: ("Critical Risk", "#dc2626"), 9: ("Critical Risk", "#dc2626"), 8: ("High Risk", "#d97706"), 7: ("High Risk", "#d97706"), 6: ("Medium Risk", "#ca8a04")}
            for flag in red_flags:
                sev = flag.get('severity', 5)
                sev_label, sev_color = sev_map.get(sev, ("Medium Risk", "#ca8a04"))
                with st.expander(f"{flag.get('category', 'Risk')}  ·  Severity {sev}/10"):
                    st.markdown(f"<span style='background:{sev_color};color:#fff;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:700;'>{sev_label}</span>", unsafe_allow_html=True)
                    st.markdown("**Clause Content**")
                    st.error(flag.get('clause_text', ''))
                    st.markdown(f"**⚡ Risk Impact:** {flag.get('impact', '')}")
                    st.caption(f"📍 Citation: {flag.get('citation', '')}")
        else:
            st.info("No red flags detected in this contract.")

    # ── Smart Review ──────────────────────────────────────────────────────────
    elif current_page == "SmartReview":
        active_tab = qp.get("tab", "BotDebate")
        tab_links_html = f"""
        <div class="custom-tabs">
            <a href="{get_nav_link('SmartReview')}&tab=BotDebate" target="_self" class="custom-tab {'active' if active_tab == 'BotDebate' else ''}">🤖 Bot Debate</a>
            <a href="{get_nav_link('SmartReview')}&tab=LogicValidator" target="_self" class="custom-tab {'active' if active_tab == 'LogicValidator' else ''}">🔀 Logic Validator</a>
            <a href="{get_nav_link('SmartReview')}&tab=AutoFixer" target="_self" class="custom-tab {'active' if active_tab == 'AutoFixer' else ''}">✨ Auto-Fixer</a>
        </div>
        """
        st.markdown("<h1 style='font-size:1.4rem;font-weight:700;color:#111827;margin-bottom:1rem;'>AI Smart Review Tools</h1>", unsafe_allow_html=True)
        render_html(tab_links_html)

        if active_tab == "BotDebate":
            render_html("""<div style='margin-bottom:1.5rem;'>
                <h2 style='font-size:1.15rem;font-weight:700;color:#0f172a;margin:0 0 4px 0;'>Adversarial AI Agent Debate</h2>
                <p style='color:#64748b;font-size:0.85rem;margin:0;'>The <span style='color:#dc2626;font-weight:600;'>Exploiter</span> probes for vulnerabilities. The <span style='color:#16a34a;font-weight:600;'>Defender</span> evaluates enforceability.</p>
            </div>""")
            loophole_logs = data.get('loophole_logs', [])
            if loophole_logs:
                for i, log_entry in enumerate(loophole_logs):
                    turn = i // 2 + 1
                    role = log_entry.get('role', 'Exploiter')
                    content = log_entry.get('content', '')
                    if role == "Exploiter":
                        with st.chat_message("Exploiter", avatar="😈"):
                            st.markdown(f"**Exploiter Agent** &nbsp;<span style='font-size:0.75rem;color:#991b1b;background:#fef2f2;padding:2px 8px;border-radius:12px;border:1px solid #fca5a5;'>Turn {turn}</span>", unsafe_allow_html=True)
                            st.write(content)
                    else:
                        with st.chat_message("Defender", avatar="🛡️"):
                            st.markdown(f"**Defender Agent** &nbsp;<span style='font-size:0.75rem;color:#166534;background:#f0fdf4;padding:2px 8px;border-radius:12px;border:1px solid #86efac;'>Turn {turn}</span>", unsafe_allow_html=True)
                            st.write(content)
            else:
                st.info("No debate logs available for this contract.")

        elif active_tab == "LogicValidator":
            render_html("""<div style='margin-bottom:1.5rem;'>
                <h2 style='font-size:1.15rem;font-weight:700;color:#0f172a;margin:0 0 4px 0;'>Logical Contradiction Map</h2>
                <p style='color:#64748b;font-size:0.85rem;margin:0;'>Clauses that directly conflict — complying with one may legally violate the other.</p>
            </div>""")
            logic_conflicts = data.get('logic_conflicts', [])
            sev_styles = {
                "Critical": ("#fef2f2", "#ef4444", "#fca5a5"),
                "High": ("#fffbeb", "#fbbf24", "#fcd34d"),
                "Medium": ("#f0fdf4", "#22c55e", "#86efac"),
            }
            if logic_conflicts:
                for conflict in logic_conflicts:
                    bg, fg, border = sev_styles.get(conflict.get('severity', 'Medium'), sev_styles["Medium"])
                    render_html(f"""
                    <div style="background:#ffffff;border:1px solid #f0f1f3;border-radius:12px;padding:1.5rem;margin-bottom:1.25rem;box-shadow:0 1px 3px rgba(0,0,0,0.02);">
                        <div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;'>
                            <div style="font-size:1.05rem;font-weight:600;color:#111827;">⚡ {conflict.get('conflict','')}</div>
                            <span style='display:inline-block;padding:3px 10px;border-radius:12px;font-size:0.75rem;font-weight:700;background:{bg};color:{fg};border:1px solid {border};'>{conflict.get('severity','')}</span>
                        </div>
                        <div style="border:1px solid #f3f4f6;border-radius:8px;padding:12px;font-size:0.85rem;line-height:1.5;margin-bottom:10px;background:#fcfcfc;"><strong>📋 Rule A:</strong> {conflict.get('rule_a','')}</div>
                        <div style="border:1px solid #f3f4f6;border-radius:8px;padding:12px;font-size:0.85rem;line-height:1.5;margin-bottom:10px;background:#fcfcfc;"><strong>📋 Rule B:</strong> {conflict.get('rule_b','')}</div>
                        <div style="font-size:0.85rem;color:#4b5563;line-height:1.5;background:#eff6ff;border-radius:8px;padding:12px;border-left:3px solid #3b82f6;">💡 <strong>Analysis:</strong> {conflict.get('explanation','')}</div>
                    </div>""")
            else:
                st.success("✅ No logical contradictions detected in this contract.")

        elif active_tab == "AutoFixer":
            active_clause_key = qp.get("clause", "Termination Rights")
            active_persona_key = qp.get("persona", "Defender")
            if active_clause_key not in playbook_data:
                active_clause_key = "Termination Rights"
            if active_persona_key not in ["Defender", "Exploiter", "Arbitrator"]:
                active_persona_key = "Defender"

            clause_payload = playbook_data[active_clause_key]
            original_text = clause_payload["original"]
            active_severity = clause_payload["severity"]
            persona_payload = clause_payload[active_persona_key]
            suggested_text = persona_payload["rewrite"]
            risk_label = persona_payload["risk_label"]
            risk_class = persona_payload["risk_class"]
            score_label = persona_payload["score"]
            rationale_text = persona_payload["rationale"]
            word_diff_html = get_word_diff(original_text, suggested_text)

            # Show AI-generated auto-fixes from backend too
            auto_fixes = data.get('auto_fixes', [])
            if auto_fixes:
                st.markdown("### 🤖 AI-Generated Fixes for Your Contract")
                for fix in auto_fixes:
                    with st.expander(f"🔧 {fix.get('issue', 'Fix')} — {fix.get('risk_level', '')} Risk"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Original Clause**")
                            st.error(fix.get('original', ''))
                        with col2:
                            st.markdown("**Suggested Rewrite**")
                            st.success(fix.get('suggested', ''))
                        st.info(f"💡 **Rationale:** {fix.get('rationale', '')}")
                st.divider()

            render_html(f"""
            <div class="glass-panel">
                <div class="glass-title">🔮 AI Negotiation Playbook Sandbox</div>
                <div class="glass-subtitle">Configure AI negotiation profiles, view side-by-side comparison, and export self-healing rewrites with dynamic word-level diff highlights.</div>
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1.25rem;margin-bottom:1.75rem;border-bottom:1px solid rgba(255,255,255,0.08);padding-bottom:1.25rem;">
                    <div style="display:flex;flex-direction:column;gap:6px;">
                        <div style="font-size:0.7rem;font-weight:600;text-transform:uppercase;color:#9ca3af;letter-spacing:0.06em;">Select Vulnerable Clause</div>
                        <div style="display:flex;gap:6px;flex-wrap:wrap;">
                            <a href="{get_playbook_link('Termination Rights', active_persona_key)}" target="_self" class="glass-btn {'active' if active_clause_key == 'Termination Rights' else ''}">📂 Termination asymmetry</a>
                            <a href="{get_playbook_link('Liability Cap', active_persona_key)}" target="_self" class="glass-btn {'active' if active_clause_key == 'Liability Cap' else ''}">📂 Uncapped Liability</a>
                            <a href="{get_playbook_link('IP Assignment', active_persona_key)}" target="_self" class="glass-btn {'active' if active_clause_key == 'IP Assignment' else ''}">📂 Overbroad IP Scope</a>
                        </div>
                    </div>
                    <div style="display:flex;flex-direction:column;gap:6px;">
                        <div style="font-size:0.7rem;font-weight:600;text-transform:uppercase;color:#9ca3af;letter-spacing:0.06em;">AI Negotiation Profile</div>
                        <div class="persona-container">
                            <a href="{get_playbook_link(active_clause_key, 'Defender')}" target="_self" class="glass-btn {'active' if active_persona_key == 'Defender' else ''}">🛡️ Defender</a>
                            <a href="{get_playbook_link(active_clause_key, 'Exploiter')}" target="_self" class="glass-btn {'active' if active_persona_key == 'Exploiter' else ''}">😈 Exploiter</a>
                            <a href="{get_playbook_link(active_clause_key, 'Arbitrator')}" target="_self" class="glass-btn {'active' if active_persona_key == 'Arbitrator' else ''}">⚖️ Arbitrator</a>
                        </div>
                    </div>
                </div>
                <div class="glass-split-screen">
                    <div class="glass-pane">
                        <div class="pane-header"><span class="pane-title">Original Contract Wording</span><span class="glass-risk-pill critical">🚨 Risk Severity: {active_severity}/10</span></div>
                        <div class="pane-content">{original_text}</div>
                    </div>
                    <div class="glass-pane">
                        <div class="pane-header"><span class="pane-title">Suggested Rewrite ({active_persona_key} Profile)</span><span class="glass-risk-pill {risk_class}">{risk_label} ({score_label})</span></div>
                        <div class="pane-content">{word_diff_html}</div>
                    </div>
                </div>
                <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:12px;padding:1.25rem;margin-top:1.5rem;border-left:4px solid #3b82f6;">
                    <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;color:#9ca3af;margin-bottom:6px;">💡 AI Negotiation Strategy & Rationale</div>
                    <div style="font-size:0.875rem;color:#e5e7eb;line-height:1.5;">{rationale_text}</div>
                </div>
                <div class="glass-actions-row">
                    <a href="#" class="glass-btn" onclick="alert('Exported Playbook Clause as PDF successfully!')">📥 Export Clause</a>
                    <a href="#" class="glass-btn primary" onclick="navigator.clipboard.writeText('{suggested_text[:100]}...').then(()=>alert('Copied to clipboard!'))">📋 Copy Rewrite</a>
                </div>
            </div>""")

    # ── Cases ─────────────────────────────────────────────────────────────────
    elif current_page == "Cases":
        render_html(f"""
        <div class="subpage-container">
            <h1 class="subpage-title">📁 Precedents & Cases Database</h1>
            <p style="color:#6b7280;font-size:0.85rem;margin-bottom:1.5rem;margin-top:-1rem;">Browse standard market precedence, past arbitration outcomes, and corporate transaction filings.</p>
            <table class="cases-table" style="margin-top:1rem;">
                <thead><tr><th>Precedent Document / Case Title</th><th>Jurisdiction</th><th>Year</th><th>Relevance Score</th><th>Clause Reference</th><th>Outcome</th></tr></thead>
                <tbody>
                    <tr><td>Nova Systems Corp vs. Standard Retail LLC</td><td>🇬🇧 United Kingdom</td><td>2025</td><td>93% (High)</td><td>Clause 5.1 (Indemnification)</td><td><span class="outcome-pill win">Win / Upheld</span></td></tr>
                    <tr><td>Global TechSoft vs. Orion Logistics Ltd</td><td>🇬🇧 United Kingdom</td><td>2024</td><td>94% (High)</td><td>Clause 2.3 (Exclusivity Cap)</td><td><span class="outcome-pill win">Win / Upheld</span></td></tr>
                    <tr><td>Confidentiality Clause Dispute in FinTech Mergers</td><td>🇪🇺 European Union</td><td>2022</td><td>89% (Medium)</td><td>Clause 5.2 (Data Breach Venue)</td><td><span class="outcome-pill settled">Settled / Arbitrated</span></td></tr>
                    <tr><td>SaaS Vendor Liability Cap Case No. 842</td><td>🇺🇸 Delaware, USA</td><td>2023</td><td>85% (Medium)</td><td>Section 10.4 (Asymmetrical Cap)</td><td><span class="outcome-pill settled">Invalidated Asymmetry</span></td></tr>
                    <tr><td>Telecomm Services IP Assignment Arbitration</td><td>🇺🇸 California, USA</td><td>2021</td><td>78% (Medium)</td><td>Section 6.3 (Work Made For Hire)</td><td><span class="outcome-pill win">Restricted Scope</span></td></tr>
                </tbody>
            </table>
        </div>""")

    # ── Legal Search ──────────────────────────────────────────────────────────
    elif current_page == "LegalSearch":
        st.markdown("<h1 style='font-size:1.4rem;font-weight:700;color:#111827;margin-bottom:0.25rem;'>🔍 AI Precedent Search Engine</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color:#6b7280;font-size:0.85rem;margin-bottom:1.5rem;'>Search multi-jurisdictional precedents, regulatory standards, and case law databases.</p>", unsafe_allow_html=True)
        st.text_input("Enter keywords, clause snippet, or category", value="indemnification fault limit liability", label_visibility="collapsed")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<h3 style='font-size:0.95rem;font-weight:600;color:#4b5563;margin-bottom:0.75rem;'>Search Results (Top 3 AI Matches)</h3>", unsafe_allow_html=True)
        render_html("""
        <div class="search-results-list">
            <div class="search-card"><div class="search-card-header"><span class="search-card-title">Delaware Court of Chancery — Asymmetric Liability Precedent</span><span class="search-card-score">94% Relevance Match</span></div><div class="search-card-content">Under Delaware contract interpretation rules, an extremely asymmetrical limitation of liability clause is scrutinized for unconscionability. While typically upheld in commercial transactions, extreme disparity requires clear waiver evidence.</div><div class="search-card-meta">📁 Precedent ID: DEL-2023-842 &nbsp;•&nbsp; ⚖️ Venue: Delaware Chancery &nbsp;•&nbsp; 📅 Cited: 14 times</div></div>
            <div class="search-card"><div class="search-card-header"><span class="search-card-title">SaaS Master Services Agreement Standard (2024 Market Baseline)</span><span class="search-card-score">88% Relevance Match</span></div><div class="search-card-content">Standard market compromise for liability caps in technology vendor agreements is a mutual cap equal to 12-24 months of fees paid or payable. Asymmetric caps represent a red flag under modern B2B SaaS norms.</div><div class="search-card-meta">📁 Precedent ID: MSA-TECH-2024 &nbsp;•&nbsp; ⚖️ Venue: IEEE Commercial Standards &nbsp;•&nbsp; 📅 Cited: 112 times</div></div>
            <div class="search-card"><div class="search-card-header"><span class="search-card-title">UK Supreme Court — Express Negligence Doctrine ruling</span><span class="search-card-score">82% Relevance Match</span></div><div class="search-card-content">To hold a party indemnified against the consequences of its own negligence, the contract terms must be clear, express, and unequivocal. General words like 'regardless of fault' are interpreted strictly against the drafting party.</div><div class="search-card-meta">📁 Precedent ID: UKSC-2021-42 &nbsp;•&nbsp; ⚖️ Venue: UK Supreme Court &nbsp;•&nbsp; 📅 Cited: 35 times</div></div>
        </div>""")

    # ── Compliance View ───────────────────────────────────────────────────────
    elif current_page == "ComplianceView":
        score = data.get('score', 50)
        gdpr_score = max(0, 100 - score // 2)
        liability_score = score
        sla_score = max(0, 100 - score // 3)
        render_html(f"""
        <div class="subpage-container">
            <h1 class="subpage-title">📈 Corporate Compliance View</h1>
            <p style="color:#6b7280;font-size:0.85rem;margin-bottom:1.5rem;margin-top:-1rem;">AI compliance score across international regulatory frameworks for <strong>{fn}</strong>.</p>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1.25rem;margin-top:1.5rem;">
                <div style="background:#fcfcfc;border:1px solid #e5e7eb;border-radius:10px;padding:1.25rem;text-align:center;">
                    <div style="font-size:0.75rem;color:#6b7280;font-weight:600;text-transform:uppercase;margin-bottom:6px;">GDPR & Privacy Compliance</div>
                    <div style="font-size:2rem;font-weight:700;color:#059669;">{gdpr_score}%</div>
                    <div style="font-size:0.72rem;color:#059669;margin-top:4px;font-weight:500;">🟢 AI Estimated Score</div>
                </div>
                <div style="background:#fcfcfc;border:1px solid #e5e7eb;border-radius:10px;padding:1.25rem;text-align:center;">
                    <div style="font-size:0.75rem;color:#6b7280;font-weight:600;text-transform:uppercase;margin-bottom:6px;">Liability Asymmetry Risk</div>
                    <div style="font-size:2rem;font-weight:700;color:#dc2626;">{liability_score}%</div>
                    <div style="font-size:0.72rem;color:#dc2626;margin-top:4px;font-weight:500;">🔴 Overall Risk Score</div>
                </div>
                <div style="background:#fcfcfc;border:1px solid #e5e7eb;border-radius:10px;padding:1.25rem;text-align:center;">
                    <div style="font-size:0.75rem;color:#6b7280;font-weight:600;text-transform:uppercase;margin-bottom:6px;">Operational SLA Feasibility</div>
                    <div style="font-size:2rem;font-weight:700;color:#d97706;">{sla_score}%</div>
                    <div style="font-size:0.72rem;color:#d97706;margin-top:4px;font-weight:500;">🟡 AI Estimated Score</div>
                </div>
            </div>
            <h3 style="font-size:0.95rem;font-weight:600;color:#111827;margin-top:2rem;margin-bottom:0.75rem;">AI Analysis Summary</h3>
            <p style="font-size:0.85rem;color:#4b5563;line-height:1.6;">{data.get('summary', 'Analysis complete.')}</p>
        </div>""")

    # ── Legal Forms ───────────────────────────────────────────────────────────
    elif current_page == "LegalForms":
        render_html("""
        <div class="subpage-container">
            <h1 class="subpage-title">📋 Premium Legal Forms Template Library</h1>
            <p style="color:#6b7280;font-size:0.85rem;margin-bottom:1.5rem;margin-top:-1rem;">Select, customize, and pre-analyze high-quality corporate agreement forms.</p>
            <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:1.25rem;margin-top:1.5rem;">
                <div style="background:#fcfcfc;border:1px solid #e5e7eb;border-radius:10px;padding:1.25rem;display:flex;flex-direction:column;justify-content:space-between;">
                    <div><div style="font-size:0.95rem;font-weight:600;color:#111827;margin-bottom:4px;">Mutual Non-Disclosure Agreement (NDA)</div><div style="font-size:0.75rem;color:#9ca3af;margin-bottom:8px;">Standard Mutual Protection Agreement · Version 4.1</div><p style="font-size:0.8rem;color:#4b5563;line-height:1.4;">A balanced, industry-standard mutual NDA featuring robust carve-outs for public domain data, clear retention limits, and California governing law.</p></div>
                    <a href="#" style="align-self:flex-start;margin-top:1rem;font-size:0.8rem;color:#3b82f6;font-weight:600;text-decoration:none;">Use Form Template →</a>
                </div>
                <div style="background:#fcfcfc;border:1px solid #e5e7eb;border-radius:10px;padding:1.25rem;display:flex;flex-direction:column;justify-content:space-between;">
                    <div><div style="font-size:0.95rem;font-weight:600;color:#111827;margin-bottom:4px;">Master Services Agreement (MSA) - Vendor Favored</div><div style="font-size:0.75rem;color:#9ca3af;margin-bottom:8px;">Vendor Protection Oriented · Version 2.3</div><p style="font-size:0.8rem;color:#4b5563;line-height:1.4;">Drafted specifically to guard the services vendor against unilateral liability exposure, broad IP transfers, and short-notice terminations.</p></div>
                    <a href="#" style="align-self:flex-start;margin-top:1rem;font-size:0.8rem;color:#3b82f6;font-weight:600;text-decoration:none;">Use Form Template →</a>
                </div>
            </div>
        </div>""")
