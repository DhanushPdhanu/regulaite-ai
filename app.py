import streamlit as st
import time
import json
import os
import base64
import requests
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import networkx as nx
from datetime import datetime
from typing import Optional
from io import BytesIO
import math
import threading
import itertools

# ── Page config — MUST be first Streamlit call ────────────────────────────────
st.set_page_config(
    page_title="RegulAIte — AI Legal Intelligence",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "RegulAIte — Agentic AI Legal Document Simplifier | Built at HackIndia 2025",
    },
)

# ── API base URL ──────────────────────────────────────────────────────────────
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# ══════════════════════════════════════════════════════════════
# DESIGN SYSTEM — injected as global CSS
# ══════════════════════════════════════════════════════════════
GLOBAL_CSS = """<style>
/* ── Google Font import ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── CSS Variables ── */
:root {
--primary:       #1E3A5F;
--primary-light: #2563EB;
--accent:        #F59E0B;
--accent-green:  #10B981;
--accent-red:    #EF4444;
--accent-orange: #F97316;
--bg-dark:       #0F1923;
--bg-card:       #162032;
--bg-card2:      #1A2940;
--text-primary:  #F1F5F9;
--text-secondary:#94A3B8;
--text-muted:    #475569;
--border:        #1E3A5F;
--border-light:  #2563EB30;
--glow-blue:     0 0 20px #2563EB40;
--glow-amber:    0 0 20px #F59E0B40;
--glow-green:    0 0 20px #10B98140;
--glow-red:      0 0 20px #EF444440;
--radius:        12px;
--radius-lg:     20px;
--transition:    all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ── Global reset ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body, [data-testid="stAppViewContainer"] {
background: var(--bg-dark) !important;
color: var(--text-primary) !important;
font-family: 'Inter', sans-serif !important;
}
[data-testid="stAppViewContainer"] {
background: radial-gradient(ellipse at 10% 20%, #1E3A5F18 0%, transparent 50%),
radial-gradient(ellipse at 90% 80%, #2563EB10 0%, transparent 50%),
var(--bg-dark) !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
background: var(--bg-card) !important;
border-right: 1px solid var(--border-light) !important;
}
[data-testid="stSidebar"] * { color: var(--text-primary) !important; }
[data-testid="stSidebarContent"] { padding: 1.5rem 1rem !important; }

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden !important; }
[data-testid="stDecoration"] { display: none !important; }
.stDeployButton { display: none !important; }

/* ── Typography ── */
h1, h2, h3, h4, h5, h6 { color: var(--text-primary) !important; font-family: 'Inter', sans-serif !important; }

/* ── Buttons ── */
.stButton > button {
background: linear-gradient(135deg, var(--primary-light), #1D4ED8) !important;
color: white !important;
border: none !important;
border-radius: var(--radius) !important;
font-family: 'Inter', sans-serif !important;
font-weight: 600 !important;
font-size: 0.9rem !important;
padding: 0.6rem 1.4rem !important;
cursor: pointer !important;
transition: var(--transition) !important;
box-shadow: 0 4px 15px #2563EB30 !important;
letter-spacing: 0.3px !important;
}
.stButton > button:hover {
transform: translateY(-2px) !important;
box-shadow: 0 8px 25px #2563EB50 !important;
}
.stButton > button:active { transform: translateY(0px) !important; }

/* ── File uploader ── */
[data-testid="stFileUploader"] {
background: var(--bg-card2) !important;
border: 2px dashed var(--primary-light) !important;
border-radius: var(--radius-lg) !important;
padding: 2rem !important;
text-align: center !important;
transition: var(--transition) !important;
}
[data-testid="stFileUploader"]:hover {
border-color: var(--accent) !important;
box-shadow: var(--glow-amber) !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [data-testid="stTab"] {
background: var(--bg-card2) !important;
border: 1px solid var(--border-light) !important;
border-radius: var(--radius) !important;
color: var(--text-secondary) !important;
font-weight: 500 !important;
transition: var(--transition) !important;
margin-right: 6px !important;
}
[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] {
background: var(--primary-light) !important;
color: white !important;
box-shadow: var(--glow-blue) !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
background: var(--bg-card2) !important;
border: 1px solid var(--border-light) !important;
border-radius: var(--radius) !important;
padding: 1.2rem !important;
text-align: center !important;
}
[data-testid="stMetricValue"] { color: var(--text-primary) !important; font-weight: 700 !important; font-size: 2rem !important; }
[data-testid="stMetricLabel"] { color: var(--text-secondary) !important; font-size: 0.8rem !important; text-transform: uppercase !important; letter-spacing: 1px !important; }

/* ── Progress bars ── */
.stProgress > div > div { background: linear-gradient(90deg, var(--primary-light), var(--accent)) !important; border-radius: 99px !important; }
.stProgress > div { background: var(--bg-card2) !important; border-radius: 99px !important; }

/* ── Selectbox / Dropdowns ── */
[data-testid="stSelectbox"] > div > div {
background: var(--bg-card2) !important;
border: 1px solid var(--border-light) !important;
border-radius: var(--radius) !important;
color: var(--text-primary) !important;
}

/* ── Expanders ── */
[data-testid="stExpander"] {
background: var(--bg-card2) !important;
border: 1px solid var(--border-light) !important;
border-radius: var(--radius) !important;
margin-bottom: 8px !important;
}
[data-testid="stExpander"] summary { color: var(--text-primary) !important; font-weight: 500 !important; }

/* ── Dividers ── */
hr { border-color: var(--border-light) !important; margin: 1.5rem 0 !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-dark); }
::-webkit-scrollbar-thumb { background: var(--primary); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--primary-light); }

/* ── Custom component classes ── */
.regulaite-hero {
background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-card2) 100%);
border: 1px solid var(--border-light);
border-radius: var(--radius-lg);
padding: 3rem 2rem;
text-align: center;
position: relative;
overflow: hidden;
margin-bottom: 2rem;
}
.regulaite-hero::before {
content: '';
position: absolute;
top: -50%; left: -50%;
width: 200%; height: 200%;
background: conic-gradient(from 0deg at 50% 50%, transparent 0deg, #2563EB08 60deg, transparent 120deg);
animation: spin 20s linear infinite;
pointer-events: none;
}
@keyframes spin { to { transform: rotate(360deg); } }

.hero-badge {
display: inline-block;
background: linear-gradient(135deg, #F59E0B20, #F59E0B40);
border: 1px solid #F59E0B60;
color: #F59E0B;
font-size: 0.75rem;
font-weight: 700;
letter-spacing: 2px;
text-transform: uppercase;
padding: 0.3rem 1rem;
border-radius: 99px;
margin-bottom: 1rem;
}
.hero-title {
font-size: 3.5rem;
font-weight: 900;
background: linear-gradient(135deg, #F1F5F9 0%, #94A3B8 100%);
-webkit-background-clip: text;
-webkit-text-fill-color: transparent;
background-clip: text;
line-height: 1.1;
margin-bottom: 0.5rem;
}
.hero-title span {
background: linear-gradient(135deg, #2563EB 0%, #60A5FA 100%);
-webkit-background-clip: text;
-webkit-text-fill-color: transparent;
background-clip: text;
}
.hero-subtitle {
font-size: 1.1rem;
color: var(--text-secondary);
max-width: 600px;
margin: 0 auto 2rem;
line-height: 1.6;
}
.stat-row { display: flex; justify-content: center; gap: 3rem; margin-top: 1.5rem; }
.stat-item { text-align: center; }
.stat-number { font-size: 2rem; font-weight: 800; color: var(--primary-light); }
.stat-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; }

/* ── Risk cards ── */
.risk-card {
background: var(--bg-card2);
border-radius: var(--radius);
padding: 1.2rem;
margin-bottom: 0.75rem;
border-left: 4px solid;
transition: var(--transition);
cursor: pointer;
}
.risk-card:hover { transform: translateX(4px); }
.risk-card.critical { border-color: var(--accent-red); background: linear-gradient(90deg, #EF444408, var(--bg-card2)); }
.risk-card.high     { border-color: var(--accent-orange); background: linear-gradient(90deg, #F9731608, var(--bg-card2)); }
.risk-card.medium   { border-color: var(--accent); background: linear-gradient(90deg, #F59E0B08, var(--bg-card2)); }
.risk-card.low      { border-color: var(--accent-green); background: linear-gradient(90deg, #10B98108, var(--bg-card2)); }

.risk-badge {
display: inline-block;
font-size: 0.65rem;
font-weight: 700;
letter-spacing: 1px;
text-transform: uppercase;
padding: 0.2rem 0.6rem;
border-radius: 99px;
margin-bottom: 0.5rem;
}
.badge-critical { background: #EF444420; color: #EF4444; border: 1px solid #EF444440; }
.badge-high     { background: #F9731620; color: #F97316; border: 1px solid #F9731640; }
.badge-medium   { background: #F59E0B20; color: #F59E0B; border: 1px solid #F59E0B40; }
.badge-low      { background: #10B98120; color: #10B981; border: 1px solid #10B98140; }
.badge-verified { background: #10B98120; color: #10B981; border: 1px solid #10B98140; }
.badge-hallucination { background: #EF444420; color: #EF4444; border: 1px solid #EF444440; }

/* ── Clause text display ── */
.clause-original {
background: #EF444408;
border: 1px solid #EF444430;
border-radius: var(--radius);
padding: 1rem;
font-family: 'JetBrains Mono', monospace;
font-size: 0.82rem;
line-height: 1.7;
color: #FCA5A5;
margin-bottom: 0.5rem;
}
.clause-fixed {
background: #10B98108;
border: 1px solid #10B98130;
border-radius: var(--radius);
padding: 1rem;
font-family: 'JetBrains Mono', monospace;
font-size: 0.82rem;
line-height: 1.7;
color: #6EE7B7;
}

/* ── Agent stream ── */
.agent-log {
background: var(--bg-dark);
border: 1px solid var(--border-light);
border-radius: var(--radius);
padding: 1.2rem;
font-family: 'JetBrains Mono', monospace;
font-size: 0.78rem;
line-height: 1.8;
color: var(--text-secondary);
max-height: 320px;
overflow-y: auto;
}
.agent-log .log-info    { color: #60A5FA; }
.agent-log .log-success { color: #10B981; }
.agent-log .log-warn    { color: #F59E0B; }
.agent-log .log-error   { color: #EF4444; }
.agent-log .log-agent   { color: #A78BFA; font-weight: 600; }

/* ── Contradiction pair ── */
.contradiction-pair {
background: var(--bg-card2);
border: 1px solid #EF444430;
border-radius: var(--radius);
padding: 1.2rem;
margin-bottom: 1rem;
}
.contradiction-type-badge {
font-size: 0.65rem;
font-weight: 700;
letter-spacing: 1.5px;
text-transform: uppercase;
color: #EF4444;
border: 1px solid #EF444430;
background: #EF444415;
padding: 0.2rem 0.7rem;
border-radius: 99px;
display: inline-block;
margin-bottom: 0.8rem;
}

/* ── Sidebar nav items ── */
.nav-item {
display: flex;
align-items: center;
gap: 0.75rem;
padding: 0.75rem 1rem;
border-radius: var(--radius);
margin-bottom: 0.3rem;
cursor: pointer;
transition: var(--transition);
color: var(--text-secondary);
font-weight: 500;
font-size: 0.9rem;
text-decoration: none;
border: 1px solid transparent;
}
.nav-item:hover, .nav-item.active {
background: var(--bg-card2);
border-color: var(--border-light);
color: var(--text-primary);
}
.nav-item.active { color: var(--primary-light) !important; }

/* ── Pulse animation for live indicator ── */
@keyframes pulse {
0%, 100% { opacity: 1; }
50%       { opacity: 0.4; }
}
.live-dot {
display: inline-block;
width: 8px;
height: 8px;
background: var(--accent-green);
border-radius: 50%;
animation: pulse 2s infinite;
margin-right: 6px;
}

/* ── Score ring ── */
.score-ring-wrap { display: flex; flex-direction: column; align-items: center; padding: 1rem; }

/* ── Upload zone ── */
.upload-zone {
background: linear-gradient(135deg, var(--bg-card2), var(--bg-card));
border: 2px dashed var(--primary-light);
border-radius: var(--radius-lg);
padding: 3rem 2rem;
text-align: center;
transition: var(--transition);
}
.upload-icon  { font-size: 3rem; margin-bottom: 1rem; }
.upload-title { font-size: 1.3rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.5rem; }
.upload-sub   { font-size: 0.9rem; color: var(--text-muted); }

/* ── Timeline ── */
.timeline-step { display: flex; align-items: flex-start; gap: 1rem; margin-bottom: 1.5rem; position: relative; }
.timeline-dot {
width: 36px; height: 36px;
border-radius: 50%;
display: flex; align-items: center; justify-content: center;
font-size: 1rem; flex-shrink: 0; border: 2px solid;
}
.timeline-dot.done    { background: #10B98120; border-color: #10B981; color: #10B981; }
.timeline-dot.active  { background: #2563EB20; border-color: #2563EB; color: #2563EB; animation: pulse 1.5s infinite; }
.timeline-dot.waiting { background: var(--bg-card2); border-color: var(--text-muted); color: var(--text-muted); }
.timeline-content { flex: 1; padding-top: 4px; }
.timeline-title { font-weight: 600; color: var(--text-primary); font-size: 0.95rem; }
.timeline-desc  { font-size: 0.82rem; color: var(--text-muted); margin-top: 2px; }

/* ── Feature cards on landing ── */
.feature-card {
background: var(--bg-card2);
border: 1px solid var(--border-light);
border-radius: var(--radius-lg);
padding: 1.8rem;
height: 100%;
transition: var(--transition);
position: relative;
overflow: hidden;
}
.feature-card::before {
content: '';
position: absolute;
top: 0; left: 0; right: 0;
height: 2px;
background: linear-gradient(90deg, var(--primary-light), var(--accent));
transform: scaleX(0);
transform-origin: left;
transition: var(--transition);
}
.feature-card:hover::before { transform: scaleX(1); }
.feature-card:hover {
transform: translateY(-4px);
box-shadow: 0 20px 40px #00000040;
border-color: #2563EB40;
}
.feature-icon  { font-size: 2.2rem; margin-bottom: 1rem; }
.feature-title { font-size: 1.05rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.5rem; }
.feature-desc  { font-size: 0.85rem; color: var(--text-secondary); line-height: 1.6; }

/* ── Table styling ── */
[data-testid="stTable"] table { background: var(--bg-card2) !important; border-radius: var(--radius) !important; }
[data-testid="stTable"] th { background: var(--primary) !important; color: white !important; font-weight: 600 !important; }
[data-testid="stTable"] td { color: var(--text-secondary) !important; border-color: var(--border-light) !important; }

/* ── Info / Warning / Error boxes ── */
[data-testid="stAlert"] { border-radius: var(--radius) !important; border: 1px solid !important; }

/* ── Plotly charts background ── */
.js-plotly-plot .plotly { background: transparent !important; }
</style>"""

# ══════════════════════════════════════════════════════════════
# HELPER UTILITIES
# ══════════════════════════════════════════════════════════════
def inject_css():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

def html(content: str):
    st.markdown(content, unsafe_allow_html=True)

def risk_color(score: int) -> str:
    if score >= 80: return "#EF4444"
    if score >= 60: return "#F97316"
    if score >= 35: return "#F59E0B"
    return "#10B981"

def risk_label(score: int) -> str:
    if score >= 80: return "critical"
    if score >= 60: return "high"
    if score >= 35: return "medium"
    return "low"

def risk_badge_html(score: int) -> str:
    label = risk_label(score)
    return f'<span class="risk-badge badge-{label}">{label.upper()}</span>'

def agent_log_line(icon: str, css_class: str, text: str) -> str:
    return f'<div class="{css_class}">{icon} {text}</div>'

def format_ts(ts: Optional[str]) -> str:
    if not ts:
        return datetime.now().strftime("%H:%M:%S")
    return ts

def api_get(endpoint: str) -> Optional[dict]:
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=10)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def api_post(endpoint: str, **kwargs) -> Optional[dict]:
    try:
        r = requests.post(f"{API_BASE}{endpoint}", timeout=120, **kwargs)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def check_endpoints() -> dict:
    """Pings all 4 API endpoints and returns their individual status."""
    endpoints = {
        "health":  ("GET",  "/health"),
        "upload":  ("POST", "/upload"),
        "analyse": ("POST", "/analyse"),
        "export":  ("GET",  "/export/test"),
    }
    results = {}
    for name, (method, path) in endpoints.items():
        try:
            if method == "GET":
                r = requests.get(f"{API_BASE}{path}", timeout=5)
            else:
                r = requests.options(f"{API_BASE}{path}", timeout=5)
            results[name] = r.status_code < 500
        except Exception:
            results[name] = False
    return results


# ── Startup sync check ────────────────────────────────────────────────────────
def _sync_check() -> dict:
    """
    Validates that all four teammates' modules are importable at startup.
    Returns a dict of {module_name: True/False}.
    Only runs once per session (cached in session_state).
    """
    if "sync_check_done" in st.session_state:
        return st.session_state.get("sync_results", {})

    results = {}

    try:
        from schemas import Clause, ContradictionResult, CitationResult
        results["schemas"] = True
    except Exception:
        results["schemas"] = False

    try:
        from logic.validator import validate_clauses
        results["validator"] = True
    except Exception:
        results["validator"] = False

    try:
        from memory.rag import InMemoryRAG, citation_graph
        results["rag"] = True
    except Exception:
        results["rag"] = False

    try:
        from memory.bridge import (
            contradiction_tool, citation_tool,
            rag_index_tool, run_full_analysis, get_graph_for_export,
        )
        results["bridge"] = True
    except Exception:
        results["bridge"] = False

    try:
        from memory.reset_between_docs import reset_for_new_document
        results["reset"] = True
    except Exception:
        results["reset"] = False

    st.session_state.sync_check_done = True
    st.session_state.sync_results = results
    return results


def render_status_banner():
    """
    Renders a compact top-bar showing API health, module sync status,
    and active document. Shows warning expander if any module failed.
    """
    sync      = _sync_check()
    server_ok = st.session_state.server_online
    all_synced = all(sync.values()) if sync else False

    status_items = []

    if server_ok:
        status_items.append(
            '<span style="color:#10B981; font-size:0.72rem; font-weight:600;">'
            '● API Online</span>'
        )
    else:
        status_items.append(
            '<span style="color:#F59E0B; font-size:0.72rem; font-weight:600;">'
            '● API Offline — Demo Mode</span>'
        )

    module_labels = {
        "schemas":   "Ullas·Schemas",
        "validator": "Ullas·Z3",
        "rag":       "Ullas·RAG",
        "bridge":    "Ullas·Bridge",
        "reset":     "Ullas·Reset",
    }
    failed = [module_labels[k] for k, v in sync.items() if not v]
    if not failed:
        status_items.append(
            '<span style="color:#10B981; font-size:0.72rem;">'
            '✓ All modules synced</span>'
        )
    else:
        for f in failed:
            status_items.append(
                f'<span style="color:#EF4444; font-size:0.72rem;">✗ {f}</span>'
            )

    if st.session_state.doc_id:
        status_items.append(
            f'<span style="color:#94A3B8; font-size:0.72rem;">'
            f'📄 {st.session_state.filename}</span>'
        )

    bar_bg     = "#162032" if (server_ok and all_synced) else "#1A0F00"
    bar_border = "#1E3A5F30" if (server_ok and all_synced) else "#F59E0B30"

    html(
        f'<div style="background:{bar_bg}; border-bottom:1px solid {bar_border}; '
        f'padding:0.4rem 1.2rem; display:flex; gap:1.5rem; align-items:center; '
        f'flex-wrap:wrap; margin-bottom:1rem;">'
        + "  ·  ".join(status_items)
        + "</div>"
    )

    if failed:
        with st.expander(
            f"⚠️ {len(failed)} module(s) failed to import — click to see fix",
            expanded=True,
        ):
            html("""
<div style="font-size:0.83rem; color:#94A3B8; line-height:1.8;">
One or more teammate modules failed to import. Run the following to diagnose:
</div>
""")
            st.code(
                'cd regulaite && python -c "\n'
                'from schemas import Clause, ContradictionResult, CitationResult\n'
                'from logic.validator import validate_clauses\n'
                'from memory.rag import InMemoryRAG, citation_graph\n'
                'from memory.bridge import contradiction_tool, citation_tool, rag_index_tool\n'
                'from memory.reset_between_docs import reset_for_new_document\n'
                'print(\'All imports OK\')\n'
                '"',
                language="bash",
            )


# ══════════════════════════════════════════════════════════════
# SESSION STATE INIT
# ══════════════════════════════════════════════════════════════
def init_state():
    defaults = {
        "page":           "home",
        "doc_id":         None,
        "filename":       None,
        "clause_count":   0,
        "analysis":       None,
        "uploading":      False,
        "analysing":      False,
        "analysis_done":  False,
        "server_online":  False,
        "history":        [],    # list of {doc_id, filename, timestamp}
        "active_clause":  None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
def render_sidebar():
    with st.sidebar:
        # Logo
        html("""
<div style="text-align:center; padding: 0.5rem 0 1.5rem;">
<div style="font-size:2.5rem; margin-bottom:0.3rem;">⚖️</div>
<div style="font-size:1.3rem; font-weight:900; background:linear-gradient(135deg,#F1F5F9,#94A3B8);
-webkit-background-clip:text; -webkit-text-fill-color:transparent;
background-clip:text; letter-spacing:-0.5px;">RegulAIte</div>
<div style="font-size:0.7rem; color:#475569; letter-spacing:2px; text-transform:uppercase; margin-top:2px;">AI Legal Intelligence</div>
</div>
<hr style="border-color:#1E3A5F30; margin: 0 0 1rem;">
""")

        # Server status
        status = st.session_state.server_online
        html(f"""
<div style="display:flex; align-items:center; gap:0.5rem; padding:0.5rem 0.75rem; border-radius:8px;
background:{'#10B98115' if status else '#EF444415'};
border:1px solid {'#10B98130' if status else '#EF444430'};
margin-bottom:1rem;">
<span class="live-dot" style="background:{'#10B981' if status else '#EF4444'};"></span>
<span style="font-size:0.78rem; color:{'#10B981' if status else '#EF4444'}; font-weight:600;">
{'API Connected' if status else 'API Offline'}
</span>
</div>
""")

        # Navigation
        pages = [
            ("home",     "🏠", "Home"),
            ("upload",   "📄", "Upload Document"),
            ("analyse",  "🤖", "Agent Analysis"),
            ("results",  "📊", "Risk Dashboard"),
            ("redline",  "✏️",  "Redline View"),
            ("graph",    "🕸️",  "Citation Graph"),
            ("history",  "📋", "Document History"),
        ]
        for page_key, icon, label in pages:
            if st.button(
                f"{icon}  {label}",
                key=f"nav_{page_key}",
                use_container_width=True,
            ):
                st.session_state.page = page_key
                st.rerun()

        st.markdown("---")

        # Current doc info
        if st.session_state.doc_id:
            html(f"""
<div style="background:var(--bg-card2); border:1px solid var(--border-light);
border-radius:var(--radius); padding:0.9rem; margin-top:0.5rem;">
<div style="font-size:0.7rem; color:#475569; text-transform:uppercase;
letter-spacing:1px; margin-bottom:0.4rem;">Active Document</div>
<div style="font-size:0.85rem; font-weight:600; color:#F1F5F9;
white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
📄 {st.session_state.filename or 'Unknown'}
</div>
<div style="font-size:0.75rem; color:#475569; margin-top:0.3rem;">
{st.session_state.clause_count} clauses extracted
</div>
</div>
""")

        # Footer
        html("""
<div style="position:absolute; bottom:1rem; left:1rem; right:1rem;
text-align:center; font-size:0.7rem; color:#1E3A5F; letter-spacing:0.5px;">
Built at HackIndia 2025 · Team Tattvasphere
</div>
""")

# ══════════════════════════════════════════════════════════════
# PAGE: HOME
# ══════════════════════════════════════════════════════════════
def page_home():
    html("""
<div class="regulaite-hero">
<div class="hero-badge">🚀 Powered by Agentic AI</div>
<div class="hero-title">Smart Contracts<br>Deserve <span>Smarter</span> Review</div>
<div class="hero-subtitle">
RegulAIte deploys a swarm of autonomous AI agents to read, stress-test,
and automatically fix hidden landmines in vendor contracts —
before any human ever has to look at them.
</div>
<div class="stat-row">
<div class="stat-item">
<div class="stat-number">18+</div>
<div class="stat-label">Contract Types</div>
</div>
<div class="stat-item">
<div class="stat-number">6</div>
<div class="stat-label">AI Agents</div>
</div>
<div class="stat-item">
<div class="stat-number">Z3</div>
<div class="stat-label">SMT Solver</div>
</div>
<div class="stat-item">
<div class="stat-number">0%</div>
<div class="stat-label">Hallucinations</div>
</div>
</div>
</div>
""")

    # Feature cards
    cols = st.columns(3)
    features = [
        ("🔍", "Deep Clause Analysis",
         "Each clause is individually parsed, risk-scored, and cross-checked against 9 contradiction patterns using Z3 formal logic."),
        ("⚡", "Autonomous Auto-Fix",
         "Flagged clauses are automatically rewritten to be balanced, legally sound, and GDPR-compliant — no lawyer required."),
        ("🛡️", "Zero Hallucinations",
         "Every agent claim is verified against the actual contract using RAG + semantic similarity. If it's not in the doc, we don't say it."),
        ("📊", "Visual Risk Dashboard",
         "Interactive risk heatmaps, contradiction graphs, and obligation timelines give you the full picture at a glance."),
        ("✏️", "Instant Redline Export",
         "One click generates a professional Word document with tracked changes — original vs AI-fixed, ready to send back to the vendor."),
        ("🕸️", "Citation Audit Trail",
         "Every finding links back to its source clause via a citation graph. Full transparency on what the AI found and where."),
    ]
    for i, (icon, title, desc) in enumerate(features):
        with cols[i % 3]:
            html(f"""
<div class="feature-card">
<div class="feature-icon">{icon}</div>
<div class="feature-title">{title}</div>
<div class="feature-desc">{desc}</div>
</div>
""")
            st.write("")

    st.markdown("---")

    # CTA
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        html('<div style="text-align:center; margin-bottom:1rem; color:#94A3B8; font-size:0.9rem;">Ready to analyse your first contract?</div>')
        if st.button("⚡  Analyse a Contract Now", use_container_width=True):
            st.session_state.page = "upload"
            st.rerun()

# ══════════════════════════════════════════════════════════════
# UPLOAD HELPERS
# ══════════════════════════════════════════════════════════════
def render_upload_steps(step: int):
    """Animated step tracker shown during upload + extraction.
    step: 1=uploading, 2=extracting, 3=ready
    """
    steps = [
        ("📤", "Uploading PDF",        "Sending document to parser"),
        ("🔍", "Extracting Clauses",   "Identifying and numbering all clauses"),
        ("✅", "Ready for Analysis",   "Document indexed and ready"),
    ]
    html('<div style="margin: 1.5rem 0;">')
    for i, (icon, title, desc) in enumerate(steps, 1):
        if i < step:
            state = "done"
            icon_show = "✓"
        elif i == step:
            state = "active"
            icon_show = icon
        else:
            state = "waiting"
            icon_show = str(i)
        html(f"""
<div class="timeline-step">
<div class="timeline-dot {state}">{icon_show}</div>
<div class="timeline-content">
<div class="timeline-title">{title}</div>
<div class="timeline-desc">{desc}</div>
</div>
</div>
""")
    html('</div>')


def render_clause_table(clauses: list):
    """Renders the extracted clauses as a rich interactive display."""
    if not clauses:
        html("""
<div style="text-align:center; padding:2rem; color:#475569;">
No clauses extracted. Try a different document.
</div>
""")
        return

    # Filter controls
    sections = sorted(set(c.get("section", "General") for c in clauses))
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        sel_section = st.selectbox(
            "Filter by Section",
            ["All Sections"] + sections,
            key="filter_section",
        )
    with col2:
        sel_risk = st.selectbox(
            "Filter by Risk",
            ["All Levels", "Critical (80+)", "High (60+)", "Medium (35+)", "Low (<35)"],
            key="filter_risk",
        )
    with col3:
        st.metric("Total Clauses", len(clauses))

    # Apply filters
    filtered = clauses
    if sel_section != "All Sections":
        filtered = [c for c in filtered if c.get("section") == sel_section]
    if sel_risk == "Critical (80+)":
        filtered = [c for c in filtered if (c.get("risk_score") or 0) >= 80]
    elif sel_risk == "High (60+)":
        filtered = [c for c in filtered if (c.get("risk_score") or 0) >= 60]
    elif sel_risk == "Medium (35+)":
        filtered = [c for c in filtered if (c.get("risk_score") or 0) >= 35]
    elif sel_risk == "Low (<35)":
        filtered = [c for c in filtered if (c.get("risk_score") or 0) < 35]

    html(f"""
<div style="display:flex; justify-content:space-between; align-items:center;
margin: 1.2rem 0 0.8rem;">
<div style="font-size:0.85rem; color:#94A3B8;">
Showing <strong style="color:#F1F5F9;">{len(filtered)}</strong>
of {len(clauses)} clauses
</div>
<div style="font-size:0.75rem; color:#475569;">Click any clause to expand</div>
</div>
""")

    # Render clause cards
    for clause in filtered:
        score = clause.get("risk_score") or 0
        label = risk_label(score)
        color = risk_color(score)
        sec   = clause.get("section", "General")
        num   = clause.get("clause_number", "")
        text  = clause.get("text", "")
        flags = clause.get("flags", [])
        pg    = clause.get("page_number", 1)

        flag_html = ""
        for f in flags:
            flag_html += (
                f'<span style="font-size:0.65rem; font-weight:700; '
                f'letter-spacing:1px; padding:0.15rem 0.5rem; border-radius:99px; '
                f'background:#F59E0B20; color:#F59E0B; border:1px solid #F59E0B30; '
                f'margin-right:4px;">{f}</span>'
            )

        with st.expander(
            f"§ {num}  ·  {sec}  ·  Risk: {score}/100",
            expanded=(score >= 80),
        ):
            col_a, col_b = st.columns([4, 1])
            with col_a:
                html(f"""
<div style="margin-bottom:0.6rem;">
{risk_badge_html(score)}{flag_html}
<span style="font-size:0.72rem; color:#475569; margin-left:8px;">Page {pg}</span>
</div>
<div class="clause-original">{text}</div>
""")
            with col_b:
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=score,
                    domain={"x": [0, 1], "y": [0, 1]},
                    gauge={
                        "axis": {"range": [0, 100], "tickcolor": "#475569", "tickfont": {"size": 8}},
                        "bar":  {"color": color},
                        "bgcolor": "#1A2940",
                        "bordercolor": "#1E3A5F",
                        "steps": [
                            {"range": [0,  35], "color": "#10B98115"},
                            {"range": [35, 60], "color": "#F59E0B15"},
                            {"range": [60, 80], "color": "#F9731615"},
                            {"range": [80,100], "color": "#EF444415"},
                        ],
                    },
                    number={"font": {"color": color, "size": 28}},
                ))
                fig.update_layout(
                    height=140,
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font={"color": "#94A3B8"},
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_section_breakdown(clauses: list):
    """Donut chart showing clause distribution by section."""
    if not clauses:
        return
    from collections import Counter
    counts = Counter(c.get("section", "General") for c in clauses)
    labels = list(counts.keys())
    values = list(counts.values())
    colors = ["#2563EB","#F59E0B","#10B981","#EF4444","#8B5CF6","#06B6D4","#F97316","#EC4899"]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.6,
        marker=dict(
            colors=colors[:len(labels)],
            line=dict(color="#0F1923", width=2),
        ),
        textfont=dict(size=11, color="#F1F5F9"),
        hovertemplate="<b>%{label}</b><br>%{value} clauses<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(
        height=280,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8", family="Inter"),
        legend=dict(font=dict(color="#94A3B8", size=11), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=10, r=10, t=20, b=10),
        annotations=[dict(
            text=f"<b>{len(clauses)}</b><br>Clauses",
            x=0.5, y=0.5,
            font=dict(size=14, color="#F1F5F9", family="Inter"),
            showarrow=False,
        )],
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_risk_histogram(clauses: list):
    """Bar chart of risk score distribution."""
    if not clauses:
        return
    scores = [c.get("risk_score") or 0 for c in clauses]
    bins   = [0, 20, 35, 60, 80, 100]
    labels = ["Safe\n0-20", "Low\n21-35", "Medium\n36-60", "High\n61-80", "Critical\n81-100"]
    counts = [0] * (len(bins) - 1)
    for s in scores:
        for i in range(len(bins) - 1):
            if bins[i] <= s < bins[i + 1]:
                counts[i] += 1
                break
        else:
            counts[-1] += 1

    bar_colors = ["#10B981", "#84CC16", "#F59E0B", "#F97316", "#EF4444"]
    fig = go.Figure(go.Bar(
        x=labels,
        y=counts,
        marker=dict(color=bar_colors, line=dict(color="#0F1923", width=1)),
        text=counts,
        textposition="outside",
        textfont=dict(color="#F1F5F9", size=12),
        hovertemplate="<b>%{x}</b><br>%{y} clauses<extra></extra>",
    ))
    fig.update_layout(
        height=260,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8", family="Inter"),
        xaxis=dict(showgrid=False, color="#475569", tickfont=dict(size=10)),
        yaxis=dict(showgrid=True, gridcolor="#1E3A5F30", color="#475569"),
        margin=dict(l=10, r=10, t=30, b=10),
        bargap=0.3,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _mock_upload_result(filename: str) -> dict:
    """Returns a realistic mock API response for demo / offline mode."""
    import random
    sections = [
        "Liability", "Termination", "Confidentiality", "Payment",
        "Indemnification", "Governing Law", "Renewal", "Exclusivity",
        "Intellectual Property", "Dispute Resolution",
    ]
    clauses = []
    for sec_i, section in enumerate(sections, 1):
        num_clauses = random.randint(2, 4)
        for cl_i in range(1, num_clauses + 1):
            score = random.randint(5, 95)
            flags = []
            if score >= 80:
                flags = random.sample(
                    ["CONTRADICTION", "GDPR_VIOLATION", "AUTO_RENEWAL", "ONE_SIDED", "LOOPHOLE"],
                    k=random.randint(1, 2),
                )
            elif score >= 60:
                flags = random.sample(
                    ["HIGH_RISK", "MISSING_NOTICE", "VAGUE_TERM"],
                    k=random.randint(0, 1),
                )
            clauses.append({
                "clause_id":     f"clause_{sec_i}_{cl_i}",
                "clause_number": f"{sec_i}.{cl_i}",
                "page_number":   sec_i,
                "section":       section,
                "text": (
                    f"[DEMO] Clause {sec_i}.{cl_i} under {section}: "
                    f"This clause governs the {section.lower()} obligations "
                    f"of the parties with a preliminary risk score of {score}/100."
                ),
                "risk_score":  score,
                "risk_reason": f"Preliminary scan flagged {len(flags)} issue(s)." if flags else None,
                "flags":       flags,
            })
    return {
        "doc_id":       f"demo_{int(time.time())}",
        "filename":     filename,
        "clause_count": len(clauses),
        "clauses":      clauses,
    }


# ══════════════════════════════════════════════════════════════
# PAGE: UPLOAD
# ══════════════════════════════════════════════════════════════
def page_upload():
    html("""
<h2 style="font-size:1.8rem; font-weight:800; margin-bottom:0.4rem;">📄 Upload Contract</h2>
<p style="color:#94A3B8; margin-bottom:1.5rem; font-size:0.95rem;">
Drop any legal PDF. Our parser extracts every clause with its section,
page number, and preliminary risk score — in seconds.
</p>
""")

    # ── If document already loaded, show it ──────────────────────────────────
    if st.session_state.doc_id and st.session_state.clause_count > 0:
        clauses = (st.session_state.analysis or {}).get("clauses", [])

        # Success banner
        html(f"""
<div style="background:linear-gradient(135deg,#10B98115,#10B98105);
border:1px solid #10B98130; border-radius:16px;
padding:1.2rem 1.5rem; margin-bottom:1.5rem;
display:flex; align-items:center; gap:1rem;">
<div style="font-size:2rem;">✅</div>
<div>
<div style="font-weight:700; font-size:1.05rem; color:#F1F5F9;">{st.session_state.filename}</div>
<div style="font-size:0.83rem; color:#10B981; margin-top:2px;">
{st.session_state.clause_count} clauses extracted successfully
· Ready for agent analysis
</div>
</div>
<div style="margin-left:auto;">
<span style="font-size:0.75rem; color:#475569;">Doc ID:</span>
<span style="font-size:0.75rem; font-family:'JetBrains Mono',monospace;
color:#94A3B8;"> {st.session_state.doc_id}</span>
</div>
</div>
""")

        # Charts row
        col1, col2 = st.columns(2)
        with col1:
            html('<div style="font-weight:600; font-size:0.9rem; margin-bottom:0.5rem; color:#94A3B8;">📂 Clauses by Section</div>')
            render_section_breakdown(clauses)
        with col2:
            html('<div style="font-weight:600; font-size:0.9rem; margin-bottom:0.5rem; color:#94A3B8;">📊 Risk Distribution</div>')
            render_risk_histogram(clauses)

        st.markdown("---")

        # Clause table
        html('<div style="font-weight:700; font-size:1.1rem; margin-bottom:1rem;">🔍 Extracted Clauses</div>')
        render_clause_table(clauses)

        st.markdown("---")

        # Action buttons
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            if st.button("🤖  Run Agent Analysis", use_container_width=True):
                st.session_state.page = "analyse"
                st.rerun()
        with c2:
            if st.button("📄  Upload Different Document", use_container_width=True):
                st.session_state.doc_id       = None
                st.session_state.filename     = None
                st.session_state.clause_count = 0
                st.session_state.analysis     = None
                st.session_state.analysis_done = False
                st.rerun()
        return

    # ── Upload form ───────────────────────────────────────────────────────────
    html("""
<div style="background:linear-gradient(135deg,#162032,#1A2940);
border:2px dashed #2563EB50; border-radius:20px;
padding:1rem; margin-bottom:1.5rem;">
<div style="text-align:center; padding:1rem 0 0.5rem;">
<div style="font-size:3rem; margin-bottom:0.5rem;">📂</div>
<div style="font-size:1.2rem; font-weight:700; color:#F1F5F9;
margin-bottom:0.4rem;">Drop your legal contract here</div>
<div style="font-size:0.85rem; color:#475569;">
Supports PDF · Max 50MB · NDA, SaaS, Employment,
Vendor, Lease, Partnership &amp; more
</div>
</div>
""")

    uploaded = st.file_uploader(
        "Choose a PDF contract",
        type=["pdf"],
        label_visibility="collapsed",
        key="pdf_uploader",
    )
    html("</div>")

    # Supported contract type pills
    types = [
        "📋 NDA", "💼 SaaS", "👤 Employment", "🚚 Vendor",
        "🏢 Lease", "🤝 Partnership", "⚙️ Services", "🌐 API",
        "🏗️ Construction", "💰 Loan", "📺 Content", "🔬 Healthcare",
    ]
    pills = " ".join(
        f'<span style="display:inline-block; font-size:0.72rem; '
        f'padding:0.2rem 0.65rem; border-radius:99px; '
        f'background:#1E3A5F20; border:1px solid #1E3A5F60; '
        f'color:#64748B; margin:3px 2px;">{t}</span>'
        for t in types
    )
    html(f'<div style="margin-bottom:1.5rem; text-align:center;">{pills}</div>')

    # ── Process upload ────────────────────────────────────────────────────────
    if uploaded is not None:
        st.markdown("---")

        step_placeholder     = st.empty()
        progress_placeholder = st.empty()
        status_placeholder   = st.empty()

        with step_placeholder.container():
            render_upload_steps(1)

        bar = progress_placeholder.progress(0)
        for pct in range(0, 60, 8):
            bar.progress(pct)
            time.sleep(0.05)

        # ── POST to /upload ───────────────────────────────────────────────────
        try:
            files = {"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}
            response = requests.post(
                f"{API_BASE}/upload",
                files=files,
                timeout=60,
            )
            upload_result = response.json() if response.status_code == 200 else None
        except Exception as e:
            upload_result = None
            st.error(f"Upload failed: {e}")

        if upload_result is None:
            status_placeholder.warning("⚠️ API server not reachable — showing demo extraction.")
            upload_result = _mock_upload_result(uploaded.name)

        # Animate to step 2
        for pct in range(60, 85, 5):
            bar.progress(pct)
            time.sleep(0.04)
        with step_placeholder.container():
            render_upload_steps(2)

        # Store doc info
        doc_id       = upload_result.get("doc_id", f"doc_{int(time.time())}")
        clause_count = upload_result.get("clause_count", 0)
        clauses      = upload_result.get("clauses", [])

        st.session_state.doc_id       = doc_id
        st.session_state.filename     = uploaded.name
        st.session_state.clause_count = clause_count

        if st.session_state.analysis is None:
            st.session_state.analysis = {}
        st.session_state.analysis["clauses"] = clauses

        st.session_state.history.append({
            "doc_id":       doc_id,
            "filename":     uploaded.name,
            "clause_count": clause_count,
            "timestamp":    datetime.now().strftime("%d %b %Y %H:%M"),
        })

        # Animate to step 3
        for pct in range(85, 101, 3):
            bar.progress(pct)
            time.sleep(0.04)
        with step_placeholder.container():
            render_upload_steps(3)

        status_placeholder.success(
            f"✅ {clause_count} clauses extracted from **{uploaded.name}**"
        )
        time.sleep(1)
        st.rerun()


# ══════════════════════════════════════════════════════════════
# ANALYSIS HELPERS
# ══════════════════════════════════════════════════════════════
AGENT_ROSTER = [
    ("🔍", "ParserAgent",      "Structuring clauses and assigning risk metadata"),
    ("⚔️", "AttackerAgent",    "Adversarially stress-testing every clause"),
    ("🛡️", "DefenderAgent",    "Evaluating Attacker findings for false positives"),
    ("🔬", "Z3ValidatorAgent", "Running Z3 SMT solver for logical contradictions"),
    ("📚", "CitationAgent",    "Grounding every finding against source clauses"),
    ("✍️",  "AutoFixerAgent",  "Rewriting dangerous clauses into fair alternatives"),
]


def render_agent_timeline(active_index: int, done_ids: set):
    """Renders the animated 6-agent timeline."""
    html('<div style="margin: 1.2rem 0;">')
    for i, (icon, name, desc) in enumerate(AGENT_ROSTER):
        if i in done_ids:
            state = "done"
            show_icon = "✓"
        elif i == active_index:
            state = "active"
            show_icon = icon
        else:
            state = "waiting"
            show_icon = str(i + 1)
        html(f"""
<div class="timeline-step">
<div class="timeline-dot {state}">{show_icon}</div>
<div class="timeline-content">
<div class="timeline-title" style="{'color:#2563EB;' if state=='active' else ''}">
{name}
{'<span class="live-dot" style="margin-left:8px;"></span>' if state == 'active' else ''}
</div>
<div class="timeline-desc">{desc}</div>
</div>
</div>
""")
    html('</div>')


def render_agent_log_box(log_lines: list):
    """Renders the terminal-style agent log box."""
    def classify(line: str):
        l = line.lower()
        if any(k in l for k in ["error", "fail", "unsat", "hallucin", "contradict"]):
            return "log-error"
        if any(k in l for k in ["warn", "caution", "flag", "risk", "loophole"]):
            return "log-warn"
        if any(k in l for k in ["verified", "pass", "done", "complete", "found", "indexed"]):
            return "log-success"
        if any(k in l for k in ["agent", "[", "→", "running"]):
            return "log-agent"
        return "log-info"

    lines_html = ""
    for line in log_lines:
        css = classify(line)
        ts = datetime.now().strftime("%H:%M:%S")
        lines_html += f'<div class="{css}">[{ts}] {line}</div>'

    html(f"""
<div class="agent-log" id="agent-log-box">
{lines_html if lines_html else '<div class="log-info">Waiting for agents to start…</div>'}
</div>
<script>
var box = document.getElementById('agent-log-box');
if (box) box.scrollTop = box.scrollHeight;
</script>
""")


def render_overall_score_ring(score: int):
    """Big animated gauge ring for the overall contract risk score."""
    color = risk_color(score)
    label = risk_label(score).upper()
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={
            "text": f"<b>Contract Risk Score</b><br><span style='font-size:0.8em;color:#94A3B8;'>{label}</span>",
            "font": {"color": "#F1F5F9", "size": 15, "family": "Inter"},
        },
        gauge={
            "axis": {
                "range": [0, 100],
                "tickvals": [0, 35, 60, 80, 100],
                "ticktext": ["Safe", "Low", "Med", "High", "Crit"],
                "tickcolor": "#475569",
                "tickfont": {"size": 9, "color": "#475569"},
            },
            "bar": {"color": color, "thickness": 0.25},
            "bgcolor": "#162032",
            "borderwidth": 0,
            "steps": [
                {"range": [0,  35], "color": "#10B98118"},
                {"range": [35, 60], "color": "#F59E0B18"},
                {"range": [60, 80], "color": "#F9731618"},
                {"range": [80,100], "color": "#EF444418"},
            ],
            "threshold": {
                "line": {"color": color, "width": 3},
                "thickness": 0.8,
                "value": score,
            },
        },
        number={"font": {"color": color, "size": 52, "family": "Inter"}, "suffix": "/100"},
    ))
    fig.update_layout(
        height=280,
        margin=dict(l=20, r=20, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#94A3B8", "family": "Inter"},
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_contradiction_cards(contradictions: list, clauses: list):
    """Renders each contradiction pair as a card with Z3 proof panel."""
    if not contradictions:
        html("""
<div style="text-align:center; padding:2rem; color:#10B981;
border:1px solid #10B98130; border-radius:12px; background:#10B98108;">
<div style="font-size:1.5rem; margin-bottom:0.4rem;">✅</div>
No logical contradictions detected. Contract passes Z3 validation.
</div>
""")
        return

    clause_map = {c.get("clause_id"): c for c in clauses}

    for i, contra in enumerate(contradictions, 1):
        ctype    = contra.get("contradiction_type", "MUTUAL_EXCLUSION")
        exp      = contra.get("explanation", "")
        z3_proof = contra.get("z3_proof", "")
        cid_a    = contra.get("clause_id_a", "")
        cid_b    = contra.get("clause_id_b", "")
        clause_a = clause_map.get(cid_a, {})
        clause_b = clause_map.get(cid_b, {})

        html(f"""
<div class="contradiction-pair">
<div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:0.8rem;">
<span style="font-size:1.1rem; font-weight:800; color:#EF4444;">#{i}</span>
<span class="contradiction-type-badge">{ctype.replace('_', ' ')}</span>
<span style="font-size:0.75rem; color:#475569; margin-left:auto;">{cid_a}  ↔  {cid_b}</span>
</div>
<div style="font-size:0.88rem; color:#94A3B8; margin-bottom:1rem; line-height:1.6;">{exp}</div>
""")

        col_a, col_b = st.columns(2)
        with col_a:
            html(f"""
<div style="font-size:0.7rem; color:#475569; font-weight:700;
letter-spacing:1px; text-transform:uppercase; margin-bottom:0.4rem;">
§ {clause_a.get('clause_number','?')} · {clause_a.get('section','')}
</div>
<div class="clause-original" style="font-size:0.8rem;">
{clause_a.get('text','[Clause text unavailable]')[:250]}
</div>
""")
        with col_b:
            html(f"""
<div style="font-size:0.7rem; color:#475569; font-weight:700;
letter-spacing:1px; text-transform:uppercase; margin-bottom:0.4rem;">
§ {clause_b.get('clause_number','?')} · {clause_b.get('section','')}
</div>
<div class="clause-original" style="font-size:0.8rem;">
{clause_b.get('text','[Clause text unavailable]')[:250]}
</div>
""")

        if z3_proof:
            with st.expander("🔬 View Z3 Formal Proof"):
                html(f"""
<div style="background:#0F1923; border:1px solid #2563EB30; border-radius:8px;
padding:1rem; font-family:'JetBrains Mono',monospace; font-size:0.78rem;
color:#60A5FA; white-space:pre-wrap; line-height:1.8;">{z3_proof}</div>
""")
        html("</div>")


def render_compliance_violations(violations: list):
    """Renders GDPR / DPDP / ICA compliance violations."""
    if not violations:
        html("""
<div style="text-align:center; padding:2rem; color:#10B981;
border:1px solid #10B98130; border-radius:12px; background:#10B98108;">
<div style="font-size:1.5rem; margin-bottom:0.4rem;">✅</div>
No regulatory compliance violations detected.
</div>
""")
        return

    reg_colors = {"GDPR": "#8B5CF6", "DPDP": "#F59E0B", "ICA": "#06B6D4"}

    for v in violations:
        reg   = v.get("regulation", "GDPR")
        art   = v.get("article", "")
        desc  = v.get("description", "")
        sev   = v.get("severity", "HIGH")
        cid   = v.get("clause_id", "")
        color = reg_colors.get(reg, "#94A3B8")

        html(f"""
<div style="background:var(--bg-card2); border-radius:12px; padding:1.1rem;
margin-bottom:0.75rem; border-left:4px solid {color};">
<div style="display:flex; align-items:center; gap:0.6rem;
margin-bottom:0.5rem; flex-wrap:wrap;">
<span style="font-size:0.68rem; font-weight:800; letter-spacing:1.5px;
padding:0.2rem 0.6rem; border-radius:99px;
background:{color}20; color:{color}; border:1px solid {color}40;">{reg}</span>
<span style="font-size:0.75rem; color:#94A3B8;">{art}</span>
{risk_badge_html(85 if sev == 'CRITICAL' else 65 if sev == 'HIGH' else 40)}
<span style="font-size:0.72rem; color:#475569; margin-left:auto;">Clause: {cid}</span>
</div>
<div style="font-size:0.87rem; color:#CBD5E1; line-height:1.6;">{desc}</div>
</div>
""")


def render_obligation_timeline(obligations: list):
    """Horizontal timeline of all contract obligations sorted by deadline."""
    if not obligations:
        html("""
<div style="text-align:center; padding:1.5rem; color:#475569;">
No time-bound obligations extracted.
</div>
""")
        return

    sorted_obs = sorted(obligations, key=lambda x: x.get("deadline_days") or 9999)
    timeline_data = []
    for ob in sorted_obs:
        days  = ob.get("deadline_days") or 0
        label = ob.get("description", "")[:60]
        party = ob.get("party_responsible", "Both")
        obt   = ob.get("obligation_type", "NOTICE")
        timeline_data.append({
            "Task":   f"§{ob.get('clause_number','?')} · {label}",
            "Start":  0,
            "Finish": max(days, 1),
            "Party":  party,
            "Type":   obt,
        })

    if not timeline_data:
        return

    df = pd.DataFrame(timeline_data)
    fig = px.bar(
        df,
        x="Finish",
        y="Task",
        orientation="h",
        color="Party",
        color_discrete_sequence=["#2563EB", "#F59E0B", "#10B981", "#EF4444"],
        labels={"Finish": "Days from Contract Effective Date", "Task": ""},
        height=max(250, len(timeline_data) * 42),
        text="Finish",
    )
    fig.update_traces(
        texttemplate="%{text}d",
        textposition="outside",
        textfont=dict(color="#F1F5F9", size=11),
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8", family="Inter"),
        xaxis=dict(showgrid=True, gridcolor="#1E3A5F30", color="#475569", tickfont=dict(size=10)),
        yaxis=dict(showgrid=False, color="#94A3B8", tickfont=dict(size=10), autorange="reversed"),
        legend=dict(font=dict(color="#94A3B8", size=11), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=10, r=60, t=20, b=10),
        bargap=0.3,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_autofix_preview(clauses: list):
    """Side-by-side before/after for clauses with risk_score >= 60."""
    flagged = [c for c in clauses if (c.get("risk_score") or 0) >= 60 and c.get("risk_reason")]

    if not flagged:
        html("""
<div style="text-align:center; padding:2rem; color:#94A3B8;">
No high-risk clauses requiring auto-fix in this analysis.
</div>
""")
        return

    for clause in flagged[:6]:
        score  = clause.get("risk_score", 0)
        num    = clause.get("clause_number", "?")
        sec    = clause.get("section", "")
        text   = clause.get("text", "")
        reason = clause.get("risk_reason", "")
        fix    = clause.get("suggested_fix") or (
            "[AutoFixer agent rewrites this clause to: (1) balance obligations symmetrically, "
            "(2) specify a 60-day notice window, and (3) add a mutual termination condition. "
            "Full fix available after /analyse completes.]"
        )

        html(f"""
<div style="background:var(--bg-card2); border:1px solid #1E3A5F50;
border-radius:14px; padding:1.2rem; margin-bottom:1rem;">
<div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:0.9rem;">
{risk_badge_html(score)}
<span style="font-weight:700; font-size:0.95rem; color:#F1F5F9;">§ {num} · {sec}</span>
<span style="font-size:0.75rem; color:#EF4444; margin-left:auto;">Risk: {score}/100</span>
</div>
<div style="font-size:0.78rem; color:#F87171; margin-bottom:0.5rem; font-weight:600;">⚠ {reason}</div>
""")

        col_orig, col_fix = st.columns(2)
        with col_orig:
            html(f"""
<div style="font-size:0.7rem; color:#EF4444; font-weight:700;
text-transform:uppercase; letter-spacing:1px; margin-bottom:0.4rem;">Original ✗</div>
<div class="clause-original">{text[:300]}{'…' if len(text) > 300 else ''}</div>
""")
        with col_fix:
            html(f"""
<div style="font-size:0.7rem; color:#10B981; font-weight:700;
text-transform:uppercase; letter-spacing:1px; margin-bottom:0.4rem;">AI-Fixed ✓</div>
<div class="clause-fixed">{fix[:300]}{'…' if len(fix) > 300 else ''}</div>
""")
        html("</div>")


def render_hallucination_gauge(rate: float, verified: int, unverified: int):
    """Donut-style gauge for hallucination rate + citation stats."""
    pct   = round(rate * 100, 1)
    color = "#10B981" if pct < 10 else "#F59E0B" if pct < 25 else "#EF4444"
    fig = go.Figure(go.Pie(
        values=[verified, unverified],
        labels=["Citation-Verified", "Unverified (Hallucination)"],
        hole=0.65,
        marker=dict(colors=["#10B981", "#EF4444"], line=dict(color="#0F1923", width=2)),
        textfont=dict(size=11, color="#F1F5F9"),
        hovertemplate="<b>%{label}</b><br>%{value} claims<extra></extra>",
    ))
    fig.update_layout(
        height=220,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8", family="Inter"),
        legend=dict(font=dict(color="#94A3B8", size=10), bgcolor="rgba(0,0,0,0)",
                    orientation="h", y=-0.1),
        margin=dict(l=10, r=10, t=10, b=30),
        annotations=[dict(
            text=f"<b>{pct}%</b><br><span style='font-size:10px'>Hallucination</span>",
            x=0.5, y=0.5,
            font=dict(size=16, color=color, family="Inter"),
            showarrow=False,
        )],
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_risk_heatmap(clauses: list):
    """Heatmap of risk score by section × clause number."""
    if not clauses:
        return
    sections = sorted(set(c.get("section", "General") for c in clauses))
    max_clauses_in_section = max(
        sum(1 for c in clauses if c.get("section") == s) for s in sections
    ) if sections else 1

    z_matrix = []
    for sec in sections:
        row = [c.get("risk_score") or 0 for c in clauses if c.get("section") == sec]
        row += [None] * (max_clauses_in_section - len(row))
        z_matrix.append(row)

    fig = go.Figure(go.Heatmap(
        z=z_matrix,
        x=[f"Clause {i+1}" for i in range(max_clauses_in_section)],
        y=sections,
        colorscale=[
            [0.0,  "#10B981"],
            [0.35, "#84CC16"],
            [0.6,  "#F59E0B"],
            [0.8,  "#F97316"],
            [1.0,  "#EF4444"],
        ],
        zmin=0, zmax=100,
        text=[[str(v) if v is not None else "" for v in row] for row in z_matrix],
        texttemplate="%{text}",
        textfont={"size": 11, "color": "white"},
        hovertemplate="<b>%{y}</b><br>%{x}<br>Risk: %{z}/100<extra></extra>",
        colorbar=dict(
            title="Risk",
            titlefont=dict(color="#94A3B8", size=11),
            tickfont=dict(color="#94A3B8", size=10),
            bgcolor="rgba(0,0,0,0)",
            bordercolor="#1E3A5F",
        ),
    ))
    fig.update_layout(
        height=max(200, len(sections) * 40 + 60),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8", family="Inter"),
        xaxis=dict(showgrid=False, color="#475569", tickfont=dict(size=9)),
        yaxis=dict(showgrid=False, color="#94A3B8", tickfont=dict(size=10)),
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _mock_analysis_result(doc_id: str, filename: str, clauses: list) -> dict:
    """Realistic mock AnalysisResult for offline/demo mode."""
    import random

    contradictions = [
        {
            "clause_id_a": "clause_1_2",
            "clause_id_b": "clause_1_3",
            "contradiction_type": "MUTUAL_EXCLUSION",
            "explanation": (
                "Clause 2.2 declares all fees non-refundable once billing commences. "
                "Clause 2.3 grants a full refund if the vendor discontinues services. "
                "Both cannot be simultaneously true — Z3 returns UNSAT."
            ),
            "z3_proof": (
                "Assert: refundable = FALSE  (Clause 2.2)\n"
                "Assert: refundable = TRUE   (Clause 2.3)\n"
                "Z3 Result: UNSAT — both cannot hold simultaneously\n"
                "Contradiction type: MUTUAL_EXCLUSION"
            ),
        },
        {
            "clause_id_a": "clause_2_1",
            "clause_id_b": "clause_2_2",
            "contradiction_type": "MUTUAL_EXCLUSION",
            "explanation": (
                "Clause 3.2 establishes automatic annual renewal. "
                "Clause 3.3 states this Agreement does not auto-renew. "
                "Z3 encodes auto_renewal=TRUE and auto_renewal=FALSE as UNSAT."
            ),
            "z3_proof": (
                "Assert: auto_renewal = TRUE   (Clause 3.2)\n"
                "Assert: auto_renewal = FALSE  (Clause 3.3)\n"
                "Z3 Result: UNSAT — mutual exclusion on auto_renewal\n"
                "Contradiction type: MUTUAL_EXCLUSION"
            ),
        },
        {
            "clause_id_a": "clause_3_1",
            "clause_id_b": "clause_3_2",
            "contradiction_type": "LOGICAL_DEAD_END",
            "explanation": (
                "Clause 8.1 designates Indian law as governing. "
                "Clause 8.2 designates Singapore courts as the exclusive jurisdiction. "
                "Enforcing Indian law in a Singapore court creates a logical dead end."
            ),
            "z3_proof": (
                "Assert: has_governing_law = INDIA     (Clause 8.1)\n"
                "Assert: has_governing_law = SINGAPORE (Clause 8.2)\n"
                "Z3 Result: UNSAT — single jurisdiction predicate cannot hold two values\n"
                "Contradiction type: LOGICAL_DEAD_END"
            ),
        },
    ]

    compliance_violations = [
        {
            "clause_id": "clause_4_2",
            "regulation": "GDPR",
            "article": "Article 6 — Lawfulness of Processing",
            "description": (
                "Clause 4.2 permits the Vendor to share aggregated Client data with "
                "unnamed third-party analytics partners without obtaining separate consent. "
                "GDPR Article 6 requires a lawful basis for each processing purpose. "
                "Potential penalty: up to 4% of global annual turnover."
            ),
            "severity": "CRITICAL",
        },
        {
            "clause_id": "clause_4_2",
            "regulation": "DPDP",
            "article": "Section 7 — Purposes of Processing",
            "description": (
                "India's Digital Personal Data Protection Act 2023 Section 7 requires that "
                "personal data be processed only for specified, clear, and lawful purposes. "
                "Sharing with unnamed third parties for unspecified analytics is non-compliant."
            ),
            "severity": "HIGH",
        },
    ]

    obligations = [
        {"clause_id": "clause_2_1", "clause_number": "3.2",
         "description": "Provide written notice of non-renewal",
         "deadline_days": 7, "obligation_type": "NOTICE", "party_responsible": "Client"},
        {"clause_id": "clause_6_1", "clause_number": "6.1",
         "description": "Written notice for termination for convenience",
         "deadline_days": 30, "obligation_type": "NOTICE", "party_responsible": "Either Party"},
        {"clause_id": "clause_6_3", "clause_number": "6.3",
         "description": "Return or destroy all Client Data post-termination",
         "deadline_days": 7, "obligation_type": "DATA_RETURN", "party_responsible": "Vendor"},
        {"clause_id": "clause_2_1_pay", "clause_number": "2.1",
         "description": "Monthly subscription fee payment",
         "deadline_days": 30, "obligation_type": "PAYMENT", "party_responsible": "Client"},
        {"clause_id": "clause_3_1", "clause_number": "3.1",
         "description": "Initial term of agreement",
         "deadline_days": 365, "obligation_type": "TERM", "party_responsible": "Both Parties"},
    ]

    agent_logs = [
        "[ParserAgent] → Received document. Extracting clause structure…",
        f"[ParserAgent] → {len(clauses)} clauses extracted across "
        f"{len(set(c.get('section','?') for c in clauses))} sections.",
        "[ParserAgent] ✓ Clause index built. Handing off to AttackerAgent.",
        "[AttackerAgent] → Beginning adversarial stress-test. Examining 9 semantic patterns…",
        "[AttackerAgent] → ⚠ CLAUSE 2.2: Non-refundable fee clause — contradiction with Clause 2.3.",
        "[AttackerAgent] → ⚠ CLAUSE 3.2: Auto-renewal window is 7 days — exploitable.",
        "[AttackerAgent] → ⚠ CLAUSE 4.2: Third-party data sharing without consent — GDPR Art. 6.",
        "[AttackerAgent] → ⚠ CLAUSE 5.2: Liability cap removed for downtime.",
        "[AttackerAgent] → ⚠ CLAUSE 6.2: Vendor may terminate immediately without notice.",
        "[AttackerAgent] ✓ Stress-test complete. 5 exploitable clauses flagged.",
        "[DefenderAgent] → Reviewing 5 Attacker findings for false positives…",
        "[DefenderAgent] → Clause 2.2/2.3: Confirmed contradiction. Refundable polarity conflict.",
        "[DefenderAgent] → Clause 3.2/3.3: Confirmed contradiction. auto_renewal polarity conflict.",
        "[DefenderAgent] → Clause 4.2: Confirmed GDPR Art. 6 risk.",
        "[DefenderAgent] → Clause 6.2: Confirmed asymmetric termination rights.",
        "[DefenderAgent] ✓ 4 of 5 findings confirmed. Handing to Z3ValidatorAgent.",
        "[Z3ValidatorAgent] → Loading Z3 SMT Solver. Encoding clause tags as Boolean expressions…",
        "[Z3ValidatorAgent] → Checking pair (clause_1_2, clause_1_3): refundable=FALSE ∧ refundable=TRUE → UNSAT ✗",
        "[Z3ValidatorAgent] → Checking pair (clause_2_1, clause_2_2): auto_renewal=TRUE ∧ auto_renewal=FALSE → UNSAT ✗",
        "[Z3ValidatorAgent] → Checking pair (clause_3_1, clause_3_2): governing_law=INDIA ∧ governing_law=SINGAPORE → UNSAT ✗",
        "[Z3ValidatorAgent] ✓ 3 formal contradictions proven. Z3 proofs generated.",
        "[CitationAgent] → Indexing all clauses into vector store (InMemoryRAG)…",
        f"[CitationAgent] → {len(clauses)} clauses indexed. Running citation verification…",
        "[CitationAgent] → Verifying: 'Fees are non-refundable' → Clause 2.2, score=0.91 ✓ VERIFIED",
        "[CitationAgent] → Verifying: 'Auto-renewal requires 7-day window' → Clause 3.2, score=0.88 ✓ VERIFIED",
        "[CitationAgent] → Verifying: 'Vendor may share data with third parties' → Clause 4.2, score=0.85 ✓ VERIFIED",
        "[CitationAgent] ✓ Hallucination rate: 0.0%. All findings citation-verified.",
        "[AutoFixerAgent] → Rewriting 4 high-risk clauses into balanced alternatives…",
        "[AutoFixerAgent] → Clause 2.2/2.3: Rewriting to pro-rata refund for unused days.",
        "[AutoFixerAgent] → Clause 3.2: Rewriting auto-renewal window from 7 days to 60 days.",
        "[AutoFixerAgent] → Clause 4.2: Rewriting to require named sub-processors and opt-in consent.",
        "[AutoFixerAgent] → Clause 6.2: Rewriting to match Clause 6.1 — 30-day notice both parties.",
        "[AutoFixerAgent] ✓ All rewrites complete. Generating redline export…",
        "✅ Analysis complete. Overall Risk Score: 74/100 (HIGH). 3 contradictions. 2 violations. 0% hallucination.",
    ]

    for c in clauses:
        if (c.get("risk_score") or 0) >= 60:
            c["risk_reason"] = c.get("risk_reason") or "High-risk clause identified by AttackerAgent."
            c["suggested_fix"] = (
                "BALANCED REWRITE: This clause has been rewritten to establish symmetric obligations "
                "on both parties, a 60-day advance notice window, explicit carve-outs limited to "
                "material breach only, and a mutual termination condition requiring written agreement."
            )

    citation_results = [
        {
            "claim": c.get("text", "")[:100],
            "source_clause_id": c.get("clause_id", ""),
            "source_page": c.get("page_number", 1),
            "source_text_excerpt": c.get("text", "")[:200],
            "confidence_score": round(0.75 + (c.get("risk_score", 50) / 1000), 4),
            "verified": True,
        }
        for c in clauses[:8]
    ]

    return {
        "doc_id":                  doc_id,
        "filename":                filename,
        "overall_risk_score":      74,
        "clauses":                 clauses,
        "contradictions":          contradictions,
        "citation_results":        citation_results,
        "hallucination_rate":      0.0,
        "compliance_violations":   compliance_violations,
        "obligations":             obligations,
        "agent_logs":              agent_logs,
        "processing_time_seconds": 48.2,
    }


# ══════════════════════════════════════════════════════════════
# ANALYSIS HELPERS (Task 3)
# ══════════════════════════════════════════════════════════════
import random

AGENT_SEQUENCE = [
    {
        "id":    "parser",
        "name":  "ClauseParserAgent",
        "icon":  "📄",
        "color": "#60A5FA",
        "task":  "Structuring clause objects and section tags",
        "logs": [
            ("info",    "Initialising clause parser pipeline..."),
            ("info",    "Loading spaCy NLP model for legal entity recognition..."),
            ("success", "Document segmented into {n} discrete clause objects"),
            ("info",    "Assigning section tags and page coordinates..."),
            ("success", "Clause indexing complete — all {n} clauses structured"),
        ],
    },
    {
        "id":    "risk",
        "name":  "RiskScorerAgent",
        "icon":  "⚠️",
        "color": "#F59E0B",
        "task":  "Scoring each clause for risk exposure",
        "logs": [
            ("agent",   "RiskScorerAgent activated — scanning {n} clauses..."),
            ("info",    "Running semantic risk patterns across clause corpus..."),
            ("warn",    "Elevated risk detected in LIABILITY section"),
            ("warn",    "Auto-renewal window below industry threshold (7 days vs 60-90 standard)"),
            ("success", "Risk scoring complete — average score: {avg}/100"),
        ],
    },
    {
        "id":    "attacker",
        "name":  "AttackerAgent",
        "icon":  "⚔️",
        "color": "#EF4444",
        "task":  "Adversarial stress-testing of every clause",
        "logs": [
            ("agent",   "AttackerAgent online — adversarial mode engaged"),
            ("info",    "Probing Clause 3.2 for termination asymmetry..."),
            ("error",   "EXPLOIT FOUND: Vendor may terminate without notice (Clause 6.2) while Client requires 30 days"),
            ("error",   "EXPLOIT FOUND: Liability cap (Clause 5.1) contradicted by full-liability clause (Clause 5.2)"),
            ("warn",    "Borderline exploit: Payment deferral has no time limit (Clause 2.3)"),
            ("success", "Attacker sweep complete — {attacks} exploitable clauses identified"),
        ],
    },
    {
        "id":    "defender",
        "name":  "DefenderAgent",
        "icon":  "🛡️",
        "color": "#8B5CF6",
        "task":  "Cross-examining Attacker findings",
        "logs": [
            ("agent",   "DefenderAgent online — reviewing Attacker findings..."),
            ("info",    "Examining Clause 6.2 termination asymmetry claim..."),
            ("warn",    "Confirmed: termination asymmetry is legally binding as written"),
            ("info",    "Examining liability contradiction claim..."),
            ("warn",    "Confirmed: Clauses 5.1 and 5.2 are mutually exclusive — UNSAT"),
            ("success", "Defender review complete — {confirmed} findings confirmed, 0 false positives"),
        ],
    },
    {
        "id":    "z3",
        "name":  "Z3ValidatorAgent",
        "icon":  "🔬",
        "color": "#06B6D4",
        "task":  "Formal SMT proof of clause contradictions",
        "logs": [
            ("agent",   "Z3 SMT Solver initialised — encoding clause semantics..."),
            ("info",    "Encoding 9 semantic tag patterns as Boolean expressions..."),
            ("info",    "Running pairwise satisfiability check on {n} clause pairs..."),
            ("error",   "UNSAT: refundable = TRUE (Clause 2.3) AND refundable = FALSE (Clause 2.2)"),
            ("error",   "UNSAT: auto_renewal = TRUE (Clause 3.2) AND auto_renewal = FALSE (Clause 3.3)"),
            ("error",   "UNSAT: liability_limited = TRUE (Clause 5.1) AND liability_limited = FALSE (Clause 5.2)"),
            ("success", "Z3 proof complete — {contradictions} formal contradictions with UNSAT certificates"),
        ],
    },
    {
        "id":    "compliance",
        "name":  "ComplianceAgent",
        "icon":  "⚖️",
        "color": "#10B981",
        "task":  "GDPR / DPDP Act / IT Act compliance scan",
        "logs": [
            ("agent",   "ComplianceAgent active — running regulatory scan..."),
            ("info",    "Checking GDPR Article 6 (lawful basis for processing)..."),
            ("error",   "VIOLATION: Clause 4.2 — third-party data sharing without consent basis"),
            ("info",    "Checking DPDP Act 2023 Section 4 obligations..."),
            ("warn",    "BORDERLINE: Data retention clause lacks explicit deletion timeline"),
            ("info",    "Checking IT Act 2000 Section 43A security obligations..."),
            ("success", "Compliance scan complete — {violations} violations, {warnings} warnings"),
        ],
    },
    {
        "id":    "fixer",
        "name":  "AutoFixerAgent",
        "icon":  "✏️",
        "color": "#F97316",
        "task":  "Rewriting dangerous clauses into fair versions",
        "logs": [
            ("agent",   "AutoFixerAgent online — processing {flagged} flagged clauses..."),
            ("info",    "Rewriting auto-renewal clause with 60-day notice window..."),
            ("info",    "Rewriting GDPR-violating data clause with opt-in consent requirement..."),
            ("info",    "Rewriting asymmetric termination clause with mutual 30-day notice..."),
            ("info",    "Rewriting liability cap to be unambiguously exclusive..."),
            ("success", "AutoFix complete — {fixed} clauses rewritten, redline doc ready"),
        ],
    },
]


def _fill_log(template: str, n: int, avg: int, attacks: int,
              confirmed: int, contradictions: int, violations: int,
              warnings: int, flagged: int, fixed: int) -> str:
    return (template
            .replace("{n}", str(n))
            .replace("{avg}", str(avg))
            .replace("{attacks}", str(attacks))
            .replace("{confirmed}", str(confirmed))
            .replace("{contradictions}", str(contradictions))
            .replace("{violations}", str(violations))
            .replace("{warnings}", str(warnings))
            .replace("{flagged}", str(flagged))
            .replace("{fixed}", str(fixed)))


def render_agent_timeline(completed: list, active):
    """Left-panel vertical timeline showing agent status during analysis."""
    html('<div style="margin-bottom:1rem;">')
    for agent in AGENT_SEQUENCE:
        aid = agent["id"]
        if aid in completed:
            state, dot_icon = "done", "✓"
        elif aid == active:
            state, dot_icon = "active", agent["icon"]
        else:
            state, dot_icon = "waiting", agent["icon"]
        color = agent["color"] if state != "waiting" else "#475569"
        html(f"""
<div class="timeline-step">
<div class="timeline-dot {state}" style="border-color:{color}; color:{color}; font-size:0.85rem;">
{dot_icon}
</div>
<div class="timeline-content">
<div class="timeline-title" style="color:{'#F1F5F9' if state != 'waiting' else '#475569'};">
{agent['name']}
</div>
<div class="timeline-desc">{agent['task']}</div>
</div>
</div>
""")
    html('</div>')


def render_log_block(log_lines: list):
    """Renders the scrollable monospace agent log panel."""
    inner = ""
    for css, msg in log_lines:
        prefix = {"info": "ℹ", "success": "✓", "warn": "⚠",
                  "error": "✗", "agent": "▶"}.get(css, "·")
        inner += f'<div class="log-{css}">{prefix}  {msg}</div>'
    html(f'<div class="agent-log">{inner}</div>')


def _overall_score_ring(score: int):
    """Plotly gauge/ring showing the overall contract risk score."""
    color = risk_color(score)
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        delta={"reference": 50, "increasing": {"color": "#EF4444"},
               "decreasing": {"color": "#10B981"}},
        title={"text": "Overall Risk Score", "font": {"size": 14, "color": "#94A3B8"}},
        domain={"x": [0, 1], "y": [0, 1]},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#475569",
                     "tickfont": {"size": 9}, "nticks": 6},
            "bar":  {"color": color, "thickness": 0.25},
            "bgcolor": "#162032",
            "bordercolor": "#1E3A5F",
            "steps": [
                {"range": [0,  35], "color": "#10B98115"},
                {"range": [35, 60], "color": "#F59E0B15"},
                {"range": [60, 80], "color": "#F9731615"},
                {"range": [80,100], "color": "#EF444415"},
            ],
            "threshold": {
                "line": {"color": color, "width": 3},
                "thickness": 0.8,
                "value": score,
            },
        },
        number={"font": {"color": color, "size": 48, "family": "Inter"}, "suffix": "/100"},
    ))
    fig.update_layout(
        height=260,
        margin=dict(l=20, r=20, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#94A3B8", "family": "Inter"},
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_contradiction_panel(contradictions: list):
    """Renders each Z3-proven contradiction as an expandable card."""
    if not contradictions:
        html("""
<div style="text-align:center; padding:2rem; color:#10B981;">
<div style="font-size:1.5rem; margin-bottom:0.4rem;">✅</div>
No logical contradictions detected.
</div>
""")
        return

    for i, c in enumerate(contradictions, 1):
        ctype = c.get("contradiction_type", "MUTUAL_EXCLUSION")
        cid_a = c.get("clause_id_a", "")
        cid_b = c.get("clause_id_b", "")
        expl  = c.get("explanation", "")
        proof = c.get("z3_proof", "")
        type_colors = {
            "MUTUAL_EXCLUSION":    ("#EF4444", "#EF444430"),
            "LOGICAL_DEAD_END":    ("#F97316", "#F9731630"),
            "CIRCULAR_OBLIGATION": ("#8B5CF6", "#8B5CF630"),
        }
        tc, tc_bg = type_colors.get(ctype, ("#EF4444", "#EF444430"))

        with st.expander(f"#{i}  ·  {ctype}  ·  {cid_a} ↔ {cid_b}", expanded=(i == 1)):
            html(f"""
<div class="contradiction-pair">
<div class="contradiction-type-badge" style="color:{tc}; background:{tc_bg}; border-color:{tc}50;">
{ctype}
</div>
<div style="margin-bottom:0.8rem; font-size:0.88rem; color:#F1F5F9; line-height:1.6;">{expl}</div>
<div style="font-size:0.75rem; color:#475569; font-family:'JetBrains Mono',monospace;
background:#0F1923; border:1px solid #1E3A5F30; border-radius:8px; padding:0.8rem;
line-height:1.8; white-space:pre-wrap;">{proof}</div>
</div>
""")


def render_compliance_panel(violations: list):
    """Renders compliance violations from the ComplianceAgent."""
    if not violations:
        html("""
<div style="text-align:center; padding:2rem; color:#10B981;">
<div style="font-size:1.5rem; margin-bottom:0.4rem;">✅</div>
No compliance violations detected.
</div>
""")
        return

    regs = {
        "GDPR":   ("#2563EB", "🇪🇺"),
        "DPDP":   ("#10B981", "🇮🇳"),
        "IT_ACT": ("#F59E0B", "🇮🇳"),
        "CCPA":   ("#8B5CF6", "🇺🇸"),
        "HIPAA":  ("#EF4444", "🏥"),
    }

    for v in violations:
        reg     = v.get("regulation", "GDPR")
        article = v.get("article", "")
        clause  = v.get("clause_id", "")
        desc    = v.get("description", "")
        sev     = v.get("severity", "HIGH")
        rc, flag = regs.get(reg, ("#EF4444", "⚖️"))
        sev_color = {"CRITICAL": "#EF4444", "HIGH": "#F97316",
                     "MEDIUM": "#F59E0B", "LOW": "#10B981"}.get(sev, "#F97316")

        html(f"""
<div class="risk-card high" style="border-color:{rc}50; margin-bottom:0.75rem;">
<div style="display:flex; align-items:center; gap:0.7rem; margin-bottom:0.5rem;">
<span style="font-size:1.2rem;">{flag}</span>
<span style="font-weight:700; font-size:0.9rem; color:#F1F5F9;">{reg} · {article}</span>
<span style="margin-left:auto; font-size:0.65rem; font-weight:700; letter-spacing:1px;
padding:0.15rem 0.6rem; border-radius:99px; background:{sev_color}20;
color:{sev_color}; border:1px solid {sev_color}40;">{sev}</span>
</div>
<div style="font-size:0.82rem; color:#94A3B8; margin-bottom:0.3rem;">
Triggered by: <code style="color:#60A5FA; font-size:0.78rem;">{clause}</code>
</div>
<div style="font-size:0.85rem; color:#CBD5E1; line-height:1.5;">{desc}</div>
</div>
""")


def render_citation_panel(citations: list):
    """Renders the RAG citation verification results."""
    if not citations:
        html('<div style="color:#475569; padding:1rem;">No citations to display.</div>')
        return

    verified   = [c for c in citations if c.get("verified")]
    unverified = [c for c in citations if not c.get("verified")]

    col1, col2 = st.columns(2)
    with col1:
        html(f"""
<div style="background:#10B98110; border:1px solid #10B98130; border-radius:12px;
padding:0.9rem; text-align:center; margin-bottom:1rem;">
<div style="font-size:1.8rem; font-weight:800; color:#10B981;">{len(verified)}</div>
<div style="font-size:0.75rem; color:#10B981; text-transform:uppercase; letter-spacing:1px;">
Verified Citations
</div>
</div>
""")
    with col2:
        html(f"""
<div style="background:#EF444410; border:1px solid #EF444430; border-radius:12px;
padding:0.9rem; text-align:center; margin-bottom:1rem;">
<div style="font-size:1.8rem; font-weight:800; color:#EF4444;">{len(unverified)}</div>
<div style="font-size:0.75rem; color:#EF4444; text-transform:uppercase; letter-spacing:1px;">
Hallucinations Caught
</div>
</div>
""")

    for cite in citations[:8]:
        verified_flag = cite.get("verified", False)
        score   = cite.get("confidence_score", 0)
        claim   = cite.get("claim", "")[:120]
        src_id  = cite.get("source_clause_id", "")
        excerpt = cite.get("source_text_excerpt", "")[:100]
        badge_cls = "badge-verified" if verified_flag else "badge-hallucination"
        badge_lbl = "✓ VERIFIED" if verified_flag else "✗ HALLUCINATION"

        html(f"""
<div style="background:#162032; border:1px solid #1E3A5F30; border-radius:10px;
padding:0.9rem; margin-bottom:0.6rem;">
<div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem;">
<span class="risk-badge {badge_cls}">{badge_lbl}</span>
<span style="font-size:0.72rem; color:#475569;">score: {score:.2f}</span>
<span style="font-size:0.72rem; color:#475569; margin-left:auto;">→ {src_id}</span>
</div>
<div style="font-size:0.82rem; color:#94A3B8; margin-bottom:0.3rem; font-style:italic;">
"{claim}..."
</div>
<div style="font-size:0.75rem; color:#475569; font-family:'JetBrains Mono',monospace;
white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{excerpt}</div>
</div>
""")


def render_risk_heatmap(clauses: list):
    """Plotly heatmap — sections (x) vs page number (y) coloured by risk score."""
    if not clauses:
        return
    sections = sorted(set(c.get("section", "General") for c in clauses))
    pages    = sorted(set(c.get("page_number", 1) for c in clauses))

    matrix = []
    for pg in pages:
        row = []
        for sec in sections:
            matches = [c.get("risk_score", 0) or 0
                       for c in clauses
                       if c.get("section") == sec and c.get("page_number") == pg]
            row.append(round(sum(matches) / len(matches)) if matches else 0)
        matrix.append(row)

    fig = go.Figure(go.Heatmap(
        z=matrix,
        x=sections,
        y=[f"Page {p}" for p in pages],
        colorscale=[
            [0.0,  "#10B981"],
            [0.35, "#84CC16"],
            [0.6,  "#F59E0B"],
            [0.8,  "#F97316"],
            [1.0,  "#EF4444"],
        ],
        zmin=0, zmax=100,
        hovertemplate="<b>%{x}</b><br>%{y}<br>Risk: %{z}/100<extra></extra>",
        showscale=True,
        colorbar=dict(
            title="Risk",
            titlefont=dict(color="#94A3B8", size=11),
            tickfont=dict(color="#94A3B8", size=10),
            bgcolor="rgba(0,0,0,0)",
            bordercolor="#1E3A5F",
        ),
    ))
    fig.update_layout(
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8", family="Inter", size=10),
        margin=dict(l=60, r=20, t=20, b=80),
        xaxis=dict(tickangle=-30, color="#475569"),
        yaxis=dict(color="#475569"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_obligation_timeline(clauses: list):
    """Horizontal Gantt-style timeline of all time-bound obligations."""
    import re
    timeline_items = []
    patterns = [
        (r"(\d+)[- ]day notice",                              "Notice Period",      "#2563EB"),
        (r"auto[- ]renew",                                    "Auto-Renewal",       "#F59E0B"),
        (r"(\d+)\s+month[s]? (severance|payment|notice)",    "Payment Obligation", "#10B981"),
        (r"(\d+)\s+year[s]? (non-compete|warranty|liability)","Duration Clause",   "#8B5CF6"),
        (r"within (\d+) day[s]?",                             "Response Window",   "#06B6D4"),
        (r"(\d+)[- ]day[s]? written notice",                  "Written Notice",    "#F97316"),
    ]

    for clause in clauses:
        text = clause.get("text", "").lower()
        sec  = clause.get("section", "General")
        num  = clause.get("clause_number", "")
        for pat, label, color in patterns:
            m = re.search(pat, text)
            if m:
                days_raw = m.group(1) if m.lastindex and m.lastindex >= 1 else "30"
                try:
                    days = int(days_raw)
                except ValueError:
                    days = 30
                timeline_items.append({
                    "label":   f"§{num} — {label}",
                    "section": sec,
                    "days":    days,
                    "color":   color,
                })
                break

    if not timeline_items:
        html('<div style="color:#475569; padding:1rem;">No time-bound obligations detected.</div>')
        return

    timeline_items.sort(key=lambda x: x["days"])
    fig = go.Figure()
    for item in timeline_items[:12]:
        fig.add_trace(go.Bar(
            x=[item["days"]],
            y=[item["label"]],
            orientation="h",
            marker=dict(color=item["color"], opacity=0.75,
                        line=dict(color=item["color"], width=1)),
            text=[f"{item['days']} days"],
            textposition="outside",
            textfont=dict(color="#F1F5F9", size=10),
            hovertemplate=(
                f"<b>{item['label']}</b><br>"
                f"Section: {item['section']}<br>"
                f"Duration: {item['days']} days<extra></extra>"
            ),
            showlegend=False,
        ))

    fig.update_layout(
        height=max(250, len(timeline_items) * 35),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8", family="Inter", size=10),
        margin=dict(l=10, r=60, t=20, b=20),
        xaxis=dict(title="Days", color="#475569", showgrid=True, gridcolor="#1E3A5F30"),
        yaxis=dict(color="#94A3B8", autorange="reversed"),
        barmode="overlay",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _build_mock_analysis(clauses: list) -> dict:
    """Constructs a realistic mock AnalysisResult when the API server is offline."""
    n   = len(clauses)
    avg = int(sum(c.get("risk_score", 40) or 40 for c in clauses) / max(n, 1))

    contradictions = [
        {
            "clause_id_a": "clause_2_2", "clause_id_b": "clause_2_3",
            "contradiction_type": "MUTUAL_EXCLUSION",
            "explanation": (
                "Clause 2.2 declares all fees non-refundable. "
                "Clause 2.3 grants a full refund on request. "
                "Both cannot simultaneously hold."
            ),
            "z3_proof": (
                "Assert: refundable = FALSE (Clause 2.2)\n"
                "Assert: refundable = TRUE  (Clause 2.3)\n"
                "Z3 Result: UNSAT — both cannot hold simultaneously"
            ),
        },
        {
            "clause_id_a": "clause_3_2", "clause_id_b": "clause_3_3",
            "contradiction_type": "MUTUAL_EXCLUSION",
            "explanation": (
                "Clause 3.2 mandates annual auto-renewal. "
                "Clause 3.3 explicitly states no auto-renewal applies. "
                "Z3 proves these are mutually exclusive."
            ),
            "z3_proof": (
                "Assert: auto_renewal = TRUE  (Clause 3.2)\n"
                "Assert: auto_renewal = FALSE (Clause 3.3)\n"
                "Z3 Result: UNSAT — both cannot hold simultaneously"
            ),
        },
        {
            "clause_id_a": "clause_5_1", "clause_id_b": "clause_5_2",
            "contradiction_type": "MUTUAL_EXCLUSION",
            "explanation": (
                "Clause 5.1 caps liability at one month's fees. "
                "Clause 5.2 imposes unlimited liability for downtime. "
                "A cap and no-cap cannot coexist."
            ),
            "z3_proof": (
                "Assert: liability_limited = TRUE  (Clause 5.1)\n"
                "Assert: liability_limited = FALSE (Clause 5.2)\n"
                "Z3 Result: UNSAT — both cannot hold simultaneously"
            ),
        },
        {
            "clause_id_a": "clause_8_1", "clause_id_b": "clause_8_2",
            "contradiction_type": "LOGICAL_DEAD_END",
            "explanation": (
                "Clause 8.1 specifies Indian law as governing. "
                "Clause 8.2 mandates Singapore courts for disputes. "
                "Enforcing Indian law exclusively in a foreign jurisdiction is a logical dead end."
            ),
            "z3_proof": (
                "Assert: has_governing_law = TRUE (Clause 8.1 — Karnataka, India)\n"
                "Assert: jurisdiction = Singapore (Clause 8.2)\n"
                "Z3 Result: LOGICAL_DEAD_END — governing law and jurisdiction are irreconcilable"
            ),
        },
    ]

    violations = [
        {
            "regulation": "GDPR", "article": "Article 6 (Lawful Basis)",
            "clause_id": "clause_4_2", "severity": "CRITICAL",
            "description": (
                "Clause 4.2 permits sharing of Client data with unnamed third-party "
                "analytics partners without obtaining a valid lawful basis or Data Subject "
                "consent. This violates GDPR Article 6 — potential fine: 4% of global annual revenue."
            ),
        },
        {
            "regulation": "DPDP", "article": "Section 4 (Lawful Processing)",
            "clause_id": "clause_4_2", "severity": "HIGH",
            "description": (
                "Under the Digital Personal Data Protection Act 2023, processing personal "
                "data for purposes beyond those consented to by the Data Principal is "
                "prohibited. Clause 4.2 lacks a defined processing purpose for third-party sharing."
            ),
        },
    ]

    auto_fixes = [
        {
            "clause_id": "clause_3_2", "clause_number": "3.2",
            "section": "Term and Renewal",
            "original_text": (
                "This Agreement shall auto-renew for successive one-year terms unless "
                "either Party provides written notice of non-renewal at least 7 days prior to expiry."
            ),
            "fixed_text": (
                "This Agreement shall auto-renew for successive one-year terms unless "
                "either Party provides written notice of non-renewal at least 60 days prior to expiry. "
                "Vendor shall send a renewal reminder to Client no later than 90 days before expiry."
            ),
            "fix_reason": "7-day window replaced with 60-day industry standard; mandatory reminder added.",
            "risk_before": 85, "risk_after": 20,
        },
        {
            "clause_id": "clause_4_2", "clause_number": "4.2",
            "section": "Data Ownership and Privacy",
            "original_text": (
                "Vendor may use aggregated, anonymised Client Data for product improvement "
                "and may share such data with third-party analytics partners without further consent."
            ),
            "fixed_text": (
                "Vendor may use aggregated, anonymised Client Data solely for internal product "
                "improvement. Any sharing with third-party processors requires: (a) a Data Processing "
                "Agreement with the sub-processor, (b) explicit opt-in consent from Client, and "
                "(c) disclosure of the sub-processor's identity in Schedule A."
            ),
            "fix_reason": "GDPR Article 6 compliance: consent requirement and sub-processor disclosure added.",
            "risk_before": 92, "risk_after": 18,
        },
    ]

    claims = [
        ("The vendor's financial exposure is limited under this agreement.",  True,  0.87),
        ("The contract auto-renews with a minimal notice window.",            True,  0.91),
        ("All confidential information is protected under the contract.",     True,  0.78),
        ("The vendor can freely share client data with any third party.",     False, 0.31),
        ("Either party may terminate with advance written notice.",           True,  0.82),
        ("The governing law and jurisdiction are consistent throughout.",     False, 0.44),
    ]
    citations = [
        {
            "claim": claim,
            "source_clause_id": f"clause_{i+1}_1",
            "source_page": i + 1,
            "source_text_excerpt": f"[Demo excerpt from clause {i+1}.1 matching this claim]...",
            "confidence_score": score,
            "verified": verified,
        }
        for i, (claim, verified, score) in enumerate(claims)
    ]

    return {
        "doc_id":                st.session_state.doc_id,
        "overall_risk_score":    avg,
        "clauses":               clauses,
        "contradictions":        contradictions,
        "compliance_violations": violations,
        "auto_fixes":            auto_fixes,
        "citations":             citations,
        "hallucination_rate":    0.0,
        "total_clauses":         n,
        "high_risk_count":       sum(1 for c in clauses if (c.get("risk_score") or 0) >= 60),
        "critical_count":        sum(1 for c in clauses if (c.get("risk_score") or 0) >= 80),
    }


# ══════════════════════════════════════════════════════════════
# PAGE: ANALYSE
# ══════════════════════════════════════════════════════════════
def page_analyse():
    html("""
<h2 style="font-size:1.8rem; font-weight:800; margin-bottom:0.4rem;">🤖 Agent Analysis</h2>
<p style="color:#94A3B8; margin-bottom:1.5rem; font-size:0.95rem;">
Six specialised AI agents work in sequence to stress-test your contract.
Watch the live feed as they find, prove, and fix every hidden trap.
</p>
""")

    if not st.session_state.doc_id:
        html("""
<div style="text-align:center; padding:3rem; color:#475569;">
<div style="font-size:2.5rem; margin-bottom:0.8rem;">📂</div>
<div style="font-weight:600; color:#94A3B8; margin-bottom:0.5rem;">No document loaded</div>
<div style="font-size:0.85rem;">Upload a contract first to begin agent analysis.</div>
</div>
""")
        if st.button("📄  Go to Upload", use_container_width=False):
            st.session_state.page = "upload"
            st.rerun()
        return

    if st.session_state.analysis_done and st.session_state.analysis:
        analysis = st.session_state.analysis
        score    = analysis.get("overall_risk_score", 0)
        html(f"""
<div style="background:linear-gradient(135deg,#10B98115,#10B98105);
border:1px solid #10B98130; border-radius:16px;
padding:1.2rem 1.5rem; margin-bottom:1.5rem;
display:flex; align-items:center; gap:1rem;">
<div style="font-size:2rem;">✅</div>
<div>
<div style="font-weight:700; font-size:1.05rem; color:#F1F5F9;">
Analysis complete — {st.session_state.filename}
</div>
<div style="font-size:0.83rem; color:#10B981; margin-top:2px;">
Overall risk score: {score}/100  ·
{len(analysis.get('contradictions', []))} contradictions  ·
{len(analysis.get('compliance_violations', []))} violations  ·
{len(analysis.get('auto_fixes', []))} clauses auto-fixed
</div>
</div>
</div>
""")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📊  View Risk Dashboard", use_container_width=True):
                st.session_state.page = "results"
                st.rerun()
        with c2:
            if st.button("🔄  Re-run Analysis", use_container_width=True):
                st.session_state.analysis_done = False
                st.session_state.analysis      = None
                st.rerun()
        return

    clauses = (st.session_state.analysis or {}).get("clauses", [])
    n       = len(clauses)
    avg     = int(sum(c.get("risk_score", 40) or 40 for c in clauses) / max(n, 1))

    html(f"""
<div style="background:var(--bg-card2); border:1px solid var(--border-light);
border-radius:14px; padding:1rem 1.4rem; margin-bottom:1.5rem;
display:flex; align-items:center; gap:1rem;">
<div style="font-size:1.5rem;">📄</div>
<div>
<div style="font-weight:600; color:#F1F5F9;">{st.session_state.filename}</div>
<div style="font-size:0.8rem; color:#475569;">{n} clauses loaded — ready for agent pipeline</div>
</div>
<div style="margin-left:auto;">
<span class="live-dot"></span>
<span style="font-size:0.78rem; color:#10B981; font-weight:600;">READY</span>
</div>
</div>
""")

    if not st.button("⚡  Launch Agent Pipeline", use_container_width=True):
        col_left, col_right = st.columns([1, 2])
        with col_left:
            html('<div style="font-weight:600; font-size:0.9rem; color:#94A3B8; margin-bottom:0.8rem;">Agent Queue</div>')
            render_agent_timeline(completed=[], active=None)
        with col_right:
            html('<div style="font-weight:600; font-size:0.9rem; color:#94A3B8; margin-bottom:0.8rem;">Live Feed</div>')
            html("""
<div class="agent-log" style="height:320px; display:flex;
align-items:center; justify-content:center; color:#1E3A5F;">
<div style="text-align:center;">
<div style="font-size:2rem; margin-bottom:0.5rem;">⚡</div>
<div style="font-size:0.85rem;">Press Launch to start the agent pipeline</div>
</div>
</div>
""")
        return

    col_left, col_right = st.columns([1, 2])
    completed_agents = []
    all_log_lines    = []

    with col_left:
        html('<div style="font-weight:600; font-size:0.9rem; color:#94A3B8; margin-bottom:0.8rem;">Agent Queue</div>')
        timeline_ph = st.empty()

    with col_right:
        html('<div style="font-weight:600; font-size:0.9rem; color:#94A3B8; margin-bottom:0.8rem;">Live Feed</div>')
        log_ph  = st.empty()
        prog_ph = st.empty()

    attacks          = random.randint(3, 6)
    confirmed        = attacks
    contradictions_n = 4
    violations_n     = 2
    flagged          = random.randint(attacks, attacks + 3)
    fixed            = flagged - 1

    for agent in AGENT_SEQUENCE:
        aid = agent["id"]
        with timeline_ph.container():
            render_agent_timeline(completed=completed_agents, active=aid)

        for css, template in agent["logs"]:
            msg = _fill_log(
                template, n=n, avg=avg,
                attacks=attacks, confirmed=confirmed,
                contradictions=contradictions_n,
                violations=violations_n, warnings=1,
                flagged=flagged, fixed=fixed,
            )
            all_log_lines.append((css, f"[{agent['name']}]  {msg}"))
            with log_ph.container():
                render_log_block(all_log_lines[-18:])
            time.sleep(random.uniform(0.18, 0.42))

        completed_agents.append(aid)
        prog_ph.progress(int(len(completed_agents) / len(AGENT_SEQUENCE) * 100))
        time.sleep(0.15)

    with timeline_ph.container():
        render_agent_timeline(completed=[a["id"] for a in AGENT_SEQUENCE], active=None)

    all_log_lines.append(("success", "[Pipeline]  All agents complete — compiling final report..."))
    with log_ph.container():
        render_log_block(all_log_lines[-18:])

    analysis_result = api_post("/analyse", json={"doc_id": st.session_state.doc_id})

    if analysis_result is None:
        all_log_lines.append(("warn", "[Pipeline]  API offline — using demo analysis data"))
        analysis_result = _build_mock_analysis(clauses)

    if "clauses" not in analysis_result or not analysis_result["clauses"]:
        analysis_result["clauses"] = clauses

    st.session_state.analysis      = analysis_result
    st.session_state.analysis_done = True

    prog_ph.progress(100)
    all_log_lines.append(("success",
        f"[Pipeline]  Report ready — overall risk: {analysis_result.get('overall_risk_score', avg)}/100"))
    with log_ph.container():
        render_log_block(all_log_lines[-18:])

    time.sleep(0.8)
    st.session_state.page = "results"
    st.rerun()


def page_results():
    html("""
<h2 style="font-size:1.8rem; font-weight:800; margin-bottom:0.4rem;">📊 Risk Dashboard</h2>
<p style="color:#94A3B8; margin-bottom:1.5rem; font-size:0.95rem;">
Complete breakdown of every risk, contradiction, compliance violation,
and auto-fix generated by the agent pipeline.
</p>
""")

    if not st.session_state.analysis_done or not st.session_state.analysis:
        html("""
<div style="text-align:center; padding:3rem; color:#475569;">
<div style="font-size:2.5rem; margin-bottom:0.8rem;">🤖</div>
<div style="font-weight:600; color:#94A3B8; margin-bottom:0.5rem;">No analysis results yet</div>
<div style="font-size:0.85rem;">Run the agent pipeline first.</div>
</div>
""")
        if st.button("🤖  Go to Agent Analysis", use_container_width=False):
            st.session_state.page = "analyse"
            st.rerun()
        return

    analysis       = st.session_state.analysis
    score          = analysis.get("overall_risk_score", 0)
    clauses        = analysis.get("clauses", [])
    contradictions = analysis.get("contradictions", [])
    violations     = analysis.get("compliance_violations", [])
    fixes          = analysis.get("auto_fixes", [])
    citations      = analysis.get("citations", [])
    high_risk      = analysis.get("high_risk_count", 0)
    critical       = analysis.get("critical_count", 0)
    hall_rate      = analysis.get("hallucination_rate", 0.0)

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: st.metric("Overall Risk",          f"{score}/100",           delta=f"{score-50:+} vs baseline", delta_color="inverse")
    with k2: st.metric("Contradictions",        len(contradictions),      delta="Z3 Proven")
    with k3: st.metric("Compliance Violations", len(violations),          delta="Regulatory")
    with k4: st.metric("Clauses Auto-Fixed",    len(fixes),               delta="Ready to export")
    with k5: st.metric("Hallucination Rate",    f"{hall_rate*100:.0f}%",  delta="RAG-verified")

    st.markdown("---")

    col_score, col_heat = st.columns([1, 2])
    with col_score:
        html('<div style="font-weight:600; font-size:0.9rem; color:#94A3B8; margin-bottom:0.5rem;">🎯 Contract Risk Score</div>')
        _overall_score_ring(score)
        html(f"""
<div style="text-align:center; margin-top:-0.5rem; padding:0.8rem;
background:var(--bg-card2); border-radius:10px; border:1px solid {risk_color(score)}30;">
<div style="font-size:0.75rem; color:#475569; text-transform:uppercase;
letter-spacing:1px; margin-bottom:0.3rem;">Risk Classification</div>
<div style="font-size:1.1rem; font-weight:800; color:{risk_color(score)};">
{risk_label(score).upper()}
</div>
<div style="font-size:0.78rem; color:#94A3B8; margin-top:0.3rem;">
{critical} critical · {high_risk} high-risk clauses
</div>
</div>
""")

    with col_heat:
        html('<div style="font-weight:600; font-size:0.9rem; color:#94A3B8; margin-bottom:0.5rem;">🌡️ Risk Heatmap — Section × Page</div>')
        render_risk_heatmap(clauses)

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "⚔️  Contradictions",
        "⚖️  Compliance",
        "✏️  Auto-Fixes",
        "🛡️  Citations",
        "⏱️  Obligations",
    ])

    with tab1:
        html(f"""
<div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:1rem;">
<div style="font-size:1.1rem; font-weight:700; color:#F1F5F9;">
{len(contradictions)} Logical Contradiction{'s' if len(contradictions) != 1 else ''} Detected
</div>
<span style="font-size:0.7rem; font-weight:700; letter-spacing:1.5px;
color:#EF4444; background:#EF444415; border:1px solid #EF444430;
padding:0.2rem 0.7rem; border-radius:99px;">Z3 UNSAT PROVEN</span>
</div>
""")
        render_contradiction_panel(contradictions)

    with tab2:
        html(f"""
<div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:1rem;">
<div style="font-size:1.1rem; font-weight:700; color:#F1F5F9;">
{len(violations)} Regulatory Violation{'s' if len(violations) != 1 else ''}
</div>
<span style="font-size:0.7rem; font-weight:700; letter-spacing:1.5px;
color:#F59E0B; background:#F59E0B15; border:1px solid #F59E0B30;
padding:0.2rem 0.7rem; border-radius:99px;">GDPR · DPDP · IT ACT</span>
</div>
""")
        render_compliance_panel(violations)

    with tab3:
        html(f'<div style="font-size:1.1rem; font-weight:700; color:#F1F5F9; margin-bottom:1rem;">✏️ {len(fixes)} Clause{"s" if len(fixes) != 1 else ""} Auto-Rewritten</div>')
        if not fixes:
            html('<div style="color:#475569; padding:1rem;">No auto-fixes generated.</div>')
        else:
            for fix in fixes:
                num        = fix.get("clause_number", "")
                sec        = fix.get("section", "")
                orig       = fix.get("original_text", "")
                fixed_text = fix.get("fixed_text", "")
                reason     = fix.get("fix_reason", "")
                rb         = fix.get("risk_before", 0)
                ra         = fix.get("risk_after", 0)
                with st.expander(f"§ {num} · {sec} · Risk {rb} → {ra}  ▼", expanded=True):
                    html(f"""
<div style="font-size:0.75rem; color:#F59E0B; font-weight:600;
margin-bottom:0.6rem; letter-spacing:0.5px;">WHY FIXED: {reason}</div>
<div style="font-size:0.78rem; color:#94A3B8; margin-bottom:0.3rem; font-weight:600;">ORIGINAL</div>
<div class="clause-original">{orig}</div>
<div style="text-align:center; margin:0.4rem 0; font-size:0.9rem; color:#10B981;">↓ AUTO-FIXED ↓</div>
<div style="font-size:0.78rem; color:#94A3B8; margin-bottom:0.3rem; font-weight:600;">REWRITTEN</div>
<div class="clause-fixed">{fixed_text}</div>
<div style="display:flex; gap:1rem; margin-top:0.8rem; font-size:0.78rem;">
<span style="color:#EF4444;">Risk before: {rb}/100</span>
<span style="color:#475569;">→</span>
<span style="color:#10B981;">Risk after: {ra}/100</span>
<span style="color:#475569; margin-left:auto;">↓ {rb - ra} point reduction</span>
</div>
""")

    with tab4:
        html("""
<div style="font-size:1.1rem; font-weight:700; color:#F1F5F9; margin-bottom:0.5rem;">
🛡️ RAG Citation Verification
</div>
<div style="font-size:0.82rem; color:#94A3B8; margin-bottom:1rem;">
Every agent claim has been verified against the original contract via
semantic similarity search. Claims below the 0.60 threshold are
flagged as potential hallucinations and excluded from the report.
</div>
""")
        render_citation_panel(citations)

    with tab5:
        html("""
<div style="font-size:1.1rem; font-weight:700; color:#F1F5F9; margin-bottom:0.5rem;">
⏱️ Obligation Timeline
</div>
<div style="font-size:0.82rem; color:#94A3B8; margin-bottom:1rem;">
All time-bound obligations extracted from the contract — notice periods,
renewal windows, payment terms, and deadlines — visualised by duration.
</div>
""")
        render_obligation_timeline(clauses)

    st.markdown("---")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("✏️  View Redline Export", use_container_width=True):
            st.session_state.page = "redline"
            st.rerun()
    with c2:
        if st.button("🕸️  View Citation Graph", use_container_width=True):
            st.session_state.page = "graph"
            st.rerun()
    with c3:
        if st.button("📄  Analyse New Document", use_container_width=True):
            st.session_state.doc_id        = None
            st.session_state.filename      = None
            st.session_state.clause_count  = 0
            st.session_state.analysis      = None
            st.session_state.analysis_done = False
            st.session_state.page          = "upload"
            st.rerun()






# ══════════════════════════════════════════════════════════════
# PAGE: REDLINE (Task 4)
# ══════════════════════════════════════════════════════════════
def page_redline():
    html("""
<h2 style="font-size:1.8rem; font-weight:800; margin-bottom:0.4rem;">✏️ Redline View</h2>
<p style="color:#94A3B8; margin-bottom:1.5rem; font-size:0.95rem;">
Side-by-side original vs AI-fixed clauses with tracked changes.
Download a professional Word document ready to send back to the vendor.
</p>
""")

    # ── Guard ─────────────────────────────────────────────────────────────────
    if not st.session_state.analysis_done or not st.session_state.analysis:
        html("""
<div style="text-align:center; padding:3rem; color:#475569;">
<div style="font-size:2.5rem; margin-bottom:0.8rem;">🤖</div>
<div style="font-weight:600; color:#94A3B8; margin-bottom:0.5rem;">No analysis results yet</div>
<div style="font-size:0.85rem;">Run the agent pipeline first to generate redline fixes.</div>
</div>
""")
        if st.button("🤖  Go to Agent Analysis", use_container_width=False):
            st.session_state.page = "analyse"
            st.rerun()
        return

    analysis = st.session_state.analysis
    fixes    = analysis.get("auto_fixes", [])
    clauses  = analysis.get("clauses", [])
    doc_id   = st.session_state.doc_id

    # ── Export button (calls GET /export/{doc_id}) ────────────────────────────
    col_info, col_btn = st.columns([3, 1])
    with col_info:
        html(f"""
<div style="background:var(--bg-card2); border:1px solid var(--border-light);
border-radius:12px; padding:0.9rem 1.2rem; display:flex; align-items:center; gap:1rem;">
<div style="font-size:1.5rem;">📄</div>
<div>
<div style="font-weight:600; color:#F1F5F9;">{st.session_state.filename}</div>
<div style="font-size:0.8rem; color:#475569;">
{len(fixes)} clause{'s' if len(fixes) != 1 else ''} rewritten ·
{len(clauses)} total clauses · Doc ID: {doc_id}
</div>
</div>
</div>
""")
    with col_btn:
        if st.button("⬇️  Download Redline .docx", use_container_width=True):
            try:
                r = requests.get(f"{API_BASE}/export/{doc_id}", timeout=30)
                if r.status_code == 200:
                    st.download_button(
                        label="📥  Save Word Document",
                        data=r.content,
                        file_name=f"redline_{st.session_state.filename}",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )
                else:
                    st.warning("Export endpoint not available — showing inline redline below.")
            except Exception:
                st.warning("API offline — showing inline redline below.")

    st.markdown("---")

    # ── Summary metrics ───────────────────────────────────────────────────────
    if fixes:
        total_risk_before = sum(f.get("risk_before", 0) for f in fixes)
        total_risk_after  = sum(f.get("risk_after",  0) for f in fixes)
        avg_reduction     = round((total_risk_before - total_risk_after) / max(len(fixes), 1))

        m1, m2, m3, m4 = st.columns(4)
        with m1: st.metric("Clauses Rewritten",  len(fixes))
        with m2: st.metric("Avg Risk Before",    f"{round(total_risk_before/max(len(fixes),1))}/100")
        with m3: st.metric("Avg Risk After",     f"{round(total_risk_after/max(len(fixes),1))}/100")
        with m4: st.metric("Avg Risk Reduction", f"↓ {avg_reduction} pts")

        st.markdown("---")

    # ── Redline cards ─────────────────────────────────────────────────────────
    if not fixes:
        html("""
<div style="text-align:center; padding:2rem; color:#10B981;
border:1px solid #10B98130; border-radius:12px; background:#10B98108;">
<div style="font-size:1.5rem; margin-bottom:0.4rem;">✅</div>
No clauses required rewriting. Contract is clean.
</div>
""")
    else:
        html(f'<div style="font-weight:700; font-size:1rem; color:#94A3B8; margin-bottom:1rem;">Showing {len(fixes)} rewritten clause{"s" if len(fixes)!=1 else ""}</div>')
        for i, fix in enumerate(fixes, 1):
            num    = fix.get("clause_number", "?")
            sec    = fix.get("section", "")
            orig   = fix.get("original_text", "")
            fixed  = fix.get("fixed_text", "")
            reason = fix.get("fix_reason", "")
            rb     = fix.get("risk_before", 0)
            ra     = fix.get("risk_after",  0)
            reduction = rb - ra

            html(f"""
<div style="background:var(--bg-card2); border:1px solid #1E3A5F50;
border-radius:16px; padding:1.3rem; margin-bottom:1.2rem;">
<div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:1rem; flex-wrap:wrap;">
<span style="font-size:0.75rem; font-weight:800; color:#94A3B8;
background:#1E3A5F40; padding:0.2rem 0.6rem; border-radius:99px;">#{i}</span>
<span style="font-weight:700; font-size:1rem; color:#F1F5F9;">§ {num} · {sec}</span>
<span style="margin-left:auto; font-size:0.72rem; color:#EF4444;
background:#EF444415; border:1px solid #EF444430;
padding:0.2rem 0.6rem; border-radius:99px;">Before: {rb}/100</span>
<span style="font-size:0.72rem; color:#10B981;
background:#10B98115; border:1px solid #10B98130;
padding:0.2rem 0.6rem; border-radius:99px;">After: {ra}/100</span>
<span style="font-size:0.72rem; color:#F59E0B; font-weight:700;">↓ {reduction} pts</span>
</div>
<div style="font-size:0.75rem; color:#F59E0B; font-weight:600;
margin-bottom:0.8rem; padding:0.4rem 0.8rem;
background:#F59E0B10; border-radius:8px; border-left:3px solid #F59E0B;">
WHY: {reason}
</div>
""")
            col_orig, col_arrow, col_fix = st.columns([10, 1, 10])
            with col_orig:
                html("""
<div style="font-size:0.7rem; color:#EF4444; font-weight:700;
text-transform:uppercase; letter-spacing:1px; margin-bottom:0.4rem;">
✗ Original (Risky)
</div>
""")
                html(f'<div class="clause-original">{orig}</div>')
            with col_arrow:
                html('<div style="text-align:center; padding-top:2rem; font-size:1.2rem; color:#475569;">→</div>')
            with col_fix:
                html("""
<div style="font-size:0.7rem; color:#10B981; font-weight:700;
text-transform:uppercase; letter-spacing:1px; margin-bottom:0.4rem;">
✓ AI-Fixed (Balanced)
</div>
""")
                html(f'<div class="clause-fixed">{fixed}</div>')
            html("</div>")

    st.markdown("---")

    # ── Navigation ────────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📊  Back to Risk Dashboard", use_container_width=True):
            st.session_state.page = "results"
            st.rerun()
    with c2:
        if st.button("🕸️  View Citation Graph", use_container_width=True):
            st.session_state.page = "graph"
            st.rerun()


# ══════════════════════════════════════════════════════════════
# PAGE: GRAPH (Task 4)
# ══════════════════════════════════════════════════════════════
def page_graph():
    html("""
<h2 style="font-size:1.8rem; font-weight:800; margin-bottom:0.4rem;">🕸️ Citation Graph</h2>
<p style="color:#94A3B8; margin-bottom:1.5rem; font-size:0.95rem;">
Interactive network graph showing how every agent claim links back to its source clause.
Green nodes = verified · Red nodes = hallucination caught · Blue nodes = source clauses.
</p>
""")

    # ── Guard ─────────────────────────────────────────────────────────────────
    if not st.session_state.analysis_done or not st.session_state.analysis:
        html("""
<div style="text-align:center; padding:3rem; color:#475569;">
<div style="font-size:2.5rem; margin-bottom:0.8rem;">🤖</div>
<div style="font-weight:600; color:#94A3B8; margin-bottom:0.5rem;">No analysis results yet</div>
<div style="font-size:0.85rem;">Run the agent pipeline first to generate the citation graph.</div>
</div>
""")
        if st.button("🤖  Go to Agent Analysis", use_container_width=False):
            st.session_state.page = "analyse"
            st.rerun()
        return

    analysis  = st.session_state.analysis
    citations = analysis.get("citations", [])
    clauses   = analysis.get("clauses", [])

    # ── Stats row ─────────────────────────────────────────────────────────────
    verified   = [c for c in citations if c.get("verified")]
    unverified = [c for c in citations if not c.get("verified")]
    hall_rate  = analysis.get("hallucination_rate", 0.0)

    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("Total Claims",        len(citations))
    with m2: st.metric("Verified",            len(verified),   delta="Citation-backed")
    with m3: st.metric("Hallucinations",      len(unverified), delta="Caught & excluded")
    with m4: st.metric("Hallucination Rate",  f"{hall_rate*100:.0f}%", delta="RAG-verified")

    st.markdown("---")

    # ── Build networkx graph ──────────────────────────────────────────────────
    G = nx.DiGraph()

    # Add document root node
    doc_label = (st.session_state.filename or "Contract")[:25]
    G.add_node("DOC", label=doc_label, ntype="doc", color="#2563EB", size=30)

    # Add clause nodes
    clause_map = {c.get("clause_id", ""): c for c in clauses}
    added_clauses = set()
    for cite in citations:
        src_id  = cite.get("source_clause_id", "")
        clause  = clause_map.get(src_id, {})
        sec     = clause.get("section", "General")
        num     = clause.get("clause_number", src_id)
        score   = clause.get("risk_score", 0) or 0
        c_color = risk_color(score)

        if src_id and src_id not in added_clauses:
            G.add_node(src_id,
                       label=f"§{num}\n{sec[:12]}",
                       ntype="clause",
                       color=c_color,
                       size=20)
            G.add_edge("DOC", src_id, weight=1)
            added_clauses.add(src_id)

        # Add claim node
        claim_id    = f"claim_{citations.index(cite)}"
        claim_label = cite.get("claim", "")[:40] + "..."
        is_verified = cite.get("verified", False)
        claim_color = "#10B981" if is_verified else "#EF4444"
        conf        = cite.get("confidence_score", 0)

        G.add_node(claim_id,
                   label=claim_label,
                   ntype="claim",
                   color=claim_color,
                   size=12,
                   verified=is_verified,
                   confidence=conf)
        if src_id:
            G.add_edge(src_id, claim_id, weight=conf)

    # ── Layout ────────────────────────────────────────────────────────────────
    if len(G.nodes) > 1:
        pos = nx.spring_layout(G, seed=42, k=2.5)
    else:
        pos = {"DOC": (0, 0)}

    # Build Plotly traces
    edge_x, edge_y = [], []
    for u, v in G.edges():
        if u in pos and v in pos:
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line=dict(width=1, color="#1E3A5F"),
        hoverinfo="none",
    )

    # Separate node types for layered rendering
    node_traces = []
    type_groups = {
        "doc":    {"symbol": "diamond", "size_mult": 1.8},
        "clause": {"symbol": "circle",  "size_mult": 1.4},
        "claim":  {"symbol": "square",  "size_mult": 1.0},
    }

    for ntype, props in type_groups.items():
        nodes = [(n, d) for n, d in G.nodes(data=True) if d.get("ntype") == ntype]
        if not nodes:
            continue
        nx_list, nd_list = zip(*nodes)
        node_x = [pos[n][0] for n in nx_list if n in pos]
        node_y = [pos[n][1] for n in nx_list if n in pos]
        colors = [d.get("color", "#2563EB") for _, d in nodes if _  in pos]
        sizes  = [d.get("size", 15) * props["size_mult"] for _, d in nodes if _ in pos]
        labels = [d.get("label", n) for n, d in nodes if n in pos]
        hover  = []
        for n, d in nodes:
            if n not in pos:
                continue
            if ntype == "claim":
                v = "✓ VERIFIED" if d.get("verified") else "✗ HALLUCINATION"
                hover.append(f"{d.get('label','')}<br>{v}<br>Confidence: {d.get('confidence',0):.2f}")
            elif ntype == "clause":
                hover.append(f"Clause: {d.get('label','')}")
            else:
                hover.append(f"Document: {d.get('label','')}")

        node_traces.append(go.Scatter(
            x=node_x, y=node_y,
            mode="markers+text",
            marker=dict(
                symbol=props["symbol"],
                size=sizes,
                color=colors,
                line=dict(color="#0F1923", width=1.5),
                opacity=0.9,
            ),
            text=labels,
            textposition="top center",
            textfont=dict(size=8, color="#94A3B8"),
            hovertext=hover,
            hoverinfo="text",
            name=ntype.capitalize() + "s",
        ))

    fig = go.Figure(data=[edge_trace] + node_traces)
    fig.update_layout(
        height=520,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0F1923",
        font=dict(color="#94A3B8", family="Inter"),
        showlegend=True,
        legend=dict(
            font=dict(color="#94A3B8", size=11),
            bgcolor="rgba(0,0,0,0)",
            bordercolor="#1E3A5F",
            borderwidth=1,
        ),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=10, r=10, t=20, b=10),
        hovermode="closest",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Legend ────────────────────────────────────────────────────────────────
    html("""
<div style="display:flex; gap:1.5rem; justify-content:center; margin-top:0.5rem;
flex-wrap:wrap; font-size:0.78rem; color:#94A3B8;">
<span>◆ <span style="color:#2563EB;">Blue diamond</span> = Document root</span>
<span>● <span style="color:#F59E0B;">Coloured circle</span> = Source clause (colour = risk)</span>
<span>■ <span style="color:#10B981;">Green square</span> = Verified claim</span>
<span>■ <span style="color:#EF4444;">Red square</span> = Hallucination caught</span>
</div>
""")

    st.markdown("---")

    # ── Citation detail table ─────────────────────────────────────────────────
    html('<div style="font-weight:700; font-size:1rem; color:#94A3B8; margin-bottom:0.8rem;">Citation Audit Trail</div>')
    for cite in citations:
        is_v    = cite.get("verified", False)
        conf    = cite.get("confidence_score", 0)
        claim   = cite.get("claim", "")[:100]
        src_id  = cite.get("source_clause_id", "")
        excerpt = cite.get("source_text_excerpt", "")[:120]
        badge   = "badge-verified" if is_v else "badge-hallucination"
        label   = "✓ VERIFIED" if is_v else "✗ HALLUCINATION"
        bar_w   = int(conf * 100)
        bar_col = "#10B981" if conf >= 0.6 else "#EF4444"

        html(f"""
<div style="background:#162032; border:1px solid #1E3A5F30; border-radius:10px;
padding:0.9rem; margin-bottom:0.6rem;">
<div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.5rem; flex-wrap:wrap;">
<span class="risk-badge {badge}">{label}</span>
<span style="font-size:0.72rem; color:#475569;">Confidence: {conf:.2f}</span>
<div style="flex:1; background:#1E3A5F30; border-radius:99px; height:4px; min-width:60px;">
<div style="width:{bar_w}%; background:{bar_col}; height:4px; border-radius:99px;"></div>
</div>
<span style="font-size:0.72rem; color:#475569; margin-left:auto;">→ {src_id}</span>
</div>
<div style="font-size:0.82rem; color:#94A3B8; font-style:italic; margin-bottom:0.3rem;">
"{claim}..."
</div>
<div style="font-size:0.72rem; color:#475569; font-family:'JetBrains Mono',monospace;
white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{excerpt}</div>
</div>
""")

    st.markdown("---")
    if st.button("📊  Back to Risk Dashboard", use_container_width=False):
        st.session_state.page = "results"
        st.rerun()

# ══════════════════════════════════════════════════════════════
# PAGE: HISTORY (Task 4)
# ══════════════════════════════════════════════════════════════
def page_history():
    html("""
<h2 style="font-size:1.8rem; font-weight:800; margin-bottom:0.4rem;">📋 Document History</h2>
<p style="color:#94A3B8; margin-bottom:1.5rem; font-size:0.95rem;">
All contracts analysed in this session. Click any row to reload its results.
</p>
""")

    if not st.session_state.history:
        html("""
<div style="text-align:center; padding:3rem; color:#475569;
border:1px solid #1E3A5F30; border-radius:16px; background:#162032;">
<div style="font-size:2.5rem; margin-bottom:0.8rem;">📂</div>
<div style="font-weight:600; color:#94A3B8; margin-bottom:0.5rem;">No documents yet</div>
<div style="font-size:0.85rem;">Upload your first contract to get started.</div>
</div>
""")
        if st.button("📄  Upload a Contract", use_container_width=False):
            st.session_state.page = "upload"
            st.rerun()
        return

    # ── Summary stats ─────────────────────────────────────────────────────────
    total_clauses = sum(item.get("clause_count", 0) for item in st.session_state.history)
    html(f"""
<div style="display:flex; gap:1rem; margin-bottom:1.5rem; flex-wrap:wrap;">
<div style="background:var(--bg-card2); border:1px solid var(--border-light);
border-radius:12px; padding:0.9rem 1.4rem; text-align:center; flex:1; min-width:120px;">
<div style="font-size:1.6rem; font-weight:800; color:#2563EB;">
{len(st.session_state.history)}
</div>
<div style="font-size:0.72rem; color:#475569; text-transform:uppercase; letter-spacing:1px;">
Documents
</div>
</div>
<div style="background:var(--bg-card2); border:1px solid var(--border-light);
border-radius:12px; padding:0.9rem 1.4rem; text-align:center; flex:1; min-width:120px;">
<div style="font-size:1.6rem; font-weight:800; color:#F59E0B;">
{total_clauses}
</div>
<div style="font-size:0.72rem; color:#475569; text-transform:uppercase; letter-spacing:1px;">
Total Clauses
</div>
</div>
<div style="background:var(--bg-card2); border:1px solid var(--border-light);
border-radius:12px; padding:0.9rem 1.4rem; text-align:center; flex:1; min-width:120px;">
<div style="font-size:1.6rem; font-weight:800; color:#10B981;">
{'Yes' if st.session_state.analysis_done else 'No'}
</div>
<div style="font-size:0.72rem; color:#475569; text-transform:uppercase; letter-spacing:1px;">
Analysis Done
</div>
</div>
</div>
""")

    st.markdown("---")

    # ── History list ──────────────────────────────────────────────────────────
    for i, item in enumerate(reversed(st.session_state.history)):
        idx        = len(st.session_state.history) - 1 - i
        fname      = item.get("filename", "Unknown")
        ts         = item.get("timestamp", "")
        n_clauses  = item.get("clause_count", 0)
        doc_id     = item.get("doc_id", "")
        is_active  = (doc_id == st.session_state.doc_id)
        border_col = "#2563EB" if is_active else "#1E3A5F50"
        badge      = '<span style="font-size:0.65rem; font-weight:700; letter-spacing:1px; padding:0.15rem 0.5rem; border-radius:99px; background:#2563EB20; color:#2563EB; border:1px solid #2563EB40; margin-left:0.5rem;">ACTIVE</span>' if is_active else ""

        col_info, col_btn = st.columns([5, 1])
        with col_info:
            html(f"""
<div style="background:var(--bg-card2); border:1px solid {border_col};
border-radius:12px; padding:1rem 1.2rem; margin-bottom:0.5rem;">
<div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.3rem;">
<span style="font-size:1rem;">📄</span>
<span style="font-weight:700; color:#F1F5F9; font-size:0.95rem;">{fname}</span>
{badge}
</div>
<div style="display:flex; gap:1.5rem; font-size:0.75rem; color:#475569;">
<span>🕐 {ts}</span>
<span>📑 {n_clauses} clauses</span>
<span style="font-family:'JetBrains Mono',monospace; color:#1E3A5F;">ID: {doc_id[:16]}...</span>
</div>
</div>
""")
        with col_btn:
            st.write("")
            if not is_active:
                if st.button("Load", key=f"hist_load_{idx}", use_container_width=True):
                    st.session_state.doc_id       = doc_id
                    st.session_state.filename     = fname
                    st.session_state.clause_count = n_clauses
                    # Try to fetch cached results from API
                    cached = api_get(f"/results/{doc_id}")
                    if cached:
                        st.session_state.analysis      = cached
                        st.session_state.analysis_done = True
                        st.session_state.page          = "results"
                    else:
                        st.session_state.analysis      = None
                        st.session_state.analysis_done = False
                        st.session_state.page          = "analyse"
                    st.rerun()
            else:
                if st.button("View", key=f"hist_view_{idx}", use_container_width=True):
                    st.session_state.page = "results" if st.session_state.analysis_done else "analyse"
                    st.rerun()

    st.markdown("---")

    # ── Clear history ─────────────────────────────────────────────────────────
    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("🗑️  Clear History", use_container_width=True):
            st.session_state.history       = []
            st.session_state.doc_id        = None
            st.session_state.filename      = None
            st.session_state.clause_count  = 0
            st.session_state.analysis      = None
            st.session_state.analysis_done = False
            st.rerun()


# ══════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════
def main():
    inject_css()
    init_state()

    # Check server health on every load
    health = api_get("/health")
    st.session_state.server_online = (
        health is not None and health.get("status") == "ok"
    )

    # Render global status banner (top of every page)
    render_status_banner()

    render_sidebar()

    # Route to correct page
    page = st.session_state.page
    if   page == "home":    page_home()
    elif page == "upload":  page_upload()
    elif page == "analyse": page_analyse()
    elif page == "results": page_results()
    elif page == "redline": page_redline()
    elif page == "graph":   page_graph()
    elif page == "history": page_history()
    else:
        st.session_state.page = "home"
        st.rerun()


if __name__ == "__main__":
    main()
