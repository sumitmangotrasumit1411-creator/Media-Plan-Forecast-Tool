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
# Channel-mix efficiency
# ---------------------------------------------------------------------------

def _normalise_channel_split(channel_split: Optional[dict]) -> dict:
    """Return a clean channel split whose weights always total exactly 100%."""
    raw = channel_split or DEFAULT_CHANNEL_SPLIT
    weights = {
        "Sponsored Products": max(float(raw.get("Sponsored Products", 0.0)), 0.0),
        "Sponsored Brands": max(float(raw.get("Sponsored Brands", 0.0)), 0.0),
        "Sponsored Display": max(float(raw.get("Sponsored Display", 0.0)), 0.0),
    }
    total = sum(weights.values())
    if total <= 0:
        return DEFAULT_CHANNEL_SPLIT.copy()
    return {channel: weight / total for channel, weight in weights.items()}



def _channel_mix_efficiency(
    channel_split: dict,
    channel_perf_df: Optional[pd.DataFrame],
    baseline_spend: float,
    baseline_sales: float,
) -> float:
    """
    Translate a proposed SP/SB/SD budget mix into a forecast efficiency factor.

    When channel-level actuals are available, the factor compares the ROAS of
    the proposed mix with the uploaded account's overall ROAS. This makes the
    channel split a true forecast input rather than a display-only allocation.

    If channel-level actuals are unavailable, use conservative relative channel
    efficiency indices so changing the mix still changes the forecast.
    """
    default_index = {
        "Sponsored Products": 1.00,
        "Sponsored Brands": 0.92,
        "Sponsored Display": 0.78,
    }

    if not channel_split:
        return 1.0

    channel_roas = {}
    if channel_perf_df is not None and not channel_perf_df.empty:
        type_col = next(
            (c for c in ["campaign_type", "ad_product", "ad product"] if c in channel_perf_df.columns),
            None,
        )
        if type_col and "spend" in channel_perf_df.columns and "ad_sales" in channel_perf_df.columns:
            work = channel_perf_df[[type_col, "spend", "ad_sales"]].copy()
            work["spend"] = pd.to_numeric(work["spend"], errors="coerce").fillna(0.0)
            work["ad_sales"] = pd.to_numeric(work["ad_sales"], errors="coerce").fillna(0.0)
            work[type_col] = work[type_col].astype(str).str.strip().str.lower()
            aliases = {
                "sp": "Sponsored Products",
                "sponsored products": "Sponsored Products",
                "sponsored product": "Sponsored Products",
                "sb": "Sponsored Brands",
                "sponsored brands": "Sponsored Brands",
                "sponsored brand": "Sponsored Brands",
                "sd": "Sponsored Display",
                "sponsored display": "Sponsored Display",
                "sponsored displays": "Sponsored Display",
            }
            work["_channel"] = work[type_col].map(aliases)
            work = work.dropna(subset=["_channel"])
            if not work.empty:
                grouped = work.groupby("_channel")[["spend", "ad_sales"]].sum()
                for ch, row in grouped.iterrows():
                    if row["spend"] > 0:
                        channel_roas[ch] = float(row["ad_sales"] / row["spend"])

    overall_roas = (baseline_sales / baseline_spend) if baseline_spend > 0 else 0.0

    # Fill missing channel ROAS with a relative index against the account ROAS.
    for ch, idx in default_index.items():
        if ch not in channel_roas:
            channel_roas[ch] = overall_roas * idx if overall_roas > 0 else idx

    proposed_roas = sum(
        float(weight) * channel_roas.get(ch, overall_roas or 1.0)
        for ch, weight in channel_split.items()
    )
    if overall_roas <= 0 or proposed_roas <= 0:
        return 1.0
    return float(np.clip(proposed_roas / overall_roas, 0.50, 1.50))


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
    channel_perf_df: Optional[pd.DataFrame] = None,
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
    channel_split = _normalise_channel_split(custom_channel_split)

    # ---- Baseline metrics ------------------------------------------------
    baseline_revenue = total_ordered_revenue if total_ordered_revenue > 0 else total_ad_sales
    current_acos  = (total_ad_spend / total_ad_sales * 100) if total_ad_sales > 0 else None
    current_tacos = (total_ad_spend / baseline_revenue * 100) if baseline_revenue > 0 else None
    current_roas  = (total_ad_sales / total_ad_spend) if total_ad_spend > 0 else None

    # Channel mix is a real forecast driver, not just a visualization split.
    mix_efficiency = _channel_mix_efficiency(
        channel_split, channel_perf_df, total_ad_spend, total_ad_sales
    )

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
        incremental_ad_sales_needed = revenue_gap * ad_contribution_ratio * mix_efficiency
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
        # A more efficient channel mix needs less spend to generate the same
        # ad sales; a less efficient mix needs more. This keeps channel mix
        # active even when ad sales are explicitly pinned.
        mix_adjusted_acos = (current_acos or 20.0) / max(mix_efficiency, 0.01)
        effective_acos = mix_adjusted_acos * spend_multiplier
        if target_acos_override:
            effective_acos = target_acos_override
        recommended_spend = target_ad_sales * (effective_acos / 100)

    # If the user pins ad spend but leaves ad sales free, estimate the
    # sales produced by that spend using the proposed channel mix efficiency.
    if override_ad_spend and override_ad_spend > 0 and not (override_ad_sales and override_ad_sales > 0):
        if total_ad_spend > 0:
            target_ad_sales = total_ad_sales * (recommended_spend / total_ad_spend) * mix_efficiency
        elif current_roas:
            target_ad_sales = recommended_spend * current_roas * mix_efficiency

    # ---- Derived metrics -------------------------------------------------
    incremental_spend    = recommended_spend - total_ad_spend
    incremental_revenue  = target_revenue - baseline_revenue
    effective_acos       = (recommended_spend / target_ad_sales * 100) if target_ad_sales > 0 else 0
    projected_roas       = round(target_ad_sales / recommended_spend, 2) if recommended_spend > 0 else None
    projected_tacos      = round(recommended_spend / target_revenue * 100, 2) if target_revenue > 0 else None

    # Organic sales = total revenue minus ad-attributed sales
    projected_organic_sales   = max(target_revenue - target_ad_sales, 0)
    baseline_organic_sales    = max(baseline_revenue - total_ad_sales, 0)

    # Ad contribution % = ad sales / total revenue
    projected_ad_contribution = round(target_ad_sales / target_revenue * 100, 1) if target_revenue > 0 else 0
    baseline_ad_contribution  = round(total_ad_sales / baseline_revenue * 100, 1) if baseline_revenue > 0 else 0

    # Organic contribution % = organic sales / total revenue
    projected_org_contribution = round(projected_organic_sales / target_revenue * 100, 1) if target_revenue > 0 else 0
    baseline_org_contribution  = round(baseline_organic_sales / baseline_revenue * 100, 1) if baseline_revenue > 0 else 0

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
        # Baseline (always from uploaded report — never overwritten)
        "baseline_revenue":            round(baseline_revenue, 2),
        "current_ad_spend":            round(total_ad_spend, 2),
        "current_ad_sales":            round(total_ad_sales, 2),
        "current_acos_pct":            round(current_acos, 2) if current_acos else None,
        "current_tacos_pct":           round(current_tacos, 2) if current_tacos else None,
        "current_roas":                round(current_roas, 2) if current_roas else None,
        "baseline_organic_sales":      round(baseline_organic_sales, 2),
        "baseline_ad_contribution":    baseline_ad_contribution,
        "baseline_org_contribution":   baseline_org_contribution,
        # Projected targets — unique per scenario
        "growth_pct":                  growth_pct,
        "target_revenue":              round(target_revenue, 2),
        "revenue_gap":                 round(revenue_gap, 2),
        "incremental_revenue":         round(incremental_revenue, 2),
        "target_ad_sales":             round(target_ad_sales, 2),
        "recommended_spend":           round(recommended_spend, 2),
        "incremental_spend":           round(incremental_spend, 2),
        "projected_acos_pct":          round(effective_acos, 2),
        "projected_roas":              projected_roas,
        "projected_tacos_pct":         projected_tacos,
        "projected_organic_sales":     round(projected_organic_sales, 2),
        "projected_ad_contribution":   projected_ad_contribution,
        "projected_org_contribution":  projected_org_contribution,
        "channel_mix_efficiency":       round(mix_efficiency, 4),
        # Allocation
        "channel_allocation":          channel_allocation,
        "campaign_recommendations":    campaign_recommendations,
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
    channel_perf_df: Optional[pd.DataFrame] = None,
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
            channel_perf_df=channel_perf_df,
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
    # trend_df is built at weekly (freq='W') granularity, so we must GROUP
    # BY (year, month) and SUM spend/sales — never read a single row per month.
    #
    # Year selection strategy:
    #   • Multi-year data  → use the LATEST year (max_year) as actuals.
    #     The prior-year-as-baseline logic was removed because when the user
    #     uploads a 2025 report they want to see 2025 actuals, not 2024.
    #   • Single year      → use it directly.
    #
    # ACOS and ROAS are ALWAYS recomputed from the month-summed spend/sales.
    # They are never read from the pre-aggregated trend_df columns, which
    # contain period-level (weekly) rates that are wrong at monthly granularity.
    actuals_year: int = 0
    monthly_actuals: dict = {}   # month_num → {spend, ad_sales, impressions}

    if trend_df is not None and not trend_df.empty and "_period_dt" in trend_df.columns:
        work = trend_df.copy()
        work["_month"] = pd.to_datetime(work["_period_dt"]).dt.month
        work["_year"]  = pd.to_datetime(work["_period_dt"]).dt.year
        max_year = int(work["_year"].max())

        # Use the latest year present in the data as actuals
        actuals_year = max_year
        year_work = work[work["_year"] == actuals_year]

        # Aggregate by month — sum all numeric cols so weekly rows are merged
        agg_cols = {c: "sum" for c in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"]
                    if c in year_work.columns}
        if agg_cols:
            month_agg = year_work.groupby("_month", sort=True).agg(agg_cols).reset_index()
            for _, row in month_agg.iterrows():
                mn = int(row["_month"])
                sp = float(row["spend"])    if "spend"    in row.index else None
                sl = float(row["ad_sales"]) if "ad_sales" in row.index else None
                im = float(row["impressions"]) if "impressions" in row.index else None
                # Always recompute ACOS and ROAS from summed spend/sales
                ac = round(sp / sl * 100, 2) if (sp and sl and sl > 0) else None
                ro = round(sl / sp, 2)       if (sp and sl and sp > 0) else None
                monthly_actuals[mn] = {
                    "spend": sp, "ad_sales": sl,
                    "acos_%": ac, "roas": ro, "impressions": im,
                }

    monthly = pd.DataFrame()   # kept for legacy — no longer used for row lookup

    # ── Seasonal weights — used to distribute annual totals when no actuals ──
    # Each month's weight = event_multiplier / sum(all multipliers)
    raw_weights = [EVENT_SPEND_MULTIPLIER.get(m, 1.0) for m in range(1, 13)]
    total_weight = sum(raw_weights)
    seasonal_weights = [w / total_weight for w in raw_weights]  # sums to 1.0

    # Annual forecast totals. The selected scenario is the source of truth
    # for projected monthly values. We allocate those annual totals across
    # months instead of simply multiplying actual monthly values by growth.
    # This is critical: if channel mix or a custom target changes annual
    # spend/sales, every projected month must change and the table must
    # reconcile back to the scenario totals.
    actual_spend_values = [
        float(monthly_actuals.get(m, {}).get("spend") or 0.0)
        for m in range(1, 13)
    ]
    actual_sales_values = [
        float(monthly_actuals.get(m, {}).get("ad_sales") or 0.0)
        for m in range(1, 13)
    ]

    def _build_projection_weights(actual_values):
        present = [i for i, value in enumerate(actual_values) if value > 0]
        if not present:
            return list(seasonal_weights)

        present_seasonal_share = sum(seasonal_weights[i] for i in present)
        actual_total = sum(actual_values[i] for i in present)
        missing = [i for i in range(12) if i not in present]
        missing_seasonal_total = sum(seasonal_weights[i] for i in missing)

        weights = [0.0] * 12
        for i in present:
            weights[i] = present_seasonal_share * (actual_values[i] / actual_total)

        if missing:
            missing_share = max(1.0 - present_seasonal_share, 0.0)
            if missing_seasonal_total > 0:
                for i in missing:
                    weights[i] = missing_share * (seasonal_weights[i] / missing_seasonal_total)

        total = sum(weights)
        return [w / total for w in weights] if total > 0 else list(seasonal_weights)

    spend_weights = _build_projection_weights(actual_spend_values)
    sales_weights = _build_projection_weights(actual_sales_values)

    if annual_spend_override and annual_spend_override > 0:
        annual_proj_spend = float(annual_spend_override)
    else:
        actual_spend_total = sum(actual_spend_values)
        annual_proj_spend = actual_spend_total * growth_factor if actual_spend_total > 0 else 0.0

    if annual_sales_override and annual_sales_override > 0:
        annual_proj_sales = float(annual_sales_override)
    else:
        actual_sales_total = sum(actual_sales_values)
        annual_proj_sales = actual_sales_total * growth_factor if actual_sales_total > 0 else 0.0

    MONTH_NAMES = [
        "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ]

    rows = []
    for idx, month_num in enumerate(range(1, 13)):
        # Pull month actuals from the pre-aggregated dict (sums all weekly rows)
        ma = monthly_actuals.get(month_num, {})
        actual_spend = ma.get("spend")
        actual_sales = ma.get("ad_sales")
        actual_impr  = ma.get("impressions")
        # Always derive ACOS/ROAS from spend/sales — never trust pre-stored rates
        actual_acos  = round(actual_spend / actual_sales * 100, 2) if (actual_spend and actual_sales and actual_sales > 0) else None
        actual_roas  = round(actual_sales / actual_spend, 2)       if (actual_spend and actual_sales and actual_spend > 0) else None

        events = AMAZON_EVENTS.get(month_num, [])
        is_event = len(events) > 0
        event_label = " · ".join(f"{badge} {name}" for name, badge in events) if events else "—"
        spend_multiplier = EVENT_SPEND_MULTIPLIER.get(month_num, 1.0)
        spend_uplift_pct = round((spend_multiplier - 1) * 100, 0)

        # ── Projected spend ──────────────────────────────────────────────
        # Always allocate the selected scenario's annual spend. Actual monthly
        # data only determines the seasonal shape of the projection.
        proj_spend = (
            round(annual_proj_spend * spend_weights[idx], 2)
            if annual_proj_spend > 0 else 0.0
        )

        # ── Projected sales ──────────────────────────────────────────────
        # Always allocate the selected scenario's annual ad sales. This keeps
        # monthly projections synchronized with the scenario cards, charts and
        # annual totals.
        proj_sales = (
            round(annual_proj_sales * sales_weights[idx], 2)
            if annual_proj_sales > 0 else 0.0
        )

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
