"""
metrics.py — Extract and aggregate key performance metrics from parsed reports.
"""

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Amazon Ads Metrics
# ---------------------------------------------------------------------------

def extract_ads_metrics(df: pd.DataFrame) -> dict:
    """
    Compute top-level aggregated metrics from the Amazon Ads report.
    Returns a dict of scalar values.
    """
    m = {}

    def col_sum(col):
        return float(df[col].sum()) if col in df.columns else 0.0

    def col_mean(col):
        return float(df[col].mean()) if col in df.columns else None

    m["total_impressions"] = col_sum("impressions")
    m["total_clicks"] = col_sum("clicks")
    m["total_spend"] = col_sum("spend")
    m["total_ad_sales"] = col_sum("ad_sales")
    m["total_ad_orders"] = col_sum("ad_orders")

    # Derived
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

    if m["total_ad_orders"] > 0:
        m["conversion_rate"] = round(m["total_ad_orders"] / m["total_clicks"] * 100, 2) if m["total_clicks"] > 0 else None
    else:
        m["conversion_rate"] = None

    return m


def campaign_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group by campaign_name (if available) and aggregate spend + sales.
    """
    group_col = None
    for candidate in ["campaign_name", "campaign_type", "targeting", "ad_group_name"]:
        if candidate in df.columns:
            group_col = candidate
            break

    if group_col is None:
        return pd.DataFrame()

    agg = {}
    for col in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"]:
        if col in df.columns:
            agg[col] = "sum"

    result = df.groupby(group_col).agg(agg).reset_index()
    result.columns = [group_col] + [c for c in result.columns if c != group_col]

    # Add derived columns
    if "spend" in result.columns and "ad_sales" in result.columns:
        result["acos_%"] = (result["spend"] / result["ad_sales"].replace(0, np.nan) * 100).round(2)
        result["roas"] = (result["ad_sales"] / result["spend"].replace(0, np.nan)).round(2)

    if "spend" in result.columns and "clicks" in result.columns:
        result["cpc"] = (result["spend"] / result["clicks"].replace(0, np.nan)).round(4)

    return result.sort_values("spend", ascending=False)


def asin_ads_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    If the ads report has ASIN-level rows, aggregate per ASIN.
    """
    if "asin" not in df.columns:
        return pd.DataFrame()

    agg = {}
    for col in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"]:
        if col in df.columns:
            agg[col] = "sum"

    result = df.groupby("asin").agg(agg).reset_index()
    if "spend" in result.columns and "ad_sales" in result.columns:
        result["acos_%"] = (result["spend"] / result["ad_sales"].replace(0, np.nan) * 100).round(2)
        result["roas"] = (result["ad_sales"] / result["spend"].replace(0, np.nan)).round(2)

    return result.sort_values("ad_sales", ascending=False)


# ---------------------------------------------------------------------------
# Vendor Central Metrics
# ---------------------------------------------------------------------------

def extract_vendor_metrics(df: pd.DataFrame) -> dict:
    """
    Compute top-level aggregated metrics from the Vendor Central report.
    """
    m = {}

    def col_sum(col):
        return float(df[col].sum()) if col in df.columns else 0.0

    m["total_ordered_revenue"] = col_sum("ordered_revenue")
    m["total_shipped_revenue"] = col_sum("shipped_revenue")
    m["total_ordered_units"] = col_sum("ordered_units")
    m["total_shipped_units"] = col_sum("shipped_units")

    if m["total_ordered_units"] > 0 and m["total_ordered_revenue"] > 0:
        m["avg_selling_price"] = round(m["total_ordered_revenue"] / m["total_ordered_units"], 2)
    else:
        m["avg_selling_price"] = None

    return m


def asin_vendor_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-ASIN revenue and units from Vendor Central.
    """
    if "asin" not in df.columns:
        return pd.DataFrame()

    agg = {}
    for col in ["ordered_revenue", "shipped_revenue", "ordered_units", "shipped_units"]:
        if col in df.columns:
            agg[col] = "sum"

    extra_cols = []
    for col in ["product_title", "category", "brand"]:
        if col in df.columns:
            extra_cols.append(col)

    if extra_cols:
        first_vals = df.groupby("asin")[extra_cols].first().reset_index()
        result = df.groupby("asin").agg(agg).reset_index()
        result = result.merge(first_vals, on="asin", how="left")
    else:
        result = df.groupby("asin").agg(agg).reset_index()

    if "ordered_units" in result.columns and "ordered_revenue" in result.columns:
        result["avg_price"] = (result["ordered_revenue"] / result["ordered_units"].replace(0, np.nan)).round(2)

    return result.sort_values("ordered_revenue", ascending=False)


# ---------------------------------------------------------------------------
# Combined / Blended View
# ---------------------------------------------------------------------------

def merge_asin_view(ads_asin_df: pd.DataFrame, vendor_asin_df: pd.DataFrame) -> pd.DataFrame:
    """
    Join Ads ASIN data with Vendor ASIN data for a blended per-ASIN view.
    """
    if ads_asin_df.empty and vendor_asin_df.empty:
        return pd.DataFrame()

    if ads_asin_df.empty:
        return vendor_asin_df

    if vendor_asin_df.empty:
        return ads_asin_df

    merged = pd.merge(ads_asin_df, vendor_asin_df, on="asin", how="outer", suffixes=("_ads", "_vendor"))

    # Total ACOS against ordered revenue (not just ad-attributed sales)
    if "spend" in merged.columns and "ordered_revenue" in merged.columns:
        merged["tacos_%"] = (
            merged["spend"] / merged["ordered_revenue"].replace(0, np.nan) * 100
        ).round(2)

    return merged.sort_values("ordered_revenue", ascending=False, na_position="last")
