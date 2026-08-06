"""
pages/tab_forecast.py — Forecast & Media Plan tab
Contains the full render_forecast() function extracted from app.py.
All forecast calculations are identical — zero business logic changed.

Baseline / Projected separation (business logic fix):
------------------------------------------------------
The uploaded reports are ALWAYS the single source of truth for every
"Current / Actual / Baseline" value displayed in this tab.

Rule: baseline_metrics are read-only. They are extracted once from
ads_metrics / vendor_metrics and never overwritten by forecast output.

The only values that change with scenario selection are the PROJECTED
columns. Every tile, table, and chart shows:

    LEFT  = Current Performance (Uploaded Data)   ← immutable baseline
    RIGHT = Projected Performance (Forecast)       ← scenario output

When no custom target is active, the first selected growth scenario
(e.g. +10%) is used as the default projection so users always see a
meaningful Current vs Projected comparison — never identical numbers.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from forecast import run_multi_scenario, scenarios_to_dataframe, run_forecast, monthly_forecast
from utils.formatters import fmt_currency, fmt_pct, fmt_num


def render_forecast(
    ads_metrics: dict,
    vendor_metrics: dict,
    campaign_df: pd.DataFrame,
    growth_options: list,
    channel_split: dict,
    trend_df: pd.DataFrame = None,
    custom_targets: dict = None,
) -> list:
    """Render the Forecast & Media Plan tab. Returns the list of scenario dicts."""
    total_ordered_revenue = vendor_metrics.get("total_ordered_revenue", 0) if vendor_metrics else 0
    total_ad_spend  = ads_metrics.get("total_spend", 0)
    total_ad_sales  = ads_metrics.get("total_ad_sales", 0)

    baseline_revenue = total_ordered_revenue if total_ordered_revenue > 0 else total_ad_sales

    if baseline_revenue == 0:
        st.warning("No revenue data found. Please check your reports.")
        return []

    ct = custom_targets or {}

    # ---- Run growth-% scenarios -----------------------------------------------
    scenarios = run_multi_scenario(
        total_ordered_revenue=baseline_revenue,
        total_ad_spend=total_ad_spend,
        total_ad_sales=total_ad_sales,
        growth_scenarios=growth_options,
        custom_channel_split=channel_split,
        campaign_df=campaign_df if campaign_df is not None and not campaign_df.empty else None,
    )

    # ---- Custom scenario -------------------------------------------------------
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
        active = [k for k, v in ct.items() if v is not None]
        label_map = {
            "target_revenue": "Target Revenue",
            "ad_spend":       "Ad Spend",
            "ad_sales":       "Ad Sales",
            "roas":           "ROAS",
            "tacos":          "TACOS %",
        }
        active_labels = " · ".join(label_map[k] for k in active)
        st.info(f"🎯 **Custom scenario active** — pinned inputs: **{active_labels}**. All other metrics derived automatically.")

    # =========================================================================
    # BASELINE METRICS — immutable, always from uploaded reports
    # These are NEVER overwritten by any forecast output.
    # =========================================================================
    baseline_spend  = total_ad_spend                                   # from ads report
    baseline_sales  = total_ad_sales                                   # from ads report
    baseline_acos   = ads_metrics.get("overall_acos")                  # from ads report
    baseline_roas   = ads_metrics.get("overall_roas")                  # from ads report
    baseline_tacos  = round(total_ad_spend / baseline_revenue * 100, 2) if baseline_revenue > 0 else None
    baseline_clicks = ads_metrics.get("total_clicks", 0)  or 0
    baseline_impr   = ads_metrics.get("total_impressions", 0) or 0
    baseline_orders = ads_metrics.get("total_ad_orders", 0) or 0
    baseline_cpc    = ads_metrics.get("overall_cpc") or 0
    baseline_ctr    = ads_metrics.get("overall_ctr") or 0
    baseline_cvr    = ads_metrics.get("conversion_rate") or 0
    baseline_cpo    = ads_metrics.get("cost_per_order") or 0

    # =========================================================================
    # PROJECTED METRICS — always from forecast output, never from baseline
    #
    # Source priority:
    #   1. Custom scenario (when sidebar targets are set)
    #   2. First growth scenario (e.g. +10%) — ensures Current ≠ Projected
    #
    # The baseline is NEVER used as the projected value. When no scenario is
    # selected, the first available growth scenario provides projected values.
    # =========================================================================
    if custom_scenario:
        proj_scenario = custom_scenario
    elif scenarios:
        # Use the first growth scenario (+10% or lowest selected) as the
        # default projection — so tiles always show a meaningful delta
        proj_scenario = scenarios[0]
    else:
        proj_scenario = None

    if proj_scenario:
        proj_spend  = proj_scenario["recommended_spend"]
        proj_sales  = proj_scenario["target_ad_sales"]
        proj_rev    = proj_scenario["target_revenue"]
        proj_acos   = proj_scenario["projected_acos_pct"]
        proj_roas   = proj_scenario["projected_roas"]   or 0
        proj_tacos  = proj_scenario["projected_tacos_pct"] or 0
        proj_alloc  = proj_scenario["channel_allocation"]
    else:
        # Fallback: no scenario available — show baseline on both sides
        # (should never occur since scenarios always contain at least one entry)
        proj_spend  = baseline_spend
        proj_sales  = baseline_sales
        proj_rev    = baseline_revenue
        proj_acos   = baseline_acos or 0
        proj_roas   = baseline_roas or 0
        proj_tacos  = baseline_tacos or 0
        proj_alloc  = {
            ch: {"budget": round(baseline_spend * w, 2), "share_pct": round(w * 100, 1)}
            for ch, w in channel_split.items()
        }

    # Projected secondary metrics scaled by spend ratio vs BASELINE spend
    _spend_ratio  = (proj_spend / baseline_spend) if baseline_spend > 0 else 1.0
    proj_clicks   = round(baseline_clicks  * _spend_ratio)
    proj_impr     = round(baseline_impr    * _spend_ratio)
    proj_orders   = round(baseline_orders  * _spend_ratio)
    proj_cpc      = baseline_cpc   # CPC is bid/auction driven, not spend driven
    proj_ctr      = baseline_ctr   # CTR is creative driven, not spend driven
    proj_cvr      = baseline_cvr   # CVR is listing driven, not spend driven
    proj_cpo      = round(proj_spend / proj_orders, 2) if proj_orders > 0 else baseline_cpo

    # Label for the active projection (used in section headers and table)
    if custom_scenario:
        proj_label = f"🎯 Custom (+{custom_scenario['growth_pct']:.1f}%)"
    elif proj_scenario:
        proj_label = f"📈 +{proj_scenario['growth_pct']:.0f}% Scenario"
    else:
        proj_label = "Projected"

    # ── Delta badge helper ──────────────────────────────────────────────────────
    def _delta_badge(new_val, old_val, higher_is_better=True, is_pct_metric=False):
        NEUTRAL = '<span style="background:#f3f4f6;color:#6b7280;border-radius:20px;padding:3px 9px;font-size:12px;font-weight:700;">— Unchanged</span>'
        if old_val is None:
            return NEUTRAL
        new_val = new_val or 0
        old_val = old_val or 0
        delta = new_val - old_val
        if old_val != 0:
            pct = delta / abs(old_val) * 100
        else:
            pct = 0.0
        if abs(pct) < 0.01 and not is_pct_metric:
            return NEUTRAL
        if is_pct_metric and abs(delta) < 0.001:
            return NEUTRAL
        good  = (delta > 0) == higher_is_better
        bg    = "#dcfce7" if good else "#fee2e2"
        color = "#15803d" if good else "#b91c1c"
        arrow = "▲" if delta > 0 else "▼"
        sign  = "+" if delta > 0 else ""
        if is_pct_metric:
            change_str = f"{sign}{delta:.2f}pp"
        else:
            change_str = f"{sign}{pct:.1f}%"
        return (
            f'<span style="background:{bg};color:{color};border-radius:20px;'
            f'padding:3px 9px;font-size:12px;font-weight:800;white-space:nowrap;">'
            f'{arrow} {change_str}</span>'
        )

    # ── Metric tile helper ──────────────────────────────────────────────────────
    def _metric_tile(label, curr, proj, fmt_fn, higher_is_better=True, is_pct_metric=False):
        badge   = _delta_badge(proj, curr, higher_is_better, is_pct_metric)
        changed = abs(proj - (curr or 0)) > 0.001 if curr else False
        border      = "#4f46e5" if changed else "#e5e7eb"
        border_top  = "4px solid #4f46e5" if changed else "4px solid #e5e7eb"
        return f"""
        <div style="background:#ffffff;border:1px solid {border};border-top:{border_top};
                    border-radius:10px;padding:14px 16px;box-shadow:0 2px 8px rgba(0,0,0,0.05);
                    height:100%;">
            <div style="font-size:12px;font-weight:700;color:#6b7280;letter-spacing:.4px;
                        margin-bottom:10px;">{label}</div>
            <div style="display:flex;justify-content:space-between;align-items:flex-end;
                        margin-bottom:8px;">
                <div>
                    <div style="font-size:10px;color:#9ca3af;font-weight:600;
                                text-transform:uppercase;letter-spacing:.5px;">Current</div>
                    <div style="font-size:15px;font-weight:700;color:#6b7280;">{fmt_fn(curr)}</div>
                </div>
                <div style="font-size:16px;color:#9ca3af;margin-bottom:2px;">→</div>
                <div style="text-align:right;">
                    <div style="font-size:10px;color:#4f46e5;font-weight:700;
                                text-transform:uppercase;letter-spacing:.5px;">Projected</div>
                    <div style="font-size:20px;font-weight:900;color:#1e1b4b;">{fmt_fn(proj)}</div>
                </div>
            </div>
            <div style="border-top:1px solid #f3f4f6;padding-top:7px;text-align:center;">
                {badge}
            </div>
        </div>"""

    # ── Hero banner — Current Performance (Uploaded Data) ──────────────────────
    hero_items = [
        ("Current Revenue",  fmt_currency(baseline_revenue),  "Uploaded data"),
        ("Current Ad Spend", fmt_currency(baseline_spend),    "Uploaded data"),
        ("Current ACOS",     fmt_pct(baseline_acos),          "Target ≤25%"),
        ("Current ROAS",     f"{baseline_roas:.2f}x" if baseline_roas else "N/A", "Target ≥4x"),
        ("Current TACOS",    fmt_pct(baseline_tacos),         "Total ad ratio"),
        ("Current Ad Sales", fmt_currency(baseline_sales),    "Uploaded data"),
    ]
    hero_html = (
        '<div class="kpi-hero">'
        '<div style="font-size:11px;color:rgba(255,255,255,0.4);font-weight:700;'
        'text-transform:uppercase;letter-spacing:1px;margin-bottom:14px;">'
        '📂 Current Performance — Uploaded Data (Single Source of Truth)'
        '</div>'
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

    # ── Baseline validation strip ───────────────────────────────────────────────
    # Confirms that displayed Current values match the uploaded report exactly.
    _val_acos  = round(baseline_spend / baseline_sales * 100, 2) if baseline_sales > 0 else None
    _val_roas  = round(baseline_sales / baseline_spend, 2)       if baseline_spend > 0 else None
    _acos_ok   = abs((_val_acos  or 0) - (baseline_acos  or 0)) < 0.01
    _roas_ok   = abs((_val_roas  or 0) - (baseline_roas  or 0)) < 0.01
    _val_color = "#10b981" if (_acos_ok and _roas_ok) else "#f97316"
    _val_icon  = "✅" if (_acos_ok and _roas_ok) else "⚠️"
    st.markdown(f"""
    <div style="background:#f0fdf4;border:1px solid #86efac;border-left:4px solid {_val_color};
                border-radius:0 10px 10px 0;padding:10px 18px;margin-bottom:20px;
                font-size:13px;color:#166534;display:flex;gap:24px;flex-wrap:wrap;">
        <span style="font-weight:700;">{_val_icon} Baseline Validation:</span>
        <span>Ad Spend = <strong>{fmt_currency(baseline_spend)}</strong></span>
        <span>Ad Sales = <strong>{fmt_currency(baseline_sales)}</strong></span>
        <span>ACOS = <strong>{fmt_pct(_val_acos)}</strong> {"✅" if _acos_ok else "⚠️"}</span>
        <span>ROAS = <strong>{f"{_val_roas:.2f}x" if _val_roas else "N/A"}</strong> {"✅" if _roas_ok else "⚠️"}</span>
        <span style="color:#6b7280;font-size:12px;">— Computed directly from uploaded report</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Current vs Projected comparison tiles ──────────────────────────────────
    st.markdown(
        f'<div class="section-header">'
        f'📊 Current Performance (Uploaded Data) &nbsp;→&nbsp; Projected Performance ({proj_label})'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f"""
    <div class="callout-banner">
        <strong>LEFT = Current (Uploaded Data)</strong> — always from your reports, never modified. &nbsp;|&nbsp;
        <strong>RIGHT = Projected ({proj_label})</strong> — forecast output.
        Change the scenario selector below the table to see a different projection.
    </div>
    """, unsafe_allow_html=True)

    r1 = st.columns(4)
    r1[0].markdown(_metric_tile("💰 Ad Spend",     baseline_spend,   proj_spend,  fmt_currency, True),  unsafe_allow_html=True)
    r1[1].markdown(_metric_tile("📈 Ad Sales",      baseline_sales,   proj_sales,  fmt_currency, True),  unsafe_allow_html=True)
    r1[2].markdown(_metric_tile("🏪 Total Revenue", baseline_revenue, proj_rev,    fmt_currency, True),  unsafe_allow_html=True)
    r1[3].markdown(_metric_tile("💹 Revenue Gap",   0, proj_rev - baseline_revenue, fmt_currency, True), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
    r2 = st.columns(4)
    r2[0].markdown(_metric_tile("🎯 ACOS",      baseline_acos,   proj_acos,  fmt_pct,                           False, True),  unsafe_allow_html=True)
    r2[1].markdown(_metric_tile("⚡ ROAS",       baseline_roas,   proj_roas,  lambda v: f"{v:.2f}x" if v else "—", True,  False), unsafe_allow_html=True)
    r2[2].markdown(_metric_tile("📊 TACOS",      baseline_tacos,  proj_tacos, fmt_pct,                           False, True),  unsafe_allow_html=True)
    r2[3].markdown(_metric_tile("💵 Cost/Order", baseline_cpo,    proj_cpo,   fmt_currency,                      False, False), unsafe_allow_html=True)

    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
    r3 = st.columns(4)
    r3[0].markdown(_metric_tile("👁️ Impressions", baseline_impr,   proj_impr,   fmt_num,      True),  unsafe_allow_html=True)
    r3[1].markdown(_metric_tile("🖱️ Clicks",      baseline_clicks, proj_clicks, fmt_num,      True),  unsafe_allow_html=True)
    r3[2].markdown(_metric_tile("🛒 Ad Orders",   baseline_orders, proj_orders, fmt_num,      True),  unsafe_allow_html=True)
    r3[3].markdown(_metric_tile("💲 CPC",         baseline_cpc,    proj_cpc,    fmt_currency, False), unsafe_allow_html=True)

    # Projected channel split tiles (right-hand side only — no "current" channel breakdown available)
    st.markdown(
        f'<div class="section-header">💰 Projected Channel Budget — {proj_label}</div>',
        unsafe_allow_html=True,
    )
    ch_palette = {"Sponsored Products": "#4f46e5", "Sponsored Brands": "#f97316", "Sponsored Display": "#10b981"}
    ch_cols = st.columns(3)
    for col, (ch_name, alloc_data) in zip(ch_cols, proj_alloc.items()):
        color  = ch_palette.get(ch_name, "#6b7280")
        budget = alloc_data.get("budget", 0)
        share  = alloc_data.get("share_pct", 0)
        incr   = alloc_data.get("incremental_budget", 0)
        with col:
            col.markdown(f"""
            <div style="background:#ffffff;border-top:4px solid {color};border-radius:10px;
                        padding:14px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                <div style="font-size:12px;font-weight:800;color:{color};">{ch_name}</div>
                <div style="font-size:24px;font-weight:900;color:#1e1b4b;margin:6px 0;">{fmt_currency(budget)}</div>
                <div style="font-size:13px;color:#6b7280;">{share:.1f}% of projected budget</div>
                <div style="font-size:12px;font-weight:700;color:{color};margin-top:4px;">
                    +{fmt_currency(incr)} incremental</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Scenario Comparison Table ───────────────────────────────────────────────
    # Design:
    #   Row 0  = 📂 Current (Uploaded Data) — baseline only, no Projected columns
    #   Row 1+ = one row per scenario — Projected columns are UNIQUE per scenario
    #
    # The "Current" columns appear ONLY on the baseline row so users instantly
    # see that every subsequent row is a true what-if projection, not a copy.
    # All projected metrics are derived fresh by the forecast engine.

    # Compute baseline organic sales for the current row
    _b_organic = max(baseline_revenue - baseline_sales, 0)
    _b_ad_contr = round(baseline_sales / baseline_revenue * 100, 1) if baseline_revenue > 0 else 0
    _b_org_contr = round(_b_organic / baseline_revenue * 100, 1) if baseline_revenue > 0 else 0

    def _scenario_row(label: str, s: dict) -> dict:
        """Build one projected scenario row from a forecast result dict."""
        return {
            "Scenario":                    label,
            # ── Projected Revenue block ──
            "Proj. Revenue ($)":           s["target_revenue"],
            "Revenue Gap ($)":             s["revenue_gap"],
            "Incr. Revenue ($)":           s.get("incremental_revenue", s["revenue_gap"]),
            # ── Projected Ad block ──
            "Proj. Ad Spend ($)":          s["recommended_spend"],
            "Incr. Ad Spend ($)":          s["incremental_spend"],
            "Proj. Ad Sales ($)":          s["target_ad_sales"],
            "Ad Sales Contribution (%)":   s.get("projected_ad_contribution",
                                               round(s["target_ad_sales"] / s["target_revenue"] * 100, 1)
                                               if s["target_revenue"] > 0 else 0),
            # ── Projected Organic block ──
            "Proj. Organic Sales ($)":     s.get("projected_organic_sales",
                                               max(s["target_revenue"] - s["target_ad_sales"], 0)),
            "Organic Contribution (%)":    s.get("projected_org_contribution",
                                               round(max(s["target_revenue"] - s["target_ad_sales"], 0)
                                                     / s["target_revenue"] * 100, 1)
                                               if s["target_revenue"] > 0 else 0),
            # ── Projected Efficiency block ──
            "Proj. ACOS (%)":              s["projected_acos_pct"],
            "Proj. ROAS":                  s["projected_roas"] or 0,
            "Proj. TACOS (%)":             s["projected_tacos_pct"] or 0,
        }

    # Current baseline row — projected columns left blank (—)
    current_row = pd.DataFrame([{
        "Scenario":                  "📂 Current (Uploaded Data)",
        "Proj. Revenue ($)":         baseline_revenue,
        "Revenue Gap ($)":           0.0,
        "Incr. Revenue ($)":         0.0,
        "Proj. Ad Spend ($)":        baseline_spend,
        "Incr. Ad Spend ($)":        0.0,
        "Proj. Ad Sales ($)":        baseline_sales,
        "Ad Sales Contribution (%)": _b_ad_contr,
        "Proj. Organic Sales ($)":   _b_organic,
        "Organic Contribution (%)":  _b_org_contr,
        "Proj. ACOS (%)":            baseline_acos or 0,
        "Proj. ROAS":                baseline_roas or 0,
        "Proj. TACOS (%)":           baseline_tacos or 0,
    }])

    # Scenario rows
    sc_rows = []
    if custom_scenario:
        cs_label = f"🎯 Custom ({'+' if custom_scenario['growth_pct'] >= 0 else ''}{custom_scenario['growth_pct']:.1f}%)"
        sc_rows.append(_scenario_row(cs_label, custom_scenario))
    for s in scenarios:
        sc_rows.append(_scenario_row(f"📈 +{s['growth_pct']:.0f}%", s))

    full_df = pd.concat([current_row, pd.DataFrame(sc_rows)], ignore_index=True)

    col_order = [
        "Scenario",
        "Proj. Revenue ($)", "Revenue Gap ($)", "Incr. Revenue ($)",
        "Proj. Ad Spend ($)", "Incr. Ad Spend ($)", "Proj. Ad Sales ($)",
        "Ad Sales Contribution (%)", "Proj. Organic Sales ($)", "Organic Contribution (%)",
        "Proj. ACOS (%)", "Proj. ROAS", "Proj. TACOS (%)",
    ]
    full_df = full_df[[c for c in col_order if c in full_df.columns]]

    fmt = {
        "Proj. Revenue ($)":         "${:,.0f}",
        "Revenue Gap ($)":           "${:,.0f}",
        "Incr. Revenue ($)":         "${:,.0f}",
        "Proj. Ad Spend ($)":        "${:,.0f}",
        "Incr. Ad Spend ($)":        "${:,.0f}",
        "Proj. Ad Sales ($)":        "${:,.0f}",
        "Ad Sales Contribution (%)": "{:.1f}%",
        "Proj. Organic Sales ($)":   "${:,.0f}",
        "Organic Contribution (%)":  "{:.1f}%",
        "Proj. ACOS (%)":            "{:.2f}%",
        "Proj. ROAS":                "{:.2f}x",
        "Proj. TACOS (%)":           "{:.2f}%",
    }

    # Column groups header (shown as a legend above the table)
    st.markdown("""
    <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:10px;font-size:12px;font-weight:700;">
        <span style="color:#6b7280;">📂 Row 1 = Current baseline &nbsp;|&nbsp;
        All other rows = fully projected what-if scenarios</span>
        <span style="background:#dbeafe;color:#1d4ed8;border-radius:6px;padding:2px 10px;">Revenue</span>
        <span style="background:#fce7f3;color:#9d174d;border-radius:6px;padding:2px 10px;">Ad</span>
        <span style="background:#d1fae5;color:#065f46;border-radius:6px;padding:2px 10px;">Organic</span>
        <span style="background:#fef3c7;color:#92400e;border-radius:6px;padding:2px 10px;">Efficiency</span>
    </div>
    """, unsafe_allow_html=True)

    def _row_style(row):
        if str(row.get("Scenario", "")).startswith("📂 Current"):
            return ["background-color:#f0fdf4; font-weight:800; border-bottom:2px solid #10b981"] * len(row)
        if str(row.get("Scenario", "")).startswith("🎯 Custom"):
            return ["background-color:#eff6ff; font-weight:700; color:#1d4ed8"] * len(row)
        return [""] * len(row)

    st.markdown('<div class="section-header">📋 What-If Scenario Planner — All Projected Metrics Unique per Scenario</div>', unsafe_allow_html=True)
    st.dataframe(
        full_df.style.format(fmt, na_rep="—").apply(_row_style, axis=1),
        use_container_width=True,
        height=min(40 + len(full_df) * 38, 480),
    )

    # ── Baseline metrics reference strip ────────────────────────────────────────
    st.markdown(f"""
    <div style="background:#f8fafc;border:1px solid #e5e7eb;border-left:4px solid #6b7280;
                border-radius:0 8px 8px 0;padding:10px 20px;margin:8px 0 24px;
                font-size:12px;color:#6b7280;display:flex;gap:28px;flex-wrap:wrap;">
        <span style="font-weight:700;color:#374151;">📂 Current Baseline (Uploaded Data):</span>
        <span>Revenue <strong>{fmt_currency(baseline_revenue)}</strong></span>
        <span>Ad Spend <strong>{fmt_currency(baseline_spend)}</strong></span>
        <span>Ad Sales <strong>{fmt_currency(baseline_sales)}</strong></span>
        <span>Organic <strong>{fmt_currency(_b_organic)}</strong></span>
        <span>ACOS <strong>{fmt_pct(baseline_acos)}</strong></span>
        <span>ROAS <strong>{f"{baseline_roas:.2f}x" if baseline_roas else "N/A"}</strong></span>
        <span>TACOS <strong>{fmt_pct(baseline_tacos)}</strong></span>
    </div>
    """, unsafe_allow_html=True)

    # ── Revenue vs Spend chart ──────────────────────────────────────────────────
    st.markdown('<div class="section-header">📈 Current vs Projected Revenue & Spend by Scenario</div>', unsafe_allow_html=True)

    chart_labels     = ["📂 Current\n(Uploaded)"]
    chart_revenue    = [baseline_revenue]
    chart_spend      = [baseline_spend]
    bar_colors_rev   = ["#6b7280"]
    bar_colors_spend = ["#9ca3af"]

    if custom_scenario:
        chart_labels.append(cs_label)
        chart_revenue.append(custom_scenario["target_revenue"])
        chart_spend.append(custom_scenario["recommended_spend"])
        bar_colors_rev.append("#1d4ed8")
        bar_colors_spend.append("#60a5fa")

    chart_labels     += [f"+{s['growth_pct']}%" for s in scenarios]
    chart_revenue    += [s["target_revenue"]      for s in scenarios]
    chart_spend      += [s["recommended_spend"]   for s in scenarios]
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

    # ── ACOS & ROAS line charts ─────────────────────────────────────────────────
    acos_labels        = ["📂 Current\n(Uploaded)"]
    acos_values        = [baseline_acos or 0]
    roas_values        = [baseline_roas or 0]
    acos_marker_colors = ["#9ca3af"]
    roas_marker_colors = ["#9ca3af"]

    if custom_scenario:
        acos_labels.append(cs_label)
        acos_values.append(custom_scenario["projected_acos_pct"] or 0)
        roas_values.append(custom_scenario["projected_roas"]     or 0)
        acos_marker_colors.append("#1d4ed8")
        roas_marker_colors.append("#1d4ed8")

    acos_labels        += [f"+{s['growth_pct']}%" for s in scenarios]
    acos_values        += [s["projected_acos_pct"]  for s in scenarios]
    roas_values        += [s["projected_roas"] or 0 for s in scenarios]
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
        fig_acos.update_layout(title="ACOS: Current → Projected", height=320,
                                margin=dict(t=50, b=30),
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
        fig_roas.update_layout(title="ROAS: Current → Projected", height=320,
                                margin=dict(t=50, b=30),
                                xaxis_title="Scenario", yaxis_title="ROAS")
        st.plotly_chart(fig_roas, use_container_width=True)

    # ── Channel Allocation ──────────────────────────────────────────────────────
    primary       = custom_scenario if custom_scenario else next((s for s in scenarios if s["growth_pct"] == 10), scenarios[0])
    primary_label = "Custom" if custom_scenario else f"+{primary['growth_pct']}%"
    st.markdown(f'<div class="section-header">💰 Projected Channel Budget Allocation — {primary_label} Scenario</div>', unsafe_allow_html=True)

    alloc_labels  = list(primary["channel_allocation"].keys())
    alloc_budgets = [v["budget"]             for v in primary["channel_allocation"].values()]
    alloc_incr    = [v["incremental_budget"] for v in primary["channel_allocation"].values()]

    ch_col1, ch_col2 = st.columns(2)
    with ch_col1:
        fig_pie = go.Figure(go.Pie(
            labels=alloc_labels, values=alloc_budgets,
            hole=0.45, marker_colors=["#293C5B", "#e71d36", "#f59e0b"],
        ))
        fig_pie.update_layout(title="Total Budget Split", height=320,
                               margin=dict(t=50, b=10, l=10, r=10))
        st.plotly_chart(fig_pie, use_container_width=True)
    with ch_col2:
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(x=alloc_labels, y=alloc_budgets, name="Total Budget",         marker_color="#4f46e5"))
        fig_bar.add_trace(go.Bar(x=alloc_labels, y=alloc_incr,    name="Incremental Increase", marker_color="#f97316"))
        fig_bar.update_layout(
            barmode="group", title="Budget vs Incremental by Channel",
            height=320, margin=dict(t=50, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    alloc_rows = [
        {
            "Channel":                 ch,
            "Total Budget ($)":        alloc["budget"],
            "Incremental Budget ($)":  alloc["incremental_budget"],
            "Share (%)":               alloc["share_pct"],
        }
        for ch, alloc in primary["channel_allocation"].items()
    ]
    st.dataframe(pd.DataFrame(alloc_rows).style.format({
        "Total Budget ($)":       "${:,.2f}",
        "Incremental Budget ($)": "${:,.2f}",
        "Share (%)":              "{:.1f}%",
    }), use_container_width=True, height=160)

    # ── Monthly Media Plan ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-header">📅 Monthly Media Plan & High-Sales Events</div>', unsafe_allow_html=True)

    scenario_labels = []
    scenario_map    = {}

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
            index=0,
            key="monthly_scenario_select",
        )
        sel_scenario      = scenario_map[selected_label]
        sel_growth_pct    = sel_scenario["growth_pct"]
        sel_annual_spend  = sel_scenario["recommended_spend"]
        sel_annual_sales  = sel_scenario["target_ad_sales"]
    else:
        sel_growth_pct   = growth_options[0] if growth_options else 10
        sel_annual_spend = active_spend
        sel_annual_sales = active_sales
        selected_label   = f"+{sel_growth_pct}%"

    _mf_result = monthly_forecast(
        trend_df=trend_df,
        growth_pct=sel_growth_pct,
        total_ordered_revenue=baseline_revenue,
        custom_channel_split=channel_split,
        annual_spend_override=sel_annual_spend,
        annual_sales_override=sel_annual_sales,
    )
    if isinstance(_mf_result, tuple):
        monthly_df, actuals_year_from_forecast = _mf_result
    else:
        monthly_df, actuals_year_from_forecast = _mf_result, 0

    # Persist for Excel export (accessed via st.session_state in app.py)
    st.session_state["last_monthly_df"] = monthly_df

    # Event legend
    event_months = monthly_df[monthly_df["Is Event Month"] == True]
    if not event_months.empty:
        legend_html = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 18px 0;">'
        for _, row in event_months.iterrows():
            legend_html += (
                f'<span style="background:#fef3c7;border:1px solid #f59e0b;border-radius:20px;'
                f'padding:4px 12px;font-size:13px;font-weight:600;color:#92400e;">'
                f'{row["Month Name"]} — {row["Events"]}</span>'
            )
        legend_html += '</div>'
        st.markdown(legend_html, unsafe_allow_html=True)

    # Dual-axis monthly chart
    months             = monthly_df["Month Name"].tolist()
    actual_spend_vals  = [v if v is not None else 0 for v in monthly_df["Actual Spend ($)"].tolist()]
    proj_spend_vals    = monthly_df["Projected Spend ($)"].tolist()
    proj_sales_vals    = monthly_df["Projected Ad Sales ($)"].tolist()
    is_event           = monthly_df["Is Event Month"].tolist()
    bar_colors_proj    = ["#f97316" if e else "#4f46e5" for e in is_event]

    fig_monthly = go.Figure()
    fig_monthly.add_trace(go.Bar(x=months, y=actual_spend_vals, name="Actual Spend",
                                  marker_color="#9ca3af", opacity=0.7))
    fig_monthly.add_trace(go.Bar(x=months, y=proj_spend_vals,
                                  name=f"Projected Spend ({selected_label})",
                                  marker_color=bar_colors_proj, opacity=0.9))
    fig_monthly.add_trace(go.Scatter(x=months, y=proj_sales_vals,
                                      name="Projected Ad Sales", mode="lines+markers",
                                      line=dict(color="#10b981", width=2), marker=dict(size=8),
                                      yaxis="y2"))
    for i, (ev, _month) in enumerate(zip(is_event, months)):
        if ev:
            fig_monthly.add_vrect(x0=i - 0.5, x1=i + 0.5,
                                   fillcolor="rgba(249,115,22,0.10)", layer="below", line_width=0)
    fig_monthly.update_layout(
        barmode="group", height=460,
        yaxis=dict(title="Spend ($)", tickprefix="$"),
        yaxis2=dict(title="Ad Sales ($)", overlaying="y", side="right", tickprefix="$", showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=40), xaxis_title="Month",
        title=f"Monthly Spend & Sales — {selected_label} Scenario  |  🟠 = High-Sales Event Month",
    )
    st.plotly_chart(fig_monthly, use_container_width=True)

    # Monthly channel budget breakdown
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

    # Monthly ROAS & ACOS
    roas_vals = [v if v is not None else 0 for v in monthly_df["Projected ROAS"].tolist()]
    acos_vals = [v if v is not None else 0 for v in monthly_df["Projected ACOS (%)"].tolist()]
    col_r, col_a = st.columns(2)
    with col_r:
        fig_roas_m = go.Figure()
        fig_roas_m.add_trace(go.Scatter(
            x=months, y=roas_vals, mode="lines+markers", name="Projected ROAS",
            line=dict(color="#4f46e5", width=2),
            marker=dict(size=9, color=["#f97316" if e else "#4f46e5" for e in is_event]),
        ))
        fig_roas_m.update_layout(title="Monthly Projected ROAS", height=300,
                                   yaxis_title="ROAS", xaxis_title="Month", margin=dict(t=50, b=30))
        st.plotly_chart(fig_roas_m, use_container_width=True)
    with col_a:
        fig_acos_m = go.Figure()
        fig_acos_m.add_trace(go.Scatter(
            x=months, y=acos_vals, mode="lines+markers", name="Projected ACOS",
            line=dict(color="#f97316", width=2),
            marker=dict(size=9, color=["#f97316" if e else "#6b7280" for e in is_event]),
        ))
        fig_acos_m.update_layout(title="Monthly Projected ACOS (%)", height=300,
                                   yaxis_title="ACOS (%)", xaxis_title="Month", margin=dict(t=50, b=30))
        st.plotly_chart(fig_acos_m, use_container_width=True)

    # Full monthly plan table
    actual_year  = actuals_year_from_forecast if actuals_year_from_forecast else None
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

    rename_map = {
        "Actual Spend ($)":    f"Actual Spend ({actual_label}) ($)",
        "Actual Ad Sales ($)": f"Actual Sales ({actual_label}) ($)",
        "Actual ACOS (%)":     f"Actual ACOS ({actual_label})",
        "Actual ROAS":         f"Actual ROAS ({actual_label})",
    }
    disp_df = disp_df.rename(columns=rename_map)
    disp_df = disp_df.set_index("Month")

    # Totals row
    totals = {}
    for c in disp_df.columns:
        if c == "Month Name":
            totals[c] = "TOTAL"
        elif c == "Events":
            totals[c] = "—"
        elif "Uplift" in c:
            totals[c] = None
        elif "ACOS" in c:
            if "$" not in c:
                spend_col = next((x for x in disp_df.columns if "Spend" in x and ("Actual" in x) == ("Actual" in c) and "$" in x), None)
                sales_col = next((x for x in disp_df.columns if "Sales" in x and ("Actual" in x) == ("Actual" in c) and "$" in x), None)
                if spend_col and sales_col:
                    tot_sp = disp_df[spend_col].sum(skipna=True)
                    tot_sl = disp_df[sales_col].sum(skipna=True)
                    totals[c] = round(tot_sp / tot_sl * 100, 2) if tot_sl > 0 else None
                else:
                    totals[c] = None
            else:
                totals[c] = disp_df[c].sum(skipna=True)
        elif "ROAS" in c:
            spend_col = next((x for x in disp_df.columns if "Spend" in x and ("Actual" in x) == ("Actual" in c) and "$" in x), None)
            sales_col = next((x for x in disp_df.columns if "Sales" in x and ("Actual" in x) == ("Actual" in c) and "$" in x), None)
            if spend_col and sales_col:
                tot_sp = disp_df[spend_col].sum(skipna=True)
                tot_sl = disp_df[sales_col].sum(skipna=True)
                totals[c] = round(tot_sl / tot_sp, 2) if tot_sp > 0 else None
            else:
                totals[c] = None
        elif "$" in c:
            totals[c] = disp_df[c].sum(skipna=True)
        else:
            totals[c] = None

    totals_row = pd.DataFrame([totals], index=["TOTAL"])
    disp_df    = pd.concat([disp_df, totals_row])

    def _style_monthly_row(row):
        if row.name == "TOTAL":
            return [
                "background-color: #1e1b4b; color: #ffffff; font-weight: 800; "
                "font-size: 13px; border-top: 2px solid #f97316;"
            ] * len(row)
        if row["Events"] != "—":
            return ["background-color: #fffbeb; font-weight: 600"] * len(row)
        return [""] * len(row)

    fmt_map = {}
    for c in disp_df.columns:
        if "$" in c:
            fmt_map[c] = "${:,.0f}"
        elif "ACOS" in c:
            fmt_map[c] = "{:.1f}%"
        elif "ROAS" in c:
            fmt_map[c] = "{:.2f}x"
        elif "Uplift" in c:
            fmt_map[c] = "+{:.0f}%"

    styled = disp_df.style.format(fmt_map, na_rep="—").apply(_style_monthly_row, axis=1)
    st.dataframe(styled, use_container_width=True, height=494)

    return scenarios
