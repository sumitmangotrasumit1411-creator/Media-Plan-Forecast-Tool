"""
metrics.py — Extract and aggregate key performance metrics from parsed reports.

Performance notes
-----------------
* extract_ads_metrics: replaced N individual df[col].sum() calls with a single
  vectorized df[cols].sum() call — one pass over the DataFrame instead of N passes.
* campaign_breakdown / asin_ads_breakdown: derived ACOS/ROAS computed via
  vectorized division; replace(0, np.nan) avoids div-by-zero without a Python loop.
* asin_vendor_breakdown: first() for metadata columns is done in one groupby
  instead of two separate groupby operations.
"""

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Internal: shared derived-column helper
# ---------------------------------------------------------------------------

def _add_derived_ad_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    In-place addition of acos_%, roas, cpc, cvr_% to an already-aggregated df.
    Called by multiple breakdown functions to avoid duplicating this logic.
    """
    if "spend" in df.columns and "ad_sales" in df.columns:
        safe_sales = df["ad_sales"].replace(0, np.nan)
        safe_spend = df["spend"].replace(0, np.nan)
        df["acos_%"] = (df["spend"] / safe_sales * 100).round(2)
        df["roas"]   = (df["ad_sales"] / safe_spend).round(2)
    if "spend" in df.columns and "clicks" in df.columns:
        df["cpc"] = (df["spend"] / df["clicks"].replace(0, np.nan)).round(4)
    if "clicks" in df.columns and "ad_orders" in df.columns:
        df["cvr_%"] = (df["ad_orders"] / df["clicks"].replace(0, np.nan) * 100).round(2)
    return df


# ---------------------------------------------------------------------------
# Amazon Ads Metrics
# ---------------------------------------------------------------------------

def extract_ads_metrics(df: pd.DataFrame) -> dict:
    """
    Compute top-level aggregated metrics from the Amazon Ads report.

    Optimised: single vectorized df[cols].sum() call replaces N individual
    df[col].sum() calls. Derived metrics computed from those totals.
    """
    # ── Single-pass column sums ──────────────────────────────────────────────
    sum_cols = [c for c in [
        "impressions", "clicks", "spend", "ad_sales", "ad_orders",
        "ad_orders_ntb", "sales_ntb", "ad_sales_longterm",
    ] if c in df.columns]

    totals = df[sum_cols].sum() if sum_cols else pd.Series(dtype=float)

    def _get(col):
        return float(totals[col]) if col in totals else 0.0

    m = {
        "total_impressions":       _get("impressions"),
        "total_clicks":            _get("clicks"),
        "total_spend":             _get("spend"),
        "total_ad_sales":          _get("ad_sales"),
        "total_ad_orders":         _get("ad_orders"),
        "total_ad_orders_ntb":     _get("ad_orders_ntb"),
        "total_ad_sales_ntb":      _get("sales_ntb"),
        "total_ad_sales_longterm": _get("ad_sales_longterm"),
    }

    # ── Derived metrics ──────────────────────────────────────────────────────
    if m["total_ad_sales"] > 0:
        m["overall_acos"] = round(m["total_spend"] / m["total_ad_sales"] * 100, 2)
        m["overall_roas"] = round(m["total_ad_sales"] / m["total_spend"], 2) if m["total_spend"] > 0 else None
    else:
        m["overall_acos"] = None
        m["overall_roas"] = None

    if m["total_clicks"] > 0:
        m["overall_ctr"] = round(m["total_clicks"] / m["total_impressions"] * 100, 4) if m["total_impressions"] > 0 else None
        m["overall_cpc"] = round(m["total_spend"] / m["total_clicks"], 4)
    else:
        m["overall_ctr"] = None
        m["overall_cpc"] = None

    if m["total_ad_orders"] > 0 and m["total_clicks"] > 0:
        m["conversion_rate"] = round(m["total_ad_orders"] / m["total_clicks"] * 100, 2)
    else:
        m["conversion_rate"] = None

    if m["total_ad_orders_ntb"] > 0 and m["total_ad_orders"] > 0:
        m["ntb_order_pct"] = round(m["total_ad_orders_ntb"] / m["total_ad_orders"] * 100, 1)
    else:
        m["ntb_order_pct"] = None

    if m["total_ad_sales_longterm"] > 0 and m["total_spend"] > 0:
        m["longterm_roas"] = round(m["total_ad_sales_longterm"] / m["total_spend"], 2)
    else:
        m["longterm_roas"] = None

    if m["total_ad_orders"] > 0 and m["total_spend"] > 0:
        m["cost_per_order"] = round(m["total_spend"] / m["total_ad_orders"], 2)
    else:
        m["cost_per_order"] = None

    return m


def campaign_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Group by campaign_name and aggregate spend + sales."""
    group_col = next(
        (c for c in ["campaign_name", "campaign_type", "targeting", "ad_group_name"]
         if c in df.columns),
        None,
    )
    if group_col is None:
        return pd.DataFrame()

    agg_cols = {c: "sum" for c in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"] if c in df.columns}
    result = df.groupby(group_col, sort=False).agg(agg_cols).reset_index()
    result = _add_derived_ad_cols(result)

    sort_col = "spend" if "spend" in result.columns else result.columns[-1]
    return result.sort_values(sort_col, ascending=False)


def asin_ads_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Per-ASIN aggregate from the ads report."""
    if "asin" not in df.columns:
        return pd.DataFrame()

    agg_cols = {c: "sum" for c in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"] if c in df.columns}
    result = df.groupby("asin", sort=False).agg(agg_cols).reset_index()
    result = _add_derived_ad_cols(result)

    sort_col = "ad_sales" if "ad_sales" in result.columns else result.columns[-1]
    return result.sort_values(sort_col, ascending=False)


# ---------------------------------------------------------------------------
# Vendor Central Metrics
# ---------------------------------------------------------------------------

def extract_vendor_metrics(df: pd.DataFrame) -> dict:
    """Compute top-level aggregated metrics from the Vendor Central report."""
    sum_cols = [c for c in ["ordered_revenue", "shipped_revenue", "ordered_units", "shipped_units"] if c in df.columns]
    totals = df[sum_cols].sum() if sum_cols else pd.Series(dtype=float)

    def _get(col):
        return float(totals[col]) if col in totals else 0.0

    m = {
        "total_ordered_revenue": _get("ordered_revenue"),
        "total_shipped_revenue": _get("shipped_revenue"),
        "total_ordered_units":   _get("ordered_units"),
        "total_shipped_units":   _get("shipped_units"),
    }

    if m["total_ordered_units"] > 0 and m["total_ordered_revenue"] > 0:
        m["avg_selling_price"] = round(m["total_ordered_revenue"] / m["total_ordered_units"], 2)
    else:
        m["avg_selling_price"] = None

    return m


def asin_vendor_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Per-ASIN revenue and units from Vendor Central."""
    if "asin" not in df.columns:
        return pd.DataFrame()

    agg_cols = {c: "sum" for c in ["ordered_revenue", "shipped_revenue", "ordered_units", "shipped_units"] if c in df.columns}
    extra_cols = [c for c in ["product_title", "category", "brand"] if c in df.columns]

    result = df.groupby("asin", sort=False).agg(agg_cols).reset_index()

    if extra_cols:
        # Single groupby — first() for metadata, merged in one shot
        first_vals = df.groupby("asin", sort=False)[extra_cols].first().reset_index()
        result = result.merge(first_vals, on="asin", how="left")

    if "ordered_units" in result.columns and "ordered_revenue" in result.columns:
        result["avg_price"] = (result["ordered_revenue"] / result["ordered_units"].replace(0, np.nan)).round(2)

    sort_col = "ordered_revenue" if "ordered_revenue" in result.columns else result.columns[-1]
    return result.sort_values(sort_col, ascending=False)


# ---------------------------------------------------------------------------
# Combined / Blended View
# ---------------------------------------------------------------------------

def merge_asin_view(ads_asin_df: pd.DataFrame, vendor_asin_df: pd.DataFrame) -> pd.DataFrame:
    """Join Ads ASIN data with Vendor ASIN data for a blended per-ASIN view."""
    if ads_asin_df.empty and vendor_asin_df.empty:
        return pd.DataFrame()
    if ads_asin_df.empty:
        return vendor_asin_df
    if vendor_asin_df.empty:
        return ads_asin_df

    merged = pd.merge(ads_asin_df, vendor_asin_df, on="asin", how="outer", suffixes=("_ads", "_vendor"))

    if "spend" in merged.columns and "ordered_revenue" in merged.columns:
        merged["tacos_%"] = (
            merged["spend"] / merged["ordered_revenue"].replace(0, np.nan) * 100
        ).round(2)

    sort_col = "ordered_revenue" if "ordered_revenue" in merged.columns else merged.columns[-1]
    return merged.sort_values(sort_col, ascending=False, na_position="last")
