"""
pages/tab_metrics.py — Key Metrics Dashboard tab
Phase 2: Richer KPI cards with status badges, efficiency score banner,
improved gauge layout with contextual benchmarks.
"""

import streamlit as st
import plotly.graph_objects as go

from utils.formatters import fmt_currency, fmt_pct, fmt_num


# ---------------------------------------------------------------------------
# KPI card with icon + coloured status badge
# ---------------------------------------------------------------------------
_ICON_MAP = {
    "Total Ad Spend":      "💰",
    "Ad-Attributed Sales": "📈",
    "Overall ACOS":        "🎯",
    "Overall ROAS":        "⚡",
    "Total Impressions":   "👁️",
    "Total Clicks":        "🖱️",
    "CTR":                 "📡",
    "CPC":                 "💲",
    "Total Ad Orders":     "🛒",
    "Conversion Rate":     "🔄",
    "New to Brand %":      "🆕",
    "Cost per Order":      "📦",
    # Vendor
    "Total Ordered Revenue": "🏪",
    "Total Shipped Revenue": "🚚",
    "Total Ordered Units":   "📊",
    "Avg Selling Price":     "💵",
    "Glance Views":          "👀",
}


def _delta_class(label: str, value_str: str) -> str:
    """Return a CSS class for the badge based on whether metric is good/warn/info."""
    if "ACOS" in label:
        # Extract numeric — lower is better
        try:
            v = float(value_str.replace("%", "").replace("N/A", ""))
            if v <= 20:  return "metric-delta metric-delta-good"
            if v <= 35:  return "metric-delta metric-delta-warn"
            return "metric-delta metric-delta-warn"
        except Exception:
            return "metric-delta metric-delta-info"
    if "ROAS" in label:
        try:
            v = float(value_str.replace("x", "").replace("N/A", ""))
            if v >= 4:   return "metric-delta metric-delta-good"
            if v >= 2:   return "metric-delta metric-delta-warn"
            return "metric-delta metric-delta-warn"
        except Exception:
            return "metric-delta metric-delta-info"
    return "metric-delta metric-delta-info"


def _metric_card(label: str, value: str, delta: str = None) -> str:
    icon = _ICON_MAP.get(label, "📌")
    delta_html = ""
    if delta:
        cls = _delta_class(label, value)
        delta_html = f'<div class="{cls}">{delta}</div>'
    return f"""
    <div class="metric-card">
        <div class="metric-card-icon">{icon}</div>
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """


# ---------------------------------------------------------------------------
# Efficiency score banner
# ---------------------------------------------------------------------------
def _efficiency_banner(ads_metrics: dict) -> None:
    acos  = ads_metrics.get("overall_acos")
    roas  = ads_metrics.get("overall_roas")
    ctr   = ads_metrics.get("overall_ctr")
    cvr   = ads_metrics.get("conversion_rate")

    score = 0
    checks = []

    if acos is not None:
        if acos <= 20:
            score += 25; checks.append(("🟢", "ACOS Excellent", f"{acos:.1f}%"))
        elif acos <= 35:
            score += 15; checks.append(("🟡", "ACOS Acceptable", f"{acos:.1f}%"))
        else:
            checks.append(("🔴", "ACOS High", f"{acos:.1f}%"))

    if roas is not None:
        if roas >= 4:
            score += 25; checks.append(("🟢", "ROAS Strong", f"{roas:.2f}x"))
        elif roas >= 2:
            score += 15; checks.append(("🟡", "ROAS Adequate", f"{roas:.2f}x"))
        else:
            checks.append(("🔴", "ROAS Low", f"{roas:.2f}x"))

    if ctr is not None:
        if ctr >= 0.5:
            score += 25; checks.append(("🟢", "CTR Strong", f"{ctr:.2f}%"))
        elif ctr >= 0.3:
            score += 15; checks.append(("🟡", "CTR Average", f"{ctr:.2f}%"))
        else:
            checks.append(("🔴", "CTR Low", f"{ctr:.2f}%"))

    if cvr is not None:
        if cvr >= 10:
            score += 25; checks.append(("🟢", "CVR Excellent", f"{cvr:.1f}%"))
        elif cvr >= 5:
            score += 15; checks.append(("🟡", "CVR Average", f"{cvr:.1f}%"))
        else:
            checks.append(("🔴", "CVR Low", f"{cvr:.1f}%"))

    if not checks:
        return

    score = min(score, 100)
    bar_color = "#10b981" if score >= 70 else "#f97316" if score >= 40 else "#dc2626"
    grade     = "Excellent" if score >= 80 else "Good" if score >= 60 else "Fair" if score >= 40 else "Needs Work"

    checks_html = "".join(
        f'<div style="display:flex;align-items:center;gap:6px;padding:5px 10px;background:rgba(255,255,255,0.07);'
        f'border-radius:8px;min-width:160px;">'
        f'<span style="font-size:13px;">{dot}</span>'
        f'<div>'
        f'<div style="font-size:10px;color:rgba(255,255,255,0.5);font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">{name}</div>'
        f'<div style="font-size:13px;font-weight:800;color:#ffffff;">{val}</div>'
        f'</div>'
        f'</div>'
        for dot, name, val in checks
    )

    st.markdown(f"""
    <div class="kpi-hero" style="padding:18px 24px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
            <div>
                <div style="font-size:11px;color:rgba(255,255,255,0.45);font-weight:700;
                            text-transform:uppercase;letter-spacing:1px;">Account Health Score</div>
                <div style="font-size:28px;font-weight:900;color:#ffffff;line-height:1.1;margin-top:2px;">
                    {score}<span style="font-size:14px;color:rgba(255,255,255,0.5);font-weight:500;">/100</span>
                    &nbsp;<span style="font-size:14px;color:{bar_color};font-weight:700;">{grade}</span>
                </div>
            </div>
            <div style="width:140px;">
                <div style="background:rgba(255,255,255,0.12);border-radius:8px;height:8px;overflow:hidden;">
                    <div style="width:{score}%;background:linear-gradient(90deg,{bar_color},{bar_color}aa);
                                height:100%;border-radius:8px;transition:width 0.6s;"></div>
                </div>
                <div style="font-size:10px;color:rgba(255,255,255,0.35);margin-top:4px;text-align:right;">
                    vs industry benchmarks
                </div>
            </div>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:8px;">
            {checks_html}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------
def render_metrics_dashboard(ads_metrics: dict, vendor_metrics: dict) -> None:
    """Render the Key Metrics dashboard tab — Phase 2."""

    # ── Efficiency score banner ──────────────────────────────────────────
    _efficiency_banner(ads_metrics)

    # ── Ads KPI grid ─────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📊 Amazon Advertising Metrics</div>', unsafe_allow_html=True)

    roas_val = ads_metrics.get("overall_roas")
    acos_val = ads_metrics.get("overall_acos")
    kpis_ads = [
        ("Total Ad Spend",       fmt_currency(ads_metrics.get("total_spend")),       None),
        ("Ad-Attributed Sales",  fmt_currency(ads_metrics.get("total_ad_sales")),    None),
        ("Overall ACOS",         fmt_pct(acos_val),
         "✅ Efficient" if acos_val and acos_val <= 20 else
         "⚠️ Acceptable" if acos_val and acos_val <= 35 else
         "🔴 High" if acos_val else None),
        ("Overall ROAS",
         f"{roas_val:.2f}x" if roas_val else "N/A",
         "✅ Strong" if roas_val and roas_val >= 4 else
         "⚠️ Adequate" if roas_val and roas_val >= 2 else
         "🔴 Low" if roas_val else None),
        ("Total Impressions",    fmt_num(ads_metrics.get("total_impressions")),        None),
        ("Total Clicks",         fmt_num(ads_metrics.get("total_clicks")),             None),
        ("CTR",                  fmt_pct(ads_metrics.get("overall_ctr")),              None),
        ("CPC",                  fmt_currency(ads_metrics.get("overall_cpc")),         None),
        ("Total Ad Orders",      fmt_num(ads_metrics.get("total_ad_orders")),          None),
        ("Conversion Rate",      fmt_pct(ads_metrics.get("conversion_rate")),          "Click → Purchase"),
        ("New to Brand %",       fmt_pct(ads_metrics.get("ntb_order_pct")),            "First-time buyers"),
        ("Cost per Order",       fmt_currency(ads_metrics.get("cost_per_order")),      None),
    ]

    cols = st.columns(4)
    for i, (label, val, delta) in enumerate(kpis_ads):
        with cols[i % 4]:
            st.markdown(_metric_card(label, val, delta), unsafe_allow_html=True)

    # ── Vendor KPI grid ───────────────────────────────────────────────────
    if vendor_metrics:
        st.markdown('<div class="section-header">🏪 Vendor Central Sales Metrics</div>', unsafe_allow_html=True)
        kpis_vendor = [
            ("Total Ordered Revenue", fmt_currency(vendor_metrics.get("total_ordered_revenue")), None),
            ("Total Shipped Revenue", fmt_currency(vendor_metrics.get("total_shipped_revenue")), None),
            ("Total Ordered Units",   fmt_num(vendor_metrics.get("total_ordered_units")),        None),
            ("Avg Selling Price",     fmt_currency(vendor_metrics.get("avg_selling_price")),     None),
        ]
        # Add Glance Views if present (new Vendor Central format)
        gv = vendor_metrics.get("total_glance_views")
        if gv and gv > 0:
            kpis_vendor.append(("Glance Views", fmt_num(gv), "Product detail page visits"))
        cols2 = st.columns(min(len(kpis_vendor), 4))
        for i, (label, val, delta) in enumerate(kpis_vendor):
            with cols2[i % len(cols2)]:
                st.markdown(_metric_card(label, val, delta), unsafe_allow_html=True)

    # ── Performance gauges ────────────────────────────────────────────────
    if acos_val is not None or roas_val is not None:
        st.markdown('<div class="section-header">📈 Performance Gauges</div>', unsafe_allow_html=True)

        # Callout with benchmark context
        st.markdown("""
        <div class="callout-banner">
            <strong>Industry Benchmarks:</strong>
            ACOS: &nbsp;🟢 &lt;20% excellent · 🟡 20–35% acceptable · 🔴 &gt;35% high &nbsp;|&nbsp;
            ROAS: &nbsp;🔴 &lt;2x minimum · 🟡 2–4x adequate · 🟢 &gt;4x strong
        </div>
        """, unsafe_allow_html=True)

        gcols = st.columns(2)

        if acos_val is not None:
            with gcols[0]:
                fig = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=acos_val,
                    number={"suffix": "%", "font": {"size": 36, "color": "#1e1b4b"}},
                    title={"text": "ACOS — Target: ≤25%", "font": {"size": 14, "color": "#6b7280"}},
                    delta={"reference": 25, "decreasing": {"color": "#10b981"}, "increasing": {"color": "#dc2626"},
                           "suffix": "pp vs 25% benchmark"},
                    gauge={
                        "axis": {"range": [0, 80], "tickcolor": "#9ca3af", "tickfont": {"size": 11}},
                        "bar": {"color": "#4f46e5", "thickness": 0.25},
                        "bgcolor": "#f8fafc",
                        "borderwidth": 0,
                        "steps": [
                            {"range": [0, 20],  "color": "#d1fae5"},
                            {"range": [20, 35], "color": "#fef3c7"},
                            {"range": [35, 80], "color": "#fee2e2"},
                        ],
                        "threshold": {
                            "line": {"color": "#f97316", "width": 3},
                            "thickness": 0.85, "value": 35,
                        },
                    },
                ))
                fig.update_layout(
                    height=300, margin=dict(t=50, b=10, l=30, r=30),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)

        if roas_val is not None:
            with gcols[1]:
                fig2 = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=roas_val,
                    number={"suffix": "x", "font": {"size": 36, "color": "#1e1b4b"}},
                    title={"text": "ROAS — Target: ≥4x", "font": {"size": 14, "color": "#6b7280"}},
                    delta={"reference": 4, "increasing": {"color": "#10b981"}, "decreasing": {"color": "#dc2626"},
                           "suffix": "x vs 4x target"},
                    gauge={
                        "axis": {"range": [0, 10], "tickcolor": "#9ca3af", "tickfont": {"size": 11}},
                        "bar": {"color": "#f97316", "thickness": 0.25},
                        "bgcolor": "#f8fafc",
                        "borderwidth": 0,
                        "steps": [
                            {"range": [0, 2],  "color": "#fee2e2"},
                            {"range": [2, 4],  "color": "#fef3c7"},
                            {"range": [4, 10], "color": "#d1fae5"},
                        ],
                        "threshold": {
                            "line": {"color": "#10b981", "width": 3},
                            "thickness": 0.85, "value": 4,
                        },
                    },
                ))
                fig2.update_layout(
                    height=300, margin=dict(t=50, b=10, l=30, r=30),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig2, use_container_width=True)
