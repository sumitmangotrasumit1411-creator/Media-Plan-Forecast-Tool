"""
pages/tab_metrics.py — Key Metrics Dashboard tab
Renders ads + vendor KPI cards and ACOS/ROAS gauges.
"""

import streamlit as st
import plotly.graph_objects as go

from utils.formatters import fmt_currency, fmt_pct, fmt_num


def _metric_card(label, value, delta=None):
    delta_html = f'<div class="metric-delta">{delta}</div>' if delta else ""
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """


def render_metrics_dashboard(ads_metrics: dict, vendor_metrics: dict) -> None:
    """Render the Key Metrics dashboard tab."""
    st.markdown('<div class="section-header">📊 Amazon Advertising Metrics</div>', unsafe_allow_html=True)

    cols = st.columns(4)
    roas_val = ads_metrics.get("overall_roas")
    kpis_ads = [
        ("Total Ad Spend",       fmt_currency(ads_metrics.get("total_spend")),       None),
        ("Ad-Attributed Sales",  fmt_currency(ads_metrics.get("total_ad_sales")),    None),
        ("Overall ACOS",         fmt_pct(ads_metrics.get("overall_acos")),            "Lower is better"),
        ("Overall ROAS",         f"{roas_val:.2f}x" if roas_val else "N/A",           "Higher is better"),
        ("Total Impressions",    fmt_num(ads_metrics.get("total_impressions")),        None),
        ("Total Clicks",         fmt_num(ads_metrics.get("total_clicks")),             None),
        ("CTR",                  fmt_pct(ads_metrics.get("overall_ctr")),              None),
        ("CPC",                  fmt_currency(ads_metrics.get("overall_cpc")),         None),
        ("Total Ad Orders",      fmt_num(ads_metrics.get("total_ad_orders")),          None),
        ("Conversion Rate",      fmt_pct(ads_metrics.get("conversion_rate")),          "Click → Purchase"),
        ("New to Brand %",       fmt_pct(ads_metrics.get("ntb_order_pct")),            "First-time buyers"),
        ("Cost per Order",       fmt_currency(ads_metrics.get("cost_per_order")),      None),
    ]
    for i, (label, val, delta) in enumerate(kpis_ads):
        with cols[i % 4]:
            st.markdown(_metric_card(label, val, delta), unsafe_allow_html=True)

    if vendor_metrics:
        st.markdown('<div class="section-header">🏪 Vendor Central Sales Metrics</div>', unsafe_allow_html=True)
        cols2 = st.columns(4)
        kpis_vendor = [
            ("Total Ordered Revenue", fmt_currency(vendor_metrics.get("total_ordered_revenue")), None),
            ("Total Shipped Revenue", fmt_currency(vendor_metrics.get("total_shipped_revenue")), None),
            ("Total Ordered Units",   fmt_num(vendor_metrics.get("total_ordered_units")),        None),
            ("Avg Selling Price",     fmt_currency(vendor_metrics.get("avg_selling_price")),      None),
        ]
        for i, (label, val, delta) in enumerate(kpis_vendor):
            with cols2[i % 4]:
                st.markdown(_metric_card(label, val, delta), unsafe_allow_html=True)

    # Performance gauges
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
                            {"range": [0, 20],  "color": "#d1fae5"},
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
                            {"range": [0, 2],  "color": "#fee2e2"},
                            {"range": [2, 4],  "color": "#fef3c7"},
                            {"range": [4, 10], "color": "#d1fae5"},
                        ],
                        "threshold": {"line": {"color": "green", "width": 2}, "thickness": 0.75, "value": 4},
                    },
                ))
                fig2.update_layout(height=280, margin=dict(t=40, b=10, l=20, r=20))
                st.plotly_chart(fig2, use_container_width=True)
