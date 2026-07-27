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
        st.info(f"🎯 **Custom scenario active** — pinned inputs: **{active_labels}**. All other metrics derived.")

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
    scenario_labels = [f"+{s['growth_pct']}%" for s in scenarios]
    if scenario_labels:
        selected_label = st.selectbox(
            "Select Growth Scenario for Monthly Plan:",
            options=scenario_labels,
            index=min(1, len(scenario_labels) - 1),  # default +10% if available
            key="monthly_scenario_select",
        )
        sel_growth_pct = float(selected_label.replace("+", "").replace("%", ""))
    else:
        sel_growth_pct = growth_options[0] if growth_options else 10

    monthly_df = monthly_forecast(
        trend_df=trend_df,
        growth_pct=sel_growth_pct,
        total_ordered_revenue=baseline_revenue,
        custom_channel_split=channel_split,
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
        name=f"Projected Spend ({selected_label if scenario_labels else '+' + str(int(sel_growth_pct)) + '%'})",
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
        title=f"Monthly Spend & Sales — {selected_label if scenario_labels else str(int(sel_growth_pct)) + '%'} Growth Scenario  |  🟠 = High-Sales Event Month",
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
    st.markdown('<div class="section-header">📋 Monthly Plan Detail Table</div>', unsafe_allow_html=True)

    display_cols = [
        "Month Name", "Events",
        "Actual Spend ($)", "Actual Ad Sales ($)", "Actual ACOS (%)", "Actual ROAS",
        "Projected Spend ($)", "Projected Ad Sales ($)", "Projected ACOS (%)", "Projected ROAS",
        "Spend Uplift %", "SP Budget ($)", "SB Budget ($)", "SD Budget ($)",
    ]
    disp_df = monthly_df[display_cols].copy()

    def _style_monthly_row(row):
        if row["Events"] != "—":
            return ["background-color: #fffbeb; font-weight: 600"] * len(row)
        return [""] * len(row)

    money_cols = [c for c in display_cols if "$" in c]
    pct_cols   = [c for c in display_cols if "%" in c and c != "Spend Uplift %"]
    fmt_map = {}
    for c in money_cols:
        fmt_map[c] = "${:,.0f}"
    for c in pct_cols:
        fmt_map[c] = "{:.1f}%"
    fmt_map["Actual ROAS"]     = "{:.2f}x"
    fmt_map["Projected ROAS"]  = "{:.2f}x"
    fmt_map["Spend Uplift %"]  = "+{:.0f}%"

    styled = disp_df.style.format(fmt_map, na_rep="—").apply(_style_monthly_row, axis=1)
    st.dataframe(styled, use_container_width=True, height=460)

    return scenarios


# ---------------------------------------------------------------------------
# Tab 4 — Strategic Recommendations
# ---------------------------------------------------------------------------

def render_recommendations(ads_metrics, vendor_metrics, scenarios):
    st.markdown('<div class="section-header">💡 Strategic Recommendations</div>', unsafe_allow_html=True)

    acos = ads_metrics.get("overall_acos")
    roas = ads_metrics.get("overall_roas")
    ctr = ads_metrics.get("overall_ctr")
    cpc = ads_metrics.get("overall_cpc")

    recs = []

    # ACOS recommendations
    if acos is not None:
        if acos > 35:
            recs.append(("⚠️ High ACOS Alert",
                f"Your ACOS of {fmt_pct(acos)} is above the 35% benchmark. "
                "Consider pausing underperforming keywords, tightening match types to exact/phrase, "
                "and reducing bids on high-ACOS targets.", "warning"))
        elif acos < 15:
            recs.append(("✅ Efficient ACOS — Room to Scale",
                f"Your ACOS of {fmt_pct(acos)} is very efficient. "
                "You likely have headroom to increase bids and expand keyword coverage "
                "to capture more volume without sacrificing profitability.", "reco"))
        else:
            recs.append(("✅ Healthy ACOS",
                f"Your ACOS of {fmt_pct(acos)} is within a healthy range (15–35%). "
                "Focus on scaling top-performing campaigns while monitoring efficiency.", "reco"))

    # ROAS recommendations
    if roas is not None:
        if roas < 2:
            recs.append(("⚠️ Low ROAS",
                f"ROAS of {roas:.2f}x is below the 2x minimum threshold for most categories. "
                "Audit your product listing quality, review pricing vs competitors, "
                "and eliminate wasteful broad match keywords.", "warning"))
        elif roas >= 4:
            recs.append(("✅ Strong ROAS",
                f"ROAS of {roas:.2f}x is strong. Increase budgets on best-performing campaigns "
                "and consider Sponsored Brands and Sponsored Display to build brand awareness.", "reco"))

    # CTR
    if ctr is not None:
        if ctr < 0.3:
            recs.append(("⚠️ Low CTR",
                f"CTR of {fmt_pct(ctr)} is below the 0.3% baseline. "
                "Review main image quality, title relevance, and consider A+ content or "
                "enhanced listing optimisation to improve click rates.", "warning"))

    # Growth scenario insights
    if scenarios:
        s10 = next((s for s in scenarios if s["growth_pct"] == 10), None)
        if s10:
            recs.append(("📈 To Achieve +10% Sales Growth",
                f"Increase total ad spend from {fmt_currency(s10['current_ad_spend'])} to "
                f"{fmt_currency(s10['recommended_spend'])} "
                f"(+{fmt_currency(s10['incremental_spend'])} incremental). "
                f"Expected ACOS: {fmt_pct(s10['projected_acos_pct'])}, "
                f"ROAS: {s10['projected_roas']:.2f}x. "
                f"Prioritise Sponsored Products (65%) for conversion-focused spend.", "reco"))

    # Channel strategy
    recs.append(("🎯 Channel Investment Strategy",
        "**Sponsored Products (65%)** — Direct response, conversion-focused. Invest here first for ROAS efficiency. "
        "Use auto campaigns for discovery and manual exact/phrase for scaling winners. "
        "**Sponsored Brands (25%)** — Top-of-funnel awareness and brand store traffic. "
        "Run video ads for high-converting ASINs. "
        "**Sponsored Display (10%)** — Retargeting and competitor conquesting. "
        "Use for remarketing to product detail page visitors.", "reco"))

    recs.append(("📅 Seasonal Budget Planning",
        "Increase budgets 2–3 weeks before peak events (Prime Day, Black Friday, Cyber Monday, Q4). "
        "Build enough keyword history and quality score before the peak window. "
        "Recommended: +30–50% budget increase 2 weeks before peak, "
        "+15–20% during peak recovery phase.", "reco"))

    recs.append(("🔍 ASIN Prioritisation",
        "Focus incremental ad spend on your top 20% of ASINs by ordered revenue — "
        "these typically drive 80% of sales. "
        "For new ASINs with < 30 reviews, use auto campaigns with aggressive bids to build ranking history. "
        "Avoid heavy spend on ASINs below 3.5★ rating until listing quality is improved.", "reco"))

    # Render
    for title, body, card_type in recs:
        css_class = "reco-card" if card_type == "reco" else "warning-card"
        st.markdown(f"""
        <div class="{css_class}">
            <strong>{title}</strong><br>
            {body}
        </div>
        """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tab — Search Term Intelligence
# ---------------------------------------------------------------------------

def render_search_term_tab(st_insights: dict, wasted: dict, match_df):
    if not st_insights:
        st.info("No search term data found in your report. This tab requires a report with a 'Search term' column.")
        return

    # Wasted spend banner
    if wasted:
        w_amt = wasted.get("wasted_spend", 0)
        w_pct = wasted.get("wasted_pct", 0)
        col_w1, col_w2, col_w3 = st.columns(3)
        with col_w1:
            st.markdown(metric_card("💸 Wasted Spend", fmt_currency(w_amt), f"{w_pct}% of total budget — zero purchases"), unsafe_allow_html=True)
        with col_w2:
            st.markdown(metric_card("✅ Productive Spend", fmt_currency(wasted.get("total_spend", 0) - w_amt), "Generated at least 1 purchase"), unsafe_allow_html=True)
        with col_w3:
            recoverable = w_amt * 0.6
            st.markdown(metric_card("💡 Recoverable Budget", fmt_currency(recoverable), "Est. reclaimable for better keywords"), unsafe_allow_html=True)

    # Top converting search terms
    st.markdown('<div class="section-header">🏆 Top Converting Search Terms</div>', unsafe_allow_html=True)
    top_df = st_insights.get("top_converting", pd.DataFrame())
    if not top_df.empty:
        cols = [c for c in ["search_term", "ad_sales", "spend", "acos_%", "roas", "cvr_%", "ad_orders", "clicks"] if c in top_df.columns]
        disp = top_df[cols].head(20).copy()
        disp.columns = [c.replace("_", " ").replace("%", "Pct").title() for c in disp.columns]
        st.dataframe(disp, use_container_width=True, height=360)

        # Bar chart — top 10 by sales
        if "search_term" in top_df.columns and "ad_sales" in top_df.columns:
            fig = go.Figure()
            t10 = top_df.head(10)
            fig.add_trace(go.Bar(x=t10["search_term"], y=t10["ad_sales"], name="Ad Sales", marker_color="#4f46e5"))
            if "spend" in t10.columns:
                fig.add_trace(go.Bar(x=t10["search_term"], y=t10["spend"], name="Spend", marker_color="#f97316"))
            fig.update_layout(barmode="group", title="Top 10 Search Terms: Sales vs Spend",
                              xaxis_tickangle=-35, height=380, margin=dict(t=50, b=100),
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig, use_container_width=True)

    # Wasted spend table
    st.markdown('<div class="section-header">⚠️ Wasted Spend — Clicks with Zero Purchases</div>', unsafe_allow_html=True)
    waste_df = st_insights.get("wasted_spend", pd.DataFrame())
    if not waste_df.empty:
        cols = [c for c in ["search_term", "spend", "clicks", "impressions"] if c in waste_df.columns]
        disp = waste_df[cols].head(20).copy()
        disp.columns = [c.replace("_", " ").title() for c in disp.columns]
        st.dataframe(disp, use_container_width=True, height=300)
        st.markdown(f"""
        <div class="warning-card">
            <strong>Action:</strong> Add these search terms as <strong>negative keywords</strong> in your campaigns
            to stop wasting budget. Total recoverable spend: <strong>{fmt_currency(wasted.get("wasted_spend", 0))}</strong>
        </div>""", unsafe_allow_html=True)
    else:
        st.success("No pure wasted spend detected — all search terms with clicks have at least one purchase.")

    # NTB Leaders
    ntb_df = st_insights.get("ntb_leaders", pd.DataFrame())
    if not ntb_df.empty:
        st.markdown('<div class="section-header">🆕 New to Brand Leaders</div>', unsafe_allow_html=True)
        cols = [c for c in ["search_term", "ntb_%", "ad_orders_ntb", "ad_orders", "spend", "ad_sales"] if c in ntb_df.columns]
        disp = ntb_df[cols].head(15).copy()
        disp.columns = [c.replace("_", " ").replace("%", "Pct").title() for c in disp.columns]
        st.dataframe(disp, use_container_width=True, height=280)
        st.markdown("""<div class="reco-card">
            <strong>Insight:</strong> These search terms drive a high % of first-time buyers.
            Increase bids on these terms to grow your customer base and long-term brand value.
        </div>""", unsafe_allow_html=True)

    # Harvest candidates
    harvest_df = st_insights.get("harvest_candidates", pd.DataFrame())
    if not harvest_df.empty:
        st.markdown('<div class="section-header">🌱 Keyword Harvest Candidates</div>', unsafe_allow_html=True)
        cols = [c for c in ["search_term", "cvr_%", "ad_orders", "spend", "acos_%"] if c in harvest_df.columns]
        disp = harvest_df[cols].head(15).copy()
        disp.columns = [c.replace("_", " ").replace("%", "Pct").title() for c in disp.columns]
        st.dataframe(disp, use_container_width=True, height=280)
        st.markdown("""<div class="reco-card">
            <strong>Action:</strong> Add these high-converting search terms as <strong>Exact Match</strong>
            keywords in your manual campaigns to capture volume efficiently.
        </div>""", unsafe_allow_html=True)

    # Match type efficiency
    if not match_df.empty:
        st.markdown('<div class="section-header">🎯 Match Type Efficiency</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            cols = [c for c in ["match_type", "spend", "ad_sales", "acos_%", "roas", "cvr_%", "cpc"] if c in match_df.columns]
            disp = match_df[cols].copy()
            disp.columns = [c.replace("_", " ").replace("%", "Pct").title() for c in disp.columns]
            st.dataframe(disp, use_container_width=True)
        with c2:
            if "acos_%" in match_df.columns and "match_type" in match_df.columns:
                fig_mt = go.Figure()
                fig_mt.add_trace(go.Bar(x=match_df["match_type"], y=match_df["acos_%"], marker_color="#f97316", name="ACOS %"))
                fig_mt.update_layout(title="ACOS by Match Type", height=300, margin=dict(t=50, b=30))
                st.plotly_chart(fig_mt, use_container_width=True)


# ---------------------------------------------------------------------------
# Tab — Product Intelligence
# ---------------------------------------------------------------------------

def render_product_tab(prod_intel: dict, ad_prod_df, bid_df):
    if not prod_intel:
        st.info("No ASIN-level data found. This tab requires 'Advertised product ID' in your report.")
        return

    # Ad product type breakdown
    if not ad_prod_df.empty:
        st.markdown('<div class="section-header">📢 Ad Product Type Breakdown (SP / SB / SD)</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            cols = [c for c in ["ad_product", "spend", "ad_sales", "acos_%", "roas", "spend_share_%"] if c in ad_prod_df.columns]
            disp = ad_prod_df[cols].copy()
            disp.columns = [c.replace("_", " ").replace("%", "Pct").title() for c in disp.columns]
            st.dataframe(disp, use_container_width=True)
        with c2:
            if "spend" in ad_prod_df.columns and "ad_product" in ad_prod_df.columns:
                fig_pie = go.Figure(go.Pie(
                    labels=ad_prod_df["ad_product"],
                    values=ad_prod_df["spend"],
                    hole=0.45,
                    marker_colors=["#1a0a14", "#cc2200", "#798da0", "#f4f4f4"],
                ))
                fig_pie.update_layout(title="Spend Share by Ad Product", height=300, margin=dict(t=50, b=10))
                st.plotly_chart(fig_pie, use_container_width=True)

    # Top ROAS ASINs
    top_roas = prod_intel.get("top_roas", pd.DataFrame())
    if not top_roas.empty:
        st.markdown('<div class="section-header">🚀 Top 10 ASINs by ROAS — Scale These</div>', unsafe_allow_html=True)
        cols = [c for c in ["asin", "product_title", "roas", "ad_sales", "spend", "acos_%", "cvr_%", "ntb_%"] if c in top_roas.columns]
        disp = top_roas[cols].copy()
        disp.columns = [c.replace("_", " ").replace("%", "Pct").title() for c in disp.columns]
        st.dataframe(disp, use_container_width=True, height=300)

        if "asin" in top_roas.columns and "roas" in top_roas.columns:
            fig_roas = go.Figure(go.Bar(
                x=top_roas["asin"], y=top_roas["roas"],
                marker_color="#4f46e5", text=top_roas["roas"].round(1), textposition="outside",
            ))
            fig_roas.update_layout(title="Top ASINs by ROAS", height=320, margin=dict(t=50, b=40))
            st.plotly_chart(fig_roas, use_container_width=True)

    # Worst ACOS ASINs
    worst_acos = prod_intel.get("worst_acos", pd.DataFrame())
    if not worst_acos.empty:
        st.markdown('<div class="section-header">🔴 Top 10 ASINs by ACOS — Review or Pause</div>', unsafe_allow_html=True)
        cols = [c for c in ["asin", "product_title", "acos_%", "spend", "ad_sales", "roas", "ad_orders"] if c in worst_acos.columns]
        disp = worst_acos[cols].copy()
        disp.columns = [c.replace("_", " ").replace("%", "Pct").title() for c in disp.columns]
        st.dataframe(disp, use_container_width=True, height=300)
        st.markdown("""<div class="warning-card">
            <strong>Action:</strong> Review these ASINs — check listing quality, pricing vs competitors,
            and review quality. Consider pausing or reducing bids until the issues are resolved.
        </div>""", unsafe_allow_html=True)

    # Category rollup
    cat_df = prod_intel.get("by_category", pd.DataFrame())
    if not cat_df.empty:
        st.markdown('<div class="section-header">🗂️ Category Performance Rollup</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            cols = [c for c in ["category", "spend", "ad_sales", "acos_%", "roas", "ad_orders"] if c in cat_df.columns]
            disp = cat_df[cols].copy()
            disp.columns = [c.replace("_", " ").replace("%", "Pct").title() for c in disp.columns]
            st.dataframe(disp, use_container_width=True)
        with c2:
            if "category" in cat_df.columns and "ad_sales" in cat_df.columns:
                fig_cat = go.Figure(go.Bar(
                    x=cat_df["category"], y=cat_df["ad_sales"],
                    marker_color="#f97316", name="Ad Sales",
                ))
                fig_cat.update_layout(title="Ad Sales by Category", height=300,
                                      xaxis_tickangle=-30, margin=dict(t=50, b=80))
                st.plotly_chart(fig_cat, use_container_width=True)

    # Bid strategy
    if not bid_df.empty:
        st.markdown('<div class="section-header">⚙️ Bid Strategy Performance</div>', unsafe_allow_html=True)
        cols = [c for c in ["bid_strategy", "spend", "ad_sales", "acos_%", "roas", "impressions"] if c in bid_df.columns]
        disp = bid_df[cols].copy()
        disp.columns = [c.replace("_", " ").replace("%", "Pct").title() for c in disp.columns]
        st.dataframe(disp, use_container_width=True)


# ---------------------------------------------------------------------------
# Tab — Trend Analysis
# ---------------------------------------------------------------------------

def render_trend_tab(trend_df, t_summary: dict, prod_trend_df):
    if trend_df.empty:
        st.info("No date/time data found. Trend analysis requires a 'Date range' column in your report.")
        return

    # MoM summary banners
    if t_summary:
        st.markdown('<div class="section-header">📊 Period-over-Period Changes</div>', unsafe_allow_html=True)
        cols = st.columns(4)
        def delta_str(val):
            if val is None:
                return None
            arrow = "▲" if val > 0 else "▼"
            return f"{arrow} {abs(val):.1f}% vs prior period"

        with cols[0]:
            st.markdown(metric_card("Spend Change", delta_str(t_summary.get("spend_change_pct")) or "N/A",
                                     t_summary.get("latest_period")), unsafe_allow_html=True)
        with cols[1]:
            st.markdown(metric_card("Sales Change", delta_str(t_summary.get("sales_change_pct")) or "N/A",
                                     t_summary.get("latest_period")), unsafe_allow_html=True)
        with cols[2]:
            st.markdown(metric_card("ACOS Change", delta_str(t_summary.get("acos_change_pct")) or "N/A",
                                     "Lower is better"), unsafe_allow_html=True)
        with cols[3]:
            st.markdown(metric_card("ROAS Change", delta_str(t_summary.get("roas_change_pct")) or "N/A",
                                     "Higher is better"), unsafe_allow_html=True)

    # Spend vs Sales trend
    st.markdown('<div class="section-header">📈 Monthly Spend vs Sales Trend</div>', unsafe_allow_html=True)
    if "_period_dt" in trend_df.columns:
        fig = go.Figure()
        if "spend" in trend_df.columns:
            fig.add_trace(go.Scatter(x=trend_df["_period_dt"], y=trend_df["spend"],
                                      mode="lines+markers", name="Ad Spend",
                                      line=dict(color="#f97316", width=2), marker=dict(size=7)))
        if "ad_sales" in trend_df.columns:
            fig.add_trace(go.Scatter(x=trend_df["_period_dt"], y=trend_df["ad_sales"],
                                      mode="lines+markers", name="Ad Sales",
                                      line=dict(color="#4f46e5", width=2), marker=dict(size=7)))
        fig.update_layout(title="Monthly Spend vs Ad Sales", height=380,
                          xaxis_title="Month", yaxis_title="Amount ($)",
                          legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                          margin=dict(t=60, b=40))
        st.plotly_chart(fig, use_container_width=True)

    # ACOS trend
    c1, c2 = st.columns(2)
    with c1:
        if "acos_%" in trend_df.columns:
            fig_acos = go.Figure(go.Scatter(
                x=trend_df["_period_dt"], y=trend_df["acos_%"],
                mode="lines+markers", fill="tozeroy",
                line=dict(color="#f97316", width=2), marker=dict(size=6),
                fillcolor="rgba(204,34,0,0.08)",
            ))
            fig_acos.add_hline(y=25, line_dash="dash", line_color="gray", annotation_text="25% benchmark")
            fig_acos.update_layout(title="ACOS Trend (%)", height=320,
                                    xaxis_title="Month", yaxis_title="ACOS (%)",
                                    margin=dict(t=50, b=40))
            st.plotly_chart(fig_acos, use_container_width=True)
    with c2:
        if "roas" in trend_df.columns:
            fig_roas = go.Figure(go.Scatter(
                x=trend_df["_period_dt"], y=trend_df["roas"],
                mode="lines+markers", fill="tozeroy",
                line=dict(color="#4f46e5", width=2), marker=dict(size=6),
                fillcolor="rgba(26,10,20,0.08)",
            ))
            fig_roas.add_hline(y=4, line_dash="dash", line_color="green", annotation_text="4x target")
            fig_roas.update_layout(title="ROAS Trend", height=320,
                                    xaxis_title="Month", yaxis_title="ROAS",
                                    margin=dict(t=50, b=40))
            st.plotly_chart(fig_roas, use_container_width=True)

    # CPC & CTR trends
    c3, c4 = st.columns(2)
    with c3:
        if "cpc" in trend_df.columns:
            fig_cpc = go.Figure(go.Bar(
                x=trend_df["_period_dt"], y=trend_df["cpc"],
                marker_color="#f97316", name="CPC",
            ))
            fig_cpc.update_layout(title="CPC Trend ($)", height=300, margin=dict(t=50, b=40))
            st.plotly_chart(fig_cpc, use_container_width=True)
    with c4:
        if "impressions" in trend_df.columns:
            fig_imp = go.Figure(go.Bar(
                x=trend_df["_period_dt"], y=trend_df["impressions"],
                marker_color="#4f46e5", name="Impressions",
            ))
            fig_imp.update_layout(title="Monthly Impressions", height=300, margin=dict(t=50, b=40))
            st.plotly_chart(fig_imp, use_container_width=True)

    # Ad product spend trend
    if not prod_trend_df.empty and "campaign_type" in prod_trend_df.columns:
        st.markdown('<div class="section-header">📊 Monthly Spend by Ad Product (SP / SB / SD)</div>', unsafe_allow_html=True)
        fig_pt = go.Figure()
        colors = ["#1a0a14", "#cc2200", "#798da0"]
        for i, prod in enumerate(prod_trend_df["campaign_type"].unique()):
            sub = prod_trend_df[prod_trend_df["campaign_type"] == prod]
            fig_pt.add_trace(go.Bar(
                x=sub["_period_dt"], y=sub["spend"],
                name=str(prod), marker_color=colors[i % len(colors)],
            ))
        fig_pt.update_layout(barmode="stack", title="Spend by Ad Product Over Time",
                              height=360, xaxis_title="Month", yaxis_title="Spend ($)",
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                              margin=dict(t=60, b=40))
        st.plotly_chart(fig_pt, use_container_width=True)

    # Raw trend table
    with st.expander("📋 View Raw Monthly Data"):
        cols = [c for c in ["_period_dt", "spend", "ad_sales", "acos_%", "roas", "impressions", "clicks", "cpc"] if c in trend_df.columns]
        disp = trend_df[cols].copy()
        disp.columns = [c.replace("_period_dt", "Month").replace("_", " ").replace("%", "Pct").title() for c in disp.columns]
        st.dataframe(disp, use_container_width=True)


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

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
                    <strong>Get 6 insight tabs instantly</strong>
                    <span>Key Metrics &nbsp;·&nbsp; Search Term Intelligence &nbsp;·&nbsp; Product Intelligence &nbsp;·&nbsp; Trend Analysis &nbsp;·&nbsp; Forecast &nbsp;·&nbsp; Recommendations</span>
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
        "🔎 Search Term Intelligence",
        "📦 Product Intelligence",
        "📅 Trend Analysis",
        "📈 Forecast & Media Plan",
        "💡 Recommendations",
    ])

    with tab1:
        render_metrics_dashboard(ads_metrics, vendor_metrics)

    with tab2:
        render_search_term_tab(st_insights, wasted, match_df)

    with tab3:
        render_product_tab(prod_intel, ad_prod_df, bid_df)

    with tab4:
        render_trend_tab(trend_df, t_summary, prod_trend_df)

    scenarios = []
    with tab5:
        if ads_df is not None or vendor_df is not None:
            scenarios = render_forecast(
                ads_metrics, vendor_metrics, campaign_df, growth_options, channel_split,
                trend_df=trend_df, custom_targets=custom_targets,
            )

    with tab6:
        render_recommendations(ads_metrics, vendor_metrics, scenarios)

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
