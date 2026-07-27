"""
insights.py — Search term intelligence, product analysis, match type efficiency,
NTB analysis, bid strategy breakdown, and wasted spend detection.
"""

from __future__ import annotations
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Search Term Intelligence
# ---------------------------------------------------------------------------

def search_term_analysis(df: pd.DataFrame) -> dict:
    """
    Analyse search terms for conversion efficiency, wasted spend, and NTB signals.
    Returns a dict of DataFrames.
    """
    result = {}

    st_col = "search_term" if "search_term" in df.columns else None
    if st_col is None:
        return result

    agg = {}
    for col in ["spend", "ad_sales", "ad_orders", "impressions", "clicks",
                "ad_orders_ntb", "ad_sales_longterm"]:
        if col in df.columns:
            agg[col] = "sum"

    st_df = df.groupby(st_col).agg(agg).reset_index()
    st_df = st_df.rename(columns={st_col: "search_term"})

    if "spend" in st_df.columns and "ad_sales" in st_df.columns:
        st_df["acos_%"] = (st_df["spend"] / st_df["ad_sales"].replace(0, np.nan) * 100).round(2)
        st_df["roas"] = (st_df["ad_sales"] / st_df["spend"].replace(0, np.nan)).round(2)

    if "clicks" in st_df.columns and "ad_orders" in st_df.columns:
        st_df["cvr_%"] = (st_df["ad_orders"] / st_df["clicks"].replace(0, np.nan) * 100).round(2)

    if "ad_orders" in st_df.columns and "ad_orders_ntb" in st_df.columns:
        st_df["ntb_%"] = (st_df["ad_orders_ntb"] / st_df["ad_orders"].replace(0, np.nan) * 100).round(1)

    # Top converters — highest sales
    result["top_converting"] = st_df[
        st_df.get("ad_sales", pd.Series(dtype=float)).fillna(0) > 0
        if "ad_sales" in st_df.columns else pd.Series([True] * len(st_df))
    ].sort_values("ad_sales", ascending=False).head(20) if "ad_sales" in st_df.columns else pd.DataFrame()

    # Wasted spend — clicks but zero/no purchases
    if "ad_orders" in st_df.columns and "spend" in st_df.columns:
        result["wasted_spend"] = st_df[
            (st_df["ad_orders"].fillna(0) == 0) & (st_df["spend"] > 0)
        ].sort_values("spend", ascending=False).head(20)
    else:
        result["wasted_spend"] = pd.DataFrame()

    # NTB leaders — highest % of new-to-brand orders
    if "ntb_%" in st_df.columns:
        result["ntb_leaders"] = st_df[
            st_df["ntb_%"].notna() & (st_df.get("ad_orders", pd.Series(dtype=float)).fillna(0) >= 2)
        ].sort_values("ntb_%", ascending=False).head(20)
    else:
        result["ntb_leaders"] = pd.DataFrame()

    # Harvest candidates — high converting, not yet exact match
    if "cvr_%" in st_df.columns and "spend" in st_df.columns:
        result["harvest_candidates"] = st_df[
            (st_df["cvr_%"].fillna(0) >= 5) & (st_df["spend"] > 0)
        ].sort_values("cvr_%", ascending=False).head(15)
    else:
        result["harvest_candidates"] = pd.DataFrame()

    result["all_terms"] = st_df
    return result


def wasted_spend_summary(df: pd.DataFrame) -> dict:
    """Total wasted spend (clicks, no conversions)."""
    if "ad_orders" not in df.columns or "spend" not in df.columns:
        return {}
    wasted = df[df["ad_orders"].fillna(0) == 0]["spend"].sum()
    total = df["spend"].sum()
    return {
        "wasted_spend": round(float(wasted), 2),
        "wasted_pct": round(float(wasted / total * 100), 1) if total > 0 else 0,
        "total_spend": round(float(total), 2),
    }


# ---------------------------------------------------------------------------
# Match Type Efficiency
# ---------------------------------------------------------------------------

def match_type_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Compare ACOS, ROAS, CVR across Exact / Phrase / Broad match types."""
    col = "match_type" if "match_type" in df.columns else None
    if col is None:
        return pd.DataFrame()

    agg = {}
    for c in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"]:
        if c in df.columns:
            agg[c] = "sum"

    result = df.groupby(col).agg(agg).reset_index()
    result = result.rename(columns={col: "match_type"})

    if "spend" in result.columns and "ad_sales" in result.columns:
        result["acos_%"] = (result["spend"] / result["ad_sales"].replace(0, np.nan) * 100).round(2)
        result["roas"] = (result["ad_sales"] / result["spend"].replace(0, np.nan)).round(2)

    if "clicks" in result.columns and "ad_orders" in result.columns:
        result["cvr_%"] = (result["ad_orders"] / result["clicks"].replace(0, np.nan) * 100).round(2)

    if "spend" in result.columns and "clicks" in result.columns:
        result["cpc"] = (result["spend"] / result["clicks"].replace(0, np.nan)).round(4)

    sort_col = "spend" if "spend" in result.columns else result.columns[-1]
    return result.sort_values(sort_col, ascending=False)


# ---------------------------------------------------------------------------
# Product / ASIN Intelligence
# ---------------------------------------------------------------------------

def product_intelligence(df: pd.DataFrame) -> dict:
    """
    Deep per-ASIN analysis including NTB%, CVR, category rollup.
    """
    result = {}

    asin_col = "asin" if "asin" in df.columns else None
    if asin_col is None:
        return result

    agg = {}
    for c in ["spend", "ad_sales", "impressions", "clicks", "ad_orders",
              "ad_orders_ntb", "ad_sales_longterm"]:
        if c in df.columns:
            agg[c] = "sum"

    first_cols = [c for c in ["product_title", "category", "subcategory", "brand"] if c in df.columns]
    asin_df = df.groupby(asin_col).agg(agg).reset_index()

    if first_cols:
        first_vals = df.groupby(asin_col)[first_cols].first().reset_index()
        asin_df = asin_df.merge(first_vals, on=asin_col, how="left")

    if "spend" in asin_df.columns and "ad_sales" in asin_df.columns:
        asin_df["acos_%"] = (asin_df["spend"] / asin_df["ad_sales"].replace(0, np.nan) * 100).round(2)
        asin_df["roas"] = (asin_df["ad_sales"] / asin_df["spend"].replace(0, np.nan)).round(2)

    if "clicks" in asin_df.columns and "ad_orders" in asin_df.columns:
        asin_df["cvr_%"] = (asin_df["ad_orders"] / asin_df["clicks"].replace(0, np.nan) * 100).round(2)

    if "ad_orders" in asin_df.columns and "ad_orders_ntb" in asin_df.columns:
        asin_df["ntb_%"] = (asin_df["ad_orders_ntb"] / asin_df["ad_orders"].replace(0, np.nan) * 100).round(1)

    result["by_asin"] = asin_df.sort_values("ad_sales", ascending=False) if "ad_sales" in asin_df.columns else asin_df
    result["top_roas"] = asin_df.nlargest(10, "roas") if "roas" in asin_df.columns else pd.DataFrame()
    result["worst_acos"] = asin_df[asin_df["acos_%"].notna()].nlargest(10, "acos_%") if "acos_%" in asin_df.columns else pd.DataFrame()

    # Category rollup
    if "category" in df.columns:
        cat_agg = {c: "sum" for c in ["spend", "ad_sales", "ad_orders", "impressions", "clicks"] if c in df.columns}
        cat_df = df.groupby("category").agg(cat_agg).reset_index()
        if "spend" in cat_df.columns and "ad_sales" in cat_df.columns:
            cat_df["acos_%"] = (cat_df["spend"] / cat_df["ad_sales"].replace(0, np.nan) * 100).round(2)
            cat_df["roas"] = (cat_df["ad_sales"] / cat_df["spend"].replace(0, np.nan)).round(2)
        result["by_category"] = cat_df.sort_values("ad_sales", ascending=False) if "ad_sales" in cat_df.columns else cat_df
    else:
        result["by_category"] = pd.DataFrame()

    return result


# ---------------------------------------------------------------------------
# Bid Strategy Breakdown
# ---------------------------------------------------------------------------

def bid_strategy_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Compare performance across Dynamic Up/Down, Fixed, Rule-based bid strategies."""
    col = "bid_strategy" if "bid_strategy" in df.columns else None
    if col is None:
        return pd.DataFrame()

    agg = {c: "sum" for c in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"] if c in df.columns}
    result = df.groupby(col).agg(agg).reset_index()
    result = result.rename(columns={col: "bid_strategy"})

    if "spend" in result.columns and "ad_sales" in result.columns:
        result["acos_%"] = (result["spend"] / result["ad_sales"].replace(0, np.nan) * 100).round(2)
        result["roas"] = (result["ad_sales"] / result["spend"].replace(0, np.nan)).round(2)

    sort_col = "spend" if "spend" in result.columns else result.columns[-1]
    return result.sort_values(sort_col, ascending=False)


# ---------------------------------------------------------------------------
# Ad Product / Campaign Type Breakdown
# ---------------------------------------------------------------------------

def ad_product_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Sponsored Products vs Sponsored Brands vs Sponsored Display breakdown."""
    col = "campaign_type" if "campaign_type" in df.columns else None
    if col is None:
        return pd.DataFrame()

    agg = {c: "sum" for c in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"] if c in df.columns}
    result = df.groupby(col).agg(agg).reset_index()
    result = result.rename(columns={col: "ad_product"})

    if "spend" in result.columns and "ad_sales" in result.columns:
        result["acos_%"] = (result["spend"] / result["ad_sales"].replace(0, np.nan) * 100).round(2)
        result["roas"] = (result["ad_sales"] / result["spend"].replace(0, np.nan)).round(2)

    if "spend" in result.columns:
        total_spend = result["spend"].sum()
        result["spend_share_%"] = (result["spend"] / total_spend * 100).round(1) if total_spend > 0 else 0

    sort_col = "spend" if "spend" in result.columns else result.columns[-1]
    return result.sort_values(sort_col, ascending=False)
