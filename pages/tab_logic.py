"""
pages/tab_logic.py — How It Works (Engine Logic) tab
Explains every formula, override logic, and data-source mapping used
by the Amazon Media Plan Forecast Engine.
"""

import streamlit as st
import pandas as pd


def render_logic_tab() -> None:
    """Render the Engine Logic tab."""
    st.markdown('<div class="section-header">⚙️ How This Engine Works</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#ffffff;border-radius:12px;padding:20px 28px;
                box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:20px;">
        <p style="font-size:15px;color:#374151;line-height:1.8;">
        This engine ingests your <strong>Amazon Advertising report</strong> and
        <strong>Vendor Central ASIN Sales report</strong>, extracts key performance baselines,
        then models what happens to every metric when you change spend, target revenue, ROAS, or TACOS.
        Every number you see in the Forecast tab is derived from real formulas — not guesses.
        This page explains every calculation so your entire team can trust and interrogate the output.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Section 1: Core Metric Definitions ─────────────────────────────────
    st.markdown('<div class="section-header">📐 Core Metric Definitions</div>', unsafe_allow_html=True)
    metrics_def = [
        ("ACOS — Advertising Cost of Sales",
         "Spend ÷ Ad-Attributed Sales × 100",
         "How much you spend in ads for every $1 of ad-driven revenue. Lower = more efficient.",
         "Spend = $50,000 · Ad Sales = $200,000 → ACOS = 25%",
         "#f97316"),
        ("ROAS — Return on Ad Spend",
         "Ad-Attributed Sales ÷ Spend",
         "How many dollars of sales every $1 of ad spend generates. Higher = better.",
         "Ad Sales = $200,000 · Spend = $50,000 → ROAS = 4.0x",
         "#4f46e5"),
        ("TACOS — Total Advertising Cost of Sales",
         "Spend ÷ Total Ordered Revenue × 100",
         "Ad spend as a % of ALL revenue (including organic). Shows true ad efficiency against the whole business.",
         "Spend = $50,000 · Total Revenue = $500,000 → TACOS = 10%",
         "#10b981"),
        ("CVR — Conversion Rate",
         "Ad Orders ÷ Clicks × 100",
         "% of ad clicks that result in a purchase. Driven by listing quality, reviews, price.",
         "Orders = 500 · Clicks = 10,000 → CVR = 5%",
         "#6366f1"),
        ("CPC — Cost Per Click",
         "Spend ÷ Clicks",
         "Average auction price per click. Driven by keyword competition and your bid strategy.",
         "Spend = $50,000 · Clicks = 25,000 → CPC = $2.00",
         "#f59e0b"),
        ("CTR — Click-Through Rate",
         "Clicks ÷ Impressions × 100",
         "% of ad impressions that get clicked. Driven by creative quality, title, main image.",
         "Clicks = 25,000 · Impressions = 5,000,000 → CTR = 0.5%",
         "#dc2626"),
    ]
    for i in range(0, len(metrics_def), 3):
        cols = st.columns(3)
        for col, item in zip(cols, metrics_def[i:i + 3]):
            name, formula, meaning, example, color = item
            with col:
                st.markdown(f"""
                <div style="background:#ffffff;border-top:4px solid {color};border-radius:10px;
                            padding:16px;box-shadow:0 2px 8px rgba(0,0,0,0.05);height:100%;">
                    <div style="font-size:13px;font-weight:800;color:{color};margin-bottom:6px;">{name}</div>
                    <div style="background:#f0f2ff;border-radius:6px;padding:6px 10px;
                                font-family:monospace;font-size:13px;color:#1e1b4b;margin-bottom:8px;">
                        {formula}
                    </div>
                    <div style="font-size:13px;color:#374151;margin-bottom:8px;">{meaning}</div>
                    <div style="font-size:12px;color:#6b7280;font-style:italic;">📌 {example}</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)

    # ── Section 2: How Scenarios Are Computed ──────────────────────────────
    st.markdown('<div class="section-header">🔢 How Growth Scenarios Are Computed</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#ffffff;border-radius:12px;padding:20px 28px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <p style="font-size:14px;color:#374151;line-height:1.9;">
        When you select a growth scenario (e.g. <strong>+10%</strong>), the engine runs these steps in order:
        </p>
    </div>
    """, unsafe_allow_html=True)

    steps = [
        ("1", "#4f46e5", "Set Target Revenue",
         "Target Revenue = Baseline Revenue × (1 + Growth% ÷ 100)",
         "Baseline = $1,000,000 · Growth = 10% → Target = $1,100,000 · Revenue Gap = $100,000"),
        ("2", "#f97316", "Estimate Ad Contribution",
         "Ad Contribution Ratio = min(Ad Sales ÷ Total Revenue, 90%)\nIncremental Ad Sales Needed = Revenue Gap × Ad Contribution Ratio",
         "Ad Sales = $400,000 · Revenue = $1,000,000 → Ratio = 40%\nGap = $100,000 → Incremental Ad Sales = $40,000"),
        ("3", "#10b981", "Apply ACOS Efficiency Decay",
         "As you spend more, ad efficiency slightly degrades.\nDecay Multiplier = 1 + (Growth% ÷ 10) × 0.04\nProjected ACOS = Current ACOS × Decay Multiplier",
         "Current ACOS = 25% · Growth = 10% → Multiplier = 1.04 → Proj. ACOS = 26%"),
        ("4", "#6366f1", "Calculate Recommended Spend",
         "Target Ad Sales = Current Ad Sales + Incremental Ad Sales Needed\nRecommended Spend = Target Ad Sales × (Projected ACOS ÷ 100)",
         "Target Ad Sales = $440,000 · Proj. ACOS = 26% → Rec. Spend = $114,400"),
        ("5", "#f59e0b", "Derive All Other Metrics",
         "Projected ROAS = Target Ad Sales ÷ Recommended Spend\nProjected TACOS = Recommended Spend ÷ Target Revenue × 100\nIncremental Spend = Recommended Spend − Current Spend",
         "ROAS = $440,000 ÷ $114,400 = 3.85x · TACOS = $114,400 ÷ $1,100,000 = 10.4%"),
        ("6", "#dc2626", "Allocate by Channel Split",
         "SP Budget = Recommended Spend × SP%\nSB Budget = Recommended Spend × SB%\nSD Budget = Recommended Spend × SD%",
         "Spend = $114,400 · SP 65% = $74,360 · SB 25% = $28,600 · SD 10% = $11,440"),
    ]
    for num, color, title, formula, example in steps:
        st.markdown(f"""
        <div style="background:#ffffff;border-radius:10px;padding:16px 20px;margin-bottom:10px;
                    box-shadow:0 2px 6px rgba(0,0,0,0.05);border-left:5px solid {color};
                    display:flex;gap:16px;align-items:flex-start;">
            <div style="min-width:36px;height:36px;background:{color};border-radius:50%;
                        display:flex;align-items:center;justify-content:center;
                        font-size:16px;font-weight:900;color:#fff;flex-shrink:0;">{num}</div>
            <div style="flex:1;">
                <div style="font-size:14px;font-weight:800;color:{color};margin-bottom:4px;">{title}</div>
                <div style="background:#f8f9fa;border-radius:6px;padding:8px 12px;
                            font-family:monospace;font-size:12.5px;color:#1e1b4b;
                            white-space:pre-line;margin-bottom:6px;">{formula}</div>
                <div style="font-size:12px;color:#6b7280;font-style:italic;">📌 Example: {example}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Section 3: Custom Override Logic ───────────────────────────────────
    st.markdown('<div class="section-header">🎯 Custom Target Override Logic</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#eff6ff;border:2px solid #3b82f6;border-radius:12px;padding:18px 24px;margin-bottom:16px;">
        <p style="font-size:14px;color:#1e3a8a;line-height:1.9;margin:0;">
        When you enter <strong>Custom Scenario Targets</strong> in the sidebar, the engine overrides the
        growth-% math and instead back-calculates everything from your inputs. You can pin any one metric
        and the rest are derived. Multiple inputs are resolved in priority order.
        </p>
    </div>
    """, unsafe_allow_html=True)

    overrides = [
        ("🏪 Target Revenue / OPS",    "#4f46e5", "Highest priority",
         "Sets Target Revenue directly. Growth% is back-calculated: Growth = (Target ÷ Baseline − 1) × 100",
         "Input $1.2M → Growth = 20%. All spend/ROAS/TACOS derived from this new revenue base."),
        ("📈 Target Ad Sales",          "#f97316", "2nd priority",
         "Pins the ad-attributed sales you expect. Skips the ad-contribution-ratio estimate entirely.",
         "Input $500,000 → Engine uses this as Target Ad Sales to derive required spend."),
        ("⚡ Target ROAS",              "#10b981", "3rd priority (sets spend)",
         "Spend = Target Ad Sales ÷ Target ROAS. Forces the engine to find the spend that hits your ROAS target.",
         "Ad Sales = $500,000 · ROAS = 6x → Spend = $83,333"),
        ("📊 Target TACOS %",           "#6366f1", "4th priority (sets spend)",
         "Spend = Target Revenue × (TACOS ÷ 100). Useful when you have a board-level TACOS ceiling to hit.",
         "Revenue = $1.2M · TACOS = 8% → Spend = $96,000"),
        ("💰 Target Ad Spend",          "#f59e0b", "5th priority (sets spend)",
         "Pins spend directly. ACOS, ROAS, TACOS, and all volume metrics are derived from this spend level.",
         "Input $80,000 → Engine derives ACOS, ROAS, TACOS, Impressions, Clicks, Orders from this spend."),
    ]
    for name, color, priority, logic, example in overrides:
        st.markdown(f"""
        <div style="background:#ffffff;border-radius:10px;padding:14px 18px;margin-bottom:8px;
                    box-shadow:0 1px 5px rgba(0,0,0,0.05);border-left:4px solid {color};">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                <span style="font-size:14px;font-weight:800;color:{color};">{name}</span>
                <span style="font-size:11px;background:{color};color:#fff;border-radius:12px;
                             padding:2px 10px;font-weight:700;">{priority}</span>
            </div>
            <div style="font-size:13px;color:#374151;margin-bottom:4px;">{logic}</div>
            <div style="font-size:12px;color:#6b7280;font-style:italic;">📌 {example}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="reco-card" style="margin-top:6px;">
        <strong>💡 Tip — Combine inputs:</strong> You can set Target Revenue + Target ROAS together.
        The engine will use Revenue to set the revenue target, then use ROAS to back-calculate spend.
        Any metric not explicitly set is derived from the chain.
    </div>""", unsafe_allow_html=True)

    # ── Section 4: Secondary Metric Projection Logic ────────────────────────
    st.markdown('<div class="section-header">📊 How Secondary Metrics Are Projected</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#ffffff;border-radius:12px;padding:20px 28px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <p style="font-size:14px;color:#374151;line-height:1.9;margin:0 0 12px 0;">
        Once Recommended Spend is known, the engine derives all volume metrics using a <strong>Spend Ratio</strong>:
        </p>
        <div style="background:#f0f2ff;border-radius:8px;padding:14px 18px;font-family:monospace;font-size:13px;color:#1e1b4b;">
            Spend Ratio = Recommended Spend ÷ Current Spend<br><br>
            Projected Impressions = Current Impressions × Spend Ratio<br>
            Projected Clicks       = Current Clicks × Spend Ratio<br>
            Projected Ad Orders    = Current Orders × Spend Ratio<br>
            Projected Cost/Order   = Recommended Spend ÷ Projected Orders<br><br>
            CPC  = unchanged  (set by bid strategy &amp; auction competition, not budget level)<br>
            CTR  = unchanged  (set by creative quality &amp; listing, not budget level)<br>
            CVR  = unchanged  (set by listing quality &amp; price, not budget level)
        </div>
        <p style="font-size:13px;color:#6b7280;margin:12px 0 0 0;">
        <strong>Why linear scaling?</strong> Amazon Ads impression/click volume scales roughly linearly
        with budget within the range most brands operate. At very high spend levels efficiency degrades
        (captured by the ACOS decay factor). CPC, CTR, and CVR are listing/bid-driven, not budget-driven.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Section 5: Monthly Plan Logic ──────────────────────────────────────
    st.markdown('<div class="section-header">📅 Monthly Plan & Event Multipliers</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#ffffff;border-radius:12px;padding:20px 28px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <p style="font-size:14px;color:#374151;line-height:1.9;margin:0 0 12px 0;">
        The monthly plan distributes the annual forecast across 12 months using your actual monthly
        spend/sales data as the baseline, then applies event multipliers for high-traffic months:
        </p>
        <div style="background:#f0f2ff;border-radius:8px;padding:14px 18px;font-family:monospace;font-size:13px;color:#1e1b4b;margin-bottom:12px;">
            Monthly Projected Spend = Actual Month Spend × Growth Factor × Event Multiplier<br>
            Monthly Projected Sales = Actual Month Sales × Growth Factor<br><br>
            Growth Factor = 1 + (Growth% ÷ 100)<br>
            Event Multiplier = pre-set per month (see table below)
        </div>
    </div>
    """, unsafe_allow_html=True)

    event_data = [
        ("January",   "New Year Deals",                      "1.00x", "No uplift"),
        ("February",  "Valentine's Day 💝",                  "1.10x", "+10% spend"),
        ("March",     "Spring Sale 🌸",                      "1.00x", "No uplift"),
        ("April",     "—",                                   "1.00x", "No uplift"),
        ("May",       "Mother's Day 💐",                     "1.08x", "+8% spend"),
        ("June",      "Father's Day 👔 / Mid-Year ☀️",       "1.08x", "+8% spend"),
        ("July",      "Prime Day ⚡",                        "1.30x", "+30% spend — highest volume event"),
        ("August",    "Back to School 🎒",                   "1.05x", "+5% spend"),
        ("September", "—",                                   "1.00x", "No uplift"),
        ("October",   "Prime Big Deal Days ⚡",              "1.20x", "+20% spend"),
        ("November",  "Black Friday 🛒 / Cyber Monday 💻",   "1.45x", "+45% spend — peak of the year"),
        ("December",  "Holiday Season 🎄",                   "1.25x", "+25% spend"),
    ]
    ev_df = pd.DataFrame(event_data, columns=["Month", "Events", "Multiplier", "Impact"])

    def _ev_style(row):
        if row["Multiplier"] != "1.00x":
            return ["background-color:#fffbeb;font-weight:600"] * len(row)
        return [""] * len(row)

    st.dataframe(ev_df.style.apply(_ev_style, axis=1), use_container_width=True, height=460)

    # ── Section 6: Channel Split Logic ─────────────────────────────────────
    st.markdown('<div class="section-header">🎯 Channel Split Logic</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#ffffff;border-radius:12px;padding:20px 28px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <p style="font-size:14px;color:#374151;line-height:1.9;margin:0 0 12px 0;">
        The three channel sliders (SP / SB / SD) are <strong>normalised</strong> so they always sum to 100%,
        even if you enter values that don't add up:
        </p>
        <div style="background:#f0f2ff;border-radius:8px;padding:14px 18px;font-family:monospace;font-size:13px;color:#1e1b4b;margin-bottom:12px;">
            Total = SP% + SB% + SD%<br>
            Effective SP Weight = SP% ÷ Total<br>
            Effective SB Weight = SB% ÷ Total<br>
            Effective SD Weight = SD% ÷ Total<br><br>
            SP Budget = Recommended Spend × Effective SP Weight<br>
            SB Budget = Recommended Spend × Effective SB Weight<br>
            SD Budget = Recommended Spend × Effective SD Weight
        </div>
        <p style="font-size:13px;color:#6b7280;margin:0;">
        The sidebar shows the <em>effective</em> split after normalisation.
        Every chart and table in the Forecast tab reflects the normalised weights instantly.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Section 7: Data Sources ─────────────────────────────────────────────
    st.markdown('<div class="section-header">📂 Data Sources & Column Mapping</div>', unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        <div style="background:#ffffff;border-radius:10px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
            <div style="font-weight:800;font-size:14px;color:#4f46e5;margin-bottom:10px;">
                📋 Amazon Advertising Report
            </div>
            <table style="width:100%;font-size:13px;border-collapse:collapse;">
                <tr style="background:#f0f2ff;"><th style="padding:6px;text-align:left;">Engine Field</th><th style="padding:6px;text-align:left;">Report Column(s)</th></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #f0f2ff;">spend</td><td style="padding:5px;border-bottom:1px solid #f0f2ff;">Total cost, Spend, Amount spent</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #f0f2ff;">ad_sales</td><td style="padding:5px;border-bottom:1px solid #f0f2ff;">Sales, Total Sales, 7-day sales</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #f0f2ff;">ad_orders</td><td style="padding:5px;border-bottom:1px solid #f0f2ff;">Purchases, Orders, Conversions</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #f0f2ff;">impressions</td><td style="padding:5px;border-bottom:1px solid #f0f2ff;">Impressions</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #f0f2ff;">clicks</td><td style="padding:5px;border-bottom:1px solid #f0f2ff;">Clicks</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #f0f2ff;">date_range</td><td style="padding:5px;border-bottom:1px solid #f0f2ff;">Date range, Reporting period</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #f0f2ff;">campaign_type</td><td style="padding:5px;border-bottom:1px solid #f0f2ff;">Ad product, Campaign type</td></tr>
                <tr><td style="padding:5px;">asin</td><td style="padding:5px;">Advertised product ID, ASIN</td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)
    with col_b:
        st.markdown("""
        <div style="background:#ffffff;border-radius:10px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
            <div style="font-weight:800;font-size:14px;color:#f97316;margin-bottom:10px;">
                🏪 Vendor Central ASIN Sales Report
            </div>
            <table style="width:100%;font-size:13px;border-collapse:collapse;">
                <tr style="background:#fff7ed;"><th style="padding:6px;text-align:left;">Engine Field</th><th style="padding:6px;text-align:left;">Report Column(s)</th></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #fff7ed;">ordered_revenue</td><td style="padding:5px;border-bottom:1px solid #fff7ed;">Ordered Revenue, Revenue</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #fff7ed;">shipped_revenue</td><td style="padding:5px;border-bottom:1px solid #fff7ed;">Shipped Revenue</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #fff7ed;">ordered_units</td><td style="padding:5px;border-bottom:1px solid #fff7ed;">Ordered Units, Units Ordered</td></tr>
                <tr><td style="padding:5px;border-bottom:1px solid #fff7ed;">asin</td><td style="padding:5px;border-bottom:1px solid #fff7ed;">ASIN, Product ID</td></tr>
            </table>
            <div style="margin-top:14px;padding:10px 14px;background:#fff7ed;border-radius:8px;
                        border-left:4px solid #f97316;font-size:13px;color:#92400e;">
                <strong>Export tip:</strong> From Vendor Central → Analytics → Sales Diagnostics.
                Select <em>Ordered Revenue</em> + <em>Ordered Units</em> before exporting.
                Without Vendor Central data, the engine uses Ad-Attributed Sales as the revenue proxy.
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Footer note ─────────────────────────────────────────────────────────
    st.markdown("""
    <div style="background:#1e1b4b;border-radius:12px;padding:20px 28px;margin-top:20px;color:#fff;">
        <div style="font-size:15px;font-weight:800;margin-bottom:8px;">📌 Important Assumptions</div>
        <ul style="font-size:13px;color:#c7d2fe;line-height:2;margin:0;padding-left:20px;">
            <li>Ad contribution ratio is capped at 90% — ads rarely drive 100% of revenue.</li>
            <li>ACOS efficiency decay of +4% relative per 10% spend increase is a conservative industry estimate. Your actual decay depends on category competitiveness.</li>
            <li>Secondary volume metrics (impressions, clicks, orders) scale linearly with spend — valid within ±50% of current spend. Beyond that, diminishing returns apply.</li>
            <li>CPC, CTR, and CVR are held constant in projections — they are driven by listing quality and bid strategy, not budget level.</li>
            <li>Event multipliers are based on Amazon category averages. Your specific category may vary.</li>
            <li>All projections are estimates. Actual results depend on competition, listing quality, seasonality, and Amazon algorithm changes.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
