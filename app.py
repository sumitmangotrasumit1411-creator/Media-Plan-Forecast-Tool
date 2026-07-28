"""
app.py — Media Plan Forecast Engine
Streamlit application entry point.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

from parser import parse_amazon_ads_report, parse_vendor_central_report, validate_ads_report, validate_vendor_report
from metrics import (
    extract_ads_metrics,
    extract_vendor_metrics,
    campaign_breakdown,
    asin_ads_breakdown,
    asin_vendor_breakdown,
    merge_asin_view,
)
from forecast import run_multi_scenario, scenarios_to_dataframe, run_forecast, monthly_forecast
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
# Vibrant Palette — Indigo + Orange
# PRIMARY  #4f46e5  |  ACCENT  #f97316  |  BG  #f0f2ff  |  DARK  #1e1b4b
# ---------------------------------------------------------------------------
C_PRIMARY = "#4f46e5"   # vivid indigo
C_ACCENT  = "#f97316"   # warm orange
C_DARK    = "#1e1b4b"   # deep indigo-navy
C_BG      = "#f0f2ff"   # very light lavender page bg
C_WHITE   = "#ffffff"
C_MUTED   = "#6b7280"

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

    /* ── Sidebar collapsed toggle — fixed below browser URL bar ── */
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
    /* ── Header — full-width banner ── */
    .tool-header {
        margin-top: -2rem !important;
        margin-left: -2rem !important;
        margin-right: -2rem !important;
        margin-bottom: 32px !important;
        border-radius: 0 !important;
        padding: 36px 48px !important;
    }

    /* ════════════════════════════════════
       SIDEBAR  — deep indigo
    ════════════════════════════════════ */
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

    /* Number inputs & text inputs — white bg, dark text so value is visible */
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
    /* Step buttons (+/-) on number inputs — button shell */
    [data-testid="stSidebar"] [data-testid="stNumberInput"] button,
    [data-testid="stSidebar"] [data-baseweb="input"] ~ div button,
    [data-testid="stSidebar"] [data-testid="stNumberInputStepDown"],
    [data-testid="stSidebar"] [data-testid="stNumberInputStepUp"] {
        background: #4f46e5 !important;
        border: none !important;
        border-radius: 4px !important;
    }
    /* SVG icons inside the step buttons */
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

    /* File uploader */
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

    /* ════════════════════════════════════
       HEADER BANNER
    ════════════════════════════════════ */
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
    .tool-header-title {
        font-size: 28px;
        font-weight: 900;
        color: #ffffff;
        letter-spacing: 0.3px;
    }
    .tool-header-sub {
        font-size: 14px;
        color: rgba(255,255,255,0.7);
        margin-top: 6px;
        letter-spacing: 0.2px;
    }
    .tool-header-badge {
        background: #f97316;
        color: #ffffff;
        font-size: 13px;
        font-weight: 700;
        padding: 7px 18px;
        border-radius: 20px;
        letter-spacing: 0.3px;
    }

    /* ════════════════════════════════════
       METRIC CARDS
    ════════════════════════════════════ */
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
    .metric-label {
        font-size: 11px;
        color: #6b7280;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.9px;
        margin-bottom: 8px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 800;
        color: #1e1b4b;
        line-height: 1.2;
    }
    .metric-delta {
        font-size: 12px;
        color: #f97316;
        font-weight: 600;
        margin-top: 6px;
    }

    /* ════════════════════════════════════
       SECTION HEADERS
    ════════════════════════════════════ */
    .section-header {
        font-size: 17px;
        font-weight: 800;
        color: #1e1b4b;
        margin: 32px 0 16px 0;
        padding: 12px 18px;
        background: linear-gradient(90deg, rgba(79,70,229,0.07) 0%, transparent 100%);
        border-left: 5px solid #f97316;
        border-radius: 0 8px 8px 0;
        letter-spacing: 0.1px;
    }

    /* ════════════════════════════════════
       TABS
    ════════════════════════════════════ */
    .stTabs [data-baseweb="tab-list"] {
        background: #ffffff;
        border-radius: 10px 10px 0 0;
        padding: 4px 4px 0;
        border-bottom: 2px solid #e0e7ff;
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 14px;
        font-weight: 600;
        color: #6b7280;
        padding: 11px 18px;
        border-radius: 8px 8px 0 0;
        transition: all 0.15s;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #4f46e5 !important;
        background: rgba(79,70,229,0.05) !important;
    }
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

    /* ════════════════════════════════════
       RECOMMENDATION & WARNING CARDS
    ════════════════════════════════════ */
    .reco-card {
        background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
        border: 1px solid #ddd6fe;
        border-left: 5px solid #4f46e5;
        padding: 14px 18px;
        border-radius: 0 10px 10px 0;
        margin: 10px 0;
        font-size: 14px;
        line-height: 1.65;
        box-shadow: 0 2px 6px rgba(79,70,229,0.07);
    }
    .warning-card {
        background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
        border: 1px solid #fed7aa;
        border-left: 5px solid #f97316;
        padding: 14px 18px;
        border-radius: 0 10px 10px 0;
        margin: 10px 0;
        font-size: 14px;
        line-height: 1.65;
        box-shadow: 0 2px 6px rgba(249,115,22,0.08);
    }

    /* ════════════════════════════════════
       DATA TABLES
    ════════════════════════════════════ */
    [data-testid="stDataFrame"] {
        border-radius: 10px !important;
        overflow: hidden !important;
        box-shadow: 0 2px 8px rgba(79,70,229,0.08) !important;
    }

    /* ════════════════════════════════════
       DOWNLOAD BUTTON
    ════════════════════════════════════ */
    [data-testid="stDownloadButton"] button {
        background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        font-size: 14px !important;
        padding: 10px 24px !important;
        box-shadow: 0 4px 14px rgba(79,70,229,0.3) !important;
        transition: all 0.2s !important;
    }
    [data-testid="stDownloadButton"] button:hover {
        box-shadow: 0 6px 20px rgba(79,70,229,0.4) !important;
        transform: translateY(-1px) !important;
    }

    /* ════════════════════════════════════
       EXPANDER
    ════════════════════════════════════ */
    [data-testid="stExpander"] {
        border: 1px solid #e0e7ff !important;
        border-radius: 8px !important;
        background: #ffffff !important;
    }

    /* ════════════════════════════════════
       ALERTS
    ════════════════════════════════════ */
    [data-testid="stAlert"] {
        border-radius: 8px !important;
        font-size: 13px !important;
    }

    /* ════════════════════════════════════
       FOOTER
    ════════════════════════════════════ */
    .tool-footer {
        margin-top: 48px;
        padding: 22px 0 14px;
        border-top: 3px solid #4f46e5;
        text-align: center;
        font-size: 16px;
        font-weight: 500;
        color: #374151;
        line-height: 2;
        background: linear-gradient(90deg, rgba(79,70,229,0.04) 0%, transparent 50%, rgba(249,115,22,0.04) 100%);
        border-radius: 0 0 12px 12px;
        letter-spacing: 0.2px;
    }
    .tool-footer strong { color: #1e1b4b; font-weight: 800; font-size: 17px; }

    /* ════════════════════════════════════
       WELCOME BOX
    ════════════════════════════════════ */
    .welcome-box {
        background: #ffffff;
        border: 1px solid #e0e7ff;
        border-radius: 14px;
        padding: 32px 36px;
        margin: 16px 0;
        box-shadow: 0 4px 16px rgba(79,70,229,0.1);
    }
    .welcome-step {
        display: flex;
        align-items: flex-start;
        gap: 16px;
        padding: 12px 0;
        border-bottom: 1px solid #f3f4f6;
    }
    .welcome-step:last-child { border-bottom: none; }
    .step-icon {
        min-width: 38px; height: 38px;
        background: linear-gradient(135deg, #4f46e5, #f97316);
        color: #fff;
        border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
        font-weight: 800; font-size: 15px;
        box-shadow: 0 2px 8px rgba(79,70,229,0.25);
    }
    .step-text strong { font-size: 15px; color: #1e1b4b; }
    .step-text span { font-size: 14px; color: #6b7280; display: block; margin-top: 3px; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_currency(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"${val:,.2f}"

def fmt_pct(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"{val:.2f}%"

def fmt_num(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"{val:,.0f}"

def metric_card(label, value, delta=None):
    delta_html = f'<div class="metric-delta">{delta}</div>' if delta else ""
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """

def colour_acos(val):
    try:
        v = float(val)
        if v < 20:
            return "color: green"
        elif v < 35:
            return "color: orange"
        else:
            return "color: red"
    except Exception:
        return ""


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
        min_value=0,
        max_value=200,
        value=0,
        step=1,
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

    # Normalise so the three always sum to 100%
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

    # ---- Custom Target Overrides -----------------------------------------
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
        "ad_spend":       custom_ad_spend       if custom_ad_spend > 0       else None,
        "ad_sales":       custom_ad_sales       if custom_ad_sales > 0       else None,
        "roas":           custom_roas           if custom_roas > 0           else None,
        "tacos":          custom_tacos          if custom_tacos > 0          else None,
    }

    return ads_file, vendor_file, growth_options, channel_split, custom_targets


# ---------------------------------------------------------------------------
# Tab 1 — Key Metrics Dashboard
# ---------------------------------------------------------------------------

def render_metrics_dashboard(ads_metrics, vendor_metrics):
    st.markdown('<div class="section-header">📊 Amazon Advertising Metrics</div>', unsafe_allow_html=True)

    cols = st.columns(4)
    roas_val = ads_metrics.get("overall_roas")
    kpis_ads = [
        ("Total Ad Spend", fmt_currency(ads_metrics.get("total_spend")), None),
        ("Ad-Attributed Sales", fmt_currency(ads_metrics.get("total_ad_sales")), None),
        ("Overall ACOS", fmt_pct(ads_metrics.get("overall_acos")), "Lower is better"),
        ("Overall ROAS", f"{roas_val:.2f}x" if roas_val else "N/A", "Higher is better"),
        ("Total Impressions", fmt_num(ads_metrics.get("total_impressions")), None),
        ("Total Clicks", fmt_num(ads_metrics.get("total_clicks")), None),
        ("CTR", fmt_pct(ads_metrics.get("overall_ctr")), None),
        ("CPC", fmt_currency(ads_metrics.get("overall_cpc")), None),
        ("Total Ad Orders", fmt_num(ads_metrics.get("total_ad_orders")), None),
        ("Conversion Rate", fmt_pct(ads_metrics.get("conversion_rate")), "Click → Purchase"),
        ("New to Brand %", fmt_pct(ads_metrics.get("ntb_order_pct")), "First-time buyers"),
        ("Cost per Order", fmt_currency(ads_metrics.get("cost_per_order")), None),
    ]
    for i, (label, val, delta) in enumerate(kpis_ads):
        with cols[i % 4]:
            st.markdown(metric_card(label, val, delta), unsafe_allow_html=True)

    if vendor_metrics:
        st.markdown('<div class="section-header">🏪 Vendor Central Sales Metrics</div>', unsafe_allow_html=True)
        cols2 = st.columns(4)
        kpis_vendor = [
            ("Total Ordered Revenue", fmt_currency(vendor_metrics.get("total_ordered_revenue")), None),
            ("Total Shipped Revenue", fmt_currency(vendor_metrics.get("total_shipped_revenue")), None),
            ("Total Ordered Units", fmt_num(vendor_metrics.get("total_ordered_units")), None),
            ("Avg Selling Price", fmt_currency(vendor_metrics.get("avg_selling_price")), None),
        ]
        for i, (label, val, delta) in enumerate(kpis_vendor):
            with cols2[i % 4]:
                st.markdown(metric_card(label, val, delta), unsafe_allow_html=True)

    # ACOS gauge
    acos_val = ads_metrics.get("overall_acos")
    roas_val = ads_metrics.get("overall_roas")

    if acos_val is not None or roas_val is not None:
        st.markdown('<div class="section-header">📈 Performance Gauges</div>', unsafe_allow_html=True)
        gcols = st.columns(2)

        if acos_val is not None:
            with gcols[0]:
                fig = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=acos_val,
                    title={"text": "ACOS (%)"},
                    delta={"reference": 25, "decreasing": {"color": "green"}, "increasing": {"color": "red"}},
                    gauge={
                        "axis": {"range": [0, 80]},
                        "bar": {"color": "#293C5B"},
                        "steps": [
                            {"range": [0, 20], "color": "#d1fae5"},
                            {"range": [20, 35], "color": "#fef3c7"},
                            {"range": [35, 80], "color": "#fee2e2"},
                        ],
                        "threshold": {"line": {"color": "red", "width": 2}, "thickness": 0.75, "value": 35},
                    },
                ))
                fig.update_layout(height=280, margin=dict(t=40, b=10, l=20, r=20))
                st.plotly_chart(fig, use_container_width=True)

        if roas_val is not None:
            with gcols[1]:
                fig2 = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=roas_val,
                    title={"text": "ROAS"},
                    delta={"reference": 4, "increasing": {"color": "green"}, "decreasing": {"color": "red"}},
                    gauge={
                        "axis": {"range": [0, 10]},
                        "bar": {"color": "#e71d36"},
                        "steps": [
                            {"range": [0, 2], "color": "#fee2e2"},
                            {"range": [2, 4], "color": "#fef3c7"},
                            {"range": [4, 10], "color": "#d1fae5"},
                        ],
                        "threshold": {"line": {"color": "green", "width": 2}, "thickness": 0.75, "value": 4},
                    },
                ))
                fig2.update_layout(height=280, margin=dict(t=40, b=10, l=20, r=20))
                st.plotly_chart(fig2, use_container_width=True)


# ---------------------------------------------------------------------------
# Tab 2 — Campaign & ASIN Analysis
# ---------------------------------------------------------------------------

def render_campaign_analysis(ads_df, vendor_df):
    camp_df = campaign_breakdown(ads_df)
    asin_ads_df = asin_ads_breakdown(ads_df)
    asin_vendor_df = asin_vendor_breakdown(vendor_df) if vendor_df is not None else pd.DataFrame()
    merged_asin_df = merge_asin_view(asin_ads_df, asin_vendor_df)

    if not camp_df.empty:
        st.markdown('<div class="section-header">🏆 Campaign Performance Breakdown</div>', unsafe_allow_html=True)

        # Bar chart: spend vs sales
        name_col = camp_df.columns[0]
        top10 = camp_df.head(10)

        chart_cols = [c for c in ["spend", "ad_sales"] if c in top10.columns]
        if chart_cols:
            fig = go.Figure()
            if "spend" in top10.columns:
                fig.add_trace(go.Bar(x=top10[name_col], y=top10["spend"], name="Ad Spend", marker_color="#4f46e5"))
            if "ad_sales" in top10.columns:
                fig.add_trace(go.Bar(x=top10[name_col], y=top10["ad_sales"], name="Ad Sales", marker_color="#f97316"))
            fig.update_layout(
                barmode="group", title="Top 10 Campaigns: Spend vs Sales",
                xaxis_tickangle=-35, height=380,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=60, b=80),
            )
            st.plotly_chart(fig, use_container_width=True)

        # ACOS scatter
        if "acos_%" in camp_df.columns and "spend" in camp_df.columns:
            fig2 = px.scatter(
                camp_df.head(20),
                x="spend", y="acos_%",
                size="spend" if "spend" in camp_df.columns else None,
                color="roas" if "roas" in camp_df.columns else None,
                hover_name=name_col,
                title="Campaign ACOS vs Spend (bubble = spend size)",
                labels={"spend": "Ad Spend ($)", "acos_%": "ACOS (%)"},
                color_continuous_scale="RdYlGn_r",
            )
            fig2.add_hline(y=25, line_dash="dash", line_color="orange", annotation_text="25% ACOS benchmark")
            fig2.update_layout(height=380, margin=dict(t=60))
            st.plotly_chart(fig2, use_container_width=True)

        # Table
        display_cols = [c for c in [name_col, "spend", "ad_sales", "acos_%", "roas", "cpc", "impressions", "clicks"] if c in camp_df.columns]
        styled = camp_df[display_cols].head(20).copy()
        styled.columns = [c.replace("_", " ").title() for c in styled.columns]
        st.dataframe(styled, use_container_width=True, height=320)

    if not merged_asin_df.empty:
        st.markdown('<div class="section-header">🔍 ASIN-Level Analysis</div>', unsafe_allow_html=True)

        display_cols = [c for c in ["asin", "product_title", "ordered_revenue", "spend", "ad_sales", "tacos_%", "acos_%", "roas", "ordered_units"] if c in merged_asin_df.columns]
        display_df = merged_asin_df[display_cols].head(30).copy()
        display_df.columns = [c.replace("_", " ").replace("%", "Pct").title() for c in display_df.columns]
        st.dataframe(display_df, use_container_width=True, height=360)

    return camp_df, merged_asin_df


# ---------------------------------------------------------------------------
# Tab 3 — Forecast & Media Plan
# ---------------------------------------------------------------------------

def render_forecast(ads_metrics, vendor_metrics, campaign_df, growth_options, channel_split, trend_df=None, custom_targets=None):
    total_ordered_revenue = vendor_metrics.get("total_ordered_revenue", 0) if vendor_metrics else 0
    total_ad_spend = ads_metrics.get("total_spend", 0)
    total_ad_sales = ads_metrics.get("total_ad_sales", 0)

    # Use ads-attributed sales as revenue fallback if no vendor data
    baseline_revenue = total_ordered_revenue if total_ordered_revenue > 0 else total_ad_sales

    if baseline_revenue == 0:
        st.warning("No revenue data found. Please check your reports.")
        return []

    ct = custom_targets or {}

    # ---- Run growth-% scenarios
    scenarios = run_multi_scenario(
        total_ordered_revenue=baseline_revenue,
        total_ad_spend=total_ad_spend,
        total_ad_sales=total_ad_sales,
        growth_scenarios=growth_options,
        custom_channel_split=channel_split,
        campaign_df=campaign_df if campaign_df is not None and not campaign_df.empty else None,
    )

    # ---- Run custom scenario if any override is set
    custom_scenario = None
    has_custom = any(v is not None for v in ct.values())
    if has_custom:
        custom_scenario = run_forecast(
            total_ordered_revenue=baseline_revenue,
            total_ad_spend=total_ad_spend,
            total_ad_sales=total_ad_sales,
            growth_pct=0,
            custom_channel_split=channel_split,
            campaign_df=campaign_df if campaign_df is not None and not campaign_df.empty else None,
            override_target_revenue=ct.get("target_revenue"),
            override_ad_spend=ct.get("ad_spend"),
            override_ad_sales=ct.get("ad_sales"),
            override_roas=ct.get("roas"),
            override_tacos=ct.get("tacos"),
        )

        # Show which inputs drove the custom scenario
        active = [k for k, v in ct.items() if v is not None]
        label_map = {
            "target_revenue": "Target Revenue",
            "ad_spend": "Ad Spend",
            "ad_sales": "Ad Sales",
            "roas": "ROAS",
            "tacos": "TACOS %",
        }
        active_labels = " · ".join(label_map[k] for k in active)
        st.info(f"🎯 **Custom scenario active** — pinned inputs: **{active_labels}**. All other metrics derived automatically.")

    # ---- Dynamic Impact Panel — shown whenever custom targets OR channel split changes
    # Always render this so channel-split-only changes are also visible
    active_spend = custom_scenario["recommended_spend"] if custom_scenario else total_ad_spend
    active_sales = custom_scenario["target_ad_sales"]   if custom_scenario else total_ad_sales
    active_rev   = custom_scenario["target_revenue"]    if custom_scenario else baseline_revenue
    active_acos  = custom_scenario["projected_acos_pct"] if custom_scenario else (ads_metrics.get("overall_acos") or 0)
    active_roas  = custom_scenario["projected_roas"]     if custom_scenario else (ads_metrics.get("overall_roas") or 0)
    active_tacos = custom_scenario["projected_tacos_pct"] if custom_scenario else 0

    # Derive secondary metrics proportionally from spend ratio
    spend_ratio  = (active_spend / total_ad_spend) if total_ad_spend > 0 else 1.0
    curr_clicks  = ads_metrics.get("total_clicks", 0) or 0
    curr_impr    = ads_metrics.get("total_impressions", 0) or 0
    curr_orders  = ads_metrics.get("total_ad_orders", 0) or 0
    curr_cpc     = ads_metrics.get("overall_cpc") or 0
    curr_ctr     = ads_metrics.get("overall_ctr") or 0
    curr_cvr     = ads_metrics.get("conversion_rate") or 0

    # More spend → more impressions/clicks (linear), CPC stays same, CVR stays same
    proj_clicks  = round(curr_clicks  * spend_ratio)
    proj_impr    = round(curr_impr    * spend_ratio)
    proj_orders  = round(curr_orders  * spend_ratio)
    proj_cpc     = curr_cpc   # CPC driven by bids/competition, not our spend level
    proj_ctr     = curr_ctr   # CTR driven by creative/listing, not spend
    proj_cvr     = curr_cvr   # CVR driven by listing quality, not spend

    # Channel allocation for the active scenario
    active_alloc = custom_scenario["channel_allocation"] if custom_scenario else {
        ch: {"budget": round(active_spend * w, 2), "share_pct": round(w * 100, 1)}
        for ch, w in channel_split.items()
    }

    def _delta_html(new_val, old_val, fmt_fn, higher_is_better=True, is_pct_metric=False):
        """Return coloured delta HTML string."""
        if old_val is None or old_val == 0:
            return ""
        delta = new_val - old_val
        pct   = delta / abs(old_val) * 100
        good  = (delta > 0) == higher_is_better
        color = "#10b981" if good else "#dc2626"
        arrow = "▲" if delta > 0 else "▼"
        sign  = "+" if delta > 0 else ""
        if is_pct_metric:
            return f'<span style="color:{color};font-size:12px;">{arrow} {sign}{delta:.2f}pp</span>'
        return f'<span style="color:{color};font-size:12px;">{arrow} {sign}{pct:.1f}%</span>'

    def _metric_tile(label, curr, proj, fmt_fn, higher_is_better=True, is_pct_metric=False, unit=""):
        delta_html = _delta_html(proj, curr, fmt_fn, higher_is_better, is_pct_metric)
        changed = abs(proj - (curr or 0)) > 0.001 if curr else False
        border = "#4f46e5" if changed else "#e5e7eb"
        return f"""
        <div style="background:#ffffff;border:2px solid {border};border-radius:10px;
                    padding:14px 16px;box-shadow:0 2px 8px rgba(0,0,0,0.05);">
            <div style="font-size:11px;font-weight:700;color:#6b7280;letter-spacing:.5px;margin-bottom:4px;">{label}</div>
            <div style="display:flex;align-items:baseline;gap:10px;">
                <div>
                    <div style="font-size:11px;color:#9ca3af;">Current</div>
                    <div style="font-size:16px;font-weight:700;color:#374151;">{fmt_fn(curr)}</div>
                </div>
                <div style="font-size:18px;color:#9ca3af;">→</div>
                <div>
                    <div style="font-size:11px;color:#4f46e5;font-weight:700;">Projected</div>
                    <div style="font-size:20px;font-weight:900;color:#1e1b4b;">{fmt_fn(proj)}{unit}</div>
                </div>
                <div style="margin-left:auto;">{delta_html}</div>
            </div>
        </div>"""

    st.markdown('<div class="section-header">⚡ Live Impact Dashboard — All Metrics Updated</div>', unsafe_allow_html=True)
    st.caption("Every metric below updates instantly when you change Custom Targets or Channel Budget Split in the sidebar.")

    r1 = st.columns(4)
    r1[0].markdown(_metric_tile("💰 Ad Spend",        total_ad_spend, active_spend,  fmt_currency, True),  unsafe_allow_html=True)
    r1[1].markdown(_metric_tile("📈 Ad Sales",        total_ad_sales, active_sales,  fmt_currency, True),  unsafe_allow_html=True)
    r1[2].markdown(_metric_tile("🏪 Total Revenue",   baseline_revenue, active_rev,  fmt_currency, True),  unsafe_allow_html=True)
    r1[3].markdown(_metric_tile("💹 Revenue Gap",     0, active_rev - baseline_revenue, fmt_currency, True), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
    r2 = st.columns(4)
    r2[0].markdown(_metric_tile("🎯 ACOS",     ads_metrics.get("overall_acos") or 0, active_acos, fmt_pct, False, True),  unsafe_allow_html=True)
    r2[1].markdown(_metric_tile("⚡ ROAS",     ads_metrics.get("overall_roas") or 0, active_roas or 0, lambda v: f"{v:.2f}x", True, False), unsafe_allow_html=True)
    r2[2].markdown(_metric_tile("📊 TACOS",    ads_metrics.get("overall_tacos") or 0 if ads_metrics.get("overall_tacos") else 0, active_tacos or 0, fmt_pct, False, True), unsafe_allow_html=True)
    r2[3].markdown(_metric_tile("💵 Cost/Order", ads_metrics.get("cost_per_order") or 0,
                                 round(active_spend / proj_orders, 2) if proj_orders > 0 else 0,
                                 fmt_currency, False), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
    r3 = st.columns(4)
    r3[0].markdown(_metric_tile("👁️ Impressions",  curr_impr,  proj_impr,  fmt_num, True),  unsafe_allow_html=True)
    r3[1].markdown(_metric_tile("🖱️ Clicks",       curr_clicks, proj_clicks, fmt_num, True), unsafe_allow_html=True)
    r3[2].markdown(_metric_tile("🛒 Ad Orders",    curr_orders, proj_orders, fmt_num, True), unsafe_allow_html=True)
    r3[3].markdown(_metric_tile("💲 CPC",          curr_cpc, proj_cpc, fmt_currency, False), unsafe_allow_html=True)

    # Channel split tiles
    st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)
    ch_palette = {"Sponsored Products": "#4f46e5", "Sponsored Brands": "#f97316", "Sponsored Display": "#10b981"}
    ch_cols = st.columns(3)
    for col, (ch_name, alloc_data) in zip(ch_cols, active_alloc.items()):
        color = ch_palette.get(ch_name, "#6b7280")
        budget = alloc_data.get("budget", 0)
        share  = alloc_data.get("share_pct", 0)
        with col:
            col.markdown(f"""
            <div style="background:#ffffff;border-top:4px solid {color};border-radius:10px;
                        padding:14px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                <div style="font-size:12px;font-weight:800;color:{color};">{ch_name}</div>
                <div style="font-size:24px;font-weight:900;color:#1e1b4b;margin:6px 0;">{fmt_currency(budget)}</div>
                <div style="font-size:13px;color:#6b7280;">{share:.1f}% of total budget</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ---- Current achieved baseline row
    current_row = pd.DataFrame([{
        "Growth Target":         "✅ Current (Achieved)",
        "Target Revenue ($)":    baseline_revenue,
        "Revenue Gap ($)":       0.0,
        "Rec. Ad Spend ($)":     total_ad_spend,
        "Incremental Spend ($)": 0.0,
        "Projected ACOS (%)":    ads_metrics.get("overall_acos") or 0,
        "Projected ROAS":        ads_metrics.get("overall_roas") or 0,
        "Projected TACOS (%)":   0.0,
        "Target Ad Sales ($)":   total_ad_sales,
    }])

    # ---- Custom scenario row
    custom_row = None
    if custom_scenario:
        custom_row = pd.DataFrame([{
            "Growth Target":         f"🎯 Custom ({'+' if custom_scenario['growth_pct'] >= 0 else ''}{custom_scenario['growth_pct']:.1f}%)",
            "Target Revenue ($)":    custom_scenario["target_revenue"],
            "Revenue Gap ($)":       custom_scenario["revenue_gap"],
            "Rec. Ad Spend ($)":     custom_scenario["recommended_spend"],
            "Incremental Spend ($)": custom_scenario["incremental_spend"],
            "Projected ACOS (%)":    custom_scenario["projected_acos_pct"] or 0,
            "Projected ROAS":        custom_scenario["projected_roas"] or 0,
            "Projected TACOS (%)":   custom_scenario["projected_tacos_pct"] or 0,
            "Target Ad Sales ($)":   custom_scenario["target_ad_sales"],
        }])

    # ---- Scenario Comparison Table — current → custom → growth targets
    st.markdown('<div class="section-header">📋 Scenario Comparison</div>', unsafe_allow_html=True)
    sc_df = scenarios_to_dataframe(scenarios)
    # Add Target Ad Sales column to sc_df
    sc_df["Target Ad Sales ($)"] = [s["target_ad_sales"] for s in scenarios]

    parts = [current_row]
    if custom_row is not None:
        parts.append(custom_row)
    parts.append(sc_df)
    full_df = pd.concat(parts, ignore_index=True)

    # Reorder columns
    col_order = [
        "Growth Target", "Target Revenue ($)", "Target Ad Sales ($)",
        "Revenue Gap ($)", "Rec. Ad Spend ($)", "Incremental Spend ($)",
        "Projected ACOS (%)", "Projected ROAS", "Projected TACOS (%)",
    ]
    full_df = full_df[[c for c in col_order if c in full_df.columns]]

    fmt = {
        "Target Revenue ($)":    "${:,.0f}",
        "Target Ad Sales ($)":   "${:,.0f}",
        "Revenue Gap ($)":       "${:,.0f}",
        "Rec. Ad Spend ($)":     "${:,.0f}",
        "Incremental Spend ($)": "${:,.0f}",
        "Projected ACOS (%)":    "{:.2f}%",
        "Projected ROAS":        "{:.2f}x",
        "Projected TACOS (%)":   "{:.2f}%",
    }

    def _row_style(row):
        if row["Growth Target"] == "✅ Current (Achieved)":
            return ["background-color:#f0fdf4; font-weight:700"] * len(row)
        if str(row["Growth Target"]).startswith("🎯 Custom"):
            return ["background-color:#eff6ff; font-weight:700; color:#1d4ed8"] * len(row)
        return [""] * len(row)

    st.dataframe(
        full_df.style.format(fmt, na_rep="—").apply(_row_style, axis=1),
        use_container_width=True,
    )

    # ---- Chart: Revenue & Spend — Current first, then scenarios
    st.markdown('<div class="section-header">📈 Revenue vs Recommended Spend by Scenario</div>', unsafe_allow_html=True)

    # Build chart series — insert custom scenario between Current and growth scenarios
    chart_labels  = ["Current"]
    chart_revenue = [baseline_revenue]
    chart_spend   = [total_ad_spend]
    bar_colors_rev   = ["#6b7280"]
    bar_colors_spend = ["#9ca3af"]

    if custom_scenario:
        cs_label = f"🎯 Custom\n({'+' if custom_scenario['growth_pct'] >= 0 else ''}{custom_scenario['growth_pct']:.1f}%)"
        chart_labels.append(cs_label)
        chart_revenue.append(custom_scenario["target_revenue"])
        chart_spend.append(custom_scenario["recommended_spend"])
        bar_colors_rev.append("#1d4ed8")
        bar_colors_spend.append("#60a5fa")

    chart_labels  += [f"+{s['growth_pct']}%" for s in scenarios]
    chart_revenue += [s["target_revenue"] for s in scenarios]
    chart_spend   += [s["recommended_spend"] for s in scenarios]
    bar_colors_rev   += ["#1a0a14"] * len(scenarios)
    bar_colors_spend += ["#4f46e5"] * len(scenarios)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=chart_labels, y=chart_revenue, name="Revenue",  marker_color=bar_colors_rev))
    fig.add_trace(go.Bar(x=chart_labels, y=chart_spend,   name="Ad Spend", marker_color=bar_colors_spend))
    fig.update_layout(
        barmode="group", height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=40),
        yaxis_title="Amount ($)", xaxis_title="Scenario",
    )
    fig.add_vline(x=0.5, line_dash="dash", line_color="rgba(107,114,128,0.4)",
                  annotation_text="Forecast →", annotation_position="top right")
    st.plotly_chart(fig, use_container_width=True)

    # ---- Chart: ACOS & ROAS — Current → custom → scenarios
    acos_labels = ["Current"]
    acos_values = [ads_metrics.get("overall_acos") or 0]
    roas_values = [ads_metrics.get("overall_roas") or 0]
    acos_marker_colors = ["#9ca3af"]
    roas_marker_colors = ["#9ca3af"]

    if custom_scenario:
        acos_labels.append(cs_label)
        acos_values.append(custom_scenario["projected_acos_pct"] or 0)
        roas_values.append(custom_scenario["projected_roas"] or 0)
        acos_marker_colors.append("#1d4ed8")
        roas_marker_colors.append("#1d4ed8")

    acos_labels  += [f"+{s['growth_pct']}%" for s in scenarios]
    acos_values  += [s["projected_acos_pct"] for s in scenarios]
    roas_values  += [s["projected_roas"] or 0 for s in scenarios]
    acos_marker_colors += ["#f97316"] * len(scenarios)
    roas_marker_colors += ["#4f46e5"] * len(scenarios)

    col1, col2 = st.columns(2)
    with col1:
        fig_acos = go.Figure()
        fig_acos.add_trace(go.Scatter(
            x=acos_labels, y=acos_values,
            mode="lines+markers", name="ACOS (%)",
            line=dict(color="#f97316", width=2), marker=dict(size=9, color=acos_marker_colors),
        ))
        fig_acos.add_vline(x=0.5, line_dash="dash", line_color="rgba(107,114,128,0.4)")
        fig_acos.update_layout(title="ACOS: Current → Projected", height=320, margin=dict(t=50, b=30),
                                xaxis_title="Scenario", yaxis_title="ACOS (%)")
        st.plotly_chart(fig_acos, use_container_width=True)

    with col2:
        fig_roas = go.Figure()
        fig_roas.add_trace(go.Scatter(
            x=acos_labels, y=roas_values,
            mode="lines+markers", name="ROAS",
            line=dict(color="#4f46e5", width=2), marker=dict(size=9, color=roas_marker_colors),
        ))
        fig_roas.add_vline(x=0.5, line_dash="dash", line_color="rgba(107,114,128,0.4)")
        fig_roas.update_layout(title="ROAS: Current → Projected", height=320, margin=dict(t=50, b=30),
                                xaxis_title="Scenario", yaxis_title="ROAS")
        st.plotly_chart(fig_roas, use_container_width=True)

    # ---- Channel Allocation — prefer custom scenario if active, else +10%
    primary = custom_scenario if custom_scenario else next((s for s in scenarios if s["growth_pct"] == 10), scenarios[0])
    primary_label = "Custom" if custom_scenario else f"+{primary['growth_pct']}%"
    st.markdown(f'<div class="section-header">💰 Channel Budget Allocation — {primary_label} Scenario</div>', unsafe_allow_html=True)

    alloc_labels = list(primary["channel_allocation"].keys())
    alloc_budgets = [v["budget"] for v in primary["channel_allocation"].values()]
    alloc_incr = [v["incremental_budget"] for v in primary["channel_allocation"].values()]

    ch_col1, ch_col2 = st.columns(2)
    with ch_col1:
        fig_pie = go.Figure(go.Pie(
            labels=alloc_labels,
            values=alloc_budgets,
            hole=0.45,
            marker_colors=["#293C5B", "#e71d36", "#f59e0b"],
        ))
        fig_pie.update_layout(title="Total Budget Split", height=320, margin=dict(t=50, b=10, l=10, r=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    with ch_col2:
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(x=alloc_labels, y=alloc_budgets, name="Total Budget", marker_color="#4f46e5"))
        fig_bar.add_trace(go.Bar(x=alloc_labels, y=alloc_incr, name="Incremental Increase", marker_color="#f97316"))
        fig_bar.update_layout(
            barmode="group", title="Budget vs Incremental by Channel",
            height=320, margin=dict(t=50, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # ---- Channel breakdown table
    alloc_rows = []
    for ch, alloc in primary["channel_allocation"].items():
        alloc_rows.append({
            "Channel": ch,
            "Total Budget ($)": alloc["budget"],
            "Incremental Budget ($)": alloc["incremental_budget"],
            "Share (%)": alloc["share_pct"],
        })
    st.dataframe(pd.DataFrame(alloc_rows).style.format({
        "Total Budget ($)": "${:,.2f}",
        "Incremental Budget ($)": "${:,.2f}",
        "Share (%)": "{:.1f}%",
    }), use_container_width=True, height=160)

    # ---- Campaign-level recommendations
    if primary.get("campaign_recommendations"):
        st.markdown('<div class="section-header">🎯 Campaign-Level Budget Recommendations</div>', unsafe_allow_html=True)
        cr_df = pd.DataFrame(primary["campaign_recommendations"])
        display_cr = cr_df.copy()
        display_cr.columns = [c.replace("_", " ").title() for c in display_cr.columns]

        for idx, row in display_cr.iterrows():
            incr = row.get("Suggested Increase") or 0
            roas = row.get("Roas") or "N/A"
            acos = row.get("Acos Pct") or "N/A"
            name = row.get("Campaign") or f"Campaign {idx+1}"
            roas_str = f"{roas:.2f}x" if isinstance(roas, (int, float)) else str(roas)
            acos_str = f"{acos:.1f}%" if isinstance(acos, (int, float)) else str(acos)
            st.markdown(f"""
            <div class="reco-card">
                <strong>{name}</strong><br>
                Current Spend: {fmt_currency(row.get('Current Spend'))} &nbsp;|&nbsp;
                Suggested Increase: <strong>+{fmt_currency(incr)}</strong> &nbsp;|&nbsp;
                New Budget: {fmt_currency(row.get('New Budget'))} &nbsp;|&nbsp;
                ROAS: {roas_str} &nbsp;|&nbsp; ACOS: {acos_str}
            </div>
            """, unsafe_allow_html=True)

    # ======================================================================
    # Monthly Media Plan with High-Sales Event Highlights
    # ======================================================================
    st.markdown("---")
    st.markdown('<div class="section-header">📅 Monthly Media Plan & High-Sales Events</div>', unsafe_allow_html=True)

    # Scenario selector for the monthly view
    # Build options: Custom first (if active), then growth-% scenarios
    scenario_labels = []
    scenario_map    = {}  # label → scenario dict or None

    if custom_scenario:
        cs_label_monthly = f"🎯 Custom ({'+' if custom_scenario['growth_pct'] >= 0 else ''}{custom_scenario['growth_pct']:.1f}%)"
        scenario_labels.append(cs_label_monthly)
        scenario_map[cs_label_monthly] = custom_scenario

    for s in scenarios:
        lbl = f"+{s['growth_pct']}%"
        scenario_labels.append(lbl)
        scenario_map[lbl] = s

    if scenario_labels:
        selected_label = st.selectbox(
            "Select Scenario for Monthly Plan:",
            options=scenario_labels,
            index=0,  # default to custom if active, else first growth scenario
            key="monthly_scenario_select",
        )
        sel_scenario = scenario_map[selected_label]
        sel_growth_pct    = sel_scenario["growth_pct"]
        sel_annual_spend  = sel_scenario["recommended_spend"]
        sel_annual_sales  = sel_scenario["target_ad_sales"]
    else:
        sel_growth_pct   = growth_options[0] if growth_options else 10
        sel_annual_spend = active_spend
        sel_annual_sales = active_sales
        selected_label   = f"+{sel_growth_pct}%"

    monthly_df = monthly_forecast(
        trend_df=trend_df,
        growth_pct=sel_growth_pct,
        total_ordered_revenue=baseline_revenue,
        custom_channel_split=channel_split,
        annual_spend_override=sel_annual_spend,
        annual_sales_override=sel_annual_sales,
    )

    # ---- Event legend strip
    event_months = monthly_df[monthly_df["Is Event Month"] == True]
    if not event_months.empty:
        legend_html = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 18px 0;">'
        for _, row in event_months.iterrows():
            legend_html += (
                f'<span style="background:#fef3c7;border:1px solid #f59e0b;border-radius:20px;'
                f'padding:4px 12px;font-size:13px;font-weight:600;color:#92400e;">'
                f'{row["Month Name"]} — {row["Events"]}'
                f'</span>'
            )
        legend_html += '</div>'
        st.markdown(legend_html, unsafe_allow_html=True)

    # ---- Dual-axis bar chart: Actual vs Projected spend, with event annotations
    # go is already imported at the top of the file
    months = monthly_df["Month Name"].tolist()
    actual_spend_vals  = [v if v is not None else 0 for v in monthly_df["Actual Spend ($)"].tolist()]
    proj_spend_vals    = monthly_df["Projected Spend ($)"].tolist()
    proj_sales_vals    = monthly_df["Projected Ad Sales ($)"].tolist()
    is_event           = monthly_df["Is Event Month"].tolist()

    bar_colors_proj = [
        "#f97316" if e else "#4f46e5"
        for e in is_event
    ]

    fig_monthly = go.Figure()
    fig_monthly.add_trace(go.Bar(
        x=months, y=actual_spend_vals,
        name="Actual Spend", marker_color="#9ca3af",
        opacity=0.7,
    ))
    fig_monthly.add_trace(go.Bar(
        x=months, y=proj_spend_vals,
        name=f"Projected Spend ({selected_label})",
        marker_color=bar_colors_proj,
        opacity=0.9,
    ))
    fig_monthly.add_trace(go.Scatter(
        x=months, y=proj_sales_vals,
        name="Projected Ad Sales", mode="lines+markers",
        line=dict(color="#10b981", width=2), marker=dict(size=8),
        yaxis="y2",
    ))

    # Highlight event months with a shaded region
    for i, (ev, month) in enumerate(zip(is_event, months)):
        if ev:
            fig_monthly.add_vrect(
                x0=i - 0.5, x1=i + 0.5,
                fillcolor="rgba(249,115,22,0.10)", layer="below",
                line_width=0,
            )

    fig_monthly.update_layout(
        barmode="group",
        height=460,
        yaxis=dict(title="Spend ($)", tickprefix="$"),
        yaxis2=dict(title="Ad Sales ($)", overlaying="y", side="right", tickprefix="$", showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=40),
        xaxis_title="Month",
        title=f"Monthly Spend & Sales — {selected_label} Scenario  |  🟠 = High-Sales Event Month",
    )
    st.plotly_chart(fig_monthly, use_container_width=True)

    # ---- Channel budget bar chart (SP / SB / SD per month)
    st.markdown('<div class="section-header">💰 Monthly Channel Budget Breakdown</div>', unsafe_allow_html=True)
    fig_ch = go.Figure()
    fig_ch.add_trace(go.Bar(x=months, y=monthly_df["SP Budget ($)"].tolist(), name="Sponsored Products", marker_color="#4f46e5"))
    fig_ch.add_trace(go.Bar(x=months, y=monthly_df["SB Budget ($)"].tolist(), name="Sponsored Brands",   marker_color="#f97316"))
    fig_ch.add_trace(go.Bar(x=months, y=monthly_df["SD Budget ($)"].tolist(), name="Sponsored Display",  marker_color="#10b981"))
    for i, ev in enumerate(is_event):
        if ev:
            fig_ch.add_vrect(x0=i - 0.5, x1=i + 0.5, fillcolor="rgba(249,115,22,0.10)", layer="below", line_width=0)
    fig_ch.update_layout(
        barmode="stack", height=380,
        yaxis=dict(title="Budget ($)", tickprefix="$"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=50, b=40), xaxis_title="Month",
        title="Monthly Channel Budget Split (Stacked)  |  🟠 = Event Month",
    )
    st.plotly_chart(fig_ch, use_container_width=True)

    # ---- Projected ROAS & ACOS by month
    roas_vals = [v if v is not None else 0 for v in monthly_df["Projected ROAS"].tolist()]
    acos_vals = [v if v is not None else 0 for v in monthly_df["Projected ACOS (%)"].tolist()]
    col_r, col_a = st.columns(2)
    with col_r:
        fig_roas_m = go.Figure()
        fig_roas_m.add_trace(go.Scatter(
            x=months, y=roas_vals, mode="lines+markers", name="Projected ROAS",
            line=dict(color="#4f46e5", width=2), marker=dict(size=9, color=["#f97316" if e else "#4f46e5" for e in is_event]),
        ))
        fig_roas_m.update_layout(title="Monthly Projected ROAS", height=300, yaxis_title="ROAS", xaxis_title="Month", margin=dict(t=50, b=30))
        st.plotly_chart(fig_roas_m, use_container_width=True)
    with col_a:
        fig_acos_m = go.Figure()
        fig_acos_m.add_trace(go.Scatter(
            x=months, y=acos_vals, mode="lines+markers", name="Projected ACOS",
            line=dict(color="#f97316", width=2), marker=dict(size=9, color=["#f97316" if e else "#6b7280" for e in is_event]),
        ))
        fig_acos_m.update_layout(title="Monthly Projected ACOS (%)", height=300, yaxis_title="ACOS (%)", xaxis_title="Month", margin=dict(t=50, b=30))
        st.plotly_chart(fig_acos_m, use_container_width=True)

    # ---- Full monthly plan table
    # Detect which year actuals come from (for column labelling)
    actual_year = None
    if trend_df is not None and not trend_df.empty and "_period_dt" in trend_df.columns:
        try:
            actual_year = int(pd.to_datetime(trend_df["_period_dt"]).dt.year.max())
        except Exception:
            pass
    actual_label = f"{actual_year} Actuals" if actual_year else "Actuals"

    st.markdown(
        f'<div class="section-header">📋 Monthly Plan Detail Table'
        f'<span style="font-size:13px;font-weight:400;color:#6b7280;margin-left:12px;">'
        f'— {actual_label} vs {selected_label} Projected</span></div>',
        unsafe_allow_html=True,
    )

    display_cols = [
        "Month", "Month Name", "Events",
        "Actual Spend ($)", "Actual Ad Sales ($)", "Actual ACOS (%)", "Actual ROAS",
        "Projected Spend ($)", "Projected Ad Sales ($)", "Projected ACOS (%)", "Projected ROAS",
        "Spend Uplift %", "SP Budget ($)", "SB Budget ($)", "SD Budget ($)",
    ]
    disp_df = monthly_df[[c for c in display_cols if c in monthly_df.columns]].copy()

    # Rename actual columns to include year label so it's crystal clear
    rename_map = {
        "Actual Spend ($)":    f"Actual Spend ({actual_label}) ($)",
        "Actual Ad Sales ($)": f"Actual Sales ({actual_label}) ($)",
        "Actual ACOS (%)":     f"Actual ACOS ({actual_label})",
        "Actual ROAS":         f"Actual ROAS ({actual_label})",
    }
    disp_df = disp_df.rename(columns=rename_map)

    # Use Month (1–12) as the index so it shows 1→12, not 0→11
    disp_df = disp_df.set_index("Month")

    def _style_monthly_row(row):
        if row["Events"] != "—":
            return ["background-color: #fffbeb; font-weight: 600"] * len(row)
        return [""] * len(row)

    # Build format map against the (possibly renamed) columns
    fmt_map = {}
    for c in disp_df.columns:
        if "$" in c:
            fmt_map[c] = "${:,.0f}"
        elif "ACOS" in c and "Actual" in c:
            fmt_map[c] = "{:.1f}%"
        elif "ACOS" in c:
            fmt_map[c] = "{:.1f}%"
        elif "ROAS" in c:
            fmt_map[c] = "{:.2f}x"
        elif "Uplift" in c:
            fmt_map[c] = "+{:.0f}%"

    styled = disp_df.style.format(fmt_map, na_rep="—").apply(_style_monthly_row, axis=1)
    st.dataframe(styled, use_container_width=True, height=460)

    return scenarios


# ---------------------------------------------------------------------------
# Tab 4 — Strategic Recommendations
# ---------------------------------------------------------------------------

def render_recommendations(ads_metrics, vendor_metrics, scenarios):
    acos = ads_metrics.get("overall_acos")
    roas = ads_metrics.get("overall_roas")
    ctr  = ads_metrics.get("overall_ctr")
    cpc  = ads_metrics.get("overall_cpc")
    spend = ads_metrics.get("total_spend", 0)
    ntb   = ads_metrics.get("ntb_order_pct")

    # ── Priority alert bar ────────────────────────────────────────────────
    alerts, greens = [], []
    if acos is not None:
        if acos > 35:   alerts.append(f"🔴 ACOS {acos:.1f}% is above the 35% danger threshold")
        elif acos < 15: greens.append(f"🟢 ACOS {acos:.1f}% is highly efficient — room to scale spend")
        else:            greens.append(f"🟢 ACOS {acos:.1f}% is healthy (15–35% range)")
    if roas is not None:
        if roas < 2:    alerts.append(f"🔴 ROAS {roas:.2f}x is dangerously low — audit listings & match types")
        elif roas >= 4: greens.append(f"🟢 ROAS {roas:.2f}x is strong — consider expanding budgets")
    if ctr is not None and ctr < 0.3:
        alerts.append(f"🟡 CTR {ctr:.2f}% is below 0.3% — main image or title may need improvement")
    if cpc is not None and cpc > 2.5:
        alerts.append(f"🟡 CPC ${cpc:.2f} is elevated — review bid strategy and match types")
    if ntb is not None and ntb > 50:
        greens.append(f"🟢 {ntb:.0f}% of orders are New to Brand — strong customer acquisition")

    if alerts or greens:
        st.markdown('<div class="section-header">🚨 Performance Health Check</div>', unsafe_allow_html=True)
        col_a, col_g = st.columns(2)
        with col_a:
            for a in alerts:
                st.markdown(f'<div class="warning-card" style="margin-bottom:8px;">{a}</div>', unsafe_allow_html=True)
        with col_g:
            for g in greens:
                st.markdown(f'<div class="reco-card" style="margin-bottom:8px;">{g}</div>', unsafe_allow_html=True)

    # ── Scenario-driven spend action cards ───────────────────────────────
    if scenarios:
        st.markdown('<div class="section-header">📈 Growth Scenario Action Plans</div>', unsafe_allow_html=True)
        for s in scenarios[:4]:   # show up to 4 scenarios
            gpct  = s["growth_pct"]
            delta = s["incremental_spend"]
            rec   = s["recommended_spend"]
            tacos = s.get("projected_tacos_pct") or 0
            proas = s.get("projected_roas") or 0
            alloc = s.get("channel_allocation", {})
            sp_b  = alloc.get("Sponsored Products", {}).get("budget", 0)
            sb_b  = alloc.get("Sponsored Brands",   {}).get("budget", 0)
            sd_b  = alloc.get("Sponsored Display",  {}).get("budget", 0)
            label = f"+{gpct:.0f}%" if gpct >= 0 else f"{gpct:.0f}%"
            is_custom = s.get("is_custom_scenario", False)
            badge = "🎯 Custom" if is_custom else f"📈 {label} Growth"
            st.markdown(f"""
            <div class="reco-card" style="margin-bottom:12px;">
                <div style="font-size:16px;font-weight:800;margin-bottom:6px;">{badge} — Target Revenue: {fmt_currency(s['target_revenue'])}</div>
                <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:10px 0;">
                    <div style="background:#f0f2ff;border-radius:8px;padding:8px 12px;text-align:center;">
                        <div style="font-size:11px;color:#6b7280;font-weight:600;">REC. AD SPEND</div>
                        <div style="font-size:18px;font-weight:800;color:#4f46e5;">{fmt_currency(rec)}</div>
                        <div style="font-size:11px;color:#f97316;">+{fmt_currency(delta)} incremental</div>
                    </div>
                    <div style="background:#f0f2ff;border-radius:8px;padding:8px 12px;text-align:center;">
                        <div style="font-size:11px;color:#6b7280;font-weight:600;">PROJ. ROAS</div>
                        <div style="font-size:18px;font-weight:800;color:#4f46e5;">{proas:.2f}x</div>
                        <div style="font-size:11px;color:#6b7280;">vs current {(roas or 0):.2f}x</div>
                    </div>
                    <div style="background:#f0f2ff;border-radius:8px;padding:8px 12px;text-align:center;">
                        <div style="font-size:11px;color:#6b7280;font-weight:600;">PROJ. TACOS</div>
                        <div style="font-size:18px;font-weight:800;color:#f97316;">{tacos:.1f}%</div>
                        <div style="font-size:11px;color:#6b7280;">total ad cost ratio</div>
                    </div>
                    <div style="background:#f0f2ff;border-radius:8px;padding:8px 12px;text-align:center;">
                        <div style="font-size:11px;color:#6b7280;font-weight:600;">CHANNEL SPLIT</div>
                        <div style="font-size:13px;font-weight:700;color:#1e1b4b;">SP {fmt_currency(sp_b)}</div>
                        <div style="font-size:12px;color:#f97316;">SB {fmt_currency(sb_b)} · SD {fmt_currency(sd_b)}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Channel investment strategy ───────────────────────────────────────
    st.markdown('<div class="section-header">🎯 Channel Investment Strategy</div>', unsafe_allow_html=True)
    ch_cols = st.columns(3)
    channel_cards = [
        ("#4f46e5", "⚡ Sponsored Products", "Direct-response, highest ROAS",
         ["Prioritise exact/phrase match for conversion efficiency",
          "Run auto campaigns to discover new high-converting terms",
          "Scale budgets on your top 20% ASINs by ROAS",
          "Set dynamic bids — Up & Down for proven keywords"]),
        ("#f97316", "🏷️ Sponsored Brands", "Top-of-funnel & brand equity",
         ["Launch video ads for your hero ASINs — 2–3x higher CTR",
          "Drive traffic to Brand Store for higher basket size",
          "Use headline search for category defence against competitors",
          "Target shoppers browsing competitor brand pages"]),
        ("#10b981", "🎯 Sponsored Display", "Retargeting & conquesting",
         ["Remarket to product detail page visitors (high intent)",
          "Target competitor ASINs with price/review advantage",
          "Use audience targeting for category interest shoppers",
          "Run lifestyle creatives for awareness campaigns"]),
    ]
    for col, (color, title, sub, bullets) in zip(ch_cols, channel_cards):
        with col:
            bullet_html = "".join(f'<li style="margin-bottom:4px;">{b}</li>' for b in bullets)
            st.markdown(f"""
            <div style="background:#ffffff;border-top:4px solid {color};border-radius:10px;
                        padding:16px;height:100%;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                <div style="font-size:15px;font-weight:800;color:{color};margin-bottom:4px;">{title}</div>
                <div style="font-size:12px;color:#6b7280;margin-bottom:10px;">{sub}</div>
                <ul style="font-size:13px;color:#374151;padding-left:18px;margin:0;">{bullet_html}</ul>
            </div>
            """, unsafe_allow_html=True)

    # ── Seasonal budget calendar ──────────────────────────────────────────
    st.markdown('<div class="section-header">📅 Seasonal Budget Uplift Calendar</div>', unsafe_allow_html=True)
    events = [
        ("Feb", "Valentine's Day", "+10%", "#f97316"),
        ("May", "Mother's Day",    "+8%",  "#f97316"),
        ("Jun", "Father's Day",    "+8%",  "#f97316"),
        ("Jul", "Prime Day ⚡",    "+30%", "#dc2626"),
        ("Aug", "Back to School",  "+5%",  "#f59e0b"),
        ("Oct", "Prime Big Deals ⚡","+20%","#dc2626"),
        ("Nov", "Black Friday 🛒", "+45%", "#dc2626"),
        ("Nov", "Cyber Monday 💻", "+45%", "#dc2626"),
        ("Dec", "Holiday Season 🎄","+25%","#dc2626"),
    ]
    ev_cols = st.columns(len(events))
    for col, (month, name, uplift, color) in zip(ev_cols, events):
        with col:
            st.markdown(f"""
            <div style="background:#ffffff;border-radius:8px;padding:10px 6px;text-align:center;
                        border-top:3px solid {color};box-shadow:0 1px 4px rgba(0,0,0,0.07);">
                <div style="font-size:11px;font-weight:800;color:#6b7280;">{month}</div>
                <div style="font-size:12px;font-weight:700;color:#1e1b4b;line-height:1.3;">{name}</div>
                <div style="font-size:16px;font-weight:900;color:{color};margin-top:4px;">{uplift}</div>
                <div style="font-size:10px;color:#9ca3af;">budget uplift</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("""
    <div class="reco-card" style="margin-top:14px;">
        <strong>Seasonal Playbook:</strong> Increase budgets <strong>2–3 weeks before</strong> each peak event —
        Amazon's algorithm needs lead time to ramp impression share. During the event, monitor
        hourly pacing and be ready to increase daily budgets if you hit cap before noon.
        Post-event, run a 1-week recovery phase at +15% to capture residual demand.
    </div>""", unsafe_allow_html=True)

    # ── ASIN prioritisation ───────────────────────────────────────────────
    st.markdown('<div class="section-header">🔍 ASIN & Bid Strategy Priorities</div>', unsafe_allow_html=True)
    p1, p2 = st.columns(2)
    with p1:
        st.markdown("""
        <div style="background:#ffffff;border-radius:10px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
            <div style="font-weight:800;font-size:15px;color:#4f46e5;margin-bottom:10px;">📦 ASIN Investment Tiers</div>
            <div style="margin-bottom:8px;padding:8px 12px;background:#f0fdf4;border-radius:6px;border-left:4px solid #10b981;">
                <strong>🟢 Tier 1 — Scale (ROAS &gt; 4x, ACOS &lt; 20%)</strong><br>
                <span style="font-size:13px;">Increase bids +20–30%. Move winning search terms to exact match. Push SB video.</span>
            </div>
            <div style="margin-bottom:8px;padding:8px 12px;background:#fffbeb;border-radius:6px;border-left:4px solid #f59e0b;">
                <strong>🟡 Tier 2 — Optimise (ACOS 20–35%)</strong><br>
                <span style="font-size:13px;">Hold budgets. Harvest exact match terms. Prune broad match waste weekly.</span>
            </div>
            <div style="padding:8px 12px;background:#fef2f2;border-radius:6px;border-left:4px solid #dc2626;">
                <strong>🔴 Tier 3 — Review or Pause (ACOS &gt; 35%)</strong><br>
                <span style="font-size:13px;">Audit listing (images, reviews, price). Reduce bids -30% or pause for 2 weeks.</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with p2:
        st.markdown("""
        <div style="background:#ffffff;border-radius:10px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
            <div style="font-weight:800;font-size:15px;color:#f97316;margin-bottom:10px;">⚙️ Bid Strategy Guide</div>
            <div style="margin-bottom:8px;padding:8px 12px;background:#f0f2ff;border-radius:6px;border-left:4px solid #4f46e5;">
                <strong>Dynamic Up &amp; Down</strong> — Best for proven top performers<br>
                <span style="font-size:13px;">Amazon adjusts bids in real time for high-conversion placements. Use for exact match winners.</span>
            </div>
            <div style="margin-bottom:8px;padding:8px 12px;background:#f0f2ff;border-radius:6px;border-left:4px solid #4f46e5;">
                <strong>Dynamic Down Only</strong> — Best for efficiency campaigns<br>
                <span style="font-size:13px;">Protects ACOS ceiling. Ideal for broad/phrase terms still being tested.</span>
            </div>
            <div style="padding:8px 12px;background:#f0f2ff;border-radius:6px;border-left:4px solid #4f46e5;">
                <strong>Fixed Bids</strong> — Best for competitor / conquesting<br>
                <span style="font-size:13px;">Full control. Use for Sponsored Display retargeting where you set the ceiling precisely.</span>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tab — Product Intelligence (super-refined)
# ---------------------------------------------------------------------------

def render_product_tab(prod_intel: dict, ad_prod_df, bid_df, match_df=None):
    if not prod_intel and ad_prod_df.empty and (match_df is None or match_df.empty):
        st.info("No product-level data found. This tab requires 'Advertised product ID' or campaign-type columns in your report.")
        return

    # ── 1. Ad Product (SP / SB / SD) KPI strip ───────────────────────────
    if not ad_prod_df.empty:
        st.markdown('<div class="section-header">📢 Ad Type Performance — SP · SB · SD</div>', unsafe_allow_html=True)
        kpi_cols = st.columns(len(ad_prod_df))
        colors_map = {"Sponsored Products": "#4f46e5", "Sponsored Brands": "#f97316", "Sponsored Display": "#10b981"}
        for col, (_, row) in zip(kpi_cols, ad_prod_df.iterrows()):
            prod_name = str(row.get("ad_product", "Unknown"))
            color = colors_map.get(prod_name, "#6b7280")
            short = prod_name.replace("Sponsored ", "SP").replace("Products","SP").replace("Brands","SB").replace("Display","SD")
            short = prod_name  # keep full name
            roas_v = f"{row['roas']:.2f}x" if "roas" in row and pd.notna(row["roas"]) else "—"
            acos_v = f"{row['acos_%']:.1f}%" if "acos_%" in row and pd.notna(row["acos_%"]) else "—"
            shr_v  = f"{row['spend_share_%']:.0f}%" if "spend_share_%" in row and pd.notna(row.get("spend_share_%")) else "—"
            with col:
                st.markdown(f"""
                <div style="background:#ffffff;border-top:4px solid {color};border-radius:10px;
                            padding:14px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                    <div style="font-size:12px;font-weight:800;color:{color};">{prod_name}</div>
                    <div style="font-size:22px;font-weight:900;color:#1e1b4b;margin:4px 0;">{fmt_currency(row.get('spend',0))}</div>
                    <div style="font-size:12px;color:#6b7280;">Spend · {shr_v} of total</div>
                    <div style="display:flex;justify-content:space-around;margin-top:8px;">
                        <span style="font-size:13px;"><b style="color:{color};">{roas_v}</b><br><span style="color:#9ca3af;font-size:11px;">ROAS</span></span>
                        <span style="font-size:13px;"><b style="color:#f97316;">{acos_v}</b><br><span style="color:#9ca3af;font-size:11px;">ACOS</span></span>
                        <span style="font-size:13px;"><b style="color:#1e1b4b;">{fmt_currency(row.get('ad_sales',0))}</b><br><span style="color:#9ca3af;font-size:11px;">Sales</span></span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # Pie + grouped bar side-by-side
        st.markdown("<div style='margin-top:18px;'></div>", unsafe_allow_html=True)
        pc1, pc2 = st.columns(2)
        with pc1:
            if "spend" in ad_prod_df.columns:
                palette = [colors_map.get(p, "#6b7280") for p in ad_prod_df["ad_product"]]
                fig_pie = go.Figure(go.Pie(
                    labels=ad_prod_df["ad_product"], values=ad_prod_df["spend"],
                    hole=0.5, marker_colors=palette,
                    textinfo="label+percent", textfont_size=13,
                ))
                fig_pie.update_layout(title="Budget Share by Ad Type", height=300,
                                      margin=dict(t=40, b=10, l=10, r=10),
                                      showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True)
        with pc2:
            if all(c in ad_prod_df.columns for c in ["ad_product", "spend", "ad_sales"]):
                fig_grp = go.Figure()
                fig_grp.add_trace(go.Bar(x=ad_prod_df["ad_product"], y=ad_prod_df["spend"],
                                         name="Spend", marker_color="#4f46e5"))
                fig_grp.add_trace(go.Bar(x=ad_prod_df["ad_product"], y=ad_prod_df["ad_sales"],
                                         name="Ad Sales", marker_color="#f97316"))
                fig_grp.update_layout(barmode="group", title="Spend vs Sales by Ad Type",
                                      height=300, margin=dict(t=40, b=30),
                                      legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"))
                st.plotly_chart(fig_grp, use_container_width=True)

    # ── 2. ASIN Efficiency Quadrant ───────────────────────────────────────
    all_asins = prod_intel.get("by_asin", pd.DataFrame())
    if not all_asins.empty and "roas" in all_asins.columns and "acos_%" in all_asins.columns:
        st.markdown('<div class="section-header">🔬 ASIN Efficiency Quadrant</div>', unsafe_allow_html=True)
        quad = all_asins.dropna(subset=["roas", "acos_%"]).copy()
        median_roas = quad["roas"].median()
        median_acos = quad["acos_%"].median()

        def _quadrant(row):
            if row["roas"] >= median_roas and row["acos_%"] <= median_acos:
                return "🟢 Scale"
            elif row["roas"] >= median_roas and row["acos_%"] > median_acos:
                return "🟡 Optimise"
            elif row["roas"] < median_roas and row["acos_%"] <= median_acos:
                return "🟡 Monitor"
            else:
                return "🔴 Review"

        quad["Quadrant"] = quad.apply(_quadrant, axis=1)
        color_map = {"🟢 Scale": "#10b981", "🟡 Optimise": "#f59e0b",
                     "🟡 Monitor": "#6366f1", "🔴 Review": "#dc2626"}
        size_col = "ad_sales" if "ad_sales" in quad.columns else None

        fig_quad = go.Figure()
        for q_label, q_color in color_map.items():
            sub = quad[quad["Quadrant"] == q_label]
            if sub.empty:
                continue
            fig_quad.add_trace(go.Scatter(
                x=sub["roas"], y=sub["acos_%"],
                mode="markers",
                name=q_label,
                marker=dict(
                    size=[max(8, min(30, v / (sub["ad_sales"].max() / 20))) for v in sub.get("ad_sales", [12] * len(sub))] if size_col else 12,
                    color=q_color, opacity=0.8, line=dict(width=1, color="#ffffff"),
                ),
                text=sub.get("asin", sub.index),
                hovertemplate="<b>%{text}</b><br>ROAS: %{x:.2f}x<br>ACOS: %{y:.1f}%<extra></extra>",
            ))
        fig_quad.add_vline(x=median_roas, line_dash="dash", line_color="#6b7280",
                           annotation_text=f"Median ROAS {median_roas:.1f}x")
        fig_quad.add_hline(y=median_acos, line_dash="dash", line_color="#6b7280",
                           annotation_text=f"Median ACOS {median_acos:.1f}%")
        fig_quad.update_layout(
            title="ASIN Quadrant: ROAS vs ACOS  (bubble size = Ad Sales)",
            xaxis_title="ROAS", yaxis_title="ACOS (%)",
            height=460, margin=dict(t=60, b=40),
            legend=dict(orientation="h", y=1.08, x=0.5, xanchor="center"),
        )
        st.plotly_chart(fig_quad, use_container_width=True)

        # Quadrant summary counts
        qsum = quad["Quadrant"].value_counts().reset_index()
        qsum.columns = ["Quadrant", "ASIN Count"]
        q_cols = st.columns(4)
        for col, (_, row) in zip(q_cols, qsum.iterrows()):
            c = color_map.get(row["Quadrant"], "#6b7280")
            with col:
                st.markdown(f"""
                <div style="background:#ffffff;border-left:4px solid {c};border-radius:8px;
                            padding:10px 14px;box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                    <div style="font-size:22px;font-weight:900;color:{c};">{row['ASIN Count']}</div>
                    <div style="font-size:13px;color:#374151;">{row['Quadrant']} ASINs</div>
                </div>
                """, unsafe_allow_html=True)

    # ── 3. Top ROAS & Worst ACOS side-by-side ────────────────────────────
    top_roas   = prod_intel.get("top_roas",   pd.DataFrame())
    worst_acos = prod_intel.get("worst_acos", pd.DataFrame())

    t1, t2 = st.columns(2)
    with t1:
        if not top_roas.empty:
            st.markdown('<div class="section-header">🚀 Top 10 ASINs by ROAS — Scale These</div>', unsafe_allow_html=True)
            show_cols = [c for c in ["asin", "roas", "ad_sales", "spend", "acos_%", "cvr_%", "ntb_%"] if c in top_roas.columns]
            disp = top_roas[show_cols].copy()
            disp.columns = [c.replace("_", " ").replace("%", "%").title() for c in disp.columns]
            st.dataframe(disp, use_container_width=True, height=320)
            if "asin" in top_roas.columns and "roas" in top_roas.columns:
                fig_tr = go.Figure(go.Bar(
                    x=top_roas["asin"], y=top_roas["roas"],
                    marker_color="#10b981",
                    text=[f"{v:.1f}x" for v in top_roas["roas"]], textposition="outside",
                ))
                fig_tr.update_layout(title="ROAS by ASIN", height=280,
                                     margin=dict(t=40, b=60), xaxis_tickangle=-35)
                st.plotly_chart(fig_tr, use_container_width=True)

    with t2:
        if not worst_acos.empty:
            st.markdown('<div class="section-header">🔴 Top 10 ASINs by ACOS — Review or Pause</div>', unsafe_allow_html=True)
            show_cols = [c for c in ["asin", "acos_%", "spend", "ad_sales", "roas", "ad_orders"] if c in worst_acos.columns]
            disp = worst_acos[show_cols].copy()
            disp.columns = [c.replace("_", " ").replace("%", "%").title() for c in disp.columns]
            st.dataframe(disp, use_container_width=True, height=320)
            if "asin" in worst_acos.columns and "acos_%" in worst_acos.columns:
                fig_wa = go.Figure(go.Bar(
                    x=worst_acos["asin"], y=worst_acos["acos_%"],
                    marker_color="#dc2626",
                    text=[f"{v:.0f}%" for v in worst_acos["acos_%"]], textposition="outside",
                ))
                fig_wa.add_hline(y=35, line_dash="dash", line_color="#f59e0b",
                                 annotation_text="35% danger line")
                fig_wa.update_layout(title="ACOS % by ASIN", height=280,
                                     margin=dict(t=40, b=60), xaxis_tickangle=-35)
                st.plotly_chart(fig_wa, use_container_width=True)

    # ── 4. Category rollup bubble chart ──────────────────────────────────
    cat_df = prod_intel.get("by_category", pd.DataFrame())
    if not cat_df.empty and "category" in cat_df.columns:
        st.markdown('<div class="section-header">🗂️ Category Performance — Spend · Sales · ACOS</div>', unsafe_allow_html=True)
        cc1, cc2 = st.columns(2)
        with cc1:
            show = [c for c in ["category","spend","ad_sales","acos_%","roas","ad_orders"] if c in cat_df.columns]
            d = cat_df[show].copy()
            d.columns = [c.replace("_"," ").title() for c in d.columns]
            st.dataframe(d, use_container_width=True, height=260)
        with cc2:
            if all(c in cat_df.columns for c in ["category","spend","ad_sales"]):
                fig_cat = go.Figure()
                fig_cat.add_trace(go.Bar(x=cat_df["category"], y=cat_df["ad_sales"],
                                         name="Ad Sales", marker_color="#f97316"))
                fig_cat.add_trace(go.Bar(x=cat_df["category"], y=cat_df["spend"],
                                         name="Spend", marker_color="#4f46e5"))
                if "acos_%" in cat_df.columns:
                    fig_cat.add_trace(go.Scatter(x=cat_df["category"], y=cat_df["acos_%"],
                                                  mode="markers+text", name="ACOS %",
                                                  marker=dict(size=14, color="#dc2626", symbol="diamond"),
                                                  text=[f"{v:.0f}%" for v in cat_df["acos_%"]],
                                                  textposition="top center", yaxis="y2"))
                fig_cat.update_layout(
                    barmode="group", height=300, margin=dict(t=40, b=80),
                    xaxis_tickangle=-30,
                    yaxis=dict(title="Amount ($)"),
                    yaxis2=dict(title="ACOS (%)", overlaying="y", side="right", showgrid=False),
                    legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
                )
                st.plotly_chart(fig_cat, use_container_width=True)

    # ── 5. Bid strategy heatmap ───────────────────────────────────────────
    if not bid_df.empty:
        st.markdown('<div class="section-header">⚙️ Bid Strategy Performance</div>', unsafe_allow_html=True)
        bs1, bs2 = st.columns(2)
        with bs1:
            show = [c for c in ["bid_strategy","spend","ad_sales","acos_%","roas","impressions"] if c in bid_df.columns]
            d = bid_df[show].copy()
            d.columns = [c.replace("_"," ").title() for c in d.columns]
            st.dataframe(d, use_container_width=True)
        with bs2:
            if all(c in bid_df.columns for c in ["bid_strategy","acos_%","roas"]):
                fig_bs = go.Figure()
                fig_bs.add_trace(go.Bar(x=bid_df["bid_strategy"], y=bid_df["acos_%"],
                                        name="ACOS %", marker_color="#f97316"))
                fig_bs.add_trace(go.Scatter(x=bid_df["bid_strategy"], y=bid_df["roas"],
                                             mode="markers+lines", name="ROAS",
                                             marker=dict(size=12, color="#4f46e5"),
                                             line=dict(color="#4f46e5"), yaxis="y2"))
                fig_bs.update_layout(
                    title="ACOS & ROAS by Bid Strategy",
                    yaxis=dict(title="ACOS (%)"),
                    yaxis2=dict(title="ROAS", overlaying="y", side="right", showgrid=False),
                    height=300, margin=dict(t=40, b=50),
                    legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
                )
                st.plotly_chart(fig_bs, use_container_width=True)

    # ── 6. Match type efficiency ──────────────────────────────────────────
    if match_df is not None and not match_df.empty:
        st.markdown('<div class="section-header">🎯 Match Type Efficiency</div>', unsafe_allow_html=True)
        mt1, mt2 = st.columns(2)
        with mt1:
            show = [c for c in ["match_type","spend","ad_sales","acos_%","roas","cvr_%","cpc"] if c in match_df.columns]
            d = match_df[show].copy()
            d.columns = [c.replace("_"," ").title() for c in d.columns]
            st.dataframe(d, use_container_width=True)
        with mt2:
            if all(c in match_df.columns for c in ["match_type","acos_%","roas"]):
                fig_mt = go.Figure()
                fig_mt.add_trace(go.Bar(x=match_df["match_type"], y=match_df["acos_%"],
                                        name="ACOS %", marker_color="#f97316"))
                fig_mt.add_trace(go.Scatter(x=match_df["match_type"], y=match_df["roas"],
                                             mode="markers+lines", name="ROAS",
                                             marker=dict(size=12, color="#4f46e5"),
                                             line=dict(color="#4f46e5"), yaxis="y2"))
                fig_mt.update_layout(
                    title="ACOS & ROAS by Match Type",
                    yaxis=dict(title="ACOS (%)"),
                    yaxis2=dict(title="ROAS", overlaying="y", side="right", showgrid=False),
                    height=300, margin=dict(t=40, b=30),
                    legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
                )
                st.plotly_chart(fig_mt, use_container_width=True)
        st.markdown("""<div class="reco-card">
            <strong>Match Type Playbook:</strong> Exact match drives the most efficient spend
            (lowest ACOS, highest CVR). Broad match is for discovery — harvest converting terms
            weekly into exact/phrase. Pause broad match terms with &gt;10 clicks and zero orders.
        </div>""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tab — Trend Analysis (super-refined)
# ---------------------------------------------------------------------------

def render_trend_tab(trend_df, t_summary: dict, prod_trend_df):
    if trend_df.empty:
        st.info("No date/time data found. Trend analysis requires a 'Date range' column in your report.")
        return

    # ── 1. MoM delta KPI cards ────────────────────────────────────────────
    if t_summary:
        st.markdown('<div class="section-header">📊 Latest Period-over-Period Changes</div>', unsafe_allow_html=True)
        mcols = st.columns(4)
        def _delta(val, invert=False):
            if val is None: return "N/A", "#6b7280"
            good = val < 0 if invert else val > 0
            arrow = "▲" if val > 0 else "▼"
            color = "#10b981" if good else "#dc2626"
            return f"{arrow} {abs(val):.1f}%", color

        items = [
            ("💸 Spend Change",  t_summary.get("spend_change_pct"),  False),
            ("📈 Sales Change",  t_summary.get("sales_change_pct"),  False),
            ("🎯 ACOS Change",   t_summary.get("acos_change_pct"),   True),
            ("⚡ ROAS Change",   t_summary.get("roas_change_pct"),   False),
        ]
        for col, (label, val, invert) in zip(mcols, items):
            txt, color = _delta(val, invert)
            with col:
                period = t_summary.get("latest_period", "")
                st.markdown(f"""
                <div style="background:#ffffff;border-radius:10px;padding:14px;
                            box-shadow:0 2px 8px rgba(0,0,0,0.06);text-align:center;">
                    <div style="font-size:12px;color:#6b7280;font-weight:600;">{label}</div>
                    <div style="font-size:26px;font-weight:900;color:{color};">{txt}</div>
                    <div style="font-size:11px;color:#9ca3af;">vs prior · {period}</div>
                </div>
                """, unsafe_allow_html=True)

    # ── 2. Spend vs Sales annotated line chart ────────────────────────────
    st.markdown('<div class="section-header">📈 Monthly Spend vs Ad Sales</div>', unsafe_allow_html=True)
    if "_period_dt" in trend_df.columns:
        fig = go.Figure()
        if "spend" in trend_df.columns:
            fig.add_trace(go.Scatter(
                x=trend_df["_period_dt"], y=trend_df["spend"],
                mode="lines+markers", name="Ad Spend",
                line=dict(color="#f97316", width=2.5), marker=dict(size=8),
                fill="tozeroy", fillcolor="rgba(249,115,22,0.07)",
            ))
        if "ad_sales" in trend_df.columns:
            fig.add_trace(go.Scatter(
                x=trend_df["_period_dt"], y=trend_df["ad_sales"],
                mode="lines+markers", name="Ad Sales",
                line=dict(color="#4f46e5", width=2.5), marker=dict(size=8),
                fill="tozeroy", fillcolor="rgba(79,70,229,0.07)",
            ))
        # Annotate peak sales month
        if "ad_sales" in trend_df.columns and not trend_df.empty:
            peak = trend_df.loc[trend_df["ad_sales"].idxmax()]
            fig.add_annotation(x=peak["_period_dt"], y=peak["ad_sales"],
                                text=f"Peak {fmt_currency(peak['ad_sales'])}", showarrow=True,
                                arrowhead=2, font=dict(color="#4f46e5", size=12),
                                bgcolor="rgba(79,70,229,0.1)", bordercolor="#4f46e5")
        fig.update_layout(
            height=400, xaxis_title="Month", yaxis_title="Amount ($)",
            legend=dict(orientation="h", y=1.06, x=0.5, xanchor="center"),
            margin=dict(t=60, b=40), hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── 3. ACOS & ROAS with benchmarks ───────────────────────────────────
    r1, r2 = st.columns(2)
    with r1:
        if "acos_%" in trend_df.columns and "_period_dt" in trend_df.columns:
            fig_a = go.Figure()
            fig_a.add_trace(go.Scatter(
                x=trend_df["_period_dt"], y=trend_df["acos_%"],
                mode="lines+markers", fill="tozeroy",
                line=dict(color="#f97316", width=2), marker=dict(size=7),
                fillcolor="rgba(249,115,22,0.08)", name="ACOS %",
            ))
            fig_a.add_hrect(y0=0, y1=15, fillcolor="rgba(16,185,129,0.08)", line_width=0)
            fig_a.add_hrect(y0=15, y1=35, fillcolor="rgba(245,158,11,0.07)", line_width=0)
            fig_a.add_hrect(y0=35, y1=100, fillcolor="rgba(220,38,38,0.07)", line_width=0)
            fig_a.add_hline(y=25, line_dash="dash", line_color="#6b7280",
                             annotation_text="25% benchmark", annotation_font_size=11)
            fig_a.update_layout(title="ACOS Trend (%)", height=320,
                                 xaxis_title="Month", yaxis_title="ACOS (%)",
                                 margin=dict(t=50, b=40))
            st.plotly_chart(fig_a, use_container_width=True)
    with r2:
        if "roas" in trend_df.columns and "_period_dt" in trend_df.columns:
            fig_r = go.Figure()
            fig_r.add_trace(go.Scatter(
                x=trend_df["_period_dt"], y=trend_df["roas"],
                mode="lines+markers", fill="tozeroy",
                line=dict(color="#4f46e5", width=2), marker=dict(size=7),
                fillcolor="rgba(79,70,229,0.08)", name="ROAS",
            ))
            fig_r.add_hline(y=4, line_dash="dash", line_color="#10b981",
                             annotation_text="4x target", annotation_font_size=11)
            fig_r.add_hline(y=2, line_dash="dot", line_color="#dc2626",
                             annotation_text="2x minimum", annotation_font_size=11)
            fig_r.update_layout(title="ROAS Trend", height=320,
                                 xaxis_title="Month", yaxis_title="ROAS",
                                 margin=dict(t=50, b=40))
            st.plotly_chart(fig_r, use_container_width=True)

    # ── 4. CPC trend + CTR trend ──────────────────────────────────────────
    r3, r4 = st.columns(2)
    with r3:
        if "cpc" in trend_df.columns and "_period_dt" in trend_df.columns:
            fig_cpc = go.Figure()
            fig_cpc.add_trace(go.Scatter(
                x=trend_df["_period_dt"], y=trend_df["cpc"],
                mode="lines+markers", name="CPC",
                line=dict(color="#f97316", width=2), marker=dict(size=7),
                fill="tozeroy", fillcolor="rgba(249,115,22,0.07)",
            ))
            fig_cpc.update_layout(title="CPC Trend ($)", height=300,
                                   xaxis_title="Month", yaxis_title="CPC ($)",
                                   margin=dict(t=50, b=40))
            st.plotly_chart(fig_cpc, use_container_width=True)
    with r4:
        if "ctr_%" in trend_df.columns and "_period_dt" in trend_df.columns:
            fig_ctr = go.Figure()
            fig_ctr.add_trace(go.Scatter(
                x=trend_df["_period_dt"], y=trend_df["ctr_%"],
                mode="lines+markers", name="CTR %",
                line=dict(color="#10b981", width=2), marker=dict(size=7),
                fill="tozeroy", fillcolor="rgba(16,185,129,0.07)",
            ))
            fig_ctr.add_hline(y=0.3, line_dash="dash", line_color="#6b7280",
                               annotation_text="0.3% baseline")
            fig_ctr.update_layout(title="CTR Trend (%)", height=300,
                                   xaxis_title="Month", yaxis_title="CTR (%)",
                                   margin=dict(t=50, b=40))
            st.plotly_chart(fig_ctr, use_container_width=True)
        elif "impressions" in trend_df.columns and "_period_dt" in trend_df.columns:
            fig_imp = go.Figure(go.Bar(
                x=trend_df["_period_dt"], y=trend_df["impressions"],
                marker_color="#4f46e5", name="Impressions",
            ))
            fig_imp.update_layout(title="Monthly Impressions", height=300,
                                   margin=dict(t=50, b=40))
            st.plotly_chart(fig_imp, use_container_width=True)

    # ── 5. Stacked spend by ad product ───────────────────────────────────
    if not prod_trend_df.empty and "campaign_type" in prod_trend_df.columns:
        st.markdown('<div class="section-header">📊 Monthly Spend by Ad Type (SP · SB · SD)</div>', unsafe_allow_html=True)
        colors = {"Sponsored Products": "#4f46e5", "Sponsored Brands": "#f97316", "Sponsored Display": "#10b981"}
        fig_pt = go.Figure()
        for prod in prod_trend_df["campaign_type"].unique():
            sub = prod_trend_df[prod_trend_df["campaign_type"] == prod]
            fig_pt.add_trace(go.Bar(
                x=sub["_period_dt"], y=sub["spend"],
                name=str(prod),
                marker_color=colors.get(str(prod), "#6b7280"),
            ))
        fig_pt.update_layout(
            barmode="stack", height=360, xaxis_title="Month", yaxis_title="Spend ($)",
            legend=dict(orientation="h", y=1.06, x=0.5, xanchor="center"),
            margin=dict(t=60, b=40),
        )
        st.plotly_chart(fig_pt, use_container_width=True)

    # ── 6. Raw monthly data table ─────────────────────────────────────────
    with st.expander("📋 View Raw Monthly Data Table"):
        show = [c for c in ["_period_dt","spend","ad_sales","acos_%","roas","impressions","clicks","cpc","ctr_%"] if c in trend_df.columns]
        d = trend_df[show].copy()
        d.columns = [c.replace("_period_dt","Month").replace("_"," ").title() for c in d.columns]
        # Format money columns
        st.dataframe(d, use_container_width=True, height=380)


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tab — How It Works (Engine Logic)
# ---------------------------------------------------------------------------

def render_logic_tab():
    st.markdown('<div class="section-header">⚙️ How This Engine Works</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#ffffff;border-radius:12px;padding:20px 28px;
                box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:20px;">
        <p style="font-size:15px;color:#374151;line-height:1.8;">
        This engine ingests your <strong>Amazon Advertising report</strong> and
        <strong>Vendor Central ASIN Sales report</strong>, extracts key performance baselines,
        then models what happens to every metric when you change spend, target revenue, ROAS, or TACOS.
        Every number you see in the Forecast tab is derived from real formulas — not guesses.
        This page explains every calculation so your entire team can trust and interrogate the output.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Section 1: Core Metric Definitions ─────────────────────────────────
    st.markdown('<div class="section-header">📐 Core Metric Definitions</div>', unsafe_allow_html=True)
    metrics_def = [
        ("ACOS — Advertising Cost of Sales",
         "Spend ÷ Ad-Attributed Sales × 100",
         "How much you spend in ads for every $1 of ad-driven revenue. Lower = more efficient.",
         "Spend = $50,000 · Ad Sales = $200,000 → ACOS = 25%",
         "#f97316"),
        ("ROAS — Return on Ad Spend",
         "Ad-Attributed Sales ÷ Spend",
         "How many dollars of sales every $1 of ad spend generates. Higher = better.",
         "Ad Sales = $200,000 · Spend = $50,000 → ROAS = 4.0x",
         "#4f46e5"),
        ("TACOS — Total Advertising Cost of Sales",
         "Spend ÷ Total Ordered Revenue × 100",
         "Ad spend as a % of ALL revenue (including organic). Shows true ad efficiency against the whole business.",
         "Spend = $50,000 · Total Revenue = $500,000 → TACOS = 10%",
         "#10b981"),
        ("CVR — Conversion Rate",
         "Ad Orders ÷ Clicks × 100",
         "% of ad clicks that result in a purchase. Driven by listing quality, reviews, price.",
         "Orders = 500 · Clicks = 10,000 → CVR = 5%",
         "#6366f1"),
        ("CPC — Cost Per Click",
         "Spend ÷ Clicks",
         "Average auction price per click. Driven by keyword competition and your bid strategy.",
         "Spend = $50,000 · Clicks = 25,000 → CPC = $2.00",
         "#f59e0b"),
        ("CTR — Click-Through Rate",
         "Clicks ÷ Impressions × 100",
         "% of ad impressions that get clicked. Driven by creative quality, title, main image.",
         "Clicks = 25,000 · Impressions = 5,000,000 → CTR = 0.5%",
         "#dc2626"),
    ]
    for i in range(0, len(metrics_def), 3):
        cols = st.columns(3)
        for col, item in zip(cols, metrics_def[i:i+3]):
            name, formula, meaning, example, color = item
            with col:
                st.markdown(f"""
                <div style="background:#ffffff;border-top:4px solid {color};border-radius:10px;
                            padding:16px;box-shadow:0 2px 8px rgba(0,0,0,0.05);height:100%;">
                    <div style="font-size:13px;font-weight:800;color:{color};margin-bottom:6px;">{name}</div>
                    <div style="background:#f0f2ff;border-radius:6px;padding:6px 10px;
                                font-family:monospace;font-size:13px;color:#1e1b4b;margin-bottom:8px;">
                        {formula}
                    </div>
                    <div style="font-size:13px;color:#374151;margin-bottom:8px;">{meaning}</div>
                    <div style="font-size:12px;color:#6b7280;font-style:italic;">📌 {example}</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)

    # ── Section 2: How Scenarios Are Computed ──────────────────────────────
    st.markdown('<div class="section-header">🔢 How Growth Scenarios Are Computed</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#ffffff;border-radius:12px;padding:20px 28px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <p style="font-size:14px;color:#374151;line-height:1.9;">
        When you select a growth scenario (e.g. <strong>+10%</strong>), the engine runs these steps in order:
        </p>
    </div>
    """, unsafe_allow_html=True)

    steps = [
        ("1", "#4f46e5", "Set Target Revenue",
         "Target Revenue = Baseline Revenue × (1 + Growth% ÷ 100)",
         "Baseline = $1,000,000 · Growth = 10% → Target = $1,100,000 · Revenue Gap = $100,000"),
        ("2", "#f97316", "Estimate Ad Contribution",
         "Ad Contribution Ratio = min(Ad Sales ÷ Total Revenue, 90%)\nIncremental Ad Sales Needed = Revenue Gap × Ad Contribution Ratio",
         "Ad Sales = $400,000 · Revenue = $1,000,000 → Ratio = 40%\nGap = $100,000 → Incremental Ad Sales = $40,000"),
        ("3", "#10b981", "Apply ACOS Efficiency Decay",
         "As you spend more, ad efficiency slightly degrades.\nDecay Multiplier = 1 + (Growth% ÷ 10) × 0.04\nProjected ACOS = Current ACOS × Decay Multiplier",
         "Current ACOS = 25% · Growth = 10% → Multiplier = 1.04 → Proj. ACOS = 26%"),
        ("4", "#6366f1", "Calculate Recommended Spend",
         "Target Ad Sales = Current Ad Sales + Incremental Ad Sales Needed\nRecommended Spend = Target Ad Sales × (Projected ACOS ÷ 100)",
         "Target Ad Sales = $440,000 · Proj. ACOS = 26% → Rec. Spend = $114,400"),
        ("5", "#f59e0b", "Derive All Other Metrics",
         "Projected ROAS = Target Ad Sales ÷ Recommended Spend\nProjected TACOS = Recommended Spend ÷ Target Revenue × 100\nIncremental Spend = Recommended Spend − Current Spend",
         "ROAS = $440,000 ÷ $114,400 = 3.85x · TACOS = $114,400 ÷ $1,100,000 = 10.4%"),
        ("6", "#dc2626", "Allocate by Channel Split",
         "SP Budget = Recommended Spend × SP%\nSB Budget = Recommended Spend × SB%\nSD Budget = Recommended Spend × SD%",
         "Spend = $114,400 · SP 65% = $74,360 · SB 25% = $28,600 · SD 10% = $11,440"),
    ]
    for step in steps:
        num, color, title, formula, example = step
        st.markdown(f"""
        <div style="background:#ffffff;border-radius:10px;padding:16px 20px;margin-bottom:10px;
                    box-shadow:0 2px 6px rgba(0,0,0,0.05);border-left:5px solid {color};
                    display:flex;gap:16px;align-items:flex-start;">
            <div style="min-width:36px;height:36px;background:{color};border-radius:50%;
                        display:flex;align-items:center;justify-content:center;
                        font-size:16px;font-weight:900;color:#fff;flex-shrink:0;">{num}</div>
            <div style="flex:1;">
                <div style="font-size:14px;font-weight:800;color:{color};margin-bottom:4px;">{title}</div>
                <div style="background:#f8f9fa;border-radius:6px;padding:8px 12px;
                            font-family:monospace;font-size:12.5px;color:#1e1b4b;
                            white-space:pre-line;margin-bottom:6px;">{formula}</div>
                <div style="font-size:12px;color:#6b7280;font-style:italic;">📌 Example: {example}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Section 3: Custom Override Logic ───────────────────────────────────
    st.markdown('<div class="section-header">🎯 Custom Target Override Logic</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#eff6ff;border:2px solid #3b82f6;border-radius:12px;padding:18px 24px;margin-bottom:16px;">
        <p style="font-size:14px;color:#1e3a8a;line-height:1.9;margin:0;">
        When you enter <strong>Custom Scenario Targets</strong> in the sidebar, the engine overrides the
        growth-% math and instead back-calculates everything from your inputs. You can pin any one metric
        and the rest are derived. Multiple inputs are resolved in priority order.
        </p>
    </div>
    """, unsafe_allow_html=True)

    overrides = [
        ("🏪 Target Revenue / OPS",    "#4f46e5", "Highest priority",
         "Sets Target Revenue directly. Growth% is back-calculated: Growth = (Target ÷ Baseline − 1) × 100",
         "Input $1.2M → Growth = 20%. All spend/ROAS/TACOS derived from this new revenue base."),
        ("📈 Target Ad Sales",          "#f97316", "2nd priority",
         "Pins the ad-attributed sales you expect. Skips the ad-contribution-ratio estimate entirely.",
         "Input $500,000 → Engine uses this as Target Ad Sales to derive required spend."),
        ("⚡ Target ROAS",              "#10b981", "3rd priority (sets spend)",
         "Spend = Target Ad Sales ÷ Target ROAS. Forces the engine to find the spend that hits your ROAS target.",
         "Ad Sales = $500,000 · ROAS = 6x → Spend = $83,333"),
        ("📊 Target TACOS %",           "#6366f1", "4th priority (sets spend)",
         "Spend = Target Revenue × (TACOS ÷ 100). Useful when you have a board-level TACOS ceiling to hit.",
         "Revenue = $1.2M · TACOS = 8% → Spend = $96,000"),
        ("💰 Target Ad Spend",          "#f59e0b", "5th priority (sets spend)",
         "Pins spend directly. ACOS, ROAS, TACOS, and all volume metrics are derived from this spend level.",
         "Input $80,000 → Engine derives ACOS, ROAS, TACOS, Impressions, Clicks, Orders from this spend."),
    ]
    for name, color, priority, logic, example in overrides:
        st.markdown(f"""
        <div style="background:#ffffff;border-radius:10px;padding:14px 18px;margin-bottom:8px;
                    box-shadow:0 1px 5px rgba(0,0,0,0.05);border-left:4px solid {color};">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                <span style="font-size:14px;font-weight:800;color:{color};">{name}</span>
                <span style="font-size:11px;background:{color};color:#fff;border-radius:12px;
                             padding:2px 10px;font-weight:700;">{priority}</span>
            </div>
            <div style="font-size:13px;color:#374151;margin-bottom:4px;">{logic}</div>
            <div style="font-size:12px;color:#6b7280;font-style:italic;">📌 {example}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="reco-card" style="margin-top:6px;">
        <strong>💡 Tip — Combine inputs:</strong> You can set Target Revenue + Target ROAS together.
        The engine will use Revenue to set the revenue target, then use ROAS to back-calculate spend.
        Any metric not explicitly set is derived from the chain.
    </div>""", unsafe_allow_html=True)

    # ── Section 4: Secondary Metric Projection Logic ────────────────────────
    st.markdown('<div class="section-header">📊 How Secondary Metrics Are Projected</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#ffffff;border-radius:12px;padding:20px 28px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <p style="font-size:14px;color:#374151;line-height:1.9;margin:0 0 12px 0;">
        Once Recommended Spend is known, the engine derives all volume metrics using a <strong>Spend Ratio</strong>:
        </p>
        <div style="background:#f0f2ff;border-radius:8px;padding:14px 18px;font-family:monospace;font-size:13px;color:#1e1b4b;">
            Spend Ratio = Recommended Spend ÷ Current Spend<br><br>
            Projected Impressions = Current Impressions × Spend Ratio<br>
            Projected Clicks       = Current Clicks × Spend Ratio<br>
            Projected Ad Orders    = Current Orders × Spend Ratio<br>
            Projected Cost/Order   = Recommended Spend ÷ Projected Orders<br><br>
            CPC  = unchanged  (set by bid strategy &amp; auction competition, not budget level)<br>
            CTR  = unchanged  (set by creative quality &amp; listing, not budget level)<br>
            CVR  = unchanged  (set by listing quality &amp; price, not budget level)
        </div>
        <p style="font-size:13px;color:#6b7280;margin:12px 0 0 0;">
        <strong>Why linear scaling?</strong> Amazon Ads impression/click volume scales roughly linearly
        with budget within the range most brands operate. At very high spend levels efficiency degrades
        (captured by the ACOS decay factor). CPC, CTR, and CVR are listing/bid-driven, not budget-driven.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Section 5: Monthly Plan Logic ──────────────────────────────────────
    st.markdown('<div class="section-header">📅 Monthly Plan & Event Multipliers</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#ffffff;border-radius:12px;padding:20px 28px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <p style="font-size:14px;color:#374151;line-height:1.9;margin:0 0 12px 0;">
        The monthly plan distributes the annual forecast across 12 months using your actual monthly
        spend/sales data as the baseline, then applies event multipliers for high-traffic months:
        </p>
        <div style="background:#f0f2ff;border-radius:8px;padding:14px 18px;font-family:monospace;font-size:13px;color:#1e1b4b;margin-bottom:12px;">
            Monthly Projected Spend = Actual Month Spend × Growth Factor × Event Multiplier<br>
            Monthly Projected Sales = Actual Month Sales × Growth Factor<br><br>
            Growth Factor = 1 + (Growth% ÷ 100)<br>
            Event Multiplier = pre-set per month (see table below)
        </div>
    </div>
    """, unsafe_allow_html=True)

    event_data = [
        ("January",   "New Year Deals",              "1.00x", "No uplift"),
        ("February",  "Valentine's Day 💝",          "1.10x", "+10% spend"),
        ("March",     "Spring Sale 🌸",              "1.00x", "No uplift"),
        ("April",     "—",                           "1.00x", "No uplift"),
        ("May",       "Mother's Day 💐",             "1.08x", "+8% spend"),
        ("June",      "Father's Day 👔 / Mid-Year ☀️","1.08x", "+8% spend"),
        ("July",      "Prime Day ⚡",                "1.30x", "+30% spend — highest volume event"),
        ("August",    "Back to School 🎒",           "1.05x", "+5% spend"),
        ("September", "—",                           "1.00x", "No uplift"),
        ("October",   "Prime Big Deal Days ⚡",      "1.20x", "+20% spend"),
        ("November",  "Black Friday 🛒 / Cyber Monday 💻", "1.45x", "+45% spend — peak of the year"),
        ("December",  "Holiday Season 🎄",           "1.25x", "+25% spend"),
    ]
    ev_df = pd.DataFrame(event_data, columns=["Month", "Events", "Multiplier", "Impact"])
    def _ev_style(row):
        if row["Multiplier"] not in ("1.00x",):
            return ["background-color:#fffbeb;font-weight:600"] * len(row)
        return [""] * len(row)
    st.dataframe(ev_df.style.apply(_ev_style, axis=1), use_container_width=True, height=460)

    # ── Section 6: Channel Split Logic ─────────────────────────────────────
    st.markdown('<div class="section-header">🎯 Channel Split Logic</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#ffffff;border-radius:12px;padding:20px 28px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <p style="font-size:14px;color:#374151;line-height:1.9;margin:0 0 12px 0;">
        The three channel sliders (SP / SB / SD) are <strong>normalised</strong> so they always sum to 100%,
        even if you enter values that don't add up:
        </p>
        <div style="background:#f0f2ff;border-radius:8px;padding:14px 18px;font-family:monospace;font-size:13px;color:#1e1b4b;margin-bottom:12px;">
            Total = SP% + SB% + SD%<br>
            Effective SP Weight = SP% ÷ Total<br>
            Effective SB Weight = SB% ÷ Total<br>
            Effective SD Weight = SD% ÷ Total<br><br>
            SP Budget = Recommended Spend × Effective SP Weight<br>
            SB Budget = Recommended Spend × Effective SB Weight<br>
            SD Budget = Recommended Spend × Effective SD Weight
        </div>
        <p style="font-size:13px;color:#6b7280;margin:0;">
        The sidebar shows the <em>effective</em> split after normalisation.
        Every chart and table in the Forecast tab reflects the normalised weights instantly.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Section 7: Data Sources ─────────────────────────────────────────────
    st.markdown('<div class="section-header">📂 Data Sources & Column Mapping</div>', unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        <div style="background:#ffffff;border-radius:10px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
            <div style="font-weight:800;font-size:14px;color:#4f46e5;margin-bottom:10px;">
                📋 Amazon Advertising Report
            </div>
            <table style="width:100%;font-size:13px;border-collapse:collapse;">
                <tr style="background:#f0f2ff;"><th style="padding:6px;text-align:left;">Engine Field</th><th style="padding:6px;text-align:left;">Report Column(s)</th></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #f0f2ff;">spend</td><td style="padding:5px;border-bottom:1px solid #f0f2ff;">Total cost, Spend, Amount spent</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #f0f2ff;">ad_sales</td><td style="padding:5px;border-bottom:1px solid #f0f2ff;">Sales, Total Sales, 7-day sales</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #f0f2ff;">ad_orders</td><td style="padding:5px;border-bottom:1px solid #f0f2ff;">Purchases, Orders, Conversions</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #f0f2ff;">impressions</td><td style="padding:5px;border-bottom:1px solid #f0f2ff;">Impressions</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #f0f2ff;">clicks</td><td style="padding:5px;border-bottom:1px solid #f0f2ff;">Clicks</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #f0f2ff;">date_range</td><td style="padding:5px;border-bottom:1px solid #f0f2ff;">Date range, Reporting period</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #f0f2ff;">campaign_type</td><td style="padding:5px;border-bottom:1px solid #f0f2ff;">Ad product, Campaign type</td></tr>
                <tr><td style="padding:5px;">asin</td><td style="padding:5px;">Advertised product ID, ASIN</td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)
    with col_b:
        st.markdown("""
        <div style="background:#ffffff;border-radius:10px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
            <div style="font-weight:800;font-size:14px;color:#f97316;margin-bottom:10px;">
                🏪 Vendor Central ASIN Sales Report
            </div>
            <table style="width:100%;font-size:13px;border-collapse:collapse;">
                <tr style="background:#fff7ed;"><th style="padding:6px;text-align:left;">Engine Field</th><th style="padding:6px;text-align:left;">Report Column(s)</th></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #fff7ed;">ordered_revenue</td><td style="padding:5px;border-bottom:1px solid #fff7ed;">Ordered Revenue, Revenue</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #fff7ed;">shipped_revenue</td><td style="padding:5px;border-bottom:1px solid #fff7ed;">Shipped Revenue</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #fff7ed;">ordered_units</td><td style="padding:5px;border-bottom:1px solid #fff7ed;">Ordered Units, Units Ordered</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #fff7ed;">asin</td><td style="padding:5px;border-bottom:1px solid #fff7ed;">ASIN, Product ID</td></tr>
            </table>
            <div style="margin-top:14px;padding:10px 14px;background:#fff7ed;border-radius:8px;
                        border-left:4px solid #f97316;font-size:13px;color:#92400e;">
                <strong>Export tip:</strong> From Vendor Central → Analytics → Sales Diagnostics.
                Select <em>Ordered Revenue</em> + <em>Ordered Units</em> before exporting.
                Without Vendor Central data, the engine uses Ad-Attributed Sales as the revenue proxy.
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Footer note ─────────────────────────────────────────────────────────
    st.markdown("""
    <div style="background:#1e1b4b;border-radius:12px;padding:20px 28px;margin-top:20px;color:#fff;">
        <div style="font-size:15px;font-weight:800;margin-bottom:8px;">📌 Important Assumptions</div>
        <ul style="font-size:13px;color:#c7d2fe;line-height:2;margin:0;padding-left:20px;">
            <li>Ad contribution ratio is capped at 90% — ads rarely drive 100% of revenue.</li>
            <li>ACOS efficiency decay of +4% relative per 10% spend increase is a conservative industry estimate. Your actual decay depends on category competitiveness.</li>
            <li>Secondary volume metrics (impressions, clicks, orders) scale linearly with spend — valid within ±50% of current spend. Beyond that, diminishing returns apply.</li>
            <li>CPC, CTR, and CVR are held constant in projections — they are driven by listing quality and bid strategy, not budget level.</li>
            <li>Event multipliers are based on Amazon category averages. Your specific category may vary.</li>
            <li>All projections are estimates. Actual results depend on competition, listing quality, seasonality, and Amazon algorithm changes.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)



def main():
    # ---- Header ------------------------------------------------
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
                    <strong>Get 5 insight tabs instantly</strong>
                    <span>Key Metrics &nbsp;·&nbsp; Product Intelligence &nbsp;·&nbsp; Trend Analysis &nbsp;·&nbsp; Forecast &amp; Media Plan &nbsp;·&nbsp; Recommendations</span>
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

    # ---- Parse files (cached so slider changes don't re-parse) -------------
    ads_df = None
    vendor_df = None
    ads_metrics = {}
    vendor_metrics = {}

    @st.cache_data(show_spinner=False)
    def _load_ads(file):
        df = parse_amazon_ads_report(file)
        metrics = extract_ads_metrics(df)
        return df, metrics

    @st.cache_data(show_spinner=False)
    def _load_vendor(file):
        df = parse_vendor_central_report(file)
        metrics = extract_vendor_metrics(df)
        return df, metrics

    @st.cache_data(show_spinner=False)
    def _compute_breakdowns(ads_df, vendor_df):
        _ads = ads_df if ads_df is not None else pd.DataFrame()
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

    # ---- Pre-compute breakdowns (cached) ----------------------------------
    bd = _compute_breakdowns(ads_df, vendor_df)
    campaign_df    = bd["campaign_df"]
    asin_ads_df    = bd["asin_ads_df"]
    asin_vendor_df = bd["asin_vendor_df"]
    merged_asin_df = merge_asin_view(asin_ads_df, asin_vendor_df)
    st_insights    = bd["st_insights"]
    wasted         = bd["wasted"]
    match_df       = bd["match_df"]
    prod_intel     = bd["prod_intel"]
    bid_df         = bd["bid_df"]
    ad_prod_df     = bd["ad_prod_df"]
    trend_df       = bd["trend_df"]
    t_summary      = trend_summary(trend_df)
    prod_trend_df  = bd["prod_trend_df"]

    # ---- Tabs ---------------------------------------------------------------
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

    # ---- Download button ---------------------------------------------------
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

    # ---- Footer ---------------------------------------------------------------
    st.markdown("""
    <div class="tool-footer">
        Amazon Media Plan Forecast Engine &nbsp;&#183;&nbsp;
        Created by <strong>Sumeet Mangotra</strong>, Brand Ecommerce Manager
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
