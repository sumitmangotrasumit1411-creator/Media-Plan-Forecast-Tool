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
) -> dict:
    """
    Generate a media plan forecast for a given growth target.

    Parameters
    ----------
    total_ordered_revenue : float — current total sales (Vendor Central)
    total_ad_spend        : float — current ad spend
    total_ad_sales        : float — current ad-attributed sales
    growth_pct            : float — desired growth e.g. 10 for +10%
    custom_channel_split  : dict  — override default channel weights
    target_acos_override  : float — force a specific target ACOS %
    campaign_df           : pd.DataFrame — campaign-level breakdown for top-N reco

    Returns a dict with all forecast values.
    """
    channel_split = custom_channel_split or DEFAULT_CHANNEL_SPLIT

    # ---- Baseline metrics ------------------------------------------------
    baseline_revenue = total_ordered_revenue if total_ordered_revenue > 0 else total_ad_sales
    current_acos = (total_ad_spend / total_ad_sales * 100) if total_ad_sales > 0 else None
    current_tacos = (total_ad_spend / baseline_revenue * 100) if baseline_revenue > 0 else None
    current_roas = (total_ad_sales / total_ad_spend) if total_ad_spend > 0 else None

    # ---- Target revenue --------------------------------------------------
    target_revenue = baseline_revenue * (1 + growth_pct / 100)
    revenue_gap = target_revenue - baseline_revenue

    # ---- Ad contribution estimate ----------------------------------------
    # Heuristic: ads typically drive 30-60% of Amazon revenue; use actual ratio
    if baseline_revenue > 0 and total_ad_sales > 0:
        ad_contribution_ratio = min(total_ad_sales / baseline_revenue, 0.90)
    else:
        ad_contribution_ratio = 0.40  # conservative default

    # Additional ad-attributed sales needed to hit the gap
    incremental_ad_sales_needed = revenue_gap * ad_contribution_ratio

    # ---- Required spend --------------------------------------------------
    # Apply efficiency decay: more spend → higher ACOS
    spend_multiplier = 1 + (growth_pct / 10) * ACOS_EFFICIENCY_DECAY
    effective_acos = (current_acos or 20.0) * spend_multiplier

    if target_acos_override:
        effective_acos = target_acos_override

    # Recommended total spend
    target_ad_sales = total_ad_sales + incremental_ad_sales_needed
    recommended_spend = target_ad_sales * (effective_acos / 100)

    # ---- Incremental budget needed ---------------------------------------
    incremental_spend = recommended_spend - total_ad_spend

    # ---- Channel allocation ---------------------------------------------
    channel_allocation = {
        ch: {
            "budget": round(recommended_spend * weight, 2),
            "incremental_budget": round(incremental_spend * weight, 2),
            "share_pct": round(weight * 100, 1),
        }
        for ch, weight in channel_split.items()
    }

    # ---- ROAS projection ------------------------------------------------
    projected_roas = round(target_ad_sales / recommended_spend, 2) if recommended_spend > 0 else None

    # ---- TACOS projection -----------------------------------------------
    projected_tacos = round(recommended_spend / target_revenue * 100, 2) if target_revenue > 0 else None

    # ---- Top campaign recommendations -----------------------------------
    campaign_recommendations = []
    if campaign_df is not None and not campaign_df.empty:
        campaign_recommendations = _recommend_campaigns(
            campaign_df, incremental_spend, growth_pct
        )

    return {
        # Baseline
        "baseline_revenue": round(baseline_revenue, 2),
        "current_ad_spend": round(total_ad_spend, 2),
        "current_ad_sales": round(total_ad_sales, 2),
        "current_acos_pct": round(current_acos, 2) if current_acos else None,
        "current_tacos_pct": round(current_tacos, 2) if current_tacos else None,
        "current_roas": round(current_roas, 2) if current_roas else None,
        # Targets
        "growth_pct": growth_pct,
        "target_revenue": round(target_revenue, 2),
        "revenue_gap": round(revenue_gap, 2),
        "target_ad_sales": round(target_ad_sales, 2),
        "recommended_spend": round(recommended_spend, 2),
        "incremental_spend": round(incremental_spend, 2),
        "projected_acos_pct": round(effective_acos, 2),
        "projected_roas": projected_roas,
        "projected_tacos_pct": projected_tacos,
        # Allocation
        "channel_allocation": channel_allocation,
        "campaign_recommendations": campaign_recommendations,
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
# Campaign-level recommendations
# ---------------------------------------------------------------------------

def _recommend_campaigns(
    campaign_df: pd.DataFrame,
    incremental_spend: float,
    growth_pct: float,
) -> list[dict]:
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
