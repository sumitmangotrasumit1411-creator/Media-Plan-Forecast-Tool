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
        color_map = {
            "🟢 Scale":   "#10b981",
            "🟡 Optimise":"#f59e0b",
            "🟡 Monitor": "#6366f1",
            "🔴 Review":  "#dc2626",
        }
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
            disp.columns = [c.replace("_", " ").title() for c in disp.columns]
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
            disp.columns = [c.replace("_", " ").title() for c in disp.columns]
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

    # ── 4. Category rollup ────────────────────────────────────────────────
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

    # ── 5. Bid strategy heatmap ───────────────────────────────────────────
    if not bid_df.empty:
        st.markdown('<div class="section-header">⚙️ Bid Strategy Performance</div>', unsafe_allow_html=True)
        bs1, bs2 = st.columns(2)
        with bs1:
            show = [c for c in ["bid_strategy", "spend", "ad_sales", "acos_%", "roas", "impressions"] if c in bid_df.columns]
            d = bid_df[show].copy()
            d.columns = [c.replace("_", " ").title() for c in d.columns]
            st.dataframe(d, use_container_width=True)
        with bs2:
            if all(c in bid_df.columns for c in ["bid_strategy", "acos_%", "roas"]):
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
