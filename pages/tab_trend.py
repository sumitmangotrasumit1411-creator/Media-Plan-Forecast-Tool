"""
pages/tab_trend.py — Trend Analysis tab
Renders MoM KPI delta cards, spend/sales line chart, ACOS/ROAS trends,
CPC/CTR trends, stacked spend by ad type, and raw data table.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from utils.formatters import fmt_currency


def render_trend_tab(trend_df: pd.DataFrame, t_summary: dict, prod_trend_df: pd.DataFrame) -> None:
    """Render the Trend Analysis tab — Phase 2."""
    if trend_df.empty:
        st.info("No date/time data found. Trend analysis requires a 'Date range' column in your report.")
        return

    st.markdown("""
    <div class="callout-banner">
        <strong>Trend Analysis</strong> shows how your ad performance has changed over time.
        Use this to identify seasonal patterns, efficiency drift, and month-over-month momentum
        before building your forecast.
    </div>
    """, unsafe_allow_html=True)

    # ── 1. MoM delta KPI cards ────────────────────────────────────────────
    if t_summary:
        st.markdown('<div class="section-header">📊 Latest Period-over-Period Changes</div>', unsafe_allow_html=True)
        mcols = st.columns(4)

        def _delta(val, invert=False):
            if val is None:
                return "N/A", "#6b7280"
            good  = val < 0 if invert else val > 0
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
        if "ad_sales" in trend_df.columns and not trend_df.empty:
            peak = trend_df.loc[trend_df["ad_sales"].idxmax()]
            fig.add_annotation(
                x=peak["_period_dt"], y=peak["ad_sales"],
                text=f"Peak {fmt_currency(peak['ad_sales'])}", showarrow=True,
                arrowhead=2, font=dict(color="#4f46e5", size=12),
                bgcolor="rgba(79,70,229,0.1)", bordercolor="#4f46e5",
            )
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
            fig_a.add_hrect(y0=0,  y1=15,  fillcolor="rgba(16,185,129,0.08)",  line_width=0)
            fig_a.add_hrect(y0=15, y1=35,  fillcolor="rgba(245,158,11,0.07)",  line_width=0)
            fig_a.add_hrect(y0=35, y1=100, fillcolor="rgba(220,38,38,0.07)",   line_width=0)
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
            fig_r.add_hline(y=2, line_dash="dot",  line_color="#dc2626",
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
        colors = {
            "Sponsored Products": "#4f46e5",
            "Sponsored Brands":   "#f97316",
            "Sponsored Display":  "#10b981",
        }
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
        show = [c for c in ["_period_dt", "spend", "ad_sales", "acos_%", "roas",
                             "impressions", "clicks", "cpc", "ctr_%"] if c in trend_df.columns]
        d = trend_df[show].copy()
        d.columns = [c.replace("_period_dt", "Month").replace("_", " ").title() for c in d.columns]
        st.dataframe(d, use_container_width=True, height=380)
