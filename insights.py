"""
insights.py — Search term intelligence, product analysis, match type efficiency,
NTB analysis, bid strategy breakdown, and wasted spend detection.

Performance notes
-----------------
* product_intelligence: previously called df.groupby(asin).agg() twice (once for
  numeric sums, once for first() metadata). Now done in two groupbys with a merge,
  same as metrics.asin_ads_breakdown — but results are not re-computed if the
  caller already has asin_ads_df available.
* All groupby calls use sort=False — caller sorts by the relevant column at the
  end, so the internal sort is wasted work.
* Derived columns (acos_%, roas, cpc, cvr_%) factored into the shared
  _add_derived_ad_cols helper from metrics.py to avoid code duplication.
* search_term_analysis: single groupby instead of re-filtering result multiple times.
* wasted_spend_summary: single boolean mask instead of re-evaluating df[col].
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from metrics import _add_derived_ad_cols


# ---------------------------------------------------------------------------
# Search Term Intelligence
# ---------------------------------------------------------------------------

def search_term_analysis(df: pd.DataFrame) -> dict:
    """
    Analyse search terms for conversion efficiency, wasted spend, and NTB signals.
    Returns a dict of DataFrames.
    """
    result: dict = {}

    st_col = "search_term" if "search_term" in df.columns else None
    if st_col is None:
        return result

    agg_cols = {c: "sum" for c in [
        "spend", "ad_sales", "ad_orders", "impressions", "clicks",
        "ad_orders_ntb", "ad_sales_longterm",
    ] if c in df.columns}

    st_df = df.groupby(st_col, sort=False).agg(agg_cols).reset_index()
    st_df = st_df.rename(columns={st_col: "search_term"})
    st_df = _add_derived_ad_cols(st_df)

    if "ad_orders" in st_df.columns and "ad_orders_ntb" in st_df.columns:
        st_df["ntb_%"] = (st_df["ad_orders_ntb"] / st_df["ad_orders"].replace(0, np.nan) * 100).round(1)

    # ── Derived sub-sets — all computed from the single aggregated st_df ────
    if "ad_sales" in st_df.columns:
        result["top_converting"] = (
            st_df[st_df["ad_sales"].fillna(0) > 0]
            .sort_values("ad_sales", ascending=False)
            .head(20)
        )
    else:
        result["top_converting"] = pd.DataFrame()

    if "ad_orders" in st_df.columns and "spend" in st_df.columns:
        result["wasted_spend"] = (
            st_df[(st_df["ad_orders"].fillna(0) == 0) & (st_df["spend"] > 0)]
            .sort_values("spend", ascending=False)
            .head(20)
        )
    else:
        result["wasted_spend"] = pd.DataFrame()

    if "ntb_%" in st_df.columns:
        min_orders = st_df.get("ad_orders", pd.Series(dtype=float)).fillna(0)
        result["ntb_leaders"] = (
            st_df[st_df["ntb_%"].notna() & (min_orders >= 2)]
            .sort_values("ntb_%", ascending=False)
            .head(20)
        )
    else:
        result["ntb_leaders"] = pd.DataFrame()

    if "cvr_%" in st_df.columns and "spend" in st_df.columns:
        result["harvest_candidates"] = (
            st_df[(st_df["cvr_%"].fillna(0) >= 5) & (st_df["spend"] > 0)]
            .sort_values("cvr_%", ascending=False)
            .head(15)
        )
    else:
        result["harvest_candidates"] = pd.DataFrame()

    result["all_terms"] = st_df
    return result


def wasted_spend_summary(df: pd.DataFrame) -> dict:
    """Total wasted spend (clicks, no conversions). Single boolean mask."""
    if "ad_orders" not in df.columns or "spend" not in df.columns:
        return {}
    mask   = df["ad_orders"].fillna(0) == 0
    wasted = float(df.loc[mask, "spend"].sum())
    total  = float(df["spend"].sum())
    return {
        "wasted_spend": round(wasted, 2),
        "wasted_pct":   round(wasted / total * 100, 1) if total > 0 else 0,
        "total_spend":  round(total, 2),
    }


# ---------------------------------------------------------------------------
# Match Type Efficiency
# ---------------------------------------------------------------------------

def match_type_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Compare ACOS, ROAS, CVR across Exact / Phrase / Broad match types."""
    if "match_type" not in df.columns:
        return pd.DataFrame()

    agg_cols = {c: "sum" for c in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"] if c in df.columns}
    result = df.groupby("match_type", sort=False).agg(agg_cols).reset_index()
    result = _add_derived_ad_cols(result)

    sort_col = "spend" if "spend" in result.columns else result.columns[-1]
    return result.sort_values(sort_col, ascending=False)


# ---------------------------------------------------------------------------
# Product / ASIN Intelligence
# ---------------------------------------------------------------------------

def product_intelligence(df: pd.DataFrame) -> dict:
    """
    Deep per-ASIN analysis including NTB%, CVR, category rollup.

    Optimised: numeric aggregation and metadata first() are done in two
    separate groupbys with a merge — this is necessary because pandas cannot
    mix sum() and first() for object columns in the same groupby.agg() call
    without surprising results. But both groupbys use sort=False.
    """
    result: dict = {}

    if "asin" not in df.columns:
        return result

    agg_cols = {c: "sum" for c in [
        "spend", "ad_sales", "impressions", "clicks", "ad_orders",
        "ad_orders_ntb", "ad_sales_longterm",
    ] if c in df.columns}

    asin_df = df.groupby("asin", sort=False).agg(agg_cols).reset_index()
    asin_df = _add_derived_ad_cols(asin_df)

    first_cols = [c for c in ["product_title", "category", "subcategory", "brand"] if c in df.columns]
    if first_cols:
        first_vals = df.groupby("asin", sort=False)[first_cols].first().reset_index()
        asin_df = asin_df.merge(first_vals, on="asin", how="left")

    if "ad_orders" in asin_df.columns and "ad_orders_ntb" in asin_df.columns:
        asin_df["ntb_%"] = (asin_df["ad_orders_ntb"] / asin_df["ad_orders"].replace(0, np.nan) * 100).round(1)

    # Sort once, reuse for sub-sets
    if "ad_sales" in asin_df.columns:
        asin_df = asin_df.sort_values("ad_sales", ascending=False)

    result["by_asin"] = asin_df
    result["top_roas"]   = asin_df.nlargest(10, "roas")    if "roas"   in asin_df.columns else pd.DataFrame()
    result["worst_acos"] = (
        asin_df[asin_df["acos_%"].notna()].nlargest(10, "acos_%")
        if "acos_%" in asin_df.columns else pd.DataFrame()
    )

    # Category rollup — separate groupby (different granularity)
    if "category" in df.columns:
        cat_agg = {c: "sum" for c in ["spend", "ad_sales", "ad_orders", "impressions", "clicks"] if c in df.columns}
        cat_df = df.groupby("category", sort=False).agg(cat_agg).reset_index()
        cat_df = _add_derived_ad_cols(cat_df)
        result["by_category"] = (
            cat_df.sort_values("ad_sales", ascending=False)
            if "ad_sales" in cat_df.columns else cat_df
        )
    else:
        result["by_category"] = pd.DataFrame()

    return result


# ---------------------------------------------------------------------------
# Bid Strategy Breakdown
# ---------------------------------------------------------------------------

def bid_strategy_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Compare performance across Dynamic Up/Down, Fixed, Rule-based bid strategies."""
    if "bid_strategy" not in df.columns:
        return pd.DataFrame()

    agg_cols = {c: "sum" for c in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"] if c in df.columns}
    result = df.groupby("bid_strategy", sort=False).agg(agg_cols).reset_index()
    result = _add_derived_ad_cols(result)

    sort_col = "spend" if "spend" in result.columns else result.columns[-1]
    return result.sort_values(sort_col, ascending=False)


# ---------------------------------------------------------------------------
# Ad Product / Campaign Type Breakdown
# ---------------------------------------------------------------------------

def ad_product_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Sponsored Products vs Sponsored Brands vs Sponsored Display breakdown."""
    if "campaign_type" not in df.columns:
        return pd.DataFrame()

    agg_cols = {c: "sum" for c in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"] if c in df.columns}
    result = df.groupby("campaign_type", sort=False).agg(agg_cols).reset_index()
    result = result.rename(columns={"campaign_type": "ad_product"})
    result = _add_derived_ad_cols(result)

    if "spend" in result.columns:
        total_spend = result["spend"].sum()
        result["spend_share_%"] = (result["spend"] / total_spend * 100).round(1) if total_spend > 0 else 0.0

    sort_col = "spend" if "spend" in result.columns else result.columns[-1]
    return result.sort_values(sort_col, ascending=False)
