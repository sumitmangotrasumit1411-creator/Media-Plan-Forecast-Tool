"""
pages/tab_copilot.py — AI Insights Copilot (Phase 5)

A rule-based intelligence layer that reads every metric available and generates:
  1. Account Narrative — a plain-English executive summary of the account state
  2. Priority Action Board — top 10 ranked actions with effort/impact scores
  3. Opportunity Finder — specific $$$ opportunities derived from the data
  4. Anomaly Detector — flags statistical outliers vs expected benchmarks
  5. Competitive Positioning signals derived from CTR, CVR, CPC benchmarks

No external API required — all outputs are computed deterministically from
the uploaded report data. The "AI" label refers to the structured intelligence
layer, not a large language model.
"""

from __future__ import annotations

from typing import Optional
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

from utils.formatters import fmt_currency, fmt_pct, fmt_num


# ─────────────────────────────────────────────────────────────────────────────
# Benchmark constants — Amazon category averages (2024)
# ─────────────────────────────────────────────────────────────────────────────

_BENCHMARKS = {
    "acos_excellent":  20.0,
    "acos_good":       25.0,
    "acos_acceptable": 35.0,
    "roas_excellent":  6.0,
    "roas_good":       4.0,
    "roas_acceptable": 2.0,
    "ctr_excellent":   0.5,
    "ctr_good":        0.35,
    "ctr_low":         0.2,
    "cvr_excellent":   12.0,
    "cvr_good":        7.0,
    "cvr_low":         3.0,
    "cpc_high":        3.0,
    "cpc_very_high":   5.0,
    "ntb_strong":      40.0,
    "tacos_healthy":   10.0,
    "tacos_warning":   18.0,
}


# ─────────────────────────────────────────────────────────────────────────────
# Account Narrative generator
# ─────────────────────────────────────────────────────────────────────────────

def _build_narrative(
    ads_metrics: dict,
    vendor_metrics: dict,
    scenarios: list,
    campaign_df: pd.DataFrame,
    health_df: Optional[pd.DataFrame],
) -> list[dict]:
    """
    Return a list of narrative paragraphs with keys:
      title, body, sentiment ('positive'|'warning'|'critical'|'neutral'), icon
    """
    parts = []
    spend   = ads_metrics.get("total_spend") or 0
    sales   = ads_metrics.get("total_ad_sales") or 0
    acos    = ads_metrics.get("overall_acos")
    roas    = ads_metrics.get("overall_roas")
    ctr     = ads_metrics.get("overall_ctr")
    cvr     = ads_metrics.get("conversion_rate")
    cpc     = ads_metrics.get("overall_cpc")
    ntb     = ads_metrics.get("ntb_order_pct")
    impr    = ads_metrics.get("total_impressions") or 0
    clicks  = ads_metrics.get("total_clicks") or 0
    orders  = ads_metrics.get("total_ad_orders") or 0
    rev     = (vendor_metrics or {}).get("total_ordered_revenue") or sales
    tacos   = round(spend / rev * 100, 2) if rev > 0 else None

    # ── Paragraph 1: Revenue & Spend summary ─────────────────────────────────
    if spend > 0 and rev > 0:
        if acos and acos <= _BENCHMARKS["acos_good"]:
            sentiment, icon = "positive", "🟢"
            verdict = f"highly efficient ACOS of {acos:.1f}%"
        elif acos and acos <= _BENCHMARKS["acos_acceptable"]:
            sentiment, icon = "neutral", "🟡"
            verdict = f"acceptable ACOS of {acos:.1f}%"
        else:
            sentiment, icon = "warning", "🔴"
            verdict = f"elevated ACOS of {acos:.1f}%" if acos else "ACOS data unavailable"

        parts.append({
            "title": "Revenue & Ad Spend Overview",
            "icon": icon,
            "sentiment": sentiment,
            "body": (
                f"Your account generated {fmt_currency(rev)} in total revenue against "
                f"{fmt_currency(spend)} in ad spend, delivering a {verdict}. "
                f"Ad-attributed sales of {fmt_currency(sales)} represent "
                f"{round(sales/rev*100,1) if rev > 0 else 0:.1f}% of total revenue. "
                + (f"TACOS sits at {tacos:.1f}%, "
                   + ("which is healthy (below 10%)." if tacos <= _BENCHMARKS["tacos_healthy"]
                      else "indicating significant ad dependency — consider boosting organic rank." if tacos <= _BENCHMARKS["tacos_warning"]
                      else "which is critically high — organic sales need to be rebuilt urgently.")
                   if tacos else "")
            ),
        })

    # ── Paragraph 2: Efficiency deep-dive ────────────────────────────────────
    if roas is not None:
        if roas >= _BENCHMARKS["roas_excellent"]:
            sentiment, icon = "positive", "⚡"
            roas_comment = f"exceptional ROAS of {roas:.2f}x — you are getting {roas:.1f}x return on every ad dollar"
        elif roas >= _BENCHMARKS["roas_good"]:
            sentiment, icon = "positive", "🟢"
            roas_comment = f"strong ROAS of {roas:.2f}x — above the 4x industry benchmark"
        elif roas >= _BENCHMARKS["roas_acceptable"]:
            sentiment, icon = "neutral", "🟡"
            roas_comment = f"adequate ROAS of {roas:.2f}x — between 2–4x, optimisation headroom exists"
        else:
            sentiment, icon = "critical", "🔴"
            roas_comment = f"low ROAS of {roas:.2f}x — below the 2x minimum viability threshold"

        cvr_comment = ""
        if cvr is not None:
            if cvr >= _BENCHMARKS["cvr_excellent"]:
                cvr_comment = f" CVR of {cvr:.1f}% is excellent — your listings convert well."
            elif cvr >= _BENCHMARKS["cvr_good"]:
                cvr_comment = f" CVR of {cvr:.1f}% is solid; room to improve via A+ content and review count."
            else:
                cvr_comment = f" CVR of {cvr:.1f}% is below average — listing images, reviews, and price competitiveness should be reviewed urgently."

        parts.append({
            "title": "Efficiency & Conversion Analysis",
            "icon": icon,
            "sentiment": sentiment,
            "body": f"Your account delivers {roas_comment}.{cvr_comment}"
                    + (f" CPC of {fmt_currency(cpc)} is "
                       + ("competitive." if cpc <= _BENCHMARKS["cpc_high"]
                          else "elevated — consider reducing bids on broad match terms." if cpc <= _BENCHMARKS["cpc_very_high"]
                          else "very high — significant bid waste detected. Audit match types immediately.")
                       if cpc else ""),
        })

    # ── Paragraph 3: Visibility & CTR ────────────────────────────────────────
    if impr > 0 and clicks > 0:
        if ctr is not None:
            if ctr >= _BENCHMARKS["ctr_excellent"]:
                ctr_sent, ctr_icon = "positive", "🟢"
                ctr_comment = f"strong CTR of {ctr:.2f}% (above 0.5% benchmark) — your ads attract clicks well"
            elif ctr >= _BENCHMARKS["ctr_good"]:
                ctr_sent, ctr_icon = "neutral", "🟡"
                ctr_comment = f"average CTR of {ctr:.2f}% — main image and title optimisation could improve this"
            else:
                ctr_sent, ctr_icon = "warning", "🔴"
                ctr_comment = f"low CTR of {ctr:.2f}% — main image, title, and badge eligibility need review"
        else:
            ctr_sent, ctr_icon = "neutral", "📊"
            ctr_comment = "CTR data unavailable"

        parts.append({
            "title": "Visibility & Click-Through",
            "icon": ctr_icon,
            "sentiment": ctr_sent,
            "body": (
                f"Your ads generated {fmt_num(impr)} impressions and {fmt_num(clicks)} clicks, "
                f"with a {ctr_comment}. "
                f"This resulted in {fmt_num(orders)} ad orders. "
                + (f"New-to-Brand orders represent {ntb:.0f}% of purchases — "
                   + ("strong customer acquisition engine." if ntb >= _BENCHMARKS["ntb_strong"]
                      else "moderate acquisition; focus on awareness campaigns to grow.")
                   if ntb else "")
            ),
        })

    # ── Paragraph 4: Growth opportunity ──────────────────────────────────────
    if scenarios:
        s10 = next((s for s in scenarios if s["growth_pct"] == 10), scenarios[0])
        incr  = s10["incremental_spend"]
        troas = s10.get("projected_roas") or 0
        parts.append({
            "title": "Growth Opportunity at +10%",
            "icon": "📈",
            "sentiment": "neutral",
            "body": (
                f"To achieve +{s10['growth_pct']:.0f}% revenue growth to {fmt_currency(s10['target_revenue'])}, "
                f"you need an incremental {fmt_currency(incr)} in ad spend "
                f"(total budget: {fmt_currency(s10['recommended_spend'])}). "
                f"Projected ROAS at this investment level: {troas:.2f}x. "
                f"Channel recommendation: prioritise Sponsored Products for conversion efficiency, "
                f"then layer Sponsored Brands video to build upper-funnel awareness."
            ),
        })

    # ── Paragraph 5: Portfolio health ────────────────────────────────────────
    if health_df is not None and not health_df.empty and "tier" in health_df.columns:
        tier_counts = health_df["tier"].value_counts()
        n_scale   = tier_counts.get("Scale", 0)
        n_pause   = tier_counts.get("Pause", 0)
        n_total   = len(health_df)
        waste_est = health_df[health_df["tier"] == "Pause"]["spend"].sum() if "spend" in health_df.columns else 0

        sentiment = "positive" if n_pause == 0 else "warning" if n_pause <= n_total * 0.2 else "critical"
        parts.append({
            "title": "Portfolio Health Summary",
            "icon": "🏅",
            "sentiment": sentiment,
            "body": (
                f"Your portfolio of {n_total} ASINs has {n_scale} in Scale tier (score ≥ 80) "
                f"and {n_pause} in Pause tier (score < 35). "
                + (f"The Pause-tier ASINs are consuming an estimated {fmt_currency(waste_est)} "
                   f"in ad spend with poor return — pausing them would free up budget for winners. "
                   if waste_est > 0 else "")
                + (f"Focus incremental investment on your {n_scale} Scale-tier ASINs first."
                   if n_scale > 0 else "Work on improving listing quality to move ASINs into the Scale tier.")
            ),
        })

    return parts


# ─────────────────────────────────────────────────────────────────────────────
# Priority Action Board generator
# ─────────────────────────────────────────────────────────────────────────────

def _build_actions(
    ads_metrics: dict,
    vendor_metrics: dict,
    health_df: Optional[pd.DataFrame],
    campaign_df: pd.DataFrame,
) -> list[dict]:
    """
    Return ranked list of action items. Each has:
      priority (1–10), title, detail, impact ('High'|'Medium'|'Low'),
      effort ('Quick Win'|'1–2 weeks'|'1+ month'), category, color
    """
    actions = []
    spend = ads_metrics.get("total_spend") or 0
    acos  = ads_metrics.get("overall_acos")
    roas  = ads_metrics.get("overall_roas")
    ctr   = ads_metrics.get("overall_ctr")
    cvr   = ads_metrics.get("conversion_rate")
    cpc   = ads_metrics.get("overall_cpc")
    ntb   = ads_metrics.get("ntb_order_pct")
    rev   = (vendor_metrics or {}).get("total_ordered_revenue") or ads_metrics.get("total_ad_sales") or 0
    tacos = round(spend / rev * 100, 2) if rev > 0 else None

    # ── Critical actions (ACOS / ROAS failures) ───────────────────────────────
    if acos and acos > _BENCHMARKS["acos_acceptable"]:
        actions.append({
            "priority": 1, "color": "#dc2626",
            "title": f"🚨 Reduce ACOS from {acos:.1f}% to below 35%",
            "detail": "Run a Negative Keyword Audit on all Broad and Phrase match campaigns. "
                      "Pause any search terms with >5 clicks and 0 conversions. "
                      "Move top 20 converting terms to exact match to isolate efficiency.",
            "impact": "High", "effort": "Quick Win", "category": "Efficiency",
        })
    if roas and roas < _BENCHMARKS["roas_acceptable"]:
        actions.append({
            "priority": 1, "color": "#dc2626",
            "title": f"🚨 Improve ROAS from {roas:.2f}x to minimum 2x",
            "detail": "ROAS below 2x means ads are not covering their cost of sales. "
                      "Immediately audit your 5 highest-spend, lowest-ROAS campaigns and reduce bids by 30%. "
                      "Review product pricing vs competitors.",
            "impact": "High", "effort": "Quick Win", "category": "Efficiency",
        })

    # ── CTR actions ──────────────────────────────────────────────────────────
    if ctr and ctr < _BENCHMARKS["ctr_low"]:
        actions.append({
            "priority": 2, "color": "#f97316",
            "title": f"📸 Improve main image CTR (currently {ctr:.2f}%)",
            "detail": "CTR below 0.2% indicates creative fatigue or weak main images. "
                      "A/B test lifestyle vs white-background images on your top 5 ASINs. "
                      "Ensure your title front-loads the most important keyword.",
            "impact": "High", "effort": "1–2 weeks", "category": "Creative",
        })
    elif ctr and ctr < _BENCHMARKS["ctr_good"]:
        actions.append({
            "priority": 4, "color": "#f59e0b",
            "title": f"🖼️ Optimise ad creatives to lift CTR above 0.35%",
            "detail": "Test Sponsored Brands video format — typically delivers 2–3x higher CTR than static. "
                      "Add 'Amazon Choice' or 'Best Seller' badge eligibility to top ASINs.",
            "impact": "Medium", "effort": "1–2 weeks", "category": "Creative",
        })

    # ── CVR actions ──────────────────────────────────────────────────────────
    if cvr and cvr < _BENCHMARKS["cvr_low"]:
        actions.append({
            "priority": 2, "color": "#f97316",
            "title": f"🔁 Fix low conversion rate ({cvr:.1f}%)",
            "detail": "CVR below 3% points to listing quality issues or price mis-alignment. "
                      "Priority fixes: (1) Get to 100+ reviews on hero ASINs, "
                      "(2) Add A+ Content with comparison module, "
                      "(3) Check your price vs competitors and offer a Subscribe & Save option.",
            "impact": "High", "effort": "1+ month", "category": "Listing",
        })

    # ── CPC actions ──────────────────────────────────────────────────────────
    if cpc and cpc > _BENCHMARKS["cpc_very_high"]:
        actions.append({
            "priority": 2, "color": "#f97316",
            "title": f"💲 Reduce CPC (currently {fmt_currency(cpc)}) — above $5 is unsustainable",
            "detail": "Very high CPC indicates bidding wars on generic keywords. "
                      "Shift 30% of budget from short-tail broad match to long-tail exact match terms. "
                      "Run a placement report and reduce bids on top-of-search placements where CVR is low.",
            "impact": "High", "effort": "Quick Win", "category": "Bidding",
        })
    elif cpc and cpc > _BENCHMARKS["cpc_high"]:
        actions.append({
            "priority": 5, "color": "#f59e0b",
            "title": f"💲 Reduce CPC from {fmt_currency(cpc)} — above $3 needs monitoring",
            "detail": "Review Sponsored Brands placements — they often inflate CPC. "
                      "Use Bid+ only on campaigns with ROAS > 4x.",
            "impact": "Medium", "effort": "Quick Win", "category": "Bidding",
        })

    # ── TACOS ────────────────────────────────────────────────────────────────
    if tacos and tacos > _BENCHMARKS["tacos_warning"]:
        actions.append({
            "priority": 3, "color": "#f97316",
            "title": f"📊 Reduce TACOS from {tacos:.1f}% — above 18% is unsustainable",
            "detail": "High TACOS means ads are funding a large share of all revenue. "
                      "Build organic rank by investing in Vine reviews, optimising backend keywords, "
                      "and running Lightning Deals to boost organic velocity.",
            "impact": "High", "effort": "1+ month", "category": "Strategy",
        })

    # ── Scale opportunities ──────────────────────────────────────────────────
    if acos and acos <= _BENCHMARKS["acos_excellent"] and spend > 0:
        actions.append({
            "priority": 3, "color": "#10b981",
            "title": f"🚀 Scale budget — ACOS {acos:.1f}% gives room to invest more",
            "detail": f"With ACOS below 20%, you have headroom to increase spend. "
                      f"Increase daily budgets by 20% on your top 10 performing campaigns. "
                      f"Expand to Sponsored Display retargeting for category conquesting.",
            "impact": "High", "effort": "Quick Win", "category": "Scale",
        })

    # ── NTB ─────────────────────────────────────────────────────────────────
    if ntb and ntb < 20:
        actions.append({
            "priority": 6, "color": "#6366f1",
            "title": f"🆕 Grow New-to-Brand orders (only {ntb:.0f}% NTB)",
            "detail": "Low NTB% means you are primarily re-selling to existing customers. "
                      "Invest in Sponsored Brands top-of-search placements and Sponsored Display "
                      "audience targeting (in-market, lifestyle) to reach new shoppers.",
            "impact": "Medium", "effort": "1–2 weeks", "category": "Acquisition",
        })
    elif ntb and ntb >= _BENCHMARKS["ntb_strong"]:
        actions.append({
            "priority": 7, "color": "#10b981",
            "title": f"🆕 Leverage strong NTB rate ({ntb:.0f}%) — build repeat purchase",
            "detail": "High NTB means you are acquiring new customers. Protect lifetime value: "
                      "run Subscribe & Save, set up post-purchase email sequences, "
                      "and launch a loyalty promotion to convert first-time buyers.",
            "impact": "Medium", "effort": "1–2 weeks", "category": "Retention",
        })

    # ── Pause tier ASINs ─────────────────────────────────────────────────────
    if health_df is not None and not health_df.empty and "tier" in health_df.columns:
        n_pause = (health_df["tier"] == "Pause").sum()
        waste   = health_df[health_df["tier"] == "Pause"]["spend"].sum() if "spend" in health_df.columns else 0
        if n_pause > 0 and waste > 500:
            actions.append({
                "priority": 2, "color": "#dc2626",
                "title": f"⏸️ Pause {n_pause} low-score ASINs — recover {fmt_currency(waste)}",
                "detail": f"{n_pause} ASINs have health scores below 35 and are consuming "
                          f"{fmt_currency(waste)} in spend with poor return. "
                          f"Pause their campaigns for 14 days. Fix listings (reviews, images, price). "
                          f"Reallocate saved budget to Scale-tier ASINs.",
                "impact": "High", "effort": "Quick Win", "category": "Portfolio",
            })

    # ── Campaign budget cap risk ─────────────────────────────────────────────
    if campaign_df is not None and not campaign_df.empty and "spend" in campaign_df.columns:
        top_spend = campaign_df["spend"].nlargest(5).sum()
        total_spend_df = campaign_df["spend"].sum()
        if total_spend_df > 0 and top_spend / total_spend_df > 0.7:
            actions.append({
                "priority": 5, "color": "#f59e0b",
                "title": "⚠️ Budget concentration risk — top 5 campaigns hold >70% of spend",
                "detail": "Heavy concentration in a few campaigns creates fragility. "
                          "If one campaign underperforms, overall efficiency drops sharply. "
                          "Diversify by activating mid-tier campaigns and testing new match type combos.",
                "impact": "Medium", "effort": "1–2 weeks", "category": "Risk",
            })

    # Always add: harvest + exact match
    actions.append({
        "priority": 8, "color": "#4f46e5",
        "title": "🔍 Run Search Term Harvest — move winners to Exact Match",
        "detail": "Weekly: export the Search Term Report, identify terms with ≥5 orders and ACOS < target. "
                  "Add them as exact match keywords in a new campaign with a 20% higher bid. "
                  "Negate them from the broad/phrase source campaign to prevent internal competition.",
        "impact": "High", "effort": "Quick Win", "category": "Optimisation",
    })

    actions.append({
        "priority": 9, "color": "#4f46e5",
        "title": "📅 Pre-load budget 3 weeks before Prime Day & Black Friday",
        "detail": "Amazon's algorithm rewards campaigns with spend history leading into peak events. "
                  "Increase daily budgets by 15–20% starting 3 weeks before the event, then spike "
                  "by the full event multiplier (Prime Day: +30%, Black Friday: +45%) on the day.",
        "impact": "High", "effort": "1–2 weeks", "category": "Seasonal",
    })

    # Sort by priority, deduplicate, return top 10
    actions.sort(key=lambda a: a["priority"])
    return actions[:10]


# ─────────────────────────────────────────────────────────────────────────────
# Opportunity Finder
# ─────────────────────────────────────────────────────────────────────────────

def _find_opportunities(
    ads_metrics: dict,
    vendor_metrics: dict,
    scenarios: list,
    health_df: Optional[pd.DataFrame],
) -> list[dict]:
    """Return list of specific $$$ opportunity cards."""
    ops = []
    spend = ads_metrics.get("total_spend") or 0
    roas  = ads_metrics.get("overall_roas") or 0
    acos  = ads_metrics.get("overall_acos")
    rev   = (vendor_metrics or {}).get("total_ordered_revenue") or ads_metrics.get("total_ad_sales") or 0

    # Opportunity 1: Wasted spend on zero-conversion terms
    wasted_est = ads_metrics.get("total_spend", 0) * 0.12  # typical ~12% wasted on no-conversion terms
    if wasted_est > 500:
        ops.append({
            "title": "💸 Recover Wasted Spend",
            "amount": round(wasted_est, 0),
            "detail": f"Industry average: ~12% of ad spend goes to search terms with zero conversions. "
                      f"Based on your spend of {fmt_currency(spend)}, estimated recoverable waste is "
                      f"{fmt_currency(wasted_est)}. Run the Search Term Report and add negatives weekly.",
            "color": "#dc2626",
            "type": "Save",
        })

    # Opportunity 2: Scale budget on Scale-tier ASINs
    if health_df is not None and not health_df.empty and "tier" in health_df.columns:
        scale_asins = health_df[health_df["tier"] == "Scale"]
        if not scale_asins.empty and "spend" in scale_asins.columns:
            scale_spend = scale_asins["spend"].sum()
            incremental = scale_spend * 0.25  # 25% more on winners
            projected_sales = incremental * roas if roas > 0 else incremental * 3
            if incremental > 200:
                ops.append({
                    "title": f"🚀 Scale {len(scale_asins)} Winner ASINs by 25%",
                    "amount": round(projected_sales, 0),
                    "detail": f"Adding {fmt_currency(incremental)} to your {len(scale_asins)} Scale-tier ASINs "
                              f"(current spend: {fmt_currency(scale_spend)}) at current ROAS of {roas:.2f}x "
                              f"could generate an additional {fmt_currency(projected_sales)} in ad sales.",
                    "color": "#10b981",
                    "type": "Grow",
                })

    # Opportunity 3: Pause Tier → reallocate
    if health_df is not None and not health_df.empty and "tier" in health_df.columns:
        pause_spend = health_df[health_df["tier"] == "Pause"]["spend"].sum() if "spend" in health_df.columns else 0
        if pause_spend > 500 and roas > 0:
            reallocated_sales = pause_spend * roas
            ops.append({
                "title": "♻️ Reallocate Pause-Tier Budget to Winners",
                "amount": round(reallocated_sales - pause_spend, 0),
                "detail": f"Moving {fmt_currency(pause_spend)} from Pause-tier ASINs to Scale-tier ASINs "
                          f"at the current ROAS of {roas:.2f}x would generate {fmt_currency(reallocated_sales)} "
                          f"in sales vs near-zero return currently.",
                "color": "#4f46e5",
                "type": "Optimise",
            })

    # Opportunity 4: Scenario-based growth
    if scenarios:
        s10 = next((s for s in scenarios if s["growth_pct"] == 10), scenarios[0])
        gap = s10["revenue_gap"]
        if gap > 0:
            ops.append({
                "title": f"📈 +{s10['growth_pct']:.0f}% Revenue Growth = {fmt_currency(gap)} more revenue",
                "amount": round(gap, 0),
                "detail": f"Achieving +{s10['growth_pct']:.0f}% growth requires {fmt_currency(s10['incremental_spend'])} "
                          f"additional ad investment. ROI on the incremental spend: "
                          f"{round(gap / s10['incremental_spend'], 1) if s10['incremental_spend'] > 0 else 0:.1f}x.",
                "color": "#f97316",
                "type": "Grow",
            })

    # Opportunity 5: SB Video (if CTR low)
    ctr = ads_metrics.get("overall_ctr")
    if ctr and ctr < _BENCHMARKS["ctr_good"]:
        sb_spend = spend * 0.25  # typical SB% of budget
        video_upside = sb_spend * 0.30  # ~30% more sales from video vs static
        if video_upside > 1000:
            ops.append({
                "title": "🎥 Activate Sponsored Brands Video",
                "amount": round(video_upside, 0),
                "detail": f"SB Video achieves 2–3x higher CTR vs static SB ads. "
                          f"Based on your estimated SB spend of {fmt_currency(sb_spend)}, "
                          f"switching to video format could unlock ~{fmt_currency(video_upside)} in incremental sales.",
                "color": "#6366f1",
                "type": "Grow",
            })

    return ops


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly Detector
# ─────────────────────────────────────────────────────────────────────────────

def _detect_anomalies(
    ads_metrics: dict,
    campaign_df: pd.DataFrame,
) -> list[dict]:
    """Flag statistical outliers vs benchmarks."""
    anomalies = []
    acos = ads_metrics.get("overall_acos")
    roas = ads_metrics.get("overall_roas")
    ctr  = ads_metrics.get("overall_ctr")
    cvr  = ads_metrics.get("conversion_rate")
    cpc  = ads_metrics.get("overall_cpc")

    # Metric anomalies
    checks = [
        (acos, ">", _BENCHMARKS["acos_acceptable"], "ACOS",
         f"ACOS of {acos:.1f}% exceeds the 35% acceptable ceiling" if acos else "", "critical"),
        (acos, "<", 5.0, "ACOS",
         f"ACOS of {acos:.1f}% is unusually low — verify report date range completeness" if acos else "", "warning"),
        (roas, "<", _BENCHMARKS["roas_acceptable"], "ROAS",
         f"ROAS of {roas:.2f}x is below 2x minimum viability" if roas else "", "critical"),
        (roas, ">", 20.0, "ROAS",
         f"ROAS of {roas:.2f}x is unusually high — check if all spend is being captured" if roas else "", "warning"),
        (ctr, "<", 0.1, "CTR",
         f"CTR of {ctr:.2f}% is extremely low — ad creative or targeting may be misaligned" if ctr else "", "critical"),
        (cvr, "<", 1.0, "CVR",
         f"CVR of {cvr:.1f}% is critically low — listing health issues blocking conversion" if cvr else "", "critical"),
        (cpc, ">", _BENCHMARKS["cpc_very_high"], "CPC",
         f"CPC of {fmt_currency(cpc)} is very high — bid waste likely" if cpc else "", "warning"),
    ]

    for metric_val, op, threshold, metric_name, msg, severity in checks:
        if metric_val is None or not msg:
            continue
        triggered = (op == ">" and metric_val > threshold) or (op == "<" and metric_val < threshold)
        if triggered:
            anomalies.append({
                "metric": metric_name,
                "message": msg,
                "severity": severity,
                "color": "#dc2626" if severity == "critical" else "#f97316",
                "icon":  "🚨" if severity == "critical" else "⚠️",
            })

    # Campaign-level outliers
    if campaign_df is not None and not campaign_df.empty:
        if "acos_%" in campaign_df.columns and "spend" in campaign_df.columns:
            high_acos = campaign_df[
                (campaign_df["acos_%"].fillna(0) > 80) &
                (campaign_df["spend"].fillna(0) > 100)
            ]
            if not high_acos.empty:
                anomalies.append({
                    "metric": "Campaign ACOS",
                    "message": f"{len(high_acos)} campaigns have ACOS > 80% with meaningful spend — "
                               f"immediate review required",
                    "severity": "critical",
                    "color": "#dc2626",
                    "icon": "🚨",
                })

        if "roas" in campaign_df.columns and "spend" in campaign_df.columns:
            zero_roas = campaign_df[
                (campaign_df["roas"].fillna(0) == 0) &
                (campaign_df["spend"].fillna(0) > 50)
            ]
            if not zero_roas.empty:
                anomalies.append({
                    "metric": "Zero ROAS Campaigns",
                    "message": f"{len(zero_roas)} campaigns have ZERO attributed sales despite meaningful spend",
                    "severity": "critical",
                    "color": "#dc2626",
                    "icon": "🚨",
                })

    if not anomalies:
        anomalies.append({
            "metric": "All Clear",
            "message": "No critical anomalies detected. Account metrics are within acceptable ranges.",
            "severity": "ok",
            "color": "#10b981",
            "icon": "✅",
        })

    return anomalies


# ─────────────────────────────────────────────────────────────────────────────
# Main render
# ─────────────────────────────────────────────────────────────────────────────

def render_copilot_tab(
    ads_metrics: dict,
    vendor_metrics: dict,
    scenarios: list,
    campaign_df: pd.DataFrame,
    health_df: Optional[pd.DataFrame],
) -> None:
    """Render the AI Insights Copilot tab — Phase 5."""

    st.markdown("""
    <div class="callout-banner">
        <strong>🤖 AI Insights Copilot</strong> — an intelligence layer that reads every metric in your
        account and generates a structured executive narrative, ranked action board, dollar-quantified
        opportunities, and anomaly alerts. All outputs are derived directly from your data.
    </div>
    """, unsafe_allow_html=True)

    # Build all intelligence
    narrative  = _build_narrative(ads_metrics, vendor_metrics, scenarios, campaign_df, health_df)
    actions    = _build_actions(ads_metrics, vendor_metrics, health_df, campaign_df)
    opps       = _find_opportunities(ads_metrics, vendor_metrics, scenarios, health_df)
    anomalies  = _detect_anomalies(ads_metrics, campaign_df)

    cop_tab1, cop_tab2, cop_tab3, cop_tab4 = st.tabs([
        "📝 Account Narrative",
        "🎯 Priority Action Board",
        "💰 Opportunity Finder",
        "🔍 Anomaly Detector",
    ])

    # ═══════════════════════════════════════════════════════════════════════
    # Panel 1: Account Narrative
    # ═══════════════════════════════════════════════════════════════════════
    with cop_tab1:
        st.markdown('<div class="section-header">📝 Executive Account Narrative</div>',
                    unsafe_allow_html=True)
        st.markdown("""
        <div style="background:#f8f7ff;border-radius:10px;padding:12px 18px;
                    border-left:4px solid #4f46e5;margin-bottom:20px;font-size:13px;color:#4338ca;">
            This narrative is auto-generated from your report data. Share it with stakeholders
            as a starting point for strategic discussion.
        </div>
        """, unsafe_allow_html=True)

        if not narrative:
            st.info("Upload reports to generate the account narrative.")
        else:
            _sent_bg = {
                "positive": ("#f0fdf4", "#16a34a", "#dcfce7"),
                "warning":  ("#fff7ed", "#c2410c", "#ffedd5"),
                "critical": ("#fef2f2", "#b91c1c", "#fee2e2"),
                "neutral":  ("#f8f9ff", "#4338ca", "#ede9fe"),
            }
            for part in narrative:
                bg, color, badge_bg = _sent_bg.get(part["sentiment"], _sent_bg["neutral"])
                st.markdown(f"""
                <div style="background:{bg};border-radius:12px;padding:18px 22px;
                            margin-bottom:14px;border:1px solid {badge_bg};">
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                        <span style="font-size:18px;">{part['icon']}</span>
                        <span style="font-size:15px;font-weight:800;color:{color};">
                            {part['title']}</span>
                    </div>
                    <p style="font-size:14px;color:#374151;line-height:1.8;margin:0;">
                        {part['body']}
                    </p>
                </div>
                """, unsafe_allow_html=True)

        # ── Benchmark comparison radar ───────────────────────────────────────
        acos_v = ads_metrics.get("overall_acos") or 0
        roas_v = ads_metrics.get("overall_roas") or 0
        ctr_v  = ads_metrics.get("overall_ctr")  or 0
        cvr_v  = ads_metrics.get("conversion_rate") or 0
        cpc_v  = ads_metrics.get("overall_cpc")  or 0

        # Normalise each metric to 0–100 score relative to benchmark
        def _norm(val, low, high, invert=False):
            if high == low:
                return 50.0
            s = (val - low) / (high - low) * 100
            s = max(0, min(100, s))
            return 100 - s if invert else s

        your_scores = [
            _norm(acos_v, 0, 60, invert=True),      # ACOS — lower better
            _norm(roas_v, 0, 8),                     # ROAS — higher better
            _norm(ctr_v,  0, 1.0),                   # CTR  — higher better
            _norm(cvr_v,  0, 20),                    # CVR  — higher better
            _norm(max(0, 6 - (cpc_v or 0)), 0, 6),  # CPC  — lower better
        ]
        bench_scores = [
            _norm(25, 0, 60, invert=True),
            _norm(4,  0, 8),
            _norm(0.5, 0, 1.0),
            _norm(7,  0, 20),
            _norm(3,  0, 6),
        ]
        categories = ["ACOS efficiency", "ROAS", "CTR", "CVR", "CPC efficiency"]

        st.markdown('<div class="section-header">📡 Your Account vs Industry Benchmarks</div>',
                    unsafe_allow_html=True)

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=bench_scores + [bench_scores[0]],
            theta=categories + [categories[0]],
            fill="toself", name="Industry Benchmark",
            line=dict(color="#9ca3af", width=2),
            fillcolor="rgba(156,163,175,0.15)",
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=your_scores + [your_scores[0]],
            theta=categories + [categories[0]],
            fill="toself", name="Your Account",
            line=dict(color="#4f46e5", width=2),
            fillcolor="rgba(79,70,229,0.2)",
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=True,
            height=380,
            margin=dict(t=40, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════
    # Panel 2: Priority Action Board
    # ═══════════════════════════════════════════════════════════════════════
    with cop_tab2:
        st.markdown('<div class="section-header">🎯 Top Priority Actions</div>',
                    unsafe_allow_html=True)
        st.markdown("""
        <div class="callout-banner">
            Ranked by business impact and urgency. <strong>Quick Wins</strong> can be done today
            in the Ads Console. Longer-horizon items require listing or creative work.
        </div>
        """, unsafe_allow_html=True)

        if not actions:
            st.info("No specific actions generated — upload reports to enable the action board.")
        else:
            _impact_badge = {
                "High":   ("background:#fee2e2;color:#b91c1c", "High Impact"),
                "Medium": ("background:#fef3c7;color:#92400e", "Medium Impact"),
                "Low":    ("background:#f0fdf4;color:#166534", "Low Impact"),
            }
            _effort_badge = {
                "Quick Win":   ("background:#dcfce7;color:#15803d", "⚡ Quick Win"),
                "1–2 weeks":   ("background:#eff6ff;color:#1d4ed8", "📅 1–2 weeks"),
                "1+ month":    ("background:#f5f3ff;color:#6d28d9", "🗓️ 1+ month"),
            }

            for i, action in enumerate(actions, 1):
                imp_style, imp_label = _impact_badge.get(action["impact"], ("", action["impact"]))
                eff_style, eff_label = _effort_badge.get(action["effort"], ("", action["effort"]))
                st.markdown(f"""
                <div style="background:#ffffff;border-radius:12px;padding:16px 20px;
                            margin-bottom:10px;border-left:5px solid {action['color']};
                            box-shadow:0 2px 8px rgba(0,0,0,0.06);">
                    <div style="display:flex;align-items:flex-start;justify-content:space-between;
                                margin-bottom:8px;gap:10px;">
                        <div style="display:flex;align-items:center;gap:10px;">
                            <div style="min-width:28px;height:28px;background:{action['color']};
                                        border-radius:50%;display:flex;align-items:center;
                                        justify-content:center;font-size:13px;font-weight:900;
                                        color:#fff;flex-shrink:0;">{i}</div>
                            <span style="font-size:14px;font-weight:800;color:#1e1b4b;">
                                {action['title']}</span>
                        </div>
                        <div style="display:flex;gap:6px;flex-shrink:0;">
                            <span style="font-size:11px;font-weight:700;padding:3px 10px;
                                         border-radius:20px;{imp_style}">{imp_label}</span>
                            <span style="font-size:11px;font-weight:700;padding:3px 10px;
                                         border-radius:20px;{eff_style}">{eff_label}</span>
                            <span style="font-size:11px;font-weight:700;padding:3px 10px;
                                         border-radius:20px;background:#f0f2ff;color:#4f46e5;">
                                {action['category']}</span>
                        </div>
                    </div>
                    <p style="font-size:13px;color:#374151;line-height:1.7;margin:0;padding-left:38px;">
                        {action['detail']}
                    </p>
                </div>
                """, unsafe_allow_html=True)

        # ── Impact vs Effort matrix ──────────────────────────────────────────
        if actions:
            st.markdown('<div class="section-header">🗺️ Impact vs Effort Matrix</div>',
                        unsafe_allow_html=True)
            _effort_x = {"Quick Win": 1, "1–2 weeks": 2, "1+ month": 3}
            _impact_y = {"High": 3, "Medium": 2, "Low": 1}
            fig_matrix = go.Figure()
            for action in actions:
                x = _effort_x.get(action["effort"], 2)
                y = _impact_y.get(action["impact"], 2)
                fig_matrix.add_trace(go.Scatter(
                    x=[x], y=[y],
                    mode="markers+text",
                    marker=dict(size=18, color=action["color"], opacity=0.85),
                    text=[action["title"][:22] + "…" if len(action["title"]) > 22 else action["title"]],
                    textposition="top center",
                    textfont=dict(size=10, color="#374151"),
                    name=action["title"][:30],
                    showlegend=False,
                ))
            fig_matrix.update_layout(
                height=380,
                xaxis=dict(title="Effort Required", tickvals=[1, 2, 3],
                           ticktext=["Quick Win", "1–2 weeks", "1+ month"],
                           range=[0.5, 3.5]),
                yaxis=dict(title="Business Impact", tickvals=[1, 2, 3],
                           ticktext=["Low", "Medium", "High"],
                           range=[0.5, 3.5]),
                margin=dict(t=30, b=40, l=60, r=20),
                shapes=[
                    dict(type="rect", x0=0.5, x1=1.5, y0=2.5, y1=3.5,
                         fillcolor="rgba(16,185,129,0.07)", line_width=0),
                ],
                annotations=[dict(x=1, y=3.3, text="⚡ Do First", showarrow=False,
                                  font=dict(size=10, color="#10b981"))],
            )
            st.plotly_chart(fig_matrix, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════
    # Panel 3: Opportunity Finder
    # ═══════════════════════════════════════════════════════════════════════
    with cop_tab3:
        st.markdown('<div class="section-header">💰 Dollar-Quantified Opportunities</div>',
                    unsafe_allow_html=True)
        st.markdown("""
        <div class="callout-banner">
            Each opportunity is estimated from your actual data. Figures are indicative —
            actual results depend on execution quality and market conditions.
        </div>
        """, unsafe_allow_html=True)

        if not opps:
            st.info("Upload reports to discover quantified opportunities.")
        else:
            total_opp = sum(o["amount"] for o in opps if o["type"] == "Grow")
            total_save = sum(o["amount"] for o in opps if o["type"] == "Save")

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Growth Opportunities", fmt_currency(total_opp),
                      "estimated incremental revenue/sales")
            c2.metric("Total Savings Opportunities", fmt_currency(total_save),
                      "estimated recoverable ad waste")
            c3.metric("Total Opportunities Found", str(len(opps)))

            st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

            _type_styles = {
                "Grow":     ("#10b981", "#f0fdf4", "📈"),
                "Save":     ("#dc2626", "#fef2f2", "💸"),
                "Optimise": ("#4f46e5", "#f0f2ff", "⚙️"),
            }
            for opp in opps:
                color, bg, icon = _type_styles.get(opp["type"], ("#6b7280", "#f9fafb", "📌"))
                st.markdown(f"""
                <div style="background:{bg};border-radius:12px;padding:18px 22px;
                            margin-bottom:12px;border:1px solid {color}22;
                            border-left:5px solid {color};">
                    <div style="display:flex;justify-content:space-between;align-items:center;
                                margin-bottom:8px;">
                        <span style="font-size:15px;font-weight:800;color:{color};">
                            {icon} {opp['title']}</span>
                        <div style="text-align:right;">
                            <div style="font-size:22px;font-weight:900;color:{color};">
                                {fmt_currency(opp['amount'])}</div>
                            <div style="font-size:11px;color:#9ca3af;font-weight:600;">
                                {opp['type']} opportunity</div>
                        </div>
                    </div>
                    <p style="font-size:13px;color:#374151;line-height:1.7;margin:0;">
                        {opp['detail']}
                    </p>
                </div>
                """, unsafe_allow_html=True)

            # Opportunity bar chart
            fig_opp = go.Figure(go.Bar(
                x=[o["title"][:28] + "…" if len(o["title"]) > 28 else o["title"]
                   for o in opps],
                y=[o["amount"] for o in opps],
                marker_color=[_type_styles.get(o["type"], ("#6b7280",)*3)[0] for o in opps],
                text=[fmt_currency(o["amount"]) for o in opps],
                textposition="outside",
            ))
            fig_opp.update_layout(
                title="Opportunity Size by Category",
                yaxis_title="Estimated Value ($)", yaxis_tickprefix="$",
                height=380, margin=dict(t=60, b=80, l=40, r=20),
                xaxis_tickangle=-20,
            )
            st.plotly_chart(fig_opp, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════
    # Panel 4: Anomaly Detector
    # ═══════════════════════════════════════════════════════════════════════
    with cop_tab4:
        st.markdown('<div class="section-header">🔍 Anomaly & Health Check</div>',
                    unsafe_allow_html=True)
        st.markdown("""
        <div class="callout-banner">
            Automatically flags metrics and campaigns that deviate significantly from
            industry benchmarks or expected ranges.
        </div>
        """, unsafe_allow_html=True)

        critical_count = sum(1 for a in anomalies if a["severity"] == "critical")
        warning_count  = sum(1 for a in anomalies if a["severity"] == "warning")

        a1, a2, a3 = st.columns(3)
        a1.metric("🚨 Critical", critical_count,
                  "Require immediate action" if critical_count else "None — great!")
        a2.metric("⚠️ Warnings", warning_count,
                  "Monitor closely" if warning_count else "None — great!")
        a3.metric("✅ Status",
                  "Action Required" if critical_count else "Healthy" if not warning_count else "Monitor",
                  delta=None)

        st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

        for anom in anomalies:
            if anom["severity"] == "ok":
                st.markdown(f"""
                <div class="success-card">
                    {anom['icon']} <strong>{anom['metric']}:</strong> {anom['message']}
                </div>
                """, unsafe_allow_html=True)
            elif anom["severity"] == "critical":
                st.markdown(f"""
                <div style="background:#fef2f2;border-left:5px solid #dc2626;
                            border-radius:0 10px 10px 0;padding:14px 18px;margin-bottom:8px;">
                    <strong style="color:#dc2626;">{anom['icon']} CRITICAL — {anom['metric']}:</strong>
                    <span style="font-size:13px;color:#374151;"> {anom['message']}</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="warning-card" style="margin-bottom:8px;">
                    <strong>{anom['icon']} WARNING — {anom['metric']}:</strong>
                    <span style="font-size:13px;"> {anom['message']}</span>
                </div>
                """, unsafe_allow_html=True)

        # ── KPI scorecard vs benchmarks ──────────────────────────────────────
        st.markdown('<div class="section-header">📊 KPI Scorecard vs Amazon Benchmarks</div>',
                    unsafe_allow_html=True)

        score_rows = [
            ("ACOS (%)",      ads_metrics.get("overall_acos"),
             _BENCHMARKS["acos_good"],    False, "< {t:.0f}% target"),
            ("ROAS",          ads_metrics.get("overall_roas"),
             _BENCHMARKS["roas_good"],    True,  "> {t:.1f}x target"),
            ("CTR (%)",       ads_metrics.get("overall_ctr"),
             _BENCHMARKS["ctr_good"],     True,  "> {t:.2f}% target"),
            ("CVR (%)",       ads_metrics.get("conversion_rate"),
             _BENCHMARKS["cvr_good"],     True,  "> {t:.1f}% target"),
            ("CPC ($)",       ads_metrics.get("overall_cpc"),
             _BENCHMARKS["cpc_high"],     False, "< {t:.2f} target"),
        ]

        sc_data = []
        for name, val, benchmark, higher_better, tgt_label in score_rows:
            if val is None:
                continue
            tgt_str = tgt_label.format(t=benchmark)
            if higher_better:
                status = "✅ On Target" if val >= benchmark else "🔴 Below Target"
                vs = f"+{val - benchmark:.2f}" if val >= benchmark else f"{val - benchmark:.2f}"
            else:
                status = "✅ On Target" if val <= benchmark else "🔴 Above Target"
                vs = f"{val - benchmark:.2f}"
            sc_data.append({
                "Metric": name,
                "Your Value": round(val, 2),
                "Benchmark": benchmark,
                "Target": tgt_str,
                "vs Benchmark": vs,
                "Status": status,
            })

        if sc_data:
            sc_df = pd.DataFrame(sc_data)

            def _score_style(row):
                if "✅" in str(row.get("Status", "")):
                    return ["background-color:#f0fdf4"] * len(row)
                return ["background-color:#fef2f2"] * len(row)

            st.dataframe(
                sc_df.style.apply(_score_style, axis=1),
                use_container_width=True, height=240,
            )
