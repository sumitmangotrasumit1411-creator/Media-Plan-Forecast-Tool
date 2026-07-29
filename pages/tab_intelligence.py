"""
pages/tab_intelligence.py — Amazon Intelligence tab (Phase 4)

Three panels:
1. ASIN Health Scores — composite score per ASIN derived from ROAS, ACOS, CVR,
   NTB%, and vendor sell-through. Tier badges: Scale / Optimise / Review / Pause.
2. Budget Optimizer — given a total ad budget, find the optimal split across
   campaigns/ASINs weighted by their efficiency score. Shows current vs
   optimised allocation with incremental opportunity.
3. Scenario Deep-Dive — pick any growth scenario and see a drill-down of
   what changes at the ASIN and campaign level (which ASINs need scale,
   which need to be paused, how much incremental per winner).

No forecast calculations are altered — this tab is purely a read-only
intelligence layer on top of the already-computed breakdowns.
"""

from __future__ import annotations

import math
from typing import Optional

import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

from utils.formatters import fmt_currency, fmt_pct, fmt_num


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_TIER_THRESHOLDS = {
    "Scale":    80,   # score >= 80
    "Optimise": 55,   # score >= 55
    "Review":   35,   # score >= 35
    "Pause":    0,    # below 35
}

_TIER_COLORS = {
    "Scale":    ("#10b981", "#d1fae5"),
    "Optimise": ("#f59e0b", "#fef3c7"),
    "Review":   ("#f97316", "#ffedd5"),
    "Pause":    ("#dc2626", "#fee2e2"),
}

_TIER_ACTIONS = {
    "Scale":    "Increase bids +20–30%. Expand to new match types. Push SB Video.",
    "Optimise": "Hold budget. Harvest exact match terms. Prune broad waste weekly.",
    "Review":   "Audit listing (images, reviews, price). Reduce bids -20%.",
    "Pause":    "Pause campaigns for 14 days. Fix listing fundamentals first.",
}


# ─────────────────────────────────────────────────────────────────────────────
# ASIN Health Score calculation
# ─────────────────────────────────────────────────────────────────────────────

def _compute_asin_health(
    asin_ads_df: pd.DataFrame,
    merged_asin_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Compute a composite health score (0–100) for each ASIN.

    Scoring components (weights sum to 100):
      ROAS        30  — ≥6 → 30, ≥4 → 22, ≥2 → 12, else 0
      ACOS        25  — ≤15 → 25, ≤25 → 18, ≤35 → 10, else 0
      CVR%        20  — ≥15 → 20, ≥10 → 15, ≥5 → 8, else 0
      NTB%        15  — ≥60 → 15, ≥40 → 10, ≥20 → 5, else 0
      Impression  10  — top quartile → 10, mid → 6, low → 2, else 0

    Returns DataFrame with columns: asin, score, tier, + original cols.
    """
    if asin_ads_df is None or asin_ads_df.empty:
        return pd.DataFrame()

    df = asin_ads_df.copy()

    # Ensure derived cols exist
    if "roas" not in df.columns:
        if "ad_sales" in df.columns and "spend" in df.columns:
            df["roas"] = (df["ad_sales"] / df["spend"].replace(0, np.nan)).round(2)
        else:
            df["roas"] = np.nan
    if "acos_%" not in df.columns:
        if "spend" in df.columns and "ad_sales" in df.columns:
            df["acos_%"] = (df["spend"] / df["ad_sales"].replace(0, np.nan) * 100).round(2)
        else:
            df["acos_%"] = np.nan
    if "cvr_%" not in df.columns:
        if "clicks" in df.columns and "ad_orders" in df.columns:
            df["cvr_%"] = (df["ad_orders"] / df["clicks"].replace(0, np.nan) * 100).round(2)
        else:
            df["cvr_%"] = np.nan
    if "ntb_%" not in df.columns:
        if "ad_orders" in df.columns and "ad_orders_ntb" in df.columns:
            df["ntb_%"] = (df["ad_orders_ntb"] / df["ad_orders"].replace(0, np.nan) * 100).round(1)
        else:
            df["ntb_%"] = np.nan

    # ── ROAS score (30pts) ──────────────────────────────────────────────────
    roas = df.get("roas", pd.Series(np.nan, index=df.index))
    roas_score = pd.cut(
        roas.fillna(0),
        bins=[-np.inf, 2, 4, 6, np.inf],
        labels=[0, 12, 22, 30],
        right=False,
    ).astype(float)

    # ── ACOS score (25pts) ──────────────────────────────────────────────────
    acos = df.get("acos_%", pd.Series(np.nan, index=df.index))
    acos_score = pd.cut(
        acos.fillna(999),
        bins=[-np.inf, 15, 25, 35, np.inf],
        labels=[25, 18, 10, 0],
        right=False,
    ).astype(float)

    # ── CVR score (20pts) ───────────────────────────────────────────────────
    cvr = df.get("cvr_%", pd.Series(np.nan, index=df.index))
    cvr_score = pd.cut(
        cvr.fillna(0),
        bins=[-np.inf, 5, 10, 15, np.inf],
        labels=[0, 8, 15, 20],
        right=False,
    ).astype(float)

    # ── NTB score (15pts) ───────────────────────────────────────────────────
    ntb = df.get("ntb_%", pd.Series(np.nan, index=df.index))
    ntb_score = pd.cut(
        ntb.fillna(0),
        bins=[-np.inf, 20, 40, 60, np.inf],
        labels=[0, 5, 10, 15],
        right=False,
    ).astype(float)

    # ── Impression score (10pts) — quartile-based ───────────────────────────
    impr = df.get("impressions", pd.Series(0.0, index=df.index)).fillna(0)
    q1, q3 = impr.quantile(0.25), impr.quantile(0.75)
    impr_score = pd.Series(2.0, index=df.index)
    impr_score[impr >= q1]  = 6.0
    impr_score[impr >= q3]  = 10.0

    df["score"] = (roas_score + acos_score + cvr_score + ntb_score + impr_score).clip(0, 100).round(1)

    def _tier(s: float) -> str:
        if s >= 80: return "Scale"
        if s >= 55: return "Optimise"
        if s >= 35: return "Review"
        return "Pause"

    df["tier"] = df["score"].apply(_tier)

    # Merge vendor data if available
    if merged_asin_df is not None and not merged_asin_df.empty:
        vendor_cols = [c for c in ["ordered_revenue", "shipped_revenue", "ordered_units"] if c in merged_asin_df.columns]
        if vendor_cols and "asin" in merged_asin_df.columns:
            df = df.merge(merged_asin_df[["asin"] + vendor_cols], on="asin", how="left")

    return df.sort_values("score", ascending=False)


# ─────────────────────────────────────────────────────────────────────────────
# Budget Optimizer
# ─────────────────────────────────────────────────────────────────────────────

def _optimise_budget(
    health_df: pd.DataFrame,
    total_budget: float,
    campaign_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Distribute `total_budget` across campaigns proportionally to their
    composite efficiency score (ROAS * CVR / ACOS).

    Returns a DataFrame with campaign, current_spend, optimised_budget, delta.
    """
    if campaign_df is None or campaign_df.empty:
        return pd.DataFrame()

    df = campaign_df.copy()

    # Build efficiency weight per campaign
    roas_c = df.get("roas", pd.Series(1.0, index=df.index)).fillna(1).clip(lower=0.1)
    cvr_c  = df.get("cvr_%", pd.Series(5.0, index=df.index)).fillna(5).clip(lower=0.1)
    acos_c = df.get("acos_%", pd.Series(30.0, index=df.index)).fillna(30).clip(lower=1)

    # Efficiency = ROAS * CVR / ACOS  (higher is better; ACOS inverted)
    eff = (roas_c * cvr_c) / acos_c
    eff = eff.clip(lower=0)

    # Zero-weight campaigns with zero spend AND zero sales → no allocation
    if "spend" in df.columns and "ad_sales" in df.columns:
        zero_mask = (df["spend"].fillna(0) == 0) & (df["ad_sales"].fillna(0) == 0)
        eff[zero_mask] = 0

    total_eff = eff.sum()
    if total_eff == 0:
        # Fallback: equal split
        eff = pd.Series(1.0, index=df.index)
        total_eff = len(df)

    opt_budget = (eff / total_eff * total_budget).round(2)

    result = pd.DataFrame({
        "Campaign":            df.get("campaign", df.get("campaign_name", pd.Series("Campaign", index=df.index))),
        "Current Spend ($)":   df.get("spend", pd.Series(0.0, index=df.index)).fillna(0).round(2),
        "Ad Sales ($)":        df.get("ad_sales", pd.Series(0.0, index=df.index)).fillna(0).round(2),
        "ROAS":                roas_c.round(2),
        "ACOS (%)":            acos_c.round(2),
        "CVR (%)":             cvr_c.round(2),
        "Efficiency Score":    eff.round(3),
        "Optimised Budget ($)":opt_budget,
    })
    result["Delta ($)"] = (result["Optimised Budget ($)"] - result["Current Spend ($)"]).round(2)
    return result.sort_values("Efficiency Score", ascending=False)


# ─────────────────────────────────────────────────────────────────────────────
# Render helpers
# ─────────────────────────────────────────────────────────────────────────────

def _tier_badge(tier: str) -> str:
    color, bg = _TIER_COLORS.get(tier, ("#6b7280", "#f3f4f6"))
    return (
        f'<span style="background:{bg};color:{color};font-weight:700;font-size:11px;'
        f'padding:3px 10px;border-radius:20px;border:1px solid {color}33;">{tier}</span>'
    )


def _score_bar(score: float) -> str:
    color = "#10b981" if score >= 80 else "#f59e0b" if score >= 55 else "#f97316" if score >= 35 else "#dc2626"
    return (
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<div style="flex:1;background:#f3f4f6;border-radius:8px;height:8px;overflow:hidden;">'
        f'<div style="width:{score:.0f}%;background:{color};height:100%;border-radius:8px;"></div>'
        f'</div>'
        f'<span style="font-size:12px;font-weight:800;color:{color};min-width:34px;">{score:.0f}</span>'
        f'</div>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main render
# ─────────────────────────────────────────────────────────────────────────────

def render_intelligence_tab(
    asin_ads_df: pd.DataFrame,
    merged_asin_df: Optional[pd.DataFrame],
    campaign_df: pd.DataFrame,
    ads_metrics: dict,
    scenarios: list,
) -> None:
    """Render the Amazon Intelligence tab — Phase 4."""

    st.markdown("""
    <div class="callout-banner">
        <strong>🧠 Amazon Intelligence</strong> — three AI-assisted tools powered by your data:
        <strong>ASIN Health Scoring</strong> · <strong>Budget Optimizer</strong> · <strong>Scenario Deep-Dive</strong>.
        No manual configuration required — all outputs are derived automatically from your uploaded reports.
    </div>
    """, unsafe_allow_html=True)

    intel_tab1, intel_tab2, intel_tab3 = st.tabs([
        "🏅 ASIN Health Scores",
        "⚙️ Budget Optimizer",
        "🔬 Scenario Deep-Dive",
    ])

    # ── Compute health scores once ───────────────────────────────────────────
    health_df = _compute_asin_health(asin_ads_df, merged_asin_df)

    # ═══════════════════════════════════════════════════════════════════════
    # Panel 1: ASIN Health Scores
    # ═══════════════════════════════════════════════════════════════════════
    with intel_tab1:
        _render_asin_health(health_df, ads_metrics)

    # ═══════════════════════════════════════════════════════════════════════
    # Panel 2: Budget Optimizer
    # ═══════════════════════════════════════════════════════════════════════
    with intel_tab2:
        _render_budget_optimizer(health_df, campaign_df, ads_metrics)

    # ═══════════════════════════════════════════════════════════════════════
    # Panel 3: Scenario Deep-Dive
    # ═══════════════════════════════════════════════════════════════════════
    with intel_tab3:
        _render_scenario_deepdive(health_df, campaign_df, scenarios, ads_metrics)


# ─────────────────────────────────────────────────────────────────────────────
# Panel 1 — ASIN Health Scores
# ─────────────────────────────────────────────────────────────────────────────

def _render_asin_health(health_df: pd.DataFrame, ads_metrics: dict) -> None:
    if health_df.empty:
        st.info("Upload an Amazon Ads report with ASIN data to see health scores.")
        return

    # ── Tier summary strip ──────────────────────────────────────────────────
    st.markdown('<div class="section-header">🏅 ASIN Health Score Overview</div>', unsafe_allow_html=True)

    tier_counts = health_df["tier"].value_counts()
    tier_order  = ["Scale", "Optimise", "Review", "Pause"]

    cols = st.columns(4)
    for col, tier in zip(cols, tier_order):
        count  = tier_counts.get(tier, 0)
        color, bg = _TIER_COLORS[tier]
        pct    = round(count / len(health_df) * 100) if len(health_df) > 0 else 0
        action = _TIER_ACTIONS[tier]
        with col:
            st.markdown(f"""
            <div style="background:{bg};border-radius:12px;padding:16px 18px;
                        border:1px solid {color}33;border-top:4px solid {color};">
                <div style="font-size:11px;font-weight:700;color:{color};
                            text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">{tier}</div>
                <div style="font-size:32px;font-weight:900;color:{color};line-height:1;">{count}</div>
                <div style="font-size:12px;color:#6b7280;margin-top:4px;">{pct}% of ASINs</div>
                <div style="font-size:11px;color:#9ca3af;margin-top:8px;line-height:1.5;">{action}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Tier distribution donut ─────────────────────────────────────────────
    st.markdown('<div class="section-header">📊 Portfolio Distribution</div>', unsafe_allow_html=True)

    donut_col, table_col = st.columns([1, 2])

    tier_vals   = [tier_counts.get(t, 0) for t in tier_order]
    tier_colors = [_TIER_COLORS[t][0] for t in tier_order]

    with donut_col:
        fig_donut = go.Figure(go.Pie(
            labels=tier_order,
            values=tier_vals,
            hole=0.55,
            marker_colors=tier_colors,
            textinfo="label+percent",
            textfont_size=12,
        ))
        fig_donut.update_layout(
            title="ASIN Tier Distribution",
            height=340, margin=dict(t=50, b=10, l=10, r=10),
            showlegend=False,
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    # ── Score distribution histogram ─────────────────────────────────────────
    with table_col:
        fig_hist = go.Figure(go.Histogram(
            x=health_df["score"].fillna(0),
            nbinsx=20,
            marker_color="#4f46e5",
            opacity=0.8,
        ))
        fig_hist.add_vline(x=80, line_dash="dash", line_color="#10b981",
                           annotation_text="Scale threshold", annotation_position="top right")
        fig_hist.add_vline(x=55, line_dash="dash", line_color="#f59e0b",
                           annotation_text="Optimise", annotation_position="top right")
        fig_hist.add_vline(x=35, line_dash="dash", line_color="#f97316",
                           annotation_text="Review", annotation_position="top right")
        fig_hist.update_layout(
            title="Score Distribution Across All ASINs",
            xaxis_title="Health Score", yaxis_title="# ASINs",
            height=340, margin=dict(t=50, b=30, l=30, r=30),
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    # ── Filterable ASIN table ───────────────────────────────────────────────
    st.markdown('<div class="section-header">🔍 ASIN Health Details</div>', unsafe_allow_html=True)

    tier_filter = st.multiselect(
        "Filter by Tier",
        options=tier_order,
        default=tier_order,
        key="health_tier_filter",
    )
    filtered = health_df[health_df["tier"].isin(tier_filter)] if tier_filter else health_df

    display_cols = ["asin", "score", "tier"]
    for c in ["spend", "ad_sales", "roas", "acos_%", "cvr_%", "ntb_%", "impressions",
              "ordered_revenue", "ordered_units"]:
        if c in filtered.columns:
            display_cols.append(c)

    disp = filtered[display_cols].head(200).copy()
    rename = {
        "asin": "ASIN", "score": "Health Score", "tier": "Tier",
        "spend": "Ad Spend ($)", "ad_sales": "Ad Sales ($)",
        "roas": "ROAS", "acos_%": "ACOS (%)", "cvr_%": "CVR (%)",
        "ntb_%": "NTB (%)", "impressions": "Impressions",
        "ordered_revenue": "Ordered Revenue ($)", "ordered_units": "Ordered Units",
    }
    disp = disp.rename(columns={k: v for k, v in rename.items() if k in disp.columns})

    fmt = {}
    for c in disp.columns:
        if "$" in c:          fmt[c] = "${:,.0f}"
        elif "ACOS" in c:     fmt[c] = "{:.1f}%"
        elif "CVR" in c:      fmt[c] = "{:.1f}%"
        elif "NTB" in c:      fmt[c] = "{:.0f}%"
        elif "ROAS" in c:     fmt[c] = "{:.2f}x"
        elif "Score" in c:    fmt[c] = "{:.0f}"
        elif "Impressions" in c: fmt[c] = "{:,.0f}"

    def _style_tier_row(row):
        tier = row.get("Tier", "")
        bg_map = {"Scale": "#f0fdf4", "Optimise": "#fffbeb",
                  "Review": "#fff7ed", "Pause": "#fef2f2"}
        bg = bg_map.get(tier, "")
        return [f"background-color:{bg}"] * len(row)

    st.dataframe(
        disp.style.format(fmt, na_rep="—").apply(_style_tier_row, axis=1),
        use_container_width=True, height=420,
    )

    # ── Top 10 by score — horizontal bar chart ──────────────────────────────
    st.markdown('<div class="section-header">🏆 Top 20 ASINs by Health Score</div>', unsafe_allow_html=True)

    top20 = filtered.head(20)
    if not top20.empty and "asin" in top20.columns:
        bar_colors = [_TIER_COLORS[t][0] for t in top20["tier"]]
        fig_bar = go.Figure(go.Bar(
            x=top20["score"].tolist(),
            y=top20["asin"].tolist(),
            orientation="h",
            marker_color=bar_colors,
            text=[f"{s:.0f}" for s in top20["score"]],
            textposition="outside",
        ))
        fig_bar.update_layout(
            title="Top 20 ASINs — Health Score",
            xaxis_title="Score (0–100)", yaxis_title="",
            height=max(320, len(top20) * 26),
            margin=dict(t=50, b=30, l=120, r=50),
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig_bar, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# Panel 2 — Budget Optimizer
# ─────────────────────────────────────────────────────────────────────────────

def _render_budget_optimizer(
    health_df: pd.DataFrame,
    campaign_df: pd.DataFrame,
    ads_metrics: dict,
) -> None:
    st.markdown('<div class="section-header">⚙️ Budget Optimizer</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="callout-banner">
        The optimizer redistributes your total ad budget across campaigns proportionally to each
        campaign's <strong>Efficiency Score</strong> (ROAS × CVR / ACOS). High-efficiency campaigns
        receive more budget; low-efficiency campaigns are scaled back.
    </div>
    """, unsafe_allow_html=True)

    current_spend = ads_metrics.get("total_spend", 0) or 0

    opt_col, info_col = st.columns([1, 2])
    with opt_col:
        total_budget = st.number_input(
            "Total Budget to Optimise ($)",
            min_value=0.0,
            value=float(round(current_spend, 2)),
            step=1000.0,
            format="%.0f",
            key="optimizer_budget",
            help="Enter the total ad budget you want to allocate across campaigns",
        )
    with info_col:
        st.markdown(f"""
        <div style="background:#f0f2ff;border-radius:10px;padding:14px 18px;margin-top:22px;">
            <span style="font-size:13px;color:#4338ca;">
                📊 Current total spend: <strong>{fmt_currency(current_spend)}</strong> &nbsp;·&nbsp;
                {len(campaign_df) if campaign_df is not None else 0} campaigns detected
            </span>
        </div>
        """, unsafe_allow_html=True)

    if campaign_df is None or campaign_df.empty:
        st.info("Campaign data is required for budget optimisation. Upload an Amazon Ads report.")
        return

    opt_df = _optimise_budget(health_df, total_budget, campaign_df)

    if opt_df.empty:
        st.warning("Could not compute optimised budget. Check that your report contains campaign data.")
        return

    # ── Summary metrics ─────────────────────────────────────────────────────
    gainers  = opt_df[opt_df["Delta ($)"] > 0]
    losers   = opt_df[opt_df["Delta ($)"] < 0]
    unchanged = opt_df[opt_df["Delta ($)"] == 0]

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total Budget",    fmt_currency(total_budget))
    s2.metric("Scale Up",        f"{len(gainers)} campaigns",  f"+{fmt_currency(gainers['Delta ($)'].sum())}")
    s3.metric("Scale Down",      f"{len(losers)} campaigns",   f"-{fmt_currency(abs(losers['Delta ($)'].sum()))}")
    s4.metric("Unchanged",       f"{len(unchanged)} campaigns")

    # ── Waterfall / comparison chart ────────────────────────────────────────
    st.markdown('<div class="section-header">📊 Current vs Optimised Spend by Campaign</div>', unsafe_allow_html=True)

    top_n  = min(20, len(opt_df))
    top_df = opt_df.head(top_n)
    camp_names = [str(c)[:30] for c in top_df["Campaign"].tolist()]

    fig_comp = go.Figure()
    fig_comp.add_trace(go.Bar(
        name="Current Spend",
        x=camp_names, y=top_df["Current Spend ($)"].tolist(),
        marker_color="#9ca3af", opacity=0.8,
    ))
    fig_comp.add_trace(go.Bar(
        name="Optimised Budget",
        x=camp_names, y=top_df["Optimised Budget ($)"].tolist(),
        marker_color="#4f46e5", opacity=0.9,
    ))
    fig_comp.update_layout(
        barmode="group", height=420,
        xaxis_title="Campaign (top 20 by efficiency)",
        yaxis_title="Amount ($)", yaxis_tickprefix="$",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=50, b=80, l=40, r=20),
    )
    st.plotly_chart(fig_comp, use_container_width=True)

    # ── Delta bar chart (winners/losers) ────────────────────────────────────
    st.markdown('<div class="section-header">📈 Budget Reallocation Delta</div>', unsafe_allow_html=True)

    delta_df = opt_df.sort_values("Delta ($)", ascending=False).head(30)
    delta_colors = ["#10b981" if d > 0 else "#dc2626" for d in delta_df["Delta ($)"]]
    fig_delta = go.Figure(go.Bar(
        x=[str(c)[:28] for c in delta_df["Campaign"]],
        y=delta_df["Delta ($)"].tolist(),
        marker_color=delta_colors,
        text=[f"${d:+,.0f}" for d in delta_df["Delta ($)"]],
        textposition="outside",
    ))
    fig_delta.add_hline(y=0, line_color="#6b7280", line_width=1)
    fig_delta.update_layout(
        title="Budget Delta per Campaign (top 30) — Green = more budget, Red = less",
        xaxis_title="Campaign", yaxis_title="Delta ($)", yaxis_tickprefix="$",
        height=420, margin=dict(t=60, b=80, l=40, r=20),
    )
    st.plotly_chart(fig_delta, use_container_width=True)

    # ── Full optimised allocation table ─────────────────────────────────────
    st.markdown('<div class="section-header">📋 Full Optimised Allocation Table</div>', unsafe_allow_html=True)

    fmt_opt = {
        "Current Spend ($)":    "${:,.0f}",
        "Ad Sales ($)":         "${:,.0f}",
        "ROAS":                 "{:.2f}x",
        "ACOS (%)":             "{:.1f}%",
        "CVR (%)":              "{:.1f}%",
        "Efficiency Score":     "{:.3f}",
        "Optimised Budget ($)": "${:,.0f}",
        "Delta ($)":            "${:+,.0f}",
    }

    def _style_delta(row):
        d = row.get("Delta ($)", 0) or 0
        if d > 500:   return ["background-color:#f0fdf4"] * len(row)
        if d < -500:  return ["background-color:#fef2f2"] * len(row)
        return [""] * len(row)

    st.dataframe(
        opt_df.style.format(fmt_opt, na_rep="—").apply(_style_delta, axis=1),
        use_container_width=True, height=440,
    )

    # ── Pie: optimised allocation ───────────────────────────────────────────
    st.markdown('<div class="section-header">🥧 Optimised Budget Allocation</div>', unsafe_allow_html=True)
    top_pie   = opt_df[opt_df["Optimised Budget ($)"] > 0].head(12)
    other_val = opt_df[opt_df["Optimised Budget ($)"] > 0]["Optimised Budget ($)"].sum() - top_pie["Optimised Budget ($)"].sum()
    pie_labels = [str(c)[:25] for c in top_pie["Campaign"].tolist()]
    pie_vals   = top_pie["Optimised Budget ($)"].tolist()
    if other_val > 0:
        pie_labels.append("Other campaigns")
        pie_vals.append(round(other_val, 2))

    fig_pie = go.Figure(go.Pie(
        labels=pie_labels, values=pie_vals, hole=0.45,
        textinfo="label+percent", textfont_size=11,
    ))
    fig_pie.update_layout(
        title="Optimised Budget Share by Campaign (top 12)",
        height=420, margin=dict(t=60, b=10, l=10, r=10),
    )
    st.plotly_chart(fig_pie, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# Panel 3 — Scenario Deep-Dive
# ─────────────────────────────────────────────────────────────────────────────

def _render_scenario_deepdive(
    health_df: pd.DataFrame,
    campaign_df: pd.DataFrame,
    scenarios: list,
    ads_metrics: dict,
) -> None:
    st.markdown('<div class="section-header">🔬 Scenario Deep-Dive</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="callout-banner">
        Select a growth scenario to see a <strong>campaign-level and ASIN-level drill-down</strong>:
        which campaigns should scale, which should be paused, and where the incremental
        opportunity sits.
    </div>
    """, unsafe_allow_html=True)

    if not scenarios:
        st.info("Run the Forecast & Media Plan tab first to generate scenarios. Then return here.")
        return

    # ── Scenario selector ───────────────────────────────────────────────────
    scenario_labels = [f"+{s['growth_pct']:.0f}% — Target: {fmt_currency(s['target_revenue'])}"
                       for s in scenarios]
    selected_idx = st.selectbox(
        "Select Growth Scenario",
        options=range(len(scenarios)),
        format_func=lambda i: scenario_labels[i],
        key="deepdive_scenario_select",
    )
    sel = scenarios[selected_idx]

    growth_pct     = sel["growth_pct"]
    target_rev     = sel["target_revenue"]
    rec_spend      = sel["recommended_spend"]
    incr_spend     = sel["incremental_spend"]
    proj_roas      = sel.get("projected_roas") or 0
    proj_acos      = sel.get("projected_acos_pct") or 0
    channel_alloc  = sel.get("channel_allocation", {})

    # ── Scenario summary strip ──────────────────────────────────────────────
    hero_items = [
        ("Growth Target",       f"+{growth_pct:.0f}%",           "vs current revenue"),
        ("Target Revenue",      fmt_currency(target_rev),         "total ordered revenue"),
        ("Rec. Ad Spend",       fmt_currency(rec_spend),          "total budget"),
        ("Incremental Spend",   f"+{fmt_currency(incr_spend)}",   "above current"),
        ("Projected ROAS",      f"{proj_roas:.2f}x",              "blended return"),
        ("Projected ACOS",      f"{proj_acos:.1f}%",              "ad cost ratio"),
    ]
    hero_html = (
        '<div class="kpi-hero">'
        '<div style="font-size:11px;color:rgba(255,255,255,0.4);font-weight:700;'
        'text-transform:uppercase;letter-spacing:1px;margin-bottom:14px;">'
        f'Scenario: +{growth_pct:.0f}% Growth Deep-Dive</div>'
        '<div class="kpi-hero-row">'
    )
    for label, val, sub in hero_items:
        hero_html += (
            f'<div class="kpi-hero-item">'
            f'<div class="kpi-hero-label">{label}</div>'
            f'<div class="kpi-hero-value">{val}</div>'
            f'<div class="kpi-hero-sub">{sub}</div>'
            f'</div>'
        )
    hero_html += "</div></div>"
    st.markdown(hero_html, unsafe_allow_html=True)

    # ── ASIN action list for this scenario ──────────────────────────────────
    if not health_df.empty:
        st.markdown('<div class="section-header">📦 ASIN Action Plan for This Scenario</div>', unsafe_allow_html=True)

        # Calculate per-ASIN incremental budget proportional to health score
        total_score = health_df["score"].sum()
        if total_score > 0:
            health_df = health_df.copy()
            health_df["incremental_budget"] = (
                health_df["score"] / total_score * incr_spend
            ).round(2)
        else:
            health_df["incremental_budget"] = 0.0

        # Scale ASINs only
        scale_asins = health_df[health_df["tier"] == "Scale"].head(10)
        pause_asins = health_df[health_df["tier"] == "Pause"].head(10)

        col_s, col_p = st.columns(2)
        with col_s:
            st.markdown("""
            <div style="font-weight:700;color:#10b981;font-size:14px;
                        margin-bottom:10px;">🚀 ASINs to Scale</div>
            """, unsafe_allow_html=True)
            if scale_asins.empty:
                st.info("No ASINs meet the Scale threshold (score ≥ 80) yet.")
            else:
                for _, row in scale_asins.iterrows():
                    incr_b = row.get("incremental_budget", 0)
                    roas_v = row.get("roas", 0) or 0
                    acos_v = row.get("acos_%", 0) or 0
                    score_v = row.get("score", 0)
                    st.markdown(f"""
                    <div class="success-card" style="margin-bottom:8px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <strong style="font-size:13px;">{row.get('asin','—')}</strong>
                            {_tier_badge(row.get('tier','—'))}
                        </div>
                        {_score_bar(score_v)}
                        <div style="font-size:12px;color:#374151;margin-top:6px;">
                            ROAS {roas_v:.2f}x &nbsp;·&nbsp; ACOS {acos_v:.1f}% &nbsp;·&nbsp;
                            <strong style="color:#10b981;">+{fmt_currency(incr_b)} incremental</strong>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        with col_p:
            st.markdown("""
            <div style="font-weight:700;color:#dc2626;font-size:14px;
                        margin-bottom:10px;">⏸️ ASINs to Pause / Review</div>
            """, unsafe_allow_html=True)
            if pause_asins.empty:
                st.markdown(
                    '<div class="reco-card">No ASINs require pausing. Portfolio is healthy.</div>',
                    unsafe_allow_html=True,
                )
            else:
                for _, row in pause_asins.iterrows():
                    wasted = row.get("spend", 0) or 0
                    roas_v = row.get("roas", 0) or 0
                    acos_v = row.get("acos_%", 0) or 0
                    score_v = row.get("score", 0)
                    st.markdown(f"""
                    <div class="warning-card" style="margin-bottom:8px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <strong style="font-size:13px;">{row.get('asin','—')}</strong>
                            {_tier_badge(row.get('tier','—'))}
                        </div>
                        {_score_bar(score_v)}
                        <div style="font-size:12px;color:#374151;margin-top:6px;">
                            ROAS {roas_v:.2f}x &nbsp;·&nbsp; ACOS {acos_v:.1f}% &nbsp;·&nbsp;
                            <strong style="color:#dc2626;">{fmt_currency(wasted)} spend at risk</strong>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    # ── Channel spend plan for scenario ─────────────────────────────────────
    if channel_alloc:
        st.markdown('<div class="section-header">💰 Channel Spend Plan</div>', unsafe_allow_html=True)
        ch_palette = {
            "Sponsored Products": "#4f46e5",
            "Sponsored Brands":   "#f97316",
            "Sponsored Display":  "#10b981",
        }
        ch_cols = st.columns(len(channel_alloc))
        for col, (ch_name, alloc) in zip(ch_cols, channel_alloc.items()):
            color  = ch_palette.get(ch_name, "#6b7280")
            budget = alloc.get("budget", 0)
            incr   = alloc.get("incremental_budget", 0)
            share  = alloc.get("share_pct", 0)
            with col:
                st.markdown(f"""
                <div style="background:#ffffff;border-top:4px solid {color};
                            border-radius:12px;padding:16px;text-align:center;
                            box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                    <div style="font-size:12px;font-weight:800;color:{color};
                                margin-bottom:6px;">{ch_name}</div>
                    <div style="font-size:24px;font-weight:900;color:#1e1b4b;">
                        {fmt_currency(budget)}</div>
                    <div style="font-size:12px;color:#6b7280;margin-top:2px;">
                        {share:.1f}% of total</div>
                    <div style="font-size:12px;font-weight:700;color:{color};margin-top:6px;">
                        +{fmt_currency(incr)} incremental</div>
                </div>
                """, unsafe_allow_html=True)

    # ── Campaign-level budget recommendations ────────────────────────────────
    if sel.get("campaign_recommendations"):
        st.markdown('<div class="section-header">🎯 Campaign Budget Recommendations</div>', unsafe_allow_html=True)
        cr_df = pd.DataFrame(sel["campaign_recommendations"])
        if not cr_df.empty:
            cr_df.columns = [c.replace("_", " ").title() for c in cr_df.columns]
            fmt_cr = {}
            for c in cr_df.columns:
                if "$" in c or "Spend" in c or "Budget" in c:
                    fmt_cr[c] = "${:,.0f}"
                elif "Roas" in c:
                    fmt_cr[c] = "{:.2f}x"
                elif "Acos" in c or "Pct" in c:
                    fmt_cr[c] = "{:.1f}%"
            st.dataframe(
                cr_df.style.format(fmt_cr, na_rep="—"),
                use_container_width=True, height=360,
            )
