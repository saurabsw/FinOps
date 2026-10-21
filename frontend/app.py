import os
import json
import requests
import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# Configuration: Fixed to Port 8001 (Zero Port Juggling)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Static FinOps Analyzer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Fixed Backend API URL on port 8001
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8001/api/v1").rstrip("/")

def api_get(endpoint: str, params: dict = None):
    try:
        r = requests.get(f"{BACKEND_URL}{endpoint}", params=params, timeout=12)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None

def api_post(endpoint: str, data: dict = None, json_data: dict = None, files: dict = None):
    try:
        r = requests.post(f"{BACKEND_URL}{endpoint}", data=data, json=json_data, files=files, timeout=20)
        if r.status_code in [200, 201]:
            try:
                return r.json(), r.status_code
            except Exception:
                return {"status": "success", "message": r.text}, r.status_code
        else:
            try:
                err = r.json()
                msg = err.get("detail", str(err))
            except Exception:
                msg = r.text or f"HTTP {r.status_code}"
            return {"error": msg}, r.status_code
    except Exception as e:
        return {"error": str(e)}, 500

def api_clear_database():
    try:
        r = requests.post(f"{BACKEND_URL}/billing/clear", timeout=8)
        if r.status_code == 200:
            return True, r.json().get("message", "Database purged successfully.")
        r_del = requests.delete(f"{BACKEND_URL}/billing/clear", timeout=8)
        if r_del.status_code == 200:
            return True, r_del.json().get("message", "Database purged successfully.")
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)

# Check backend health synchronously
is_backend_online = False
try:
    h_resp = requests.get(f"{BACKEND_URL}/health", timeout=0.8)
    is_backend_online = (h_resp.status_code == 200)
except Exception:
    is_backend_online = False

# -----------------------------------------------------------------------------
# Flawless CSS: No White Borders, No Red Accents, High Contrast, Animated Flow
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* 1. Complete Eradication of Streamlit Header, Status Widget, Toolbars & Badges */
    header[data-testid="stHeader"],
    div[data-testid="stDecoration"],
    div[data-testid="stToolbar"],
    div[data-testid="stToolbarActions"],
    div[data-testid="stHeaderActionElements"],
    div[data-testid="stStatusWidget"],
    div[data-testid="stConnectionStatus"],
    div[data-testid="manage-app-button"],
    div[class*="StatusWidget"],
    div[class*="statusWidget"],
    div[class*="viewerBadge"],
    div[class*="ProfileBadge"],
    .stDeployButton,
    button[data-testid="baseButton-headerNoPadding"],
    div[data-testid="stMarkdownPre"],
    #MainMenu {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        height: 0 !important;
        width: 0 !important;
        max-height: 0 !important;
        max-width: 0 !important;
        pointer-events: none !important;
        position: absolute !important;
        top: -9999px !important;
        left: -9999px !important;
        z-index: -9999 !important;
    }
    
    /* 2. Global Dark Obsidian Palette */
    html, body, [data-testid="stAppViewContainer"], .stApp {
        background: radial-gradient(circle at 50% 0%, #0f172a 0%, #080c14 100%) !important;
        background-color: #080c14 !important;
        color: #f8fafc !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }
    .stApp {
        margin-top: -50px; /* Pull content up to replace hidden header */
    }
    
    /* 3. Universal High-Contrast Typography */
    h1, h2, h3, h4, h5, h6, p, label, small, strong {
        color: #f8fafc !important;
    }
    .text-muted {
        color: #94a3b8 !important;
    }
    div[data-testid="stWidgetLabel"] p,
    div[data-testid="stWidgetLabel"] label {
        color: #f1f5f9 !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
    }
    
    /* 4. Dedicated Sticky / Fixed Top Header Banner */
    .top-header-banner {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: rgba(15, 23, 42, 0.85);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 14px;
        padding: 16px 24px;
        margin-bottom: 18px;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
    }
    .brand-title-text {
        font-size: 1.8rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        background: linear-gradient(135deg, #38bdf8 0%, #34d399 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .brand-desc-text {
        font-size: 0.88rem;
        color: #94a3b8 !important;
        margin-top: 4px;
    }
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 700;
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.35);
        color: #34d399 !important;
    }
    .status-pill-offline {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 700;
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid rgba(239, 68, 68, 0.4);
        color: #f87171 !important;
    }
    .glowing-dot {
        width: 10px;
        height: 10px;
        background: #10b981;
        border-radius: 50%;
        box-shadow: 0 0 10px #10b981, 0 0 4px #34d399;
        animation: pulseDot 2s infinite ease-in-out;
    }
    .glowing-dot-red {
        width: 10px;
        height: 10px;
        background: #ef4444;
        border-radius: 50%;
        box-shadow: 0 0 10px #ef4444;
    }
    @keyframes pulseDot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.55; transform: scale(0.85); }
    }
    
    /* 5. Animated Pipeline Flow Stepper */
    .pipeline-wrapper {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: rgba(17, 24, 39, 0.7);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 14px 20px;
        margin-bottom: 22px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    .pipeline-node {
        flex: 1;
        background: rgba(22, 30, 49, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 12px 14px;
        text-align: center;
        transition: all 0.25s ease;
    }
    .pipeline-node:hover {
        border-color: #38bdf8;
        background: rgba(30, 41, 69, 0.95);
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(56, 189, 248, 0.25);
    }
    .node-header {
        font-size: 0.92rem;
        font-weight: 700;
        color: #f8fafc !important;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
    }
    .node-subtitle {
        font-size: 0.78rem;
        color: #94a3b8 !important;
        margin-top: 4px;
    }
    .pipeline-connector {
        width: 44px;
        height: 3px;
        background: rgba(255, 255, 255, 0.12);
        position: relative;
        margin: 0 10px;
        border-radius: 2px;
        overflow: hidden;
    }
    .connector-flow {
        position: absolute;
        top: 0;
        left: 0;
        height: 100%;
        width: 18px;
        background: linear-gradient(90deg, transparent, #38bdf8, #34d399, transparent);
        animation: flowAnimation 1.6s infinite linear;
    }
    @keyframes flowAnimation {
        0% { transform: translateX(-18px); }
        100% { transform: translateX(44px); }
    }
    
    /* 6. Tabs Customization: No Red, Electric Blue Highlight */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background: rgba(15, 23, 42, 0.7);
        padding: 6px 8px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }
    .stTabs button[data-baseweb="tab"] {
        height: 42px;
        background: rgba(30, 41, 59, 0.5) !important;
        color: #cbd5e1 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 8px !important;
        font-size: 0.92rem !important;
        font-weight: 600 !important;
        padding: 0 22px !important;
        transition: all 0.2s ease !important;
    }
    .stTabs button[data-baseweb="tab"]:hover {
        background: rgba(59, 130, 246, 0.18) !important;
        color: #38bdf8 !important;
        border-color: #38bdf8 !important;
    }
    .stTabs button[data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
        color: #ffffff !important;
        border-color: #3b82f6 !important;
        box-shadow: 0 4px 16px rgba(37, 99, 235, 0.4) !important;
    }
    div[data-baseweb="tab-highlight"] {
        background-color: transparent !important;
    }
    
    /* 7. Action Card Containers */
    .action-panel {
        background: rgba(17, 24, 39, 0.75);
        backdrop-filter: blur(14px);
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-radius: 14px;
        padding: 18px 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.35);
    }
    
    /* 8. Button Overrides: Absolutely NO Default Red */
    button[kind="primary"], .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    button[kind="primary"]:hover, .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
        box-shadow: 0 4px 18px rgba(59, 130, 246, 0.45) !important;
        border-color: #60a5fa !important;
        color: #ffffff !important;
    }
    button[kind="secondary"], .stButton > button {
        background: rgba(30, 41, 59, 0.75) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(255, 255, 255, 0.14) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    button[kind="secondary"]:hover, .stButton > button:hover {
        background: rgba(51, 65, 85, 0.9) !important;
        border-color: #38bdf8 !important;
        color: #38bdf8 !important;
        box-shadow: 0 4px 14px rgba(56, 189, 248, 0.2) !important;
    }
    
    /* 9. File Uploader Styling (Max 50MB, High Contrast) */
    section[data-testid="stFileUploadDropzone"] {
        background: rgba(22, 30, 49, 0.8) !important;
        border: 1.5px dashed rgba(56, 189, 248, 0.45) !important;
        border-radius: 12px !important;
        padding: 18px !important;
        color: #f8fafc !important;
    }
    section[data-testid="stFileUploadDropzone"]:hover {
        border-color: #38bdf8 !important;
        background: rgba(30, 41, 69, 0.95) !important;
    }
    section[data-testid="stFileUploadDropzone"] button {
        background: #2563eb !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    section[data-testid="stFileUploadDropzone"] small {
        color: #94a3b8 !important;
    }
    
    /* 10. Expanders: Prevent White Background Glitch */
    .streamlit-expanderHeader, details summary {
        background: rgba(22, 30, 49, 0.9) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 12px 16px !important;
    }
    .streamlit-expanderHeader:hover, details summary:hover {
        background: rgba(30, 41, 69, 1) !important;
        color: #38bdf8 !important;
        border-color: #38bdf8 !important;
    }
    details[open] > summary {
        background: rgba(30, 41, 69, 0.95) !important;
        color: #f8fafc !important;
        border-bottom-left-radius: 0 !important;
        border-bottom-right-radius: 0 !important;
    }
    .streamlit-expanderContent {
        background: rgba(15, 23, 42, 0.9) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-top: none !important;
        border-bottom-left-radius: 10px !important;
        border-bottom-right-radius: 10px !important;
        color: #f8fafc !important;
        padding: 16px !important;
    }
    
    /* 11. KPI Cards */
    .kpi-tile {
        background: linear-gradient(135deg, rgba(20, 29, 47, 0.8) 0%, rgba(13, 20, 36, 0.85) 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.3);
    }
    .kpi-title-label {
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8 !important;
        margin-bottom: 4px;
    }
    .kpi-number-val {
        font-size: 1.85rem;
        font-weight: 800;
        line-height: 1.1;
        margin-bottom: 4px;
    }
    
    /* 12. Inputs & Selectbox Controls (BaseWeb & Native) */
    div[data-baseweb="select"],
    .stSelectbox div[data-baseweb="select"] {
        background-color: #111827 !important;
        background: #111827 !important;
        border: 1px solid rgba(255, 255, 255, 0.16) !important;
        border-radius: 8px !important;
        color: #f8fafc !important;
    }
    div[data-baseweb="select"]:hover,
    .stSelectbox div[data-baseweb="select"]:hover {
        border-color: #38bdf8 !important;
    }
    div[data-baseweb="select"] > div {
        background-color: transparent !important;
        background: transparent !important;
        color: #f8fafc !important;
        border: none !important;
    }
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] div,
    div[data-baseweb="select"] input {
        color: #f8fafc !important;
    }
    div[data-baseweb="select"] svg {
        fill: #94a3b8 !important;
        color: #94a3b8 !important;
    }
    
    /* 13. Dropdown Menu Popovers (BaseWeb Portal Attached to Body) */
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    div[data-baseweb="popover"] ul,
    ul[data-baseweb="menu"],
    div[role="listbox"] {
        background-color: #0f172a !important;
        background: #0f172a !important;
        color: #f8fafc !important;
        border: 1px solid rgba(56, 189, 248, 0.35) !important;
        border-radius: 10px !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.75) !important;
        padding: 4px !important;
    }
    
    /* Popover Options / Menu Items */
    li[data-baseweb="menu-item"],
    li[role="option"],
    div[role="option"] {
        background-color: transparent !important;
        background: transparent !important;
        color: #f8fafc !important;
        border-radius: 6px !important;
        margin: 2px 0 !important;
        padding: 10px 14px !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        transition: all 0.15s ease !important;
        cursor: pointer !important;
    }
    li[data-baseweb="menu-item"] div,
    li[data-baseweb="menu-item"] span,
    li[role="option"] div,
    li[role="option"] span {
        color: #f8fafc !important;
        background: transparent !important;
    }
    
    /* Hover and Selected State in Dropdown: Electric Blue */
    li[data-baseweb="menu-item"]:hover,
    li[data-baseweb="menu-item"][aria-selected="true"],
    li[role="option"]:hover,
    li[role="option"][aria-selected="true"],
    div[role="option"]:hover,
    div[role="option"][aria-selected="true"] {
        background-color: #2563eb !important;
        background: #2563eb !important;
        color: #ffffff !important;
    }
    li[data-baseweb="menu-item"]:hover div,
    li[data-baseweb="menu-item"]:hover span,
    li[data-baseweb="menu-item"][aria-selected="true"] div,
    li[data-baseweb="menu-item"][aria-selected="true"] span,
    li[role="option"]:hover div,
    li[role="option"]:hover span,
    li[role="option"][aria-selected="true"] div,
    li[role="option"][aria-selected="true"] span {
        color: #ffffff !important;
        background: transparent !important;
    }
    
    /* 14. Code Blocks (st.code, Pre, Code, CLI Inspection Boxes) */
    div[data-testid="stCodeBlock"],
    div[data-testid="stCode"],
    .stCode,
    pre,
    code {
        background-color: #090d16 !important;
        background: #090d16 !important;
        color: #38bdf8 !important;
        border: 1px solid rgba(56, 189, 248, 0.25) !important;
        border-radius: 8px !important;
        font-family: "JetBrains Mono", Consolas, "Fira Code", Monaco, monospace !important;
        font-size: 0.88rem !important;
    }
    
    div[data-testid="stCodeBlock"] pre {
        background-color: #090d16 !important;
        background: #090d16 !important;
        padding: 14px 16px !important;
        margin: 0 !important;
        border: none !important;
    }
    div[data-testid="stCodeBlock"] code {
        background-color: transparent !important;
        background: transparent !important;
        color: #38bdf8 !important;
        border: none !important;
    }
    
    /* Syntax token overrides: Vibrant cyan, emerald, and amber */
    div[data-testid="stCodeBlock"] span,
    pre code span,
    .token {
        color: #38bdf8 !important;
        background: transparent !important;
    }
    div[data-testid="stCodeBlock"] .token.function,
    div[data-testid="stCodeBlock"] .token.builtin {
        color: #34d399 !important; /* Emerald for CLI commands: gcloud, aws, az */
        font-weight: 700 !important;
    }
    div[data-testid="stCodeBlock"] .token.parameter,
    div[data-testid="stCodeBlock"] .token.variable,
    div[data-testid="stCodeBlock"] .token.attr-name {
        color: #fbbf24 !important; /* Amber for flags */
    }
    div[data-testid="stCodeBlock"] .token.string {
        color: #a7f3d0 !important;
    }
    div[data-testid="stCodeBlock"] .token.comment {
        color: #64748b !important; /* Slate for comments */
        font-style: italic !important;
    }
    
    /* Code Copy Button */
    div[data-testid="stCodeBlock"] button {
        background: rgba(30, 41, 59, 0.9) !important;
        color: #94a3b8 !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 6px !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stCodeBlock"] button:hover {
        background: #2563eb !important;
        color: #ffffff !important;
        border-color: #38bdf8 !important;
    }
    div[data-testid="stCodeBlock"] button svg {
        fill: currentColor !important;
    }
    
    /* 15. Inputs & Text Fields */
    .stTextInput input {
        background-color: #111827 !important;
        border: 1px solid rgba(255, 255, 255, 0.16) !important;
        color: #f8fafc !important;
        border-radius: 8px !important;
        padding: 10px 14px !important;
    }
    .stTextInput input:focus {
        border-color: #38bdf8 !important;
        box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.25) !important;
    }
    
    /* 16. JSON Viewer Dark Mode */
    div[data-testid="stJson"],
    div.react-json-view {
        background-color: #090d16 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 8px !important;
        padding: 14px !important;
    }
    
    /* 17. Alert Callouts (Info, Success, Warning, Error) */
    div[data-testid="stAlert"] {
        background-color: rgba(17, 24, 39, 0.85) !important;
        border-radius: 10px !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
    }
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] div {
        color: #f8fafc !important;
    }
    
    /* 18. Radio Group (Platform Selector) */
    div[data-testid="stRadio"] label p {
        color: #cbd5e1 !important;
        font-weight: 500 !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] {
        gap: 20px !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Static Top Header Banner (Separate Dedicated Section)
# -----------------------------------------------------------------------------
if is_backend_online:
    status_pill_html = '<div class="status-pill"><div class="glowing-dot"></div><span>Backend Online (Port 8001)</span></div>'
else:
    status_pill_html = '<div class="status-pill-offline"><div class="glowing-dot-red"></div><span>Backend Offline (Run py -3 run_server.py)</span></div>'

header_html = (
    '<div class="top-header-banner">'
    '<div>'
    '<h1 class="brand-title-text">⚡ Static FinOps Analyzer</h1>'
    '<div class="brand-desc-text">Multi-Cloud FinOps Analyzer, safe remediation suggestions, and cost optimization across Google Cloud (GCP), Amazon Web Services (AWS), and Microsoft Azure.</div>'
    '</div>'
    f'<div>{status_pill_html}</div>'
    '</div>'
)
st.markdown(header_html, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Animated Flow Stepper Pipeline
# -----------------------------------------------------------------------------
pipeline_html = (
    '<div class="pipeline-wrapper">'
    '<div class="pipeline-node">'
    '<div class="node-header"><span>📥</span> 1. Ingest Data</div>'
    '<div class="node-subtitle">Upload CSV/JSON (Max 50MB)</div>'
    '</div>'
    '<div class="pipeline-connector"><div class="connector-flow"></div></div>'
    '<div class="pipeline-node">'
    '<div class="node-header"><span>📋</span> 2. Apply Policies</div>'
    '<div class="node-subtitle">26 Multi-Cloud FinOps Rules</div>'
    '</div>'
    '<div class="pipeline-connector"><div class="connector-flow"></div></div>'
    '<div class="pipeline-node">'
    '<div class="node-header"><span>🔍</span> 3. Detect Waste</div>'
    '<div class="node-subtitle">Zero-False-Positive Engine</div>'
    '</div>'
    '<div class="pipeline-connector"><div class="connector-flow"></div></div>'
    '<div class="pipeline-node">'
    '<div class="node-header"><span>🛡️</span> 4. Safe Remediation</div>'
    '<div class="node-subtitle">Inspect-Then-Confirm Script</div>'
    '</div>'
    '</div>'
)
st.markdown(pipeline_html, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Main Navigation Tabs (Clean In-Page Tabs, No Red Hover Glitch)
# -----------------------------------------------------------------------------
tab_dashboard, tab_inventory, tab_rules = st.tabs([
    "🚀 Dashboard & Analysis",
    "📦 Loaded Cloud Resources",
    "🛡️ Rule Categorizer"
])

# =============================================================================
# TAB 1: DASHBOARD & ANALYSIS (Streamlined Action Hub + Master-Detail Queue)
# =============================================================================
with tab_dashboard:
    # -------------------------------------------------------------------------
    # Section 1: Ingestion & Engine Operations (Two Clean Balanced Panels)
    # -------------------------------------------------------------------------
    col_panel_left, col_panel_right = st.columns([1.1, 1.1])

    with col_panel_left:
        st.markdown(
            '<div class="action-panel">'
            '<h4 style="margin: 0 0 12px 0; color:#38bdf8 !important;">📤 Option A: Upload Billing Export (Max 50MB)</h4>'
            '<div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 14px;">Select the cloud provider parser before uploading your billing CSV or JSON file:</div>'
            '</div>',
            unsafe_allow_html=True
        )
        
        # Cloud Provider Parser Before File Upload
        provider_choice = st.selectbox(
            "1. Cloud Provider Parser",
            ["Auto-Detect Provider", "Google Cloud (GCP)", "Amazon Web Services (AWS)", "Microsoft Azure"],
            index=0,
            key="upload_prov_choice"
        )
        p_map = {
            "Auto-Detect Provider": None,
            "Google Cloud (GCP)": "gcp",
            "Amazon Web Services (AWS)": "aws",
            "Microsoft Azure": "azure"
        }

        # File Uploader Restricted to 50MB
        uploaded_file = st.file_uploader(
            "2. Select Cloud Billing File (CSV / JSON — Max 50MB):",
            type=["csv", "json"],
            key="file_uploader_50mb",
            help="Supports GCP Detailed Billing CSV/JSON, AWS CUR CSV, and Azure Cost Export CSV (max 50MB)."
        )

        if uploaded_file is not None:
            # 50MB size guard
            file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
            if file_size_mb > 50.0:
                st.error(f"❌ File size ({file_size_mb:.1f} MB) exceeds the 50 MB limit. Please upload a smaller export.")
            else:
                st.info(f"File ready: `{uploaded_file.name}` ({file_size_mb:.2f} MB)")
                if st.button("📤 Ingest & Run Optimization Scan", type="primary", use_container_width=True):
                    with st.spinner("Ingesting and evaluating billing records..."):
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type or "text/csv")}
                        params = {"cloud_provider": p_map[provider_choice]} if p_map[provider_choice] else None
                        up_res, status = api_post("/billing/upload", files=files, data=params)
                        if status == 200:
                            api_post("/optimizer/scan")
                            st.success(f"Ingested {up_res.get('total_records', 0)} records! Scan complete.")
                            st.rerun()
                        else:
                            st.error(f"Upload failed: {up_res.get('error', 'Invalid format')}")

    with col_panel_right:
        st.markdown(
            '<div class="action-panel">'
            '<h4 style="margin: 0 0 12px 0; color:#34d399 !important;">⚡ Option B: Multi-Cloud Test Data & Controls</h4>'
            '<div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 14px;">Instant one-click evaluation with verified GCP, AWS, and Azure sample datasets:</div>'
            '</div>',
            unsafe_allow_html=True
        )

        if st.button("⚡ Load Multi-Cloud Sample Data", type="primary", use_container_width=True):
            with st.spinner("Loading verified multi-cloud sample datasets into SQLite..."):
                load_res, status = api_post("/billing/load-samples?clear_existing=true")
                if status == 200:
                    api_post("/optimizer/scan")
                    st.success("Loaded 21 multi-cloud records and executed optimization scan!")
                    st.rerun()
                else:
                    st.error("Failed to load sample dataset.")

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        
        # Operational Buttons Row
        ctrl_col1, ctrl_col2 = st.columns(2)
        with ctrl_col1:
            if st.button("🔄 Re-Run Scan", use_container_width=True):
                with st.spinner("Re-evaluating FinOps policy rules..."):
                    scan_res, status = api_post("/optimizer/scan")
                    if status == 200:
                        st.success(f"Scan complete: {scan_res.get('findings_detected', 0)} waste items detected!")
                        st.rerun()
                    else:
                        st.error("Scan failed.")
        with ctrl_col2:
            if st.button("🗑️ Reset Database", use_container_width=True):
                ok, msg = api_clear_database()
                if ok:
                    st.warning("Database reset. 0 records remaining.")
                    st.rerun()
                else:
                    st.error(f"Reset failed: {msg}")

        # Compact Sample File Downloader
        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        sample_files_map = {
            "GCP Detailed Usage (CSV)": "gcp_detailed_billing_sample.csv",
            "GCP BigQuery Export (JSON)": "gcp_billing_sample.json",
            "AWS Cost & Usage Report (CSV)": "aws_cur_sample.csv",
            "Azure Cost Management Export (CSV)": "azure_cost_export_sample.csv"
        }
        selected_sample_label = st.selectbox("Download Sample Raw Files for Testing:", list(sample_files_map.keys()))
        selected_sample_file = sample_files_map[selected_sample_label]
        
        try:
            s_file_resp = requests.get(f"{BACKEND_URL}/billing/samples/{selected_sample_file}", timeout=4)
            if s_file_resp.status_code == 200:
                st.download_button(
                    label=f"📥 Download {selected_sample_file}",
                    data=s_file_resp.content,
                    file_name=selected_sample_file,
                    mime="text/csv" if selected_sample_file.endswith(".csv") else "application/json",
                    use_container_width=True
                )
        except Exception:
            pass

    st.markdown("<hr style='border: 0; border-top: 1px solid rgba(255,255,255,0.08); margin: 24px 0;'>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # Section 2: Multi-Cloud Spend & Remediation Overview (KPIs + Queue)
    # -------------------------------------------------------------------------
    summary = api_get("/optimizer/summary") or {}
    total_resources = summary.get("total_resources", 0)

    if total_resources == 0:
        st.info("💡 **Ready to analyze**: Upload a billing file or click **'⚡ Load Multi-Cloud Sample Data'** above to view the cost analysis and safe remediation queue.")
    else:
        # Platform Switcher Bar
        st.markdown("### 📊 Multi-Cloud Spend & Remediation Overview")
        selected_platform = st.radio(
            "Filter Active Platform View:",
            ["All Clouds (GCP, AWS, Azure)", "Google Cloud (GCP)", "Amazon Web Services (AWS)", "Microsoft Azure"],
            horizontal=True,
            index=0
        )
        platform_filter_map = {
            "All Clouds (GCP, AWS, Azure)": None,
            "Google Cloud (GCP)": "gcp",
            "Amazon Web Services (AWS)": "aws",
            "Microsoft Azure": "azure"
        }
        current_platform = platform_filter_map[selected_platform]

        # Fetch findings for active view
        f_params = {"status": "pending"}
        if current_platform:
            f_params["provider"] = current_platform
        findings_resp = api_get("/optimizer/waste-items", params=f_params) or {}
        active_findings = findings_resp.get("findings", [])

        # Executive Metrics
        total_spend = summary.get("total_spend", 0.0)
        total_waste = sum(f.get("monthly_savings_estimate", 0.0) for f in active_findings) if current_platform else summary.get("potential_monthly_savings", 0.0)
        savings_pct = (total_waste / total_spend * 100) if total_spend > 0 else 0.0
        clean_count = max(0, total_resources - len(active_findings))

        # KPI Tiles (High Contrast, Clean Presentation)
        kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)
        with kpi_c1:
            st.markdown(
                '<div class="kpi-tile">'
                '<div class="kpi-title-label">Total Monthly Cloud Spend</div>'
                f'<div class="kpi-number-val" style="color: #f8fafc;">${total_spend:,.2f}</div>'
                '<div style="font-size: 0.78rem; color: #94a3b8;">Across Ingested Accounts</div>'
                '</div>',
                unsafe_allow_html=True
            )
        with kpi_c2:
            st.markdown(
                '<div class="kpi-tile">'
                '<div class="kpi-title-label">Identified Waste Leakage</div>'
                f'<div class="kpi-number-val" style="color: #f87171;">${total_waste:,.2f}</div>'
                f'<div style="font-size: 0.78rem; color: #fca5a5;">{len(active_findings)} Actionable Items</div>'
                '</div>',
                unsafe_allow_html=True
            )
        with kpi_c3:
            st.markdown(
                '<div class="kpi-tile">'
                '<div class="kpi-title-label">Potential Monthly Savings</div>'
                f'<div class="kpi-number-val" style="color: #34d399;">{savings_pct:.1f}%</div>'
                '<div style="font-size: 0.78rem; color: #6ee7b7;">Cost Optimization Ratio</div>'
                '</div>',
                unsafe_allow_html=True
            )
        with kpi_c4:
            st.markdown(
                '<div class="kpi-tile">'
                '<div class="kpi-title-label">Active Clean Workloads</div>'
                f'<div class="kpi-number-val" style="color: #38bdf8;">{clean_count} / {total_resources}</div>'
                '<div style="font-size: 0.78rem; color: #7dd3fc;">Non-Waste Infrastructure</div>'
                '</div>',
                unsafe_allow_html=True
            )

        st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)

        # ---------------------------------------------------------------------
        # Section 3: Waste Resources & Remediation Queue (Master-Detail)
        # ---------------------------------------------------------------------
        q_head_left, q_head_right = st.columns([3, 1.2])
        with q_head_left:
            st.markdown(f"### 🛡️ Waste Resources & Remediation Queue ({len(active_findings)} items)")
            st.markdown("<div style='font-size: 0.88rem; color: #cbd5e1;'>Master summary of detected idle and orphaned resources with 2-step inspect-then-confirm remediation:</div>", unsafe_allow_html=True)
        with q_head_right:
            # Script export button
            script_url = f"{BACKEND_URL}/optimizer/generate-script"
            if current_platform:
                script_url += f"?provider={current_platform}"
            try:
                s_code_resp = requests.get(script_url, timeout=5)
                if s_code_resp.status_code == 200:
                    st.download_button(
                        label="🛡️ Export remediate_waste.sh",
                        data=s_code_resp.content,
                        file_name="remediate_waste.sh",
                        mime="application/x-sh",
                        use_container_width=True,
                        help="Generates an interactive cleanup script enforcing confirmation prompts before deleting any resource."
                    )
            except Exception:
                pass

        if not active_findings:
            st.success("🎉 No pending waste findings detected! All infrastructure meets FinOps best practice standards.")
        else:
            # Clean Summary Table First
            t_records = []
            for f in active_findings:
                r_id = f.get("resource_id", "")
                r_short = f.get("resource_name") or (r_id.split("/")[-1] if "/" in r_id else r_id)
                t_records.append({
                    "Finding #": f.get("id"),
                    "Resource": r_short,
                    "Cloud": str(f.get("provider") or f.get("cloud_provider", "")).upper(),
                    "Category": f.get("category", "General"),
                    "Severity": f.get("severity", "MEDIUM"),
                    "Monthly Waste ($)": f"${float(f.get('monthly_savings_estimate', 0)):,.2f}",
                    "Reason": f.get("reason", "")
                })
            st.dataframe(pd.DataFrame(t_records), use_container_width=True, hide_index=True)

            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
            st.markdown("#### 🔍 Master-Detail: Select Resource to Inspect & Remediate")

            # Detail Selector
            finding_options = {
                f"#{f.get('id')} — [{str(f.get('provider') or f.get('cloud_provider')).upper()}] {f.get('resource_name') or f.get('resource_id').split('/')[-1]} (${float(f.get('monthly_savings_estimate', 0)):,.2f}/mo)": f
                for f in active_findings
            }
            selected_finding_key = st.selectbox("Choose a resource finding for deep inspection:", list(finding_options.keys()))
            selected_finding = finding_options[selected_finding_key]

            # Detail Cards
            d_col1, d_col2 = st.columns([1, 1])
            with d_col1:
                st.markdown("**🔍 Step 1: Read-Only Inspection Analysis**")
                st.info(f"**Diagnostic**: {selected_finding.get('reason')}")
                st.markdown(f"- **Resource ID**: `{selected_finding.get('resource_id')}`")
                st.markdown(f"- **Triggered Rule**: `{selected_finding.get('rule_id')}` ({selected_finding.get('rule_name')})")
                st.markdown(f"- **Severity Level**: `{selected_finding.get('severity')}`")
                st.markdown(f"- **Monthly Waste Savings**: **${float(selected_finding.get('monthly_savings_estimate', 0)):,.2f} USD**")
                st.markdown("**Live Read-Only CLI Inspection Command:**")
                st.code(selected_finding.get("inspect_command", "# No inspect command"), language="bash")

            with d_col2:
                st.markdown("**🛡️ Step 2: Safe Interactive Remediation**")
                st.caption("Destructive override flags (`--quiet`, `-y`, `-f`) are strictly omitted to guarantee manual confirmation before deletion.")
                st.code(selected_finding.get("remediation_command", "# No remediation command"), language="bash")
                
                action_c1, action_c2 = st.columns(2)
                f_target_id = selected_finding.get("id")
                with action_c1:
                    if st.button("✅ Mark Remediated", key=f"btn_rem_{f_target_id}", use_container_width=True):
                        api_post(f"/optimizer/remediate-action?finding_id={f_target_id}&action=remediated")
                        st.success(f"Marked finding #{f_target_id} as remediated.")
                        st.rerun()
                with action_c2:
                    if st.button("👁️ Ignore / Keep Resource", key=f"btn_ign_{f_target_id}", use_container_width=True):
                        api_post(f"/optimizer/remediate-action?finding_id={f_target_id}&action=ignored")
                        st.info(f"Ignored finding #{f_target_id}.")
                        st.rerun()

# =============================================================================
# TAB 2: LOADED CLOUD RESOURCES (Clean Inventory)
# =============================================================================
with tab_inventory:
    st.markdown("### 📦 Loaded Cloud Resources")
    st.markdown("<div style='font-size: 0.88rem; color: #cbd5e1; margin-bottom: 16px;'>Searchable canonical resource inventory stored in local SQLite database:</div>", unsafe_allow_html=True)

    inv_c1, inv_c2, inv_c3 = st.columns([1, 1, 2])
    with inv_c1:
        inv_prov = st.selectbox("Cloud Provider Filter:", ["All Providers", "GCP", "AWS", "Azure"], key="tab2_prov_filter")
    with inv_c2:
        inv_rtype = st.selectbox("Resource Type Filter:", ["All Types", "disk", "ip", "instance", "snapshot", "load_balancer", "database", "bucket"], key="tab2_type_filter")
    with inv_c3:
        inv_search = st.text_input("Search Resources (Name, ID, Project):", placeholder="e.g. disk-prod, staging, vol-...", key="tab2_search")

    query_params = {"limit": 300}
    if inv_prov != "All Providers":
        query_params["provider"] = inv_prov.lower()
    if inv_rtype != "All Types":
        query_params["resource_type"] = inv_rtype

    raw_inv = api_get("/billing/records", params=query_params) or {}
    inv_items = raw_inv.get("items", [])

    if inv_search:
        s_term = inv_search.lower()
        inv_items = [i for i in inv_items if s_term in str(i.get("resource_id", "")).lower() or s_term in str(i.get("resource_name", "")).lower() or s_term in str(i.get("project_or_account_id", "")).lower()]

    st.markdown(f"**Loaded Resources: {len(inv_items)} items**")
    if not inv_items:
        st.info("No cloud resources found. Ingest a billing file or click '⚡ Load Multi-Cloud Sample Data' in the first tab.")
    else:
        inv_rows = []
        for item in inv_items:
            inv_rows.append({
                "Resource Name": item.get("resource_name") or item.get("resource_id", "").split("/")[-1],
                "Cloud": str(item.get("provider", "")).upper(),
                "Type": item.get("resource_type", ""),
                "Region / Zone": item.get("region_or_zone", ""),
                "Project / Account": item.get("project_or_account_id", ""),
                "Monthly Cost": f"${float(item.get('cost_amount', 0)):,.2f}",
                "Status Hint": item.get("status_hint", "active"),
                "Resource ID": item.get("resource_id", "")
            })
        st.dataframe(pd.DataFrame(inv_rows), use_container_width=True, hide_index=True)

        with st.expander("🔍 Deep Inspection: Raw JSON Metadata Viewer", expanded=False):
            st.json(inv_items[:10])

# =============================================================================
# TAB 3: RULE CATEGORIZER (26 Rules Bifurcated by Tier & Component)
# =============================================================================
with tab_rules:
    st.markdown("### 🛡️ FinOps Policy Rule Categorizer")
    st.markdown("<div style='font-size: 0.88rem; color: #cbd5e1; margin-bottom: 16px;'>Comprehensive Two-Tier Governance Catalog: Tier 1 (Deterministic Core Best Practices) & Tier 2 (Declarative Custom Governance Policies).</div>", unsafe_allow_html=True)

    rules_data = api_get("/rules") or {}
    b_rules = rules_data.get("built_in_rules", [])
    c_rules = rules_data.get("custom_rules", [])
    total_rule_count = len(b_rules) + len(c_rules)

    # 4 High-Contrast KPI Cards
    r_c1, r_c2, r_c3, r_c4 = st.columns(4)
    with r_c1:
        st.markdown(
            '<div class="kpi-tile">'
            '<div class="kpi-title-label">Total Active Policies</div>'
            f'<div class="kpi-number-val" style="color: #f8fafc;">{total_rule_count}</div>'
            '<div style="font-size: 0.78rem; color: #94a3b8;">Enforced in Engine</div>'
            '</div>',
            unsafe_allow_html=True
        )
    with r_c2:
        st.markdown(
            '<div class="kpi-tile">'
            '<div class="kpi-title-label">Tier 1: Core Best Practices</div>'
            f'<div class="kpi-number-val" style="color: #38bdf8;">{len(b_rules)}</div>'
            '<div style="font-size: 0.78rem; color: #7dd3fc;">Deterministic Rules</div>'
            '</div>',
            unsafe_allow_html=True
        )
    with r_c3:
        st.markdown(
            '<div class="kpi-tile">'
            '<div class="kpi-title-label">Tier 2: Custom Governance</div>'
            f'<div class="kpi-number-val" style="color: #34d399;">{len(c_rules)}</div>'
            '<div style="font-size: 0.78rem; color: #6ee7b7;">Declarative Policies</div>'
            '</div>',
            unsafe_allow_html=True
        )
    with r_c4:
        st.markdown(
            '<div class="kpi-tile">'
            '<div class="kpi-title-label">Covered Architectures</div>'
            '<div class="kpi-number-val" style="color: #fbbf24;">5</div>'
            '<div style="font-size: 0.78rem; color: #fde68a;">Compute, Net, Disk, DB, K8s</div>'
            '</div>',
            unsafe_allow_html=True
        )

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # Filter Controls
    rf_col1, rf_col2 = st.columns(2)
    with rf_col1:
        arch_filter = st.selectbox(
            "Filter by Cloud Architecture Component:",
            ["All Components", "Compute", "Networking", "Storage & Backup", "Databases & Caching", "Containers & Serverless", "Governance & Custom"],
            key="rule_arch_select"
        )
    with rf_col2:
        cloud_filter = st.selectbox(
            "Filter by Cloud Platform:",
            ["All Platforms", "GCP", "AWS", "Azure", "Multi-Cloud"],
            key="rule_cloud_select"
        )

    def apply_rule_filters(r_list):
        out = r_list
        if arch_filter != "All Components":
            out = [r for r in out if arch_filter.lower() in str(r.get("component", "")).lower() or arch_filter.lower() in str(r.get("category", "")).lower()]
        if cloud_filter != "All Platforms":
            out = [r for r in out if cloud_filter.lower() in str(r.get("provider", "")).lower()]
        return out

    filtered_t1 = apply_rule_filters(b_rules)
    filtered_t2 = apply_rule_filters(c_rules)

    # Section A: Tier 1
    st.markdown(f"#### 🏛️ Tier 1: Deterministic Vendor Best Practices ({len(filtered_t1)} Rules)")
    st.markdown("<div style='font-size: 0.85rem; color: #94a3b8; margin-bottom: 10px;'>Hardened detection logic guaranteeing zero false positives on active infrastructure:</div>", unsafe_allow_html=True)

    t1_table_data = []
    for r in filtered_t1:
        t1_table_data.append({
            "Rule ID": r.get("id"),
            "Rule Name": r.get("name"),
            "Component": r.get("component", "Compute"),
            "Provider": str(r.get("provider", "multi-cloud")).upper(),
            "Severity": r.get("severity", "HIGH"),
            "Description": r.get("description", "")
        })
    st.dataframe(pd.DataFrame(t1_table_data), use_container_width=True, hide_index=True)

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # Section B: Tier 2
    st.markdown(f"#### ⚙️ Tier 2: Declarative Custom Governance Policies ({len(filtered_t2)} Rules)")
    st.markdown("<div style='font-size: 0.85rem; color: #94a3b8; margin-bottom: 10px;'>Custom policies enforcing tagging compliance, non-production budget limits, and regional constraints:</div>", unsafe_allow_html=True)

    if filtered_t2:
        t2_table_data = []
        for cr in filtered_t2:
            t2_table_data.append({
                "Policy ID": cr.get("id"),
                "Policy Name": cr.get("name"),
                "Severity": cr.get("severity", "MEDIUM"),
                "Logic Operator": str(cr.get("logic_operator", "all")).upper(),
                "Active": "✅ Yes" if cr.get("enabled", True) else "❌ No",
                "Description": cr.get("description", "")
            })
        st.dataframe(pd.DataFrame(t2_table_data), use_container_width=True, hide_index=True)
    else:
        st.info("No custom governance rules match the active filters.")

    # Section C: Custom Rule Builder
    with st.expander("➕ Define New Tier 2 Custom Governance Policy", expanded=False):
        with st.form("custom_rule_form"):
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                p_name = st.text_input("Policy Name", placeholder="e.g. Flag Dev Storage Exceeding $100")
                p_desc = st.text_input("Description", placeholder="Enforce cost ceiling on development disk allocations")
                p_sev = st.selectbox("Severity Level", ["CRITICAL", "HIGH", "MEDIUM", "LOW"], index=1)
            with c_f2:
                p_attr = st.selectbox("Resource Attribute", ["cost_amount", "resource_type", "status_hint", "region_or_zone", "tags.Owner", "tags.Environment"])
                p_op = st.selectbox("Operator", ["greater_than", "less_than", "equals", "contains"])
                p_threshold = st.text_input("Threshold Value", value="100")

            submit_rule = st.form_submit_button("Create Custom Governance Policy", type="primary")
            if submit_rule and p_name:
                val = float(p_threshold) if p_op in ["greater_than", "less_than"] and p_threshold.replace(".", "", 1).isdigit() else p_threshold
                rule_body = {
                    "name": p_name,
                    "description": p_desc,
                    "provider": "*",
                    "resource_type": "*",
                    "conditions": [{"field": p_attr, "operator": p_op, "value": val}],
                    "logic_operator": "all",
                    "severity": p_sev,
                    "inspect_template": f"echo 'Auditing {{{{resource_id}}}} on {p_attr} {p_op} {p_threshold}'",
                    "remediation_template": f"echo 'Action required on non-compliant resource: {{{{resource_id}}}}'"
                }
                res, st_code = api_post("/rules", json_data=rule_body)
                if st_code in [200, 201]:
                    st.success(f"Custom governance rule '{p_name}' successfully registered!")
                    api_post("/optimizer/scan")
                    st.rerun()
                else:
                    st.error(f"Failed to register custom rule: {res}")
