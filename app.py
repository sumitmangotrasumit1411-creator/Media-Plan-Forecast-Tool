"""
app.py — Amazon Media Plan Forecast Engine
Streamlit application entry point.

Architecture (Phase 1 refactor):
  ├── CSS + page config (this file)
  ├── Module-level @st.cache_data functions (this file)
  ├── sidebar() — upload + settings (this file)
  ├── main() — tab orchestration (this file)
  └── pages/
      ├── tab_metrics.py        — render_metrics_dashboard()
      ├── tab_product.py        — render_product_tab()
      ├── tab_trend.py          — render_trend_tab()
      ├── tab_forecast.py       — render_forecast()
      ├── tab_recommendations.py — render_recommendations()
      └── tab_logic.py          — render_logic_tab()
"""

import streamlit as st
import pandas as pd

from parser import parse_amazon_ads_report, parse_vendor_central_report, validate_ads_report, validate_vendor_report
from metrics import (
    extract_ads_metrics,
    extract_vendor_metrics,
    campaign_breakdown,
    asin_ads_breakdown,
    asin_vendor_breakdown,
    merge_asin_view,
)
from exporter import build_excel_media_plan
from insights import (
    search_term_analysis,
    wasted_spend_summary,
    match_type_analysis,
    product_intelligence,
    bid_strategy_analysis,
    ad_product_analysis,
)
from trends import build_trend_df, trend_summary, ad_product_trend

from pages.tab_metrics        import render_metrics_dashboard
from pages.tab_product        import render_product_tab
from pages.tab_trend          import render_trend_tab
from pages.tab_forecast       import render_forecast
from pages.tab_recommendations import render_recommendations
from pages.tab_logic          import render_logic_tab

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
# Global CSS — Indigo + Orange palette
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* ── Global font & size boost ── */
    html, body, [class*="css"] {
        font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
        font-size: 16px !important;
    }
    p, span, div, li, td, th { font-size: 15px; line-height: 1.7; }
    h1 { font-size: 28px !important; font-weight: 800 !important; }
    h2 { font-size: 22px !important; font-weight: 700 !important; }
    h3 { font-size: 18px !important; font-weight: 700 !important; }
    label, .stSelectbox label, .stMultiSelect label,
    .stSlider label, .stNumberInput label { font-size: 14px !important; font-weight: 600 !important; }

    /* ── Hide Streamlit toolbar clutter ── */
    #MainMenu { visibility: hidden; }
    .stDeployButton { display: none !important; }
    header[data-testid="stHeader"] {
        background: transparent !important;
        box-shadow: none !important;
        height: 0 !important;
        min-height: 0 !important;
    }

    /* ── Sidebar collapsed toggle ── */
    button[data-testid="collapsedControl"] {
        visibility: visible !important;
        display: flex !important;
        width: 52px !important;
        height: 52px !important;
        background: #4f46e5 !important;
        border-radius: 0 12px 12px 0 !important;
        border: none !important;
        box-shadow: 4px 0 18px rgba(79,70,229,0.45) !important;
        position: fixed !important;
        top: 80px !important;
        left: 0 !important;
        z-index: 9999 !important;
        align-items: center !important;
        justify-content: center !important;
    }
    button[data-testid="collapsedControl"] svg {
        fill: #ffffff !important;
        width: 24px !important;
        height: 24px !important;
    }
    button[data-testid="collapsedControl"]:hover {
        background: #f97316 !important;
        box-shadow: 4px 0 22px rgba(249,115,22,0.55) !important;
        width: 58px !important;
    }

    /* ── Page background ── */
    .stApp { background: #f0f2ff !important; }
    .block-container {
        padding-top: 2rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        padding-bottom: 2rem !important;
    }
    .tool-header {
        margin-top: -2rem !important;
        margin-left: -2rem !important;
        margin-right: -2rem !important;
        margin-bottom: 32px !important;
        border-radius: 0 !important;
        padding: 36px 48px !important;
    }

    /* ════════════ SIDEBAR ════════════ */
    [data-testid="stSidebar"] {
        background: linear-gradient(175deg, #1e1b4b 0%, #312e81 100%) !important;
        border-right: 1px solid rgba(79,70,229,0.35) !important;
    }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3 { color: #ffffff !important; }
    [data-testid="stSidebar"] hr {
        border: none !important;
        border-top: 1px solid rgba(255,255,255,0.15) !important;
        margin: 10px 0 !important;
    }
    [data-testid="stSidebar"] input[type="number"],
    [data-testid="stSidebar"] input[type="text"] {
        background: #ffffff !important;
        color: #1e1b4b !important;
        border: 1px solid rgba(255,255,255,0.4) !important;
        border-radius: 6px !important;
    }
    [data-testid="stSidebar"] [data-testid="stNumberInput"] input,
    [data-testid="stSidebar"] [data-baseweb="input"] input {
        background: #ffffff !important;
        color: #1e1b4b !important;
    }
    [data-testid="stSidebar"] [data-testid="stNumberInput"] button,
    [data-testid="stSidebar"] [data-baseweb="input"] ~ div button,
    [data-testid="stSidebar"] [data-testid="stNumberInputStepDown"],
    [data-testid="stSidebar"] [data-testid="stNumberInputStepUp"] {
        background: #4f46e5 !important;
        border: none !important;
        border-radius: 4px !important;
    }
    [data-testid="stSidebar"] [data-testid="stNumberInput"] button svg,
    [data-testid="stSidebar"] [data-testid="stNumberInputStepDown"] svg,
    [data-testid="stSidebar"] [data-testid="stNumberInputStepUp"] svg,
    [data-testid="stSidebar"] [data-testid="stNumberInput"] button svg path,
    [data-testid="stSidebar"] [data-testid="stNumberInputStepDown"] svg path,
    [data-testid="stSidebar"] [data-testid="stNumberInputStepUp"] svg path {
        fill: #ffffff !important;
        stroke: #ffffff !important;
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
        background: rgba(255,255,255,0.96) !important;
        border: 2px dashed rgba(249,115,22,0.7) !important;
        border-radius: 8px !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]:hover {
        border-color: #f97316 !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * {
        color: #1e1b4b !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {
        background: #4f46e5 !important;
        color: #ffffff !important;
        border-radius: 6px !important;
        font-weight: 700 !important;
        font-size: 12px !important;
        padding: 6px 14px !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button * {
        color: #ffffff !important;
    }

    /* ════════════ HEADER BANNER ════════════ */
    .tool-header {
        background: linear-gradient(120deg, #1e1b4b 0%, #4f46e5 60%, #7c3aed 100%);
        padding: 22px 32px;
        border-radius: 14px;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 4px solid #f97316;
        box-shadow: 0 6px 24px rgba(79,70,229,0.22);
    }
    .tool-header-title { font-size: 28px; font-weight: 900; color: #ffffff; letter-spacing: 0.3px; }
    .tool-header-sub   { font-size: 14px; color: rgba(255,255,255,0.7); margin-top: 6px; letter-spacing: 0.2px; }
    .tool-header-badge {
        background: #f97316; color: #ffffff;
        font-size: 13px; font-weight: 700;
        padding: 7px 18px; border-radius: 20px; letter-spacing: 0.3px;
    }

    /* ════════════ METRIC CARDS ════════════ */
    .metric-card {
        background: #ffffff;
        border: 1px solid #e0e7ff;
        border-radius: 12px;
        padding: 18px 20px 14px;
        margin: 6px 0;
        box-shadow: 0 2px 10px rgba(79,70,229,0.08);
        position: relative;
        overflow: hidden;
    }
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 4px;
        background: linear-gradient(90deg, #4f46e5, #f97316);
        border-radius: 12px 12px 0 0;
    }
    .metric-label  { font-size: 11px; color: #6b7280; font-weight: 700; text-transform: uppercase; letter-spacing: 0.9px; margin-bottom: 8px; }
    .metric-value  { font-size: 26px; font-weight: 800; color: #1e1b4b; line-height: 1.2; }
    .metric-delta  { font-size: 12px; color: #f97316; font-weight: 600; margin-top: 6px; }

    /* ════════════ SECTION HEADERS ════════════ */
    .section-header {
        font-size: 17px; font-weight: 800; color: #1e1b4b;
        margin: 32px 0 16px 0; padding: 12px 18px;
        background: linear-gradient(90deg, rgba(79,70,229,0.07) 0%, transparent 100%);
        border-left: 5px solid #f97316;
        border-radius: 0 8px 8px 0; letter-spacing: 0.1px;
    }

    /* ════════════ TABS ════════════ */
    .stTabs [data-baseweb="tab-list"] {
        background: #ffffff;
        border-radius: 10px 10px 0 0;
        padding: 4px 4px 0;
        border-bottom: 2px solid #e0e7ff;
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 14px; font-weight: 600; color: #6b7280;
        padding: 11px 18px; border-radius: 8px 8px 0 0; transition: all 0.15s;
    }
    .stTabs [data-baseweb="tab"]:hover { color: #4f46e5 !important; background: rgba(79,70,229,0.05) !important; }
    .stTabs [aria-selected="true"] {
        color: #4f46e5 !important;
        background: rgba(79,70,229,0.07) !important;
        border-bottom: 3px solid #4f46e5 !important;
        font-weight: 700 !important;
    }
    .stTabs [data-baseweb="tab-panel"] {
        background: #ffffff;
        border-radius: 0 0 12px 12px;
        padding: 20px 4px 4px;
        border: 1px solid #e0e7ff;
        border-top: none;
    }

    /* ════════════ RECO / WARNING CARDS ════════════ */
    .reco-card {
        background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
        border: 1px solid #ddd6fe;
        border-left: 5px solid #4f46e5;
        padding: 14px 18px;
        border-radius: 0 10px 10px 0;
        margin: 10px 0; font-size: 14px; line-height: 1.65;
        box-shadow: 0 2px 6px rgba(79,70,229,0.07);
    }
    .warning-card {
        background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
        border: 1px solid #fed7aa;
        border-left: 5px solid #f97316;
        padding: 14px 18px;
        border-radius: 0 10px 10px 0;
        margin: 10px 0; font-size: 14px; line-height: 1.65;
        box-shadow: 0 2px 6px rgba(249,115,22,0.08);
    }

    /* ════════════ MISC ════════════ */
    [data-testid="stDataFrame"] { border-radius: 10px !important; overflow: hidden !important; box-shadow: 0 2px 8px rgba(79,70,229,0.08) !important; }
    [data-testid="stDownloadButton"] button {
        background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
        color: #ffffff !important; border: none !important;
        border-radius: 8px !important; font-weight: 700 !important;
        font-size: 14px !important; padding: 10px 24px !important;
        box-shadow: 0 4px 14px rgba(79,70,229,0.3) !important;
        transition: all 0.2s !important;
    }
    [data-testid="stDownloadButton"] button:hover {
        box-shadow: 0 6px 20px rgba(79,70,229,0.4) !important;
        transform: translateY(-1px) !important;
    }
    [data-testid="stExpander"]  { border: 1px solid #e0e7ff !important; border-radius: 8px !important; background: #ffffff !important; }
    [data-testid="stAlert"]     { border-radius: 8px !important; font-size: 13px !important; }

    /* ════════════ FOOTER ════════════ */
    .tool-footer {
        margin-top: 48px; padding: 22px 0 14px;
        border-top: 3px solid #4f46e5;
        text-align: center; font-size: 16px; font-weight: 500; color: #374151;
        line-height: 2;
        background: linear-gradient(90deg, rgba(79,70,229,0.04) 0%, transparent 50%, rgba(249,115,22,0.04) 100%);
        border-radius: 0 0 12px 12px; letter-spacing: 0.2px;
    }
    .tool-footer strong { color: #1e1b4b; font-weight: 800; font-size: 17px; }

    /* ════════════ WELCOME BOX ════════════ */
    .welcome-box {
        background: #ffffff; border: 1px solid #e0e7ff; border-radius: 14px;
        padding: 32px 36px; margin: 16px 0;
        box-shadow: 0 4px 16px rgba(79,70,229,0.1);
    }
    .welcome-step {
        display: flex; align-items: flex-start; gap: 16px;
        padding: 12px 0; border-bottom: 1px solid #f3f4f6;
    }
    .welcome-step:last-child { border-bottom: none; }
    .step-icon {
        min-width: 38px; height: 38px;
        background: linear-gradient(135deg, #4f46e5, #f97316);
        color: #fff; border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
        font-weight: 800; font-size: 15px;
        box-shadow: 0 2px 8px rgba(79,70,229,0.25);
    }
    .step-text strong { font-size: 15px; color: #1e1b4b; }
    .step-text span   { font-size: 14px; color: #6b7280; display: block; margin-top: 3px; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Module-level cached functions
# (MUST be at module level — defining @st.cache_data inside a function
#  creates a new cache object on every rerun, completely defeating caching)
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
    """
    All heavy breakdown computations in one cached call.
    Re-runs only when ads_df or vendor_df actually changes.
    """
    _ads = ads_df  if ads_df    is not None else pd.DataFrame()
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
    """Merge ads + vendor ASIN views. Cached separately (small, fast)."""
    return merge_asin_view(asin_ads_df, asin_vendor_df)


@st.cache_data(show_spinner=False)
def _cached_trend_summary(trend_df):
    """Cached trend summary — trend_df only changes when file changes."""
    return trend_summary(trend_df)


# ---------------------------------------------------------------------------
# Sidebar — Upload & Settings
# ---------------------------------------------------------------------------

def sidebar():
    st.sidebar.markdown("""
    <div style="text-align:center; padding:18px 0 14px;">
        <div style="font-size:22px; font-weight:900; color:#ffffff; letter-spacing:1px;">
            📊 Media Plan Engine
        </div>
        <div style="font-size:11px; color:rgba(255,255,255,0.5); margin-top:4px; letter-spacing:0.5px;">
            AMAZON ADVERTISING ANALYTICS
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📤 Upload Reports")
    st.sidebar.markdown("---")

    st.sidebar.markdown(
        "<p style='color:#fff; font-size:13px; font-weight:600; margin-bottom:4px;'>Amazon Advertising Report</p>",
        unsafe_allow_html=True,
    )
    ads_file = st.sidebar.file_uploader(
        "Amazon Advertising Report",
        type=["csv", "xlsx", "xls"],
        help="Export from Amazon Ads Console: Campaign Manager → Reports (up to 2GB)",
        label_visibility="collapsed",
    )

    st.sidebar.markdown(
        "<p style='color:#fff; font-size:13px; font-weight:600; margin-bottom:4px; margin-top:12px;'>Vendor Central ASIN Sales Report</p>",
        unsafe_allow_html=True,
    )
    vendor_file = st.sidebar.file_uploader(
        "Vendor Central ASIN Sales Report",
        type=["csv", "xlsx", "xls"],
        help="Export from Vendor Central → Analytics → Sales Diagnostics (up to 2GB)",
        label_visibility="collapsed",
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ Forecast Settings")

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

    st.sidebar.markdown("### 🎯 Channel Budget Split")
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

    st.sidebar.caption(
        f"Effective split → SP: **{sp_w*100:.1f}%** · SB: **{sb_w*100:.1f}%** · SD: **{sd_w*100:.1f}%**"
        + ("" if _total == 100 else f"  *(normalised from {_total}%)*")
    )

    channel_split = {
        "Sponsored Products": sp_w,
        "Sponsored Brands":   sb_w,
        "Sponsored Display":  sd_w,
    }

    # ---- Custom Target Overrides -------------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎯 Custom Scenario Targets")
    st.sidebar.caption("Enter any target(s) below — leave at 0 to use growth % math instead.")

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
        format="%.2f", help="Pin the ROAS you want to achieve (derives spend from ad sales / ROAS)",
    )
    custom_tacos = st.sidebar.number_input(
        "Target TACOS (%)", min_value=0.0, value=0.0, step=0.5,
        format="%.2f", help="Pin the TACOS % (derives spend from revenue × TACOS%)",
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
        <div>
            <div class="tool-header-title">📊 Amazon Media Plan Forecast Engine</div>
            <div class="tool-header-sub">Upload your reports · Analyse performance · Plan for growth</div>
        </div>
        <div class="tool-header-badge">Media Intelligence</div>
    </div>
    """, unsafe_allow_html=True)

    ads_file, vendor_file, growth_options, channel_split, custom_targets = sidebar()

    # ── Welcome screen ──────────────────────────────────────────────────────
    if not ads_file and not vendor_file:
        st.markdown("""
        <div class="welcome-box">
            <div style="font-size:20px; font-weight:800; color:#1a0a14; margin-bottom:20px;">
                👋 Welcome — Upload your reports to get started
            </div>
            <div class="welcome-step">
                <div class="step-icon">1</div>
                <div class="step-text">
                    <strong>Upload your Amazon Advertising Report</strong>
                    <span>Ads Console → Reports → Sponsored Products / Brands / Display &nbsp;(CSV or XLSX, up to 2GB)</span>
                </div>
            </div>
            <div class="welcome-step">
                <div class="step-icon">2</div>
                <div class="step-text">
                    <strong>Upload your Vendor Central ASIN Sales Report</strong>
                    <span>Vendor Central → Analytics → Sales Diagnostics &nbsp;(CSV or XLSX)</span>
                </div>
            </div>
            <div class="welcome-step">
                <div class="step-icon">3</div>
                <div class="step-text">
                    <strong>Get 6 insight tabs instantly</strong>
                    <span>Key Metrics &nbsp;·&nbsp; Product Intelligence &nbsp;·&nbsp; Trend Analysis &nbsp;·&nbsp; Forecast &amp; Media Plan &nbsp;·&nbsp; Recommendations &nbsp;·&nbsp; How It Works</span>
                </div>
            </div>
            <div class="welcome-step">
                <div class="step-icon">4</div>
                <div class="step-text">
                    <strong>Model growth scenarios</strong>
                    <span>+10%, +20%, +30% and custom — get recommended ad spend, channel split, and per-campaign budget actions</span>
                </div>
            </div>
            <div class="welcome-step">
                <div class="step-icon">5</div>
                <div class="step-text">
                    <strong>Download a full Excel Media Plan</strong>
                    <span>5-sheet workbook — Executive Summary, Scenarios, Campaign Recommendations, Campaign Performance, ASIN Analysis</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div class="tool-footer">
            Amazon Media Plan Forecast Engine &nbsp;&#183;&nbsp;
            Created by <strong>Sumeet Mangotra</strong>, Brand Ecommerce Manager
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Parse files (module-level cache — never re-parsed on slider changes) ──
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

    # ── Pre-compute breakdowns (cached — never re-run on slider changes) ────
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

    # ── Download Excel Media Plan ───────────────────────────────────────────
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
                label="⬇️ Download Excel Media Plan",
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

    # ── Footer ──────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="tool-footer">
        Amazon Media Plan Forecast Engine &nbsp;&#183;&nbsp;
        Created by <strong>Sumeet Mangotra</strong>, Brand Ecommerce Manager
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
