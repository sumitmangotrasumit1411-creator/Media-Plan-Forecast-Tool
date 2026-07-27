"""
app.py — Media Plan Forecast Tool
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
from forecast import run_multi_scenario, scenarios_to_dataframe, run_forecast
from exporter import build_excel_media_plan

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Acosta | Amazon Media Plan Forecast",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Acosta Brand Colors (from official logo)
# DARK BG  #1a0a14  |  RED  #cc2200  |  WHITE #ffffff  |  GREY #f4f4f4
# ---------------------------------------------------------------------------
ACOSTA_DARK  = "#1a0a14"
ACOSTA_RED   = "#cc2200"
ACOSTA_GREY  = "#f4f4f4"
ACOSTA_MUTED = "#6b7280"

st.markdown("""
<style>
    /* ---- Acosta brand palette ---- */
    :root {
        --acosta-dark: #1a0a14;
        --acosta-red:  #cc2200;
        --acosta-grey: #f4f4f4;
        --acosta-muted: #6b7280;
    }

    /* Sidebar background — matches logo dark bg */
    [data-testid="stSidebar"] { background-color: #1a0a14 !important; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3 { color: #ffffff !important; }
    [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.15) !important; }

    /* Header banner */
    .acosta-header {
        background: #1a0a14;
        padding: 16px 24px;
        border-radius: 8px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 3px solid #cc2200;
    }
    .acosta-header-right { text-align: right; }
    .acosta-header-sub {
        font-size: 12px; color: rgba(255,255,255,0.65); margin-top: 6px;
    }
    .acosta-badge {
        background: #cc2200; color: #ffffff;
        font-size: 11px; font-weight: 700;
        padding: 4px 12px; border-radius: 20px;
        white-space: nowrap; display: inline-block;
    }
    .acosta-created-by {
        font-size: 11px; color: rgba(255,255,255,0.5);
        margin-top: 4px;
    }

    /* Metric cards */
    .metric-card {
        background: #f9f9f9;
        border: 1px solid #e5e7eb;
        border-top: 3px solid #1a0a14;
        border-radius: 6px;
        padding: 16px 20px;
        margin: 4px 0;
    }
    .metric-label { font-size: 11px; color: #6b7280; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; }
    .metric-value { font-size: 22px; font-weight: 800; color: #1a0a14; }
    .metric-delta { font-size: 12px; color: #cc2200; font-weight: 500; }

    /* Section headers */
    .section-header {
        font-size: 17px; font-weight: 700; color: #1a0a14;
        border-bottom: 3px solid #cc2200; padding-bottom: 6px;
        margin: 28px 0 16px 0;
    }

    /* Recommendation cards */
    .reco-card {
        background: #fdf5f0;
        border-left: 4px solid #1a0a14;
        padding: 12px 16px;
        border-radius: 4px;
        margin: 8px 0;
    }
    .warning-card {
        background: #fff0f0;
        border-left: 4px solid #cc2200;
        padding: 12px 16px;
        border-radius: 4px;
        margin: 8px 0;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab"] { font-size: 14px; font-weight: 600; }
    .stTabs [aria-selected="true"] { color: #cc2200 !important; border-bottom-color: #cc2200 !important; }

    /* Footer */
    .acosta-footer {
        margin-top: 40px;
        padding: 16px 0 8px;
        border-top: 2px solid #1a0a14;
        text-align: center;
        font-size: 12px;
        color: #6b7280;
    }
    .acosta-footer strong { color: #1a0a14; }
    .acosta-footer a { color: #cc2200; text-decoration: none; }
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
    <div style="text-align:center; padding:16px 0 10px;">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 70" width="148" height="47">
          <rect width="220" height="70" rx="4" fill="#1a0a14"/>
          <rect x="155" y="8"  width="9" height="9" fill="#cc2200"/>
          <rect x="164" y="8"  width="9" height="9" fill="#8b1a1a"/>
          <rect x="155" y="17" width="9" height="9" fill="#8b1a1a"/>
          <rect x="164" y="17" width="9" height="9" fill="#cc2200"/>
          <text x="14" y="50" font-family="Arial Black,Arial,sans-serif"
                font-weight="900" font-size="34" fill="#ffffff" letter-spacing="-0.5">acosta</text>
        </svg>
        <div style="font-size:10px; color:rgba(255,255,255,0.5); margin-top:8px;">
            Sumeet Mangotra &#183; Brand Ecommerce Manager
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📂 Upload Reports")
    st.sidebar.markdown("---")

    ads_file = st.sidebar.file_uploader(
        "Amazon Advertising Report",
        type=["csv", "xlsx", "xls"],
        help="Export from Amazon Ads Console: Campaign Manager → Reports (up to 2GB)",
    )

    vendor_file = st.sidebar.file_uploader(
        "Vendor Central ASIN Sales Report",
        type=["csv", "xlsx", "xls"],
        help="Export from Vendor Central → Analytics → Sales Diagnostics (up to 2GB)",
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
    sb_pct = st.sidebar.slider("Sponsored Brands %", 0, 100 - sp_pct, 25)
    sd_pct = 100 - sp_pct - sb_pct
    st.sidebar.markdown(f"Sponsored Display: **{sd_pct}%** (auto-calculated)")

    channel_split = {
        "Sponsored Products": sp_pct / 100,
        "Sponsored Brands": sb_pct / 100,
        "Sponsored Display": sd_pct / 100,
    }

    return ads_file, vendor_file, growth_options, channel_split


# ---------------------------------------------------------------------------
# Tab 1 — Key Metrics Dashboard
# ---------------------------------------------------------------------------

def render_metrics_dashboard(ads_metrics, vendor_metrics):
    st.markdown('<div class="section-header">📊 Amazon Advertising Metrics</div>', unsafe_allow_html=True)

    cols = st.columns(4)
    kpis_ads = [
        ("Total Ad Spend", fmt_currency(ads_metrics.get("total_spend")), None),
        ("Ad-Attributed Sales", fmt_currency(ads_metrics.get("total_ad_sales")), None),
        ("Overall ACOS", fmt_pct(ads_metrics.get("overall_acos")), "Lower is better"),
        ("Overall ROAS", f"{ads_metrics.get('overall_roas') or 'N/A':.2f}x" if ads_metrics.get("overall_roas") else "N/A", "Higher is better"),
        ("Total Impressions", fmt_num(ads_metrics.get("total_impressions")), None),
        ("Total Clicks", fmt_num(ads_metrics.get("total_clicks")), None),
        ("CTR", fmt_pct(ads_metrics.get("overall_ctr")), None),
        ("CPC", fmt_currency(ads_metrics.get("overall_cpc")), None),
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
                fig.add_trace(go.Bar(x=top10[name_col], y=top10["spend"], name="Ad Spend", marker_color="#293C5B"))
            if "ad_sales" in top10.columns:
                fig.add_trace(go.Bar(x=top10[name_col], y=top10["ad_sales"], name="Ad Sales", marker_color="#e71d36"))
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

def render_forecast(ads_metrics, vendor_metrics, campaign_df, growth_options, channel_split):
    total_ordered_revenue = vendor_metrics.get("total_ordered_revenue", 0) if vendor_metrics else 0
    total_ad_spend = ads_metrics.get("total_spend", 0)
    total_ad_sales = ads_metrics.get("total_ad_sales", 0)

    # Use ads-attributed sales as revenue fallback if no vendor data
    baseline_revenue = total_ordered_revenue if total_ordered_revenue > 0 else total_ad_sales

    if baseline_revenue == 0:
        st.warning("No revenue data found. Please check your reports.")
        return []

    scenarios = run_multi_scenario(
        total_ordered_revenue=baseline_revenue,
        total_ad_spend=total_ad_spend,
        total_ad_sales=total_ad_sales,
        growth_scenarios=growth_options,
        custom_channel_split=channel_split,
        campaign_df=campaign_df if campaign_df is not None and not campaign_df.empty else None,
    )

    # ---- Scenario Comparison Table
    st.markdown('<div class="section-header">📋 Scenario Comparison</div>', unsafe_allow_html=True)
    sc_df = scenarios_to_dataframe(scenarios)
    st.dataframe(sc_df.style.format({
        "Target Revenue ($)": "${:,.2f}",
        "Revenue Gap ($)": "${:,.2f}",
        "Rec. Ad Spend ($)": "${:,.2f}",
        "Incremental Spend ($)": "${:,.2f}",
        "Projected ACOS (%)": "{:.2f}%",
        "Projected ROAS": "{:.2f}x",
        "Projected TACOS (%)": "{:.2f}%",
    }), use_container_width=True)

    # ---- Chart: Revenue & Spend across scenarios
    st.markdown('<div class="section-header">📈 Revenue vs Recommended Spend by Scenario</div>', unsafe_allow_html=True)

    fig = go.Figure()
    labels = [f"+{s['growth_pct']}%" for s in scenarios]
    fig.add_trace(go.Bar(x=labels, y=[s["target_revenue"] for s in scenarios], name="Target Revenue", marker_color="#293C5B"))
    fig.add_trace(go.Bar(x=labels, y=[s["recommended_spend"] for s in scenarios], name="Rec. Ad Spend", marker_color="#e71d36"))
    fig.add_hline(y=baseline_revenue, line_dash="dot", line_color="gray", annotation_text=f"Current Revenue: {fmt_currency(baseline_revenue)}")
    fig.add_hline(y=total_ad_spend, line_dash="dot", line_color="#f59e0b", annotation_text=f"Current Spend: {fmt_currency(total_ad_spend)}")
    fig.update_layout(
        barmode="group", height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=40),
        yaxis_title="Amount ($)",
        xaxis_title="Growth Scenario",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ---- Chart: ACOS & ROAS Trend
    col1, col2 = st.columns(2)
    with col1:
        fig_acos = go.Figure()
        fig_acos.add_trace(go.Scatter(
            x=labels, y=[s["projected_acos_pct"] for s in scenarios],
            mode="lines+markers", name="Projected ACOS (%)",
            line=dict(color="#e71d36", width=2), marker=dict(size=8),
        ))
        if ads_metrics.get("overall_acos"):
            fig_acos.add_hline(y=ads_metrics["overall_acos"], line_dash="dash", line_color="gray",
                                annotation_text="Current ACOS")
        fig_acos.update_layout(title="Projected ACOS by Growth Target", height=320, margin=dict(t=50, b=30))
        st.plotly_chart(fig_acos, use_container_width=True)

    with col2:
        fig_roas = go.Figure()
        fig_roas.add_trace(go.Scatter(
            x=labels, y=[s["projected_roas"] or 0 for s in scenarios],
            mode="lines+markers", name="Projected ROAS",
            line=dict(color="#293C5B", width=2), marker=dict(size=8),
        ))
        if ads_metrics.get("overall_roas"):
            fig_roas.add_hline(y=ads_metrics["overall_roas"], line_dash="dash", line_color="gray",
                                annotation_text="Current ROAS")
        fig_roas.update_layout(title="Projected ROAS by Growth Target", height=320, margin=dict(t=50, b=30))
        st.plotly_chart(fig_roas, use_container_width=True)

    # ---- Channel Allocation for primary scenario (+10%)
    primary = next((s for s in scenarios if s["growth_pct"] == 10), scenarios[0])
    st.markdown(f'<div class="section-header">💰 Channel Budget Allocation — +{primary["growth_pct"]}% Scenario</div>', unsafe_allow_html=True)

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
        fig_bar.add_trace(go.Bar(x=alloc_labels, y=alloc_budgets, name="Total Budget", marker_color="#293C5B"))
        fig_bar.add_trace(go.Bar(x=alloc_labels, y=alloc_incr, name="Incremental Increase", marker_color="#e71d36"))
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
# Main App
# ---------------------------------------------------------------------------

def main():
    # ---- Acosta Header Banner ------------------------------------------------
    st.markdown("""
    <div class="acosta-header">
        <div style="display:flex; align-items:center; gap:20px;">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 70" width="140" height="45">
              <rect width="220" height="70" rx="4" fill="#1a0a14"/>
              <rect x="155" y="8"  width="9" height="9" fill="#cc2200"/>
              <rect x="164" y="8"  width="9" height="9" fill="#8b1a1a"/>
              <rect x="155" y="17" width="9" height="9" fill="#8b1a1a"/>
              <rect x="164" y="17" width="9" height="9" fill="#cc2200"/>
              <text x="14" y="50" font-family="Arial Black,Arial,sans-serif"
                    font-weight="900" font-size="34" fill="#ffffff" letter-spacing="-0.5">acosta</text>
            </svg>
            <div>
                <div style="font-size:16px; font-weight:700; color:#ffffff; letter-spacing:0.3px;">
                    Amazon Media Plan Forecast Tool
                </div>
                <div class="acosta-header-sub">
                    Omnichannel Retail Growth Catalyst &#183; Brand Ecommerce Intelligence
                </div>
            </div>
        </div>
        <div class="acosta-header-right">
            <div class="acosta-badge">Brand Ecommerce</div>
            <div class="acosta-created-by">Sumeet Mangotra, Brand Ecommerce Manager</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    ads_file, vendor_file, growth_options, channel_split = sidebar()

    if not ads_file and not vendor_file:
        st.info("👈 Upload your reports using the sidebar to get started.")
        st.markdown("""
        ### What this tool does:
        1. **Parses** your Amazon Advertising + Vendor Central reports (CSV or XLSX)
        2. **Extracts** key metrics: ACOS, ROAS, CTR, CPC, ordered revenue, ASIN performance
        3. **Models growth scenarios** — e.g. +10% total sales — and recommends optimal ad spend
        4. **Allocates budget** across Sponsored Products, Brands & Display
        5. **Recommends** which campaigns to increase budgets on, based on efficiency (ROAS)
        6. **Exports** a full Excel media plan workbook

        ### Reports you need:
        | Report | Source | Export format |
        |--------|--------|--------------|
        | Amazon Advertising Report | Amazon Ads Console → Reports → Sponsored Products/Brands/Display | CSV or XLSX |
        | ASIN Sales Report | Vendor Central → Analytics → Sales Diagnostics | CSV or XLSX |

        > **Tip:** You can use just one report — the tool adapts if only one is uploaded.
        """)
        # Footer on landing page
        st.markdown("""
        <div class="acosta-footer">
            <strong>Acosta</strong> · Amazon Media Plan Forecast Tool ·
            Created by <strong>Sumeet Mangotra</strong>, Brand Ecommerce Manager ·
            <a href="https://www.acosta.com" target="_blank">acosta.com</a>
        </div>
        """, unsafe_allow_html=True)
        return

    # ---- Parse files -------------------------------------------------------
    ads_df = None
    vendor_df = None
    ads_metrics = {}
    vendor_metrics = {}

    with st.spinner("📂 Reading and parsing reports — large files may take 30–60 seconds..."):
        if ads_file:
            try:
                ads_df = parse_amazon_ads_report(ads_file)
                missing = validate_ads_report(ads_df)
                if missing:
                    st.warning(f"Amazon Ads report is missing columns: {missing}. Metrics may be partial.")
                else:
                    st.success(f"✅ Amazon Ads report loaded — {len(ads_df):,} rows, {len(ads_df.columns)} columns")
                if len(ads_df) > 500_000:
                    st.info(f"ℹ️ Large report ({len(ads_df):,} rows) — processing may take a moment.")
                ads_metrics = extract_ads_metrics(ads_df)
            except Exception as e:
                st.error(f"Error reading Amazon Ads report: {e}")
                ads_df = None

        if vendor_file:
            try:
                vendor_df = parse_vendor_central_report(vendor_file)
                missing_v = validate_vendor_report(vendor_df)
                if missing_v:
                    st.warning(f"Vendor Central report is missing columns: {missing_v}. Metrics may be partial.")
                else:
                    st.success(f"✅ Vendor Central report loaded — {len(vendor_df):,} rows, {len(vendor_df.columns)} columns")
                vendor_metrics = extract_vendor_metrics(vendor_df)
            except Exception as e:
                st.error(f"Error reading Vendor Central report: {e}")
                vendor_df = None

    if ads_df is None and vendor_df is None:
        st.error("Could not load any reports. Please check file formats and try again.")
        return

    # ---- Pre-compute breakdowns -------------------------------------------
    campaign_df = campaign_breakdown(ads_df) if ads_df is not None else pd.DataFrame()
    asin_ads_df = asin_ads_breakdown(ads_df) if ads_df is not None else pd.DataFrame()
    asin_vendor_df = asin_vendor_breakdown(vendor_df) if vendor_df is not None else pd.DataFrame()
    merged_asin_df = merge_asin_view(asin_ads_df, asin_vendor_df)

    # ---- Tabs ---------------------------------------------------------------
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Key Metrics",
        "🔍 Campaign & ASIN Analysis",
        "📈 Forecast & Media Plan",
        "💡 Recommendations",
    ])

    with tab1:
        render_metrics_dashboard(ads_metrics, vendor_metrics)

    with tab2:
        render_campaign_analysis(ads_df if ads_df is not None else pd.DataFrame(),
                                  vendor_df)

    scenarios = []
    with tab3:
        if ads_df is not None or vendor_df is not None:
            scenarios = render_forecast(
                ads_metrics, vendor_metrics, campaign_df, growth_options, channel_split
            )

    with tab4:
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

    # ---- Acosta Footer --------------------------------------------------------
    st.markdown("""
    <div class="acosta-footer">
        <strong>Acosta</strong> &nbsp;·&nbsp; Amazon Media Plan Forecast Tool &nbsp;·&nbsp;
        Created by <strong>Sumeet Mangotra</strong>, Brand Ecommerce Manager &nbsp;·&nbsp;
        <a href="https://www.acosta.com" target="_blank">acosta.com</a>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
