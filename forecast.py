"""
forecast.py — Scenario-based media plan forecasting engine.

Given baseline metrics, computes recommended ad spend, budget allocation,
expected ACOS/ROAS, and channel-level investment for growth scenarios.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional


# ---------------------------------------------------------------------------
# Constants — industry benchmarks / allocation heuristics
# ---------------------------------------------------------------------------

# Default channel split for Sponsored Products / Brands / Display
DEFAULT_CHANNEL_SPLIT = {
    "Sponsored Products": 0.65,
    "Sponsored Brands": 0.25,
    "Sponsored Display": 0.10,
}

# Efficiency curve: as spend increases, ACOS typically rises
# These multipliers represent expected ACOS degradation per 10% spend increase
ACOS_EFFICIENCY_DECAY = 0.04  # +4% relative ACOS per 10% spend increase


# ---------------------------------------------------------------------------
# Core Forecast Engine
# ---------------------------------------------------------------------------

def run_forecast(
    total_ordered_revenue: float,
    total_ad_spend: float,
    total_ad_sales: float,
    growth_pct: float,
    custom_channel_split: Optional[dict] = None,
    target_acos_override: Optional[float] = None,
    campaign_df: Optional[pd.DataFrame] = None,
    # Custom target overrides — any one of these pins that metric directly
    override_target_revenue: Optional[float] = None,
    override_ad_spend: Optional[float] = None,
    override_ad_sales: Optional[float] = None,
    override_roas: Optional[float] = None,
    override_tacos: Optional[float] = None,
) -> dict:
    """
    Generate a media plan forecast for a given growth target.

    Custom overrides (override_*) take priority over growth_pct math.
    Resolution order when multiple overrides supplied:
      1. override_target_revenue  — sets target revenue directly
      2. override_ad_sales        — pins target ad-attributed sales
      3. override_roas            — derives spend from ad sales / roas
      4. override_tacos           — derives spend from revenue * tacos%
      5. override_ad_spend        — pins recommended spend directly
    Any metric not pinned is derived from the others.
    """
    channel_split = custom_channel_split or DEFAULT_CHANNEL_SPLIT

    # ---- Baseline metrics ------------------------------------------------
    baseline_revenue = total_ordered_revenue if total_ordered_revenue > 0 else total_ad_sales
    current_acos  = (total_ad_spend / total_ad_sales * 100) if total_ad_sales > 0 else None
    current_tacos = (total_ad_spend / baseline_revenue * 100) if baseline_revenue > 0 else None
    current_roas  = (total_ad_sales / total_ad_spend) if total_ad_spend > 0 else None

    # ---- Step 1: resolve target_revenue ----------------------------------
    if override_target_revenue and override_target_revenue > 0:
        target_revenue = override_target_revenue
        growth_pct = round((target_revenue / baseline_revenue - 1) * 100, 2) if baseline_revenue > 0 else growth_pct
    else:
        target_revenue = baseline_revenue * (1 + growth_pct / 100)

    revenue_gap = target_revenue - baseline_revenue

    # ---- Step 2: resolve target_ad_sales ---------------------------------
    if override_ad_sales and override_ad_sales > 0:
        target_ad_sales = override_ad_sales
    else:
        if baseline_revenue > 0 and total_ad_sales > 0:
            ad_contribution_ratio = min(total_ad_sales / baseline_revenue, 0.90)
        else:
            ad_contribution_ratio = 0.40
        incremental_ad_sales_needed = revenue_gap * ad_contribution_ratio
        target_ad_sales = total_ad_sales + incremental_ad_sales_needed

    # ---- Step 3: resolve recommended_spend --------------------------------
    if override_ad_spend and override_ad_spend > 0:
        recommended_spend = override_ad_spend
    elif override_roas and override_roas > 0:
        # spend = ad_sales / ROAS
        recommended_spend = target_ad_sales / override_roas
    elif override_tacos and override_tacos > 0:
        # spend = revenue * TACOS%
        recommended_spend = target_revenue * (override_tacos / 100)
    else:
        spend_multiplier = 1 + (growth_pct / 10) * ACOS_EFFICIENCY_DECAY
        effective_acos = (current_acos or 20.0) * spend_multiplier
        if target_acos_override:
            effective_acos = target_acos_override
        recommended_spend = target_ad_sales * (effective_acos / 100)

    # ---- Derived metrics -------------------------------------------------
    incremental_spend = recommended_spend - total_ad_spend
    effective_acos = (recommended_spend / target_ad_sales * 100) if target_ad_sales > 0 else 0
    projected_roas = round(target_ad_sales / recommended_spend, 2) if recommended_spend > 0 else None
    projected_tacos = round(recommended_spend / target_revenue * 100, 2) if target_revenue > 0 else None

    # ---- Channel allocation ----------------------------------------------
    channel_allocation = {
        ch: {
            "budget": round(recommended_spend * weight, 2),
            "incremental_budget": round(incremental_spend * weight, 2),
            "share_pct": round(weight * 100, 1),
        }
        for ch, weight in channel_split.items()
    }

    # ---- Top campaign recommendations ------------------------------------
    campaign_recommendations = []
    if campaign_df is not None and not campaign_df.empty:
        campaign_recommendations = _recommend_campaigns(
            campaign_df, incremental_spend, growth_pct
        )

    return {
        # Baseline
        "baseline_revenue":   round(baseline_revenue, 2),
        "current_ad_spend":   round(total_ad_spend, 2),
        "current_ad_sales":   round(total_ad_sales, 2),
        "current_acos_pct":   round(current_acos, 2) if current_acos else None,
        "current_tacos_pct":  round(current_tacos, 2) if current_tacos else None,
        "current_roas":       round(current_roas, 2) if current_roas else None,
        # Targets
        "growth_pct":         growth_pct,
        "target_revenue":     round(target_revenue, 2),
        "revenue_gap":        round(revenue_gap, 2),
        "target_ad_sales":    round(target_ad_sales, 2),
        "recommended_spend":  round(recommended_spend, 2),
        "incremental_spend":  round(incremental_spend, 2),
        "projected_acos_pct": round(effective_acos, 2),
        "projected_roas":     projected_roas,
        "projected_tacos_pct": projected_tacos,
        # Allocation
        "channel_allocation":        channel_allocation,
        "campaign_recommendations":  campaign_recommendations,
        # Track which overrides were used (for UI labelling)
        "is_custom_scenario": any([
            override_target_revenue, override_ad_spend,
            override_ad_sales, override_roas, override_tacos,
        ]),
    }


def run_multi_scenario(
    total_ordered_revenue: float,
    total_ad_spend: float,
    total_ad_sales: float,
    growth_scenarios: list,
    custom_channel_split: Optional[dict] = None,
    campaign_df: Optional[pd.DataFrame] = None,
) -> list:
    """Run forecast for multiple growth scenarios and return a list of results."""
    return [
        run_forecast(
            total_ordered_revenue=total_ordered_revenue,
            total_ad_spend=total_ad_spend,
            total_ad_sales=total_ad_sales,
            growth_pct=g,
            custom_channel_split=custom_channel_split,
            campaign_df=campaign_df,
        )
        for g in growth_scenarios
    ]


def scenarios_to_dataframe(scenarios: list) -> pd.DataFrame:
    """Flatten scenario results into a comparison DataFrame."""
    rows = []
    for s in scenarios:
        rows.append({
            "Growth Target": f"+{s['growth_pct']}%",
            "Target Revenue ($)": s["target_revenue"],
            "Revenue Gap ($)": s["revenue_gap"],
            "Rec. Ad Spend ($)": s["recommended_spend"],
            "Incremental Spend ($)": s["incremental_spend"],
            "Projected ACOS (%)": s["projected_acos_pct"],
            "Projected ROAS": s["projected_roas"],
            "Projected TACOS (%)": s["projected_tacos_pct"],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Monthly forecast with high-sales event tagging
# ---------------------------------------------------------------------------

# Known Amazon / retail high-sales events by month number
AMAZON_EVENTS: dict = {
    1:  [("New Year Deals", "🎉")],
    2:  [("Valentine's Day", "💝")],
    3:  [("Spring Sale", "🌸")],
    4:  [],
    5:  [("Mother's Day", "💐")],
    6:  [("Father's Day", "👔"), ("Mid-Year Sale", "☀️")],
    7:  [("Prime Day", "⚡"), ("Summer Sale", "🌞")],
    8:  [("Back to School", "🎒")],
    9:  [],
    10: [("Pre-Holiday Push", "🍂"), ("Prime Big Deal Days", "⚡")],
    11: [("Black Friday", "🛒"), ("Cyber Monday", "💻")],
    12: [("Holiday Season", "🎄"), ("Year-End Sale", "🎁")],
}

# Spend multipliers for event months
EVENT_SPEND_MULTIPLIER: dict = {
    7:  1.30,   # Prime Day
    10: 1.20,   # Prime Big Deal Days / Pre-Holiday
    11: 1.45,   # Black Friday / Cyber Monday
    12: 1.25,   # Holiday
    2:  1.10,   # Valentine's
    5:  1.08,   # Mother's Day
    6:  1.08,   # Father's Day
    8:  1.05,   # Back to School
}


def monthly_forecast(
    trend_df: pd.DataFrame,
    growth_pct: float,
    total_ordered_revenue: float,
    custom_channel_split: Optional[dict] = None,
    annual_spend_override: Optional[float] = None,
    annual_sales_override: Optional[float] = None,
):
    """
    Build a month-by-month media plan for a given growth scenario.

    Uses actual monthly trend data as the baseline where available.
    When actuals are missing, distributes annual totals using seasonal
    event-multiplier weights so the table is never empty.

    annual_spend_override / annual_sales_override: pass the custom
    scenario's annual spend/sales to override the growth-% projection.

    Returns
    -------
    (DataFrame, int)  — monthly plan DataFrame + the actuals_year used (0 = none).
    """
    channel_split = custom_channel_split or DEFAULT_CHANNEL_SPLIT
    growth_factor = 1 + growth_pct / 100

    # ── Build monthly actuals from trend_df ──────────────────────────────
    # Strategy: if trend_df contains multi-year data (e.g. 2024 + 2025),
    # use the PRIOR year (max_year - 1) as "last year actuals" so the
    # forecast table shows 2024 actual vs 2025 projected.
    # If only one year is present, use it directly.
    actuals_year: int = 0
    if trend_df is not None and not trend_df.empty and "_period_dt" in trend_df.columns:
        work = trend_df.copy()
        work["_month"] = pd.to_datetime(work["_period_dt"]).dt.month
        work["_year"]  = pd.to_datetime(work["_period_dt"]).dt.year
        max_year  = int(work["_year"].max())
        min_year  = int(work["_year"].min())
        # Prefer prior year as actuals baseline when multi-year data available
        if max_year > min_year:
            actuals_year = max_year - 1
        else:
            actuals_year = max_year
        monthly = work[work["_year"] == actuals_year].copy()
        monthly = monthly.sort_values("_month").reset_index(drop=True)
    else:
        monthly = pd.DataFrame()

    # ── Seasonal weights — used to distribute annual totals when no actuals ──
    # Each month's weight = event_multiplier / sum(all multipliers)
    raw_weights = [EVENT_SPEND_MULTIPLIER.get(m, 1.0) for m in range(1, 13)]
    total_weight = sum(raw_weights)
    seasonal_weights = [w / total_weight for w in raw_weights]  # sums to 1.0

    # Annual totals to distribute (used only when actuals are missing per month)
    # If override provided (custom scenario), use it; else use growth-% estimate
    if annual_spend_override and annual_spend_override > 0:
        annual_proj_spend = annual_spend_override
    else:
        # Derive from total_ordered_revenue and default ACOS
        annual_proj_spend = 0.0  # will fall back to seasonal distribution below

    if annual_sales_override and annual_sales_override > 0:
        annual_proj_sales = annual_sales_override
    else:
        annual_proj_sales = 0.0

    MONTH_NAMES = [
        "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ]

    rows = []
    for idx, month_num in enumerate(range(1, 13)):
        actual_row = monthly[monthly["_month"] == month_num] if not monthly.empty else pd.DataFrame()

        actual_spend = float(actual_row["spend"].values[0])    if not actual_row.empty and "spend"    in actual_row.columns else None
        actual_sales = float(actual_row["ad_sales"].values[0]) if not actual_row.empty and "ad_sales" in actual_row.columns else None
        actual_acos  = float(actual_row["acos_%"].values[0])   if not actual_row.empty and "acos_%"   in actual_row.columns else None
        actual_roas  = float(actual_row["roas"].values[0])     if not actual_row.empty and "roas"     in actual_row.columns else None
        actual_impr  = float(actual_row["impressions"].values[0]) if not actual_row.empty and "impressions" in actual_row.columns else None

        events = AMAZON_EVENTS.get(month_num, [])
        is_event = len(events) > 0
        event_label = " · ".join(f"{badge} {name}" for name, badge in events) if events else "—"
        spend_multiplier = EVENT_SPEND_MULTIPLIER.get(month_num, 1.0)
        spend_uplift_pct = round((spend_multiplier - 1) * 100, 0)

        # ── Projected spend ──────────────────────────────────────────────
        if actual_spend is not None:
            # Have actuals — scale by growth + event multiplier
            proj_spend = round(actual_spend * growth_factor * spend_multiplier, 2)
        elif annual_proj_spend > 0:
            # No actuals but have annual total — distribute seasonally
            proj_spend = round(annual_proj_spend * seasonal_weights[idx] * spend_multiplier, 2)
        else:
            proj_spend = 0.0

        # ── Projected sales ──────────────────────────────────────────────
        if actual_sales is not None:
            proj_sales = round(actual_sales * growth_factor, 2)
        elif annual_proj_sales > 0:
            proj_sales = round(annual_proj_sales * seasonal_weights[idx], 2)
        else:
            proj_sales = 0.0

        proj_acos = round(proj_spend / proj_sales * 100, 2) if proj_sales > 0 else None
        proj_roas = round(proj_sales / proj_spend, 2)       if proj_spend > 0 else None

        ch_alloc = {ch: round(proj_spend * w, 2) for ch, w in channel_split.items()}

        rows.append({
            "Month":                  month_num,
            "Month Name":             MONTH_NAMES[month_num],
            "Actual Spend ($)":       actual_spend,
            "Actual Ad Sales ($)":    actual_sales,
            "Actual ACOS (%)":        actual_acos,
            "Actual ROAS":            actual_roas,
            "Actual Impressions":     actual_impr,
            "Projected Spend ($)":    proj_spend,
            "Projected Ad Sales ($)": proj_sales,
            "Projected ACOS (%)":     proj_acos,
            "Projected ROAS":         proj_roas,
            "Events":                 event_label,
            "Is Event Month":         is_event,
            "Spend Uplift %":         spend_uplift_pct,
            "SP Budget ($)":          ch_alloc.get("Sponsored Products", 0),
            "SB Budget ($)":          ch_alloc.get("Sponsored Brands", 0),
            "SD Budget ($)":          ch_alloc.get("Sponsored Display", 0),
        })

    return pd.DataFrame(rows), actuals_year


# ---------------------------------------------------------------------------
# Campaign-level recommendations
# ---------------------------------------------------------------------------

def _recommend_campaigns(
    campaign_df: pd.DataFrame,
    incremental_spend: float,
    growth_pct: float,
) -> list:
    """
    Suggest per-campaign budget increases based on efficiency (ROAS / ACOS).
    High-ROAS campaigns get proportionally more of the incremental budget.
    """
    df = campaign_df.copy()
    name_col = df.columns[0]  # first column is the group key

    if "roas" not in df.columns and "acos_%" not in df.columns:
        return []

    # Score = ROAS (higher is better); fallback to inverse ACOS
    if "roas" in df.columns:
        df["_score"] = df["roas"].fillna(0)
    else:
        df["_score"] = (100 / df["acos_%"].replace(0, np.nan)).fillna(0)

    # Only increase budget for campaigns with positive efficiency
    df = df[df["_score"] > 0].copy()
    if df.empty:
        return []

    total_score = df["_score"].sum()
    df["_weight"] = df["_score"] / total_score
    df["suggested_increase"] = (df["_weight"] * incremental_spend).round(2)

    if "spend" in df.columns:
        df["new_budget"] = (df["spend"] + df["suggested_increase"]).round(2)

    records = []
    for _, row in df.head(10).iterrows():
        rec = {
            "campaign": row[name_col],
            "current_spend": round(row["spend"], 2) if "spend" in row else None,
            "suggested_increase": round(row["suggested_increase"], 2),
            "new_budget": round(row["new_budget"], 2) if "new_budget" in row else None,
            "roas": round(row["roas"], 2) if "roas" in df.columns else None,
            "acos_pct": round(row["acos_%"], 2) if "acos_%" in df.columns else None,
        }
        records.append(rec)

    return records
