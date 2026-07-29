"""
pages/tab_recommendations.py — Strategic Recommendations tab
Renders performance health check, growth scenario action plans,
channel investment strategy, seasonal budget calendar, and ASIN/bid strategy tiers.
"""

import streamlit as st

from utils.formatters import fmt_currency, fmt_pct


def render_recommendations(ads_metrics: dict, vendor_metrics: dict, scenarios: list) -> None:
    """Render the Strategic Recommendations tab."""
    acos  = ads_metrics.get("overall_acos")
    roas  = ads_metrics.get("overall_roas")
    ctr   = ads_metrics.get("overall_ctr")
    cpc   = ads_metrics.get("overall_cpc")
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
        for s in scenarios[:4]:
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
            badge = "🎯 Custom" if s.get("is_custom_scenario") else f"📈 {label} Growth"
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
        ("Feb", "Valentine's Day",    "+10%", "#f97316"),
        ("May", "Mother's Day",       "+8%",  "#f97316"),
        ("Jun", "Father's Day",       "+8%",  "#f97316"),
        ("Jul", "Prime Day ⚡",       "+30%", "#dc2626"),
        ("Aug", "Back to School",     "+5%",  "#f59e0b"),
        ("Oct", "Prime Big Deals ⚡", "+20%", "#dc2626"),
        ("Nov", "Black Friday 🛒",    "+45%", "#dc2626"),
        ("Nov", "Cyber Monday 💻",    "+45%", "#dc2626"),
        ("Dec", "Holiday Season 🎄",  "+25%", "#dc2626"),
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
