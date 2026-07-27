"""
parser.py — Flexible ingestion of Amazon Advertising & Vendor Central reports.
Handles CSV and XLSX. Auto-detects column names from common Amazon export variations.
"""

from __future__ import annotations

import pandas as pd
import io

# ---------------------------------------------------------------------------
# Column aliases — map every known Amazon export header variant to a canonical name
# ---------------------------------------------------------------------------

AD_COLUMN_ALIASES = {
    # Impressions
    "impressions": "impressions",
    "viewable impressions": "viewable_impressions",
    # Clicks
    "clicks": "clicks",
    # Spend / Cost
    "spend": "spend",
    "cost": "spend",
    "ad spend": "spend",
    "total spend": "spend",
    "total cost": "spend",                          # All Campaign Performance Report
    "campaign budget amount": "campaign_budget",
    # Sales (ad-attributed)
    "sales": "ad_sales",
    "attributed sales": "ad_sales",
    "7 day total sales": "ad_sales",
    "14 day total sales": "ad_sales",
    "total attributed sales": "ad_sales",
    "ad sales": "ad_sales",
    "long-term sales": "ad_sales_longterm",
    # Orders / Purchases
    "orders": "ad_orders",
    "purchases": "ad_orders",                       # All Campaign Performance Report
    "attributed conversions": "ad_orders",
    "total orders": "ad_orders",
    "purchases (new to brand)": "ad_orders_ntb",
    "cost per purchase": "cpp",
    "cost per purchase (new to brand)": "cpp_ntb",
    # CTR
    "click-through rate (ctr)": "ctr",
    "ctr": "ctr",
    "viewable ctr (vctr)": "vctr",
    # CPC
    "cost per click (cpc)": "cpc",
    "cpc": "cpc",
    # ACOS
    "acos": "acos",
    "advertising cost of sales (acos)": "acos",
    "total acos": "acos",
    # ROAS
    "roas": "roas",
    "return on ad spend (roas)": "roas",
    "total roas": "roas",
    "long-term roas": "roas_longterm",
    # Campaign metadata
    "campaign name": "campaign_name",
    "ad group name": "ad_group_name",
    "targeting": "targeting",
    "targeting match type": "match_type",
    "match type": "match_type",
    "target type": "target_type",
    "target status": "target_status",
    "target bid": "target_bid",
    "search term": "search_term",
    "matched target": "matched_target",
    "asin": "asin",
    "sku": "sku",
    "portfolio name": "portfolio_name",
    "campaign type": "campaign_type",
    "ad product": "campaign_type",                  # All Campaign Performance Report
    "advertised asin": "asin",
    "advertised sku": "sku",
    "advertised product id": "asin",
    "advertised product name": "product_title",
    "advertised product brand": "brand",
    "advertised product category": "category",
    "advertised product subcategory": "subcategory",
    "campaign id": "campaign_id",
    "campaign bid strategy": "bid_strategy",
    "date range": "date_range",
    "advertiser account id": "account_id",
    "advertiser account name": "account_name",
    "top-of-search impression share (is)": "tos_is",
    "percent of purchases new to brand": "pct_ntb_purchases",
    "percent of sales new to brand": "pct_ntb_sales",
    "sales (new to brand)": "sales_ntb",
}

VENDOR_COLUMN_ALIASES = {
    # Revenue
    "ordered revenue": "ordered_revenue",
    "ordered product sales": "ordered_revenue",
    "total ordered revenue": "ordered_revenue",
    "shipped revenue": "shipped_revenue",
    "shipped product sales": "shipped_revenue",
    "total shipped revenue": "shipped_revenue",
    # Units
    "ordered units": "ordered_units",
    "shipped units": "shipped_units",
    "total ordered units": "ordered_units",
    "total shipped units": "shipped_units",
    # ASIN
    "asin": "asin",
    "product title": "product_title",
    "product name": "product_title",
    "title": "product_title",
    # Category
    "category": "category",
    "subcategory": "subcategory",
    # Period
    "week": "period",
    "month": "period",
    "date": "period",
    "reporting period": "period",
    # Brand
    "brand": "brand",
}


def _normalise_columns(df: pd.DataFrame, alias_map: dict) -> pd.DataFrame:
    """Lowercase + strip column names, then map to canonical names."""
    df.columns = [c.strip().lower() for c in df.columns]
    rename = {col: alias_map[col] for col in df.columns if col in alias_map}
    df = df.rename(columns=rename)
    return df


def _clean_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Strip currency symbols / percent signs and coerce to float."""
    for col in df.columns:
        if df[col].dtype == object:
            sample = df[col].dropna().astype(str)
            if sample.str.contains(r"[\$\%\,]", regex=True).any():
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace(r"[\$\%\,]", "", regex=True)
                    .str.strip()
                )
                df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _read_file(uploaded_file) -> pd.DataFrame:
    """Read an uploaded Streamlit file object (CSV or XLSX) into a DataFrame."""
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    if name.endswith(".csv"):
        # Try common encodings
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                df = pd.read_csv(io.BytesIO(raw), encoding=enc, thousands=",")
                return df
            except Exception:
                continue
        raise ValueError("Could not decode CSV file.")
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(raw), engine="openpyxl")
        return df
    else:
        raise ValueError(f"Unsupported file format: {uploaded_file.name}")


def parse_amazon_ads_report(uploaded_file) -> pd.DataFrame:
    """
    Parse an Amazon Advertising (Sponsored Products / Brands / Display) report.
    Returns a normalised DataFrame with canonical column names.
    """
    df = _read_file(uploaded_file)
    df = _normalise_columns(df, AD_COLUMN_ALIASES)
    df = _clean_numeric(df)
    return df


def parse_vendor_central_report(uploaded_file) -> pd.DataFrame:
    """
    Parse a Vendor Central ASIN Sales report.
    Returns a normalised DataFrame with canonical column names.
    """
    df = _read_file(uploaded_file)
    df = _normalise_columns(df, VENDOR_COLUMN_ALIASES)
    df = _clean_numeric(df)
    return df


def validate_ads_report(df: pd.DataFrame) -> list:
    """Return list of missing critical columns."""
    required = ["spend", "ad_sales"]
    return [c for c in required if c not in df.columns]


def validate_vendor_report(df: pd.DataFrame) -> list:
    """Return list of missing critical columns."""
    required = ["ordered_revenue"]
    return [c for c in required if c not in df.columns]
