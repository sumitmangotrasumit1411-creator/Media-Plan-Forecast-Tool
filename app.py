"""
app.py — Amazon Media Plan Forecast Engine
Streamlit application entry point.

Architecture (Phase 1 refactor):
  ├── CSS + page config (this file)
  ├── Module-level @st.cache_data functions (this file)
  ├── sidebar() — upload + settings (this file)
  ├── main() — tab orchestration (this file)
  └── pages/
      ├── tab_metrics.py         — render_metrics_dashboard()
      ├── tab_product.py         — render_product_tab()
      ├── tab_trend.py           — render_trend_tab()
      ├── tab_forecast.py        — render_forecast()
      ├── tab_recommendations.py — render_recommendations()
      └── tab_logic.py           — render_logic_tab()
"""

import streamlit as st
import pandas as pd

from parser import (
    parse_amazon_ads_report, parse_vendor_central_report,
    validate_ads_report, validate_vendor_report,
)
from metrics import (
    extract_ads_metrics, extract_vendor_metrics,
    campaign_breakdown, asin_ads_breakdown,
    asin_vendor_breakdown, merge_asin_view,
)
from exporter import build_excel_media_plan
from insights import (
    search_term_analysis, wasted_spend_summary, match_type_analysis,
    product_intelligence, bid_strategy_analysis, ad_product_analysis,
)
from trends import build_trend_df, trend_summary, ad_product_trend

from pages.tab_metrics         import render_metrics_dashboard
from pages.tab_product         import render_product_tab
from pages.tab_trend           import render_trend_tab
from pages.tab_forecast        import render_forecast
from pages.tab_recommendations import render_recommendations
from pages.tab_logic           import render_logic_tab

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Amazon Media Plan Forecast Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global CSS  — Phase 2 enterprise SaaS redesign
# Palette:  Primary #4f46e5 · Accent #f97316 · Dark #1e1b4b · BG #f0f2ff
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* ═══════════════════════════════════════════════════════════════════════════
   BASE TYPOGRAPHY & RESET
═══════════════════════════════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: "Inter", -apple-system, "Segoe UI", system-ui, sans-serif !important;
    font-size: 15px !important;
    -webkit-font-smoothing: antialiased;
}
p, span, li, td, th { font-size: 14px; line-height: 1.65; color: #374151; }
h1 { font-size: 26px !important; font-weight: 800 !important; color: #111827 !important; }
h2 { font-size: 20px !important; font-weight: 700 !important; color: #1f2937 !important; }
h3 { font-size: 17px !important; font-weight: 700 !important; color: #1f2937 !important; }
label, .stSelectbox label, .stMultiSelect label,
.stSlider label, .stNumberInput label {
    font-size: 13px !important; font-weight: 600 !important; color: #6b7280 !important;
    text-transform: uppercase; letter-spacing: 0.5px;
}

/* ═══════════════════════════════════════════════════════════════════════════
   HIDE STREAMLIT CHROME
═══════════════════════════════════════════════════════════════════════════ */
#MainMenu, .stDeployButton { visibility: hidden !important; display: none !important; }
header[data-testid="stHeader"] {
    background: transparent !important; box-shadow: none !important;
    height: 0 !important; min-height: 0 !important;
}
footer { display: none !important; }

/* ═══════════════════════════════════════════════════════════════════════════
   PAGE BACKGROUND
═══════════════════════════════════════════════════════════════════════════ */
.stApp {
    background: linear-gradient(160deg, #f0f2ff 0%, #faf5ff 40%, #fff7f0 100%) !important;
    min-height: 100vh;
}
.block-container {
    padding-top: 1.5rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    padding-bottom: 3rem !important;
    max-width: 1400px !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   SIDEBAR COLLAPSED TOGGLE
═══════════════════════════════════════════════════════════════════════════ */
button[data-testid="collapsedControl"] {
    visibility: visible !important; display: flex !important;
    width: 48px !important; height: 48px !important;
    background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
    border-radius: 0 12px 12px 0 !important; border: none !important;
    box-shadow: 3px 0 16px rgba(79,70,229,0.5) !important;
    position: fixed !important; top: 72px !important; left: 0 !important;
    z-index: 9999 !important;
    align-items: center !important; justify-content: center !important;
    transition: all 0.2s ease !important;
}
button[data-testid="collapsedControl"] svg {
    fill: #ffffff !important; width: 22px !important; height: 22px !important;
}
button[data-testid="collapsedControl"]:hover {
    background: linear-gradient(135deg, #f97316, #ea580c) !important;
    box-shadow: 3px 0 20px rgba(249,115,22,0.55) !important;
    width: 54px !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   SIDEBAR
═══════════════════════════════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f0c29 0%, #1e1b4b 35%, #24225a 70%, #2d1b69 100%) !important;
    border-right: 1px solid rgba(99,102,241,0.25) !important;
}
[data-testid="stSidebar"] * { color: #e0e7ff !important; }
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 { color: #ffffff !important; font-size: 12px !important; text-transform: uppercase; letter-spacing: 1px; }
[data-testid="stSidebar"] hr {
    border: none !important; border-top: 1px solid rgba(99,102,241,0.3) !important; margin: 8px 0 !important;
}
[data-testid="stSidebar"] input[type="number"],
[data-testid="stSidebar"] input[type="text"] {
    background: rgba(255,255,255,0.12) !important; color: #ffffff !important;
    border: 1px solid rgba(99,102,241,0.4) !important; border-radius: 8px !important;
}
[data-testid="stSidebar"] input[type="number"]:focus,
[data-testid="stSidebar"] input[type="text"]:focus {
    background: rgba(255,255,255,0.18) !important; border-color: #818cf8 !important;
    box-shadow: 0 0 0 2px rgba(79,70,229,0.3) !important;
}
[data-testid="stSidebar"] [data-testid="stNumberInput"] input,
[data-testid="stSidebar"] [data-baseweb="input"] input {
    background: rgba(255,255,255,0.12) !important; color: #ffffff !important;
}
[data-testid="stSidebar"] [data-testid="stNumberInputStepDown"],
[data-testid="stSidebar"] [data-testid="stNumberInputStepUp"],
[data-testid="stSidebar"] [data-testid="stNumberInput"] button {
    background: rgba(79,70,229,0.6) !important; border: none !important; border-radius: 6px !important;
}
[data-testid="stSidebar"] [data-testid="stNumberInputStepDown"] svg path,
[data-testid="stSidebar"] [data-testid="stNumberInputStepUp"] svg path,
[data-testid="stSidebar"] [data-testid="stNumberInput"] button svg path {
    fill: #ffffff !important; stroke: #ffffff !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
    background: rgba(255,255,255,0.06) !important;
    border: 2px dashed rgba(249,115,22,0.55) !important; border-radius: 10px !important;
    transition: border-color 0.2s;
}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]:hover {
    border-color: #f97316 !important; background: rgba(249,115,22,0.08) !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * { color: #c7d2fe !important; }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {
    background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
    color: #ffffff !important; border-radius: 7px !important;
    font-weight: 700 !important; font-size: 12px !important; padding: 6px 14px !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button * { color: #ffffff !important; }
/* Slider track */
[data-testid="stSidebar"] [data-baseweb="slider"] [role="slider"] {
    background: #f97316 !important; border-color: #f97316 !important;
}
/* Multiselect pills */
[data-testid="stSidebar"] [data-baseweb="tag"] {
    background: rgba(79,70,229,0.5) !important; border: none !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   HEADER BANNER
═══════════════════════════════════════════════════════════════════════════ */
.tool-header {
    background: linear-gradient(118deg, #0f0c29 0%, #1e1b4b 28%, #4f46e5 68%, #7c3aed 100%);
    padding: 28px 36px 24px;
    border-radius: 16px;
    margin-bottom: 28px;
    display: flex; align-items: center; justify-content: space-between;
    border-bottom: 3px solid #f97316;
    box-shadow: 0 8px 32px rgba(79,70,229,0.28), 0 2px 8px rgba(0,0,0,0.12);
    position: relative; overflow: hidden;
}
.tool-header::before {
    content: '';
    position: absolute; top: 0; right: 0; bottom: 0; left: 0;
    background: radial-gradient(ellipse at 80% 50%, rgba(249,115,22,0.12) 0%, transparent 60%);
    pointer-events: none;
}
.tool-header-left  { position: relative; z-index: 1; }
.tool-header-right { position: relative; z-index: 1; display: flex; align-items: center; gap: 12px; }
.tool-header-title {
    font-size: 26px; font-weight: 900; color: #ffffff; letter-spacing: -0.3px; line-height: 1.2;
}
.tool-header-sub {
    font-size: 13px; color: rgba(255,255,255,0.6); margin-top: 5px; letter-spacing: 0.2px;
}
.tool-header-badge {
    background: linear-gradient(135deg, #f97316, #ea580c);
    color: #ffffff; font-size: 12px; font-weight: 700;
    padding: 6px 16px; border-radius: 20px; letter-spacing: 0.5px;
    box-shadow: 0 2px 10px rgba(249,115,22,0.4);
}
.tool-header-status {
    background: rgba(255,255,255,0.12); backdrop-filter: blur(4px);
    color: rgba(255,255,255,0.85); font-size: 12px; font-weight: 600;
    padding: 6px 14px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.2);
}

/* ═══════════════════════════════════════════════════════════════════════════
   METRIC CARDS — Phase 2 redesign
═══════════════════════════════════════════════════════════════════════════ */
.metric-card {
    background: #ffffff;
    border: 1px solid rgba(224,231,255,0.8);
    border-radius: 14px;
    padding: 18px 20px 16px;
    margin: 6px 0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04), 0 4px 16px rgba(79,70,229,0.06);
    position: relative; overflow: hidden;
    transition: box-shadow 0.2s, transform 0.15s;
}
.metric-card:hover {
    box-shadow: 0 4px 20px rgba(79,70,229,0.14);
    transform: translateY(-1px);
}
.metric-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, #4f46e5 0%, #a78bfa 50%, #f97316 100%);
    border-radius: 14px 14px 0 0;
}
.metric-card-icon {
    font-size: 20px; margin-bottom: 10px; line-height: 1;
}
.metric-label {
    font-size: 10.5px; color: #9ca3af; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;
}
.metric-value {
    font-size: 24px; font-weight: 800; color: #111827; line-height: 1.15;
    letter-spacing: -0.5px;
}
.metric-delta {
    font-size: 11.5px; font-weight: 600; margin-top: 8px;
    display: inline-flex; align-items: center; gap: 4px;
    padding: 2px 8px; border-radius: 12px;
}
.metric-delta-good  { background: #dcfce7; color: #15803d; }
.metric-delta-warn  { background: #fef3c7; color: #92400e; }
.metric-delta-info  { background: #eff6ff; color: #1e40af; }

/* ═══════════════════════════════════════════════════════════════════════════
   SECTION HEADERS — Phase 2
═══════════════════════════════════════════════════════════════════════════ */
.section-header {
    font-size: 15px; font-weight: 700; color: #1e1b4b;
    margin: 32px 0 16px 0; padding: 11px 18px;
    background: linear-gradient(90deg, rgba(79,70,229,0.06) 0%, rgba(79,70,229,0.01) 100%);
    border-left: 4px solid #f97316;
    border-radius: 0 10px 10px 0;
    letter-spacing: 0.1px; display: flex; align-items: center; gap: 8px;
}

/* ═══════════════════════════════════════════════════════════════════════════
   INFO / CALLOUT BANNERS
═══════════════════════════════════════════════════════════════════════════ */
.callout-banner {
    background: linear-gradient(90deg, rgba(79,70,229,0.07) 0%, rgba(79,70,229,0.02) 100%);
    border: 1px solid rgba(79,70,229,0.18); border-radius: 10px;
    padding: 12px 18px; margin-bottom: 20px;
    font-size: 13.5px; color: #4338ca; font-weight: 500; line-height: 1.6;
}
.callout-banner strong { color: #1e1b4b; }

/* ═══════════════════════════════════════════════════════════════════════════
   TABS — Phase 2
═══════════════════════════════════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
    background: #ffffff;
    border-radius: 12px 12px 0 0;
    padding: 6px 8px 0;
    border-bottom: 2px solid #e0e7ff;
    gap: 2px;
    box-shadow: 0 -1px 0 #e0e7ff inset;
}
.stTabs [data-baseweb="tab"] {
    font-size: 13.5px; font-weight: 600; color: #6b7280;
    padding: 10px 16px; border-radius: 8px 8px 0 0;
    transition: all 0.15s ease; white-space: nowrap;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #4f46e5 !important; background: rgba(79,70,229,0.06) !important;
}
.stTabs [aria-selected="true"] {
    color: #4f46e5 !important;
    background: linear-gradient(180deg, rgba(79,70,229,0.08) 0%, rgba(79,70,229,0.04) 100%) !important;
    border-bottom: 3px solid #4f46e5 !important;
    font-weight: 700 !important;
}
.stTabs [data-baseweb="tab-panel"] {
    background: #ffffff;
    border-radius: 0 0 14px 14px;
    padding: 24px 8px 8px;
    border: 1px solid #e0e7ff; border-top: none;
    box-shadow: 0 4px 16px rgba(79,70,229,0.05);
}

/* ═══════════════════════════════════════════════════════════════════════════
   RECOMMENDATION & WARNING CARDS — Phase 2
═══════════════════════════════════════════════════════════════════════════ */
.reco-card {
    background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
    border: 1px solid #c4b5fd; border-left: 4px solid #4f46e5;
    padding: 14px 18px; border-radius: 0 12px 12px 0;
    margin: 10px 0; font-size: 13.5px; line-height: 1.7;
    box-shadow: 0 2px 8px rgba(79,70,229,0.08);
}
.warning-card {
    background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
    border: 1px solid #fdba74; border-left: 4px solid #f97316;
    padding: 14px 18px; border-radius: 0 12px 12px 0;
    margin: 10px 0; font-size: 13.5px; line-height: 1.7;
    box-shadow: 0 2px 8px rgba(249,115,22,0.1);
}
.success-card {
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    border: 1px solid #86efac; border-left: 4px solid #16a34a;
    padding: 14px 18px; border-radius: 0 12px 12px 0;
    margin: 10px 0; font-size: 13.5px; line-height: 1.7;
    box-shadow: 0 2px 8px rgba(22,163,74,0.08);
}

/* ═══════════════════════════════════════════════════════════════════════════
   STAT / KPI SUMMARY ROWS
═══════════════════════════════════════════════════════════════════════════ */
.kpi-hero {
    background: linear-gradient(118deg, #1e1b4b 0%, #312e81 55%, #4c1d95 100%);
    border-radius: 14px; padding: 20px 28px;
    margin-bottom: 24px; color: #fff;
    box-shadow: 0 6px 24px rgba(30,27,75,0.3);
}
.kpi-hero-row {
    display: flex; gap: 0; flex-wrap: nowrap;
}
.kpi-hero-item {
    flex: 1; text-align: center; padding: 8px 12px;
    border-right: 1px solid rgba(255,255,255,0.12);
}
.kpi-hero-item:last-child { border-right: none; }
.kpi-hero-label {
    font-size: 10px; font-weight: 700; color: rgba(255,255,255,0.5);
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;
}
.kpi-hero-value {
    font-size: 22px; font-weight: 900; color: #ffffff; line-height: 1.1;
}
.kpi-hero-sub {
    font-size: 11px; color: rgba(255,255,255,0.45); margin-top: 2px;
}

/* ═══════════════════════════════════════════════════════════════════════════
   STATUS BADGES
═══════════════════════════════════════════════════════════════════════════ */
.badge {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px;
    letter-spacing: 0.3px;
}
.badge-green  { background: #dcfce7; color: #15803d; }
.badge-orange { background: #ffedd5; color: #c2410c; }
.badge-red    { background: #fee2e2; color: #b91c1c; }
.badge-blue   { background: #eff6ff; color: #1d4ed8; }
.badge-purple { background: #f5f3ff; color: #6d28d9; }

/* ═══════════════════════════════════════════════════════════════════════════
   DATA TABLES
═══════════════════════════════════════════════════════════════════════════ */
[data-testid="stDataFrame"] {
    border-radius: 12px !important; overflow: hidden !important;
    box-shadow: 0 2px 12px rgba(79,70,229,0.07) !important;
    border: 1px solid #e0e7ff !important;
}
[data-testid="stDataFrame"] table thead tr th {
    background: #f5f3ff !important; color: #4f46e5 !important;
    font-weight: 700 !important; font-size: 12px !important;
    text-transform: uppercase; letter-spacing: 0.5px;
}

/* ═══════════════════════════════════════════════════════════════════════════
   DOWNLOAD BUTTON
═══════════════════════════════════════════════════════════════════════════ */
[data-testid="stDownloadButton"] button {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
    color: #ffffff !important; border: none !important;
    border-radius: 10px !important; font-weight: 700 !important;
    font-size: 14px !important; padding: 12px 28px !important;
    box-shadow: 0 4px 16px rgba(79,70,229,0.35) !important;
    transition: all 0.2s ease !important; letter-spacing: 0.2px !important;
}
[data-testid="stDownloadButton"] button:hover {
    box-shadow: 0 6px 24px rgba(79,70,229,0.45) !important;
    transform: translateY(-2px) !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   EXPANDER / ALERT
═══════════════════════════════════════════════════════════════════════════ */
[data-testid="stExpander"] {
    border: 1px solid #e0e7ff !important; border-radius: 10px !important;
    background: #fafbff !important; overflow: hidden !important;
}
[data-testid="stExpander"] summary {
    font-weight: 600 !important; color: #4f46e5 !important;
}
[data-testid="stAlert"] { border-radius: 10px !important; font-size: 13px !important; }

/* ═══════════════════════════════════════════════════════════════════════════
   FOOTER
═══════════════════════════════════════════════════════════════════════════ */
.tool-footer {
    margin-top: 56px; padding: 24px 0 16px;
    border-top: 2px solid #e0e7ff;
    text-align: center; font-size: 13px; font-weight: 500; color: #9ca3af;
    line-height: 2.2;
}
.tool-footer strong { color: #4f46e5; font-weight: 700; font-size: 14px; }
.tool-footer .footer-logo {
    display: inline-block; background: linear-gradient(135deg, #4f46e5, #f97316);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    font-size: 20px; font-weight: 900; letter-spacing: -0.5px; margin-bottom: 4px;
}

/* ═══════════════════════════════════════════════════════════════════════════
   WELCOME SCREEN — Phase 2 grid layout
═══════════════════════════════════════════════════════════════════════════ */
.welcome-hero {
    background: linear-gradient(118deg, #0f0c29 0%, #1e1b4b 35%, #312e81 70%, #4c1d95 100%);
    border-radius: 16px; padding: 40px 44px; margin-bottom: 28px; color: #fff;
    box-shadow: 0 12px 40px rgba(30,27,75,0.35); position: relative; overflow: hidden;
}
.welcome-hero::before {
    content: '';
    position: absolute; top: -60px; right: -60px; width: 280px; height: 280px;
    background: radial-gradient(circle, rgba(249,115,22,0.2) 0%, transparent 65%);
    pointer-events: none;
}
.welcome-hero::after {
    content: '';
    position: absolute; bottom: -80px; left: 40%; width: 320px; height: 320px;
    background: radial-gradient(circle, rgba(79,70,229,0.25) 0%, transparent 60%);
    pointer-events: none;
}
.welcome-title {
    font-size: 32px; font-weight: 900; color: #ffffff;
    letter-spacing: -0.5px; margin-bottom: 8px; position: relative; z-index: 1;
}
.welcome-subtitle {
    font-size: 15px; color: rgba(255,255,255,0.6);
    line-height: 1.7; position: relative; z-index: 1; max-width: 600px;
}
.welcome-grid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 28px;
}
.welcome-card {
    background: #ffffff; border-radius: 14px; padding: 22px 20px;
    box-shadow: 0 2px 12px rgba(79,70,229,0.08); border: 1px solid #e0e7ff;
    transition: box-shadow 0.2s, transform 0.15s;
}
.welcome-card:hover { box-shadow: 0 6px 24px rgba(79,70,229,0.14); transform: translateY(-2px); }
.welcome-card-num {
    width: 36px; height: 36px;
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    color: #fff; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-weight: 900; font-size: 16px; margin-bottom: 14px;
    box-shadow: 0 4px 12px rgba(79,70,229,0.3);
}
.welcome-card-title { font-size: 14px; font-weight: 700; color: #1e1b4b; margin-bottom: 6px; }
.welcome-card-desc  { font-size: 12.5px; color: #6b7280; line-height: 1.6; }
.welcome-card-tag {
    display: inline-block; margin-top: 10px;
    font-size: 11px; font-weight: 600; padding: 2px 10px; border-radius: 12px;
    background: #ede9fe; color: #4f46e5;
}

/* ═══════════════════════════════════════════════════════════════════════════
   MISCELLANEOUS IMPROVEMENTS
═══════════════════════════════════════════════════════════════════════════ */
/* Plotly charts – remove white gap at bottom */
.js-plotly-plot .plotly { border-radius: 10px; }
/* Streamlit spinner */
[data-testid="stSpinner"] { color: #4f46e5 !important; }
/* Selectbox */
[data-baseweb="select"] [data-baseweb="popover"] {
    border-radius: 10px !important;
    border: 1px solid #e0e7ff !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.12) !important;
}
/* Caption text */
.stCaption { font-size: 12px !important; color: #9ca3af !important; }
/* HR divider */
hr { border-color: #e0e7ff !important; margin: 20px 0 !important; }

/* Phase 2: smooth section transitions */
.stTabs [data-baseweb="tab-panel"] > div { animation: fadeIn 0.25s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Module-level cached functions
# (MUST be at module level — @st.cache_data inside a function creates a new
#  cache object on every rerun, completely defeating caching)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _load_ads(file):
    """Parse Amazon Ads report + extract metrics. Cached by file identity."""
    df      = parse_amazon_ads_report(file)
    metrics = extract_ads_metrics(df)
    return df, metrics


@st.cache_data(show_spinner=False)
def _load_vendor(file):
    """Parse Vendor Central report + extract metrics. Cached by file identity."""
    df      = parse_vendor_central_report(file)
    metrics = extract_vendor_metrics(df)
    return df, metrics


@st.cache_data(show_spinner=False)
def _compute_breakdowns(ads_df, vendor_df):
    """All heavy breakdown computations in one cached call."""
    _ads = ads_df    if ads_df    is not None else pd.DataFrame()
    _ven = vendor_df if vendor_df is not None else None
    return {
        "campaign_df":    campaign_breakdown(_ads),
        "asin_ads_df":    asin_ads_breakdown(_ads),
        "asin_vendor_df": asin_vendor_breakdown(_ven) if _ven is not None else pd.DataFrame(),
        "st_insights":    search_term_analysis(_ads),
        "wasted":         wasted_spend_summary(_ads),
        "match_df":       match_type_analysis(_ads),
        "prod_intel":     product_intelligence(_ads),
        "bid_df":         bid_strategy_analysis(_ads),
        "ad_prod_df":     ad_product_analysis(_ads),
        "trend_df":       build_trend_df(_ads, freq="M"),
        "prod_trend_df":  ad_product_trend(_ads, freq="M"),
    }


@st.cache_data(show_spinner=False)
def _cached_merge_asin(asin_ads_df, asin_vendor_df):
    return merge_asin_view(asin_ads_df, asin_vendor_df)


@st.cache_data(show_spinner=False)
def _cached_trend_summary(trend_df):
    return trend_summary(trend_df)


# ---------------------------------------------------------------------------
# Sidebar — Upload & Settings
# ---------------------------------------------------------------------------

def sidebar():
    st.sidebar.markdown("""
    <div style="padding:20px 4px 16px; text-align:center;">
        <div style="font-size:11px;font-weight:700;color:rgba(255,255,255,0.35);
                    letter-spacing:2px;text-transform:uppercase;margin-bottom:8px;">
            Amazon Intelligence
        </div>
        <div style="font-size:21px;font-weight:900;color:#ffffff;letter-spacing:-0.5px;line-height:1.2;">
            📊 Media Plan<br>
            <span style="background:linear-gradient(90deg,#818cf8,#f97316);
                         -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                         font-size:22px;">Forecast Engine</span>
        </div>
        <div style="width:40px;height:2px;background:linear-gradient(90deg,#4f46e5,#f97316);
                    margin:12px auto 0;border-radius:2px;"></div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("---")

    # ── Upload section ──────────────────────────────────────────────────
    st.sidebar.markdown("""
    <div style="font-size:10px;font-weight:700;color:rgba(255,255,255,0.4);
                letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px;padding-left:2px;">
        📤 Upload Reports
    </div>""", unsafe_allow_html=True)

    st.sidebar.markdown(
        "<p style='color:#c7d2fe;font-size:12px;font-weight:600;margin-bottom:4px;'>Amazon Advertising Report</p>",
        unsafe_allow_html=True,
    )
    ads_file = st.sidebar.file_uploader(
        "Amazon Advertising Report",
        type=["csv", "xlsx", "xls"],
        help="Export from Amazon Ads Console: Campaign Manager → Reports (up to 2GB)",
        label_visibility="collapsed",
    )

    st.sidebar.markdown(
        "<p style='color:#c7d2fe;font-size:12px;font-weight:600;margin-bottom:4px;margin-top:10px;'>Vendor Central ASIN Sales Report</p>",
        unsafe_allow_html=True,
    )
    vendor_file = st.sidebar.file_uploader(
        "Vendor Central ASIN Sales Report",
        type=["csv", "xlsx", "xls"],
        help="Export from Vendor Central → Analytics → Sales Diagnostics (up to 2GB)",
        label_visibility="collapsed",
    )

    st.sidebar.markdown("---")

    # ── Forecast settings ───────────────────────────────────────────────
    st.sidebar.markdown("""
    <div style="font-size:10px;font-weight:700;color:rgba(255,255,255,0.4);
                letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px;padding-left:2px;">
        ⚙️ Forecast Settings
    </div>""", unsafe_allow_html=True)

    growth_options = st.sidebar.multiselect(
        "Growth Scenarios",
        options=[5, 10, 15, 20, 25, 30, 40, 50],
        default=[10, 20, 30],
        help="Select one or more growth targets to model",
    )
    custom_growth = st.sidebar.number_input(
        "Custom Growth % (optional)",
        min_value=0, max_value=200, value=0, step=1,
        help="Add a custom growth scenario",
    )
    if custom_growth > 0 and custom_growth not in growth_options:
        growth_options = sorted(list(set(growth_options + [custom_growth])))
    if not growth_options:
        growth_options = [10]

    st.sidebar.markdown("---")

    # ── Channel split ───────────────────────────────────────────────────
    st.sidebar.markdown("""
    <div style="font-size:10px;font-weight:700;color:rgba(255,255,255,0.4);
                letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px;padding-left:2px;">
        🎯 Channel Budget Split
    </div>""", unsafe_allow_html=True)

    sp_pct = st.sidebar.slider("Sponsored Products %", 0, 100, 65)
    sb_pct = st.sidebar.slider("Sponsored Brands %",   0, 100, 25)
    sd_pct = st.sidebar.slider("Sponsored Display %",  0, 100, 10)

    _total = sp_pct + sb_pct + sd_pct
    if _total == 0:
        sp_w, sb_w, sd_w = 0.65, 0.25, 0.10
    else:
        sp_w = sp_pct / _total
        sb_w = sb_pct / _total
        sd_w = sd_pct / _total

    # Visual split bar
    st.sidebar.markdown(f"""
    <div style="margin:6px 0 12px;background:rgba(255,255,255,0.08);border-radius:8px;overflow:hidden;height:8px;display:flex;">
        <div style="width:{sp_w*100:.0f}%;background:#4f46e5;"></div>
        <div style="width:{sb_w*100:.0f}%;background:#f97316;"></div>
        <div style="width:{sd_w*100:.0f}%;background:#10b981;"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:11px;color:rgba(255,255,255,0.5);">
        <span>SP {sp_w*100:.0f}%</span><span>SB {sb_w*100:.0f}%</span><span>SD {sd_w*100:.0f}%</span>
    </div>
    """, unsafe_allow_html=True)

    channel_split = {
        "Sponsored Products": sp_w,
        "Sponsored Brands":   sb_w,
        "Sponsored Display":  sd_w,
    }

    st.sidebar.markdown("---")

    # ── Custom targets ──────────────────────────────────────────────────
    st.sidebar.markdown("""
    <div style="font-size:10px;font-weight:700;color:rgba(255,255,255,0.4);
                letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px;padding-left:2px;">
        🎯 Custom Scenario Targets
    </div>
    <div style="font-size:11.5px;color:rgba(255,255,255,0.45);margin-bottom:10px;line-height:1.5;">
        Leave at 0 to use growth % math. Set any value to pin that metric.
    </div>""", unsafe_allow_html=True)

    custom_target_revenue = st.sidebar.number_input(
        "Target Revenue / OPS ($)", min_value=0.0, value=0.0, step=10000.0,
        format="%.0f", help="Pin the exact total ordered revenue you want to hit",
    )
    custom_ad_spend = st.sidebar.number_input(
        "Target Ad Spend ($)", min_value=0.0, value=0.0, step=1000.0,
        format="%.0f", help="Pin the total ad budget you want to run with",
    )
    custom_ad_sales = st.sidebar.number_input(
        "Target Ad Sales ($)", min_value=0.0, value=0.0, step=10000.0,
        format="%.0f", help="Pin the ad-attributed sales you expect",
    )
    custom_roas = st.sidebar.number_input(
        "Target ROAS", min_value=0.0, value=0.0, step=0.1,
        format="%.2f", help="Pin the ROAS you want to achieve",
    )
    custom_tacos = st.sidebar.number_input(
        "Target TACOS (%)", min_value=0.0, value=0.0, step=0.5,
        format="%.2f", help="Pin the TACOS %",
    )

    custom_targets = {
        "target_revenue": custom_target_revenue if custom_target_revenue > 0 else None,
        "ad_spend":       custom_ad_spend       if custom_ad_spend       > 0 else None,
        "ad_sales":       custom_ad_sales       if custom_ad_sales       > 0 else None,
        "roas":           custom_roas           if custom_roas           > 0 else None,
        "tacos":          custom_tacos          if custom_tacos          > 0 else None,
    }

    return ads_file, vendor_file, growth_options, channel_split, custom_targets


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # ── Header ─────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="tool-header">
        <div class="tool-header-left">
            <div class="tool-header-title">📊 Amazon Media Plan Forecast Engine</div>
            <div class="tool-header-sub">
                Upload your reports &nbsp;·&nbsp; Analyse performance &nbsp;·&nbsp; Plan for growth
            </div>
        </div>
        <div class="tool-header-right">
            <span class="tool-header-status">🔴 Live</span>
            <span class="tool-header-badge">Media Intelligence</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    ads_file, vendor_file, growth_options, channel_split, custom_targets = sidebar()

    # ── Welcome screen ──────────────────────────────────────────────────────
    if not ads_file and not vendor_file:
        st.markdown("""
        <div class="welcome-hero">
            <div class="welcome-title">👋 Welcome to the Forecast Engine</div>
            <div class="welcome-subtitle">
                Upload your Amazon Advertising and Vendor Central reports to instantly unlock
                performance insights, growth scenario modelling, and a downloadable media plan.
            </div>
        </div>

        <div class="welcome-grid">
            <div class="welcome-card">
                <div class="welcome-card-num">1</div>
                <div class="welcome-card-title">Upload Amazon Ads Report</div>
                <div class="welcome-card-desc">
                    Export from Ads Console → Campaign Manager → Reports.
                    Supports CSV &amp; XLSX up to 2GB.
                </div>
                <span class="welcome-card-tag">SP · SB · SD campaigns</span>
            </div>
            <div class="welcome-card">
                <div class="welcome-card-num">2</div>
                <div class="welcome-card-title">Upload Vendor Central Report</div>
                <div class="welcome-card-desc">
                    Export from Vendor Central → Analytics → Sales Diagnostics.
                    Unlocks TACOS and total revenue metrics.
                </div>
                <span class="welcome-card-tag">Ordered revenue · Units</span>
            </div>
            <div class="welcome-card">
                <div class="welcome-card-num">3</div>
                <div class="welcome-card-title">6 Insight Tabs Instantly</div>
                <div class="welcome-card-desc">
                    Key Metrics · Product Intelligence · Trend Analysis ·
                    Forecast &amp; Media Plan · Recommendations · How It Works.
                </div>
                <span class="welcome-card-tag">ACOS · ROAS · TACOS</span>
            </div>
            <div class="welcome-card">
                <div class="welcome-card-num">4</div>
                <div class="welcome-card-title">Model Growth Scenarios</div>
                <div class="welcome-card-desc">
                    +10%, +20%, +30% and fully custom — get recommended ad spend,
                    channel allocation, and per-campaign budget actions.
                </div>
                <span class="welcome-card-tag">Scenario planning</span>
            </div>
            <div class="welcome-card">
                <div class="welcome-card-num">5</div>
                <div class="welcome-card-title">Monthly Media Plan</div>
                <div class="welcome-card-desc">
                    12-month spend calendar with event multipliers for Prime Day,
                    Black Friday, Holiday Season, and more.
                </div>
                <span class="welcome-card-tag">Seasonal uplift calendar</span>
            </div>
            <div class="welcome-card">
                <div class="welcome-card-num">6</div>
                <div class="welcome-card-title">Download Excel Media Plan</div>
                <div class="welcome-card-desc">
                    5-sheet workbook: Executive Summary, Scenarios,
                    Campaign Recommendations, Campaign Performance, ASIN Analysis.
                </div>
                <span class="welcome-card-tag">Board-ready export</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="tool-footer">
            <div class="footer-logo">Amazon Media Plan Forecast Engine</div><br>
            Created by <strong>Sumeet Mangotra</strong> &nbsp;·&nbsp; Brand Ecommerce Manager
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Parse files ─────────────────────────────────────────────────────────
    ads_df       = None
    vendor_df    = None
    ads_metrics  = {}
    vendor_metrics = {}

    with st.spinner("📂 Reading and parsing reports — large files may take 30–60 seconds..."):
        if ads_file:
            try:
                ads_df, ads_metrics = _load_ads(ads_file)
                missing = validate_ads_report(ads_df)
                if missing:
                    st.warning(f"Amazon Ads report is missing columns: {missing}. Metrics may be partial.")
                else:
                    st.success(f"✅ Amazon Ads report loaded — {len(ads_df):,} rows, {len(ads_df.columns)} columns")
                if len(ads_df) > 500_000:
                    st.info(f"ℹ️ Large report ({len(ads_df):,} rows) — processing may take a moment.")
            except Exception as e:
                st.error(f"Error reading Amazon Ads report: {e}")
                ads_df = None

        if vendor_file:
            try:
                vendor_df, vendor_metrics = _load_vendor(vendor_file)
                missing_v = validate_vendor_report(vendor_df)
                if missing_v:
                    st.warning(f"Vendor Central report is missing columns: {missing_v}. Metrics may be partial.")
                else:
                    st.success(f"✅ Vendor Central report loaded — {len(vendor_df):,} rows, {len(vendor_df.columns)} columns")
            except Exception as e:
                st.error(f"Error reading Vendor Central report: {e}")
                vendor_df = None

    if ads_df is None and vendor_df is None:
        st.error("Could not load any reports. Please check file formats and try again.")
        return

    # ── Pre-compute breakdowns ──────────────────────────────────────────────
    bd             = _compute_breakdowns(ads_df, vendor_df)
    campaign_df    = bd["campaign_df"]
    asin_ads_df    = bd["asin_ads_df"]
    asin_vendor_df = bd["asin_vendor_df"]
    merged_asin_df = _cached_merge_asin(asin_ads_df, asin_vendor_df)
    match_df       = bd["match_df"]
    prod_intel     = bd["prod_intel"]
    bid_df         = bd["bid_df"]
    ad_prod_df     = bd["ad_prod_df"]
    trend_df       = bd["trend_df"]
    t_summary      = _cached_trend_summary(trend_df)
    prod_trend_df  = bd["prod_trend_df"]

    # ── Tabs ────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Key Metrics",
        "📦 Product Intelligence",
        "📅 Trend Analysis",
        "📈 Forecast & Media Plan",
        "💡 Recommendations",
        "⚙️ How It Works",
    ])

    with tab1:
        render_metrics_dashboard(ads_metrics, vendor_metrics)

    with tab2:
        render_product_tab(prod_intel, ad_prod_df, bid_df, match_df)

    with tab3:
        render_trend_tab(trend_df, t_summary, prod_trend_df)

    scenarios = []
    with tab4:
        if ads_df is not None or vendor_df is not None:
            scenarios = render_forecast(
                ads_metrics, vendor_metrics, campaign_df, growth_options, channel_split,
                trend_df=trend_df, custom_targets=custom_targets,
            )

    with tab5:
        render_recommendations(ads_metrics, vendor_metrics, scenarios)

    with tab6:
        render_logic_tab()

    # ── Download ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📥 Download Full Media Plan")
    col_dl, col_info = st.columns([1, 3])
    with col_dl:
        try:
            excel_bytes = build_excel_media_plan(
                ads_metrics=ads_metrics,
                vendor_metrics=vendor_metrics,
                scenarios=scenarios if scenarios else [],
                campaign_df=campaign_df,
                asin_merged_df=merged_asin_df,
            )
            st.download_button(
                label="⬇️  Download Excel Media Plan",
                data=excel_bytes,
                file_name="media_plan_forecast.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.error(f"Could not generate Excel export: {e}")

    with col_info:
        st.markdown("""
        The downloaded workbook includes:
        - **Executive Summary** — all key metrics at a glance
        - **Scenarios Sheet** — full scenario comparison table
        - **Campaign Recommendations** — per-campaign budget actions
        - **Campaign Performance** — detailed campaign data
        - **ASIN Analysis** — blended ads + vendor view per ASIN
        """)

    # ── Footer ───────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="tool-footer">
        <div class="footer-logo">Amazon Media Plan Forecast Engine</div><br>
        Created by <strong>Sumeet Mangotra</strong> &nbsp;·&nbsp; Brand Ecommerce Manager
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
