"""
pages/tab_product.py — Product Intelligence tab
Renders ad type KPI strip, ASIN efficiency quadrant, top/worst ASINs,
category rollup, bid strategy heatmap, and match type efficiency.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from utils.formatters import fmt_currency


def render_product_tab(prod_intel: dict, ad_prod_df: pd.DataFrame, bid_df: pd.DataFrame, match_df: pd.DataFrame = None) -> None:
    """Render the Product Intelligence tab."""
    if not prod_intel and ad_prod_df.empty and (match_df is None or match_df.empty):
        st.info("No product-level data found. This tab requires 'Advertised product ID' or campaign-type columns in your report.")
        return

    # ── 1. Ad Product (SP / SB / SD) KPI strip ───────────────────────────
    if not ad_prod_df.empty:
        st.markdown('<div class="section-header">📢 Ad Type Performance — SP · SB · SD</div>', unsafe_allow_html=True)
        kpi_cols = st.columns(len(ad_prod_df))
        colors_map = {
            "Sponsored Products": "#4f46e5",
            "Sponsored Brands":   "#f97316",
            "Sponsored Display":  "#10b981",
        }
        for col, (_, row) in zip(kpi_cols, ad_prod_df.iterrows()):
            prod_name = str(row.get("ad_product", "Unknown"))
            color  = colors_map.get(prod_name, "#6b7280")
            roas_v = f"{row['roas']:.2f}x"      if "roas"          in row and pd.notna(row["roas"])          else "—"
            acos_v = f"{row['acos_%']:.1f}%"    if "acos_%"        in row and pd.notna(row["acos_%"])        else "—"
            shr_v  = f"{row['spend_share_%']:.0f}%" if "spend_share_%" in row and pd.notna(row.get("spend_share_%")) else "—"
            with col:
                st.markdown(f"""
                <div style="background:#ffffff;border-top:4px solid {color};border-radius:10px;
                            padding:14px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                    <div style="font-size:12px;font-weight:800;color:{color};">{prod_name}</div>
                    <div style="font-size:22px;font-weight:900;color:#1e1b4b;margin:4px 0;">{fmt_currency(row.get('spend', 0))}</div>
                    <div style="font-size:12px;color:#6b7280;">Spend · {shr_v} of total</div>
                    <div style="display:flex;justify-content:space-around;margin-top:8px;">
                        <span style="font-size:13px;"><b style="color:{color};">{roas_v}</b><br><span style="color:#9ca3af;font-size:11px;">ROAS</span></span>
                        <span style="font-size:13px;"><b style="color:#f97316;">{acos_v}</b><br><span style="color:#9ca3af;font-size:11px;">ACOS</span></span>
                        <span style="font-size:13px;"><b style="color:#1e1b4b;">{fmt_currency(row.get('ad_sales', 0))}</b><br><span style="color:#9ca3af;font-size:11px;">Sales</span></span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

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
                                      margin=dict(t=40, b=10, l=10, r=10), showlegend=False)
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

    # ── 3. Category rollup ────────────────────────────────────────────────
    cat_df = prod_intel.get("by_category", pd.DataFrame())
    if not cat_df.empty and "category" in cat_df.columns:
        st.markdown('<div class="section-header">🗂️ Category Performance — Spend · Sales · ACOS</div>', unsafe_allow_html=True)
        cc1, cc2 = st.columns(2)
        with cc1:
            show = [c for c in ["category", "spend", "ad_sales", "acos_%", "roas", "ad_orders"] if c in cat_df.columns]
            d = cat_df[show].copy()
            d.columns = [c.replace("_", " ").title() for c in d.columns]
            st.dataframe(d, use_container_width=True, height=260)
        with cc2:
            if all(c in cat_df.columns for c in ["category", "spend", "ad_sales"]):
                fig_cat = go.Figure()
                fig_cat.add_trace(go.Bar(x=cat_df["category"], y=cat_df["ad_sales"],
                                         name="Ad Sales", marker_color="#f97316"))
                fig_cat.add_trace(go.Bar(x=cat_df["category"], y=cat_df["spend"],
                                         name="Spend", marker_color="#4f46e5"))
                if "acos_%" in cat_df.columns:
                    fig_cat.add_trace(go.Scatter(
                        x=cat_df["category"], y=cat_df["acos_%"],
                        mode="markers+text", name="ACOS %",
                        marker=dict(size=14, color="#dc2626", symbol="diamond"),
                        text=[f"{v:.0f}%" for v in cat_df["acos_%"]],
                        textposition="top center", yaxis="y2",
                    ))
                fig_cat.update_layout(
                    barmode="group", height=300, margin=dict(t=40, b=80),
                    xaxis_tickangle=-30,
                    yaxis=dict(title="Amount ($)"),
                    yaxis2=dict(title="ACOS (%)", overlaying="y", side="right", showgrid=False),
                    legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
                )
                st.plotly_chart(fig_cat, use_container_width=True)

    # ── 5. Match type efficiency ──────────────────────────────────────────
    if match_df is not None and not match_df.empty:
        st.markdown('<div class="section-header">🎯 Match Type Efficiency</div>', unsafe_allow_html=True)
        mt1, mt2 = st.columns(2)
        with mt1:
            show = [c for c in ["match_type", "spend", "ad_sales", "acos_%", "roas", "cvr_%", "cpc"] if c in match_df.columns]
            d = match_df[show].copy()
            d.columns = [c.replace("_", " ").title() for c in d.columns]
            st.dataframe(d, use_container_width=True)
        with mt2:
            if all(c in match_df.columns for c in ["match_type", "acos_%", "roas"]):
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
