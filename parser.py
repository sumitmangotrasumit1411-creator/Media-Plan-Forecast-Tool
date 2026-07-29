"""
parser.py — Flexible ingestion of Amazon Advertising & Vendor Central reports.
Handles CSV and XLSX. Auto-detects column names from common Amazon export variations.

Performance notes
-----------------
* Large CSVs (400MB+) are read with dtype=str for all columns to avoid pandas doing
  its own slow type-inference on 1M rows. Numeric coercion happens in one vectorized
  pass with pd.to_numeric() on only the columns that need it.
* _clean_numeric now uses vectorized str.replace + pd.to_numeric instead of
  iterating row-by-row.
* The 50%-success guard prevents accidental coercion of text columns.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import io
import re

# ---------------------------------------------------------------------------
# Column aliases — map every known Amazon export header variant to a canonical name
# ---------------------------------------------------------------------------

AD_COLUMN_ALIASES: dict = {
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
    "total cost": "spend",
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
    "purchases": "ad_orders",
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
    "ad product": "campaign_type",
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
    # Direct date columns — tried first in trends.py before date_range fallback
    "start date": "start_date",
    "end date": "end_date",
    "report date": "report_date",
    "date": "report_date",
    "day": "report_date",
    "week": "week_date",
    "week ending": "week_date",
    "week start": "week_date",
    "month": "month_date",
    "reporting date": "report_date",
    "ad date": "report_date",
    "advertiser account id": "account_id",
    "advertiser account name": "account_name",
    "top-of-search impression share (is)": "tos_is",
    "percent of purchases new to brand": "pct_ntb_purchases",
    "percent of sales new to brand": "pct_ntb_sales",
    "sales (new to brand)": "sales_ntb",
}

VENDOR_COLUMN_ALIASES: dict = {
    "ordered revenue": "ordered_revenue",
    "ordered product sales": "ordered_revenue",
    "total ordered revenue": "ordered_revenue",
    "shipped revenue": "shipped_revenue",
    "shipped product sales": "shipped_revenue",
    "total shipped revenue": "shipped_revenue",
    "ordered units": "ordered_units",
    "shipped units": "shipped_units",
    "total ordered units": "ordered_units",
    "total shipped units": "shipped_units",
    "asin": "asin",
    "product title": "product_title",
    "product name": "product_title",
    "title": "product_title",
    "category": "category",
    "subcategory": "subcategory",
    "week": "period",
    "month": "period",
    "date": "period",
    "reporting period": "period",
    "brand": "brand",
}

# Columns that must never be coerced to numeric even if they contain $ / % / ,
_TEXT_COLUMNS: set = {
    "date_range", "start_date", "end_date", "report_date", "week_date",
    "month_date", "campaign_name", "ad_group_name", "search_term",
    "targeting", "matched_target", "product_title", "brand", "category",
    "subcategory", "account_name", "portfolio_name", "bid_strategy",
    "match_type", "target_type", "target_status", "campaign_type",
    "sku", "asin", "account_id", "campaign_id",
}

# Canonical numeric columns — these are always coerced; skip the heuristic check
_NUMERIC_COLUMNS: set = {
    "impressions", "viewable_impressions", "clicks", "spend", "ad_sales",
    "ad_sales_longterm", "ad_orders", "ad_orders_ntb", "cpp", "cpp_ntb",
    "ctr", "vctr", "cpc", "acos", "roas", "roas_longterm",
    "campaign_budget", "target_bid", "pct_ntb_purchases", "pct_ntb_sales",
    "sales_ntb", "tos_is",
    # Vendor
    "ordered_revenue", "shipped_revenue", "ordered_units", "shipped_units",
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise_columns(df: pd.DataFrame, alias_map: dict) -> pd.DataFrame:
    """Lowercase + strip column names, then map to canonical names."""
    df.columns = [c.strip().lower() for c in df.columns]
    rename = {col: alias_map[col] for col in df.columns if col in alias_map}
    return df.rename(columns=rename)


def _clean_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorized numeric cleaning — strip $/%/, and coerce to float.

    Fast path: canonical numeric columns are coerced directly.
    Heuristic path: object columns that look numeric (contain $/%/,) are
    coerced only if ≥50% of non-null values successfully parse (safety net).
    Known text/date columns are always skipped.
    """
    _STRIP_RE = re.compile(r"[\$\%\,]")

    for col in df.columns:
        if col in _TEXT_COLUMNS:
            continue

        series = df[col]
        if series.dtype != object:
            # Already numeric — just ensure float64
            if col in _NUMERIC_COLUMNS:
                df[col] = pd.to_numeric(series, errors="coerce")
            continue

        # Fast path for known numeric columns
        if col in _NUMERIC_COLUMNS:
            cleaned = series.str.replace(_STRIP_RE, "", regex=True).str.strip()
            df[col] = pd.to_numeric(cleaned, errors="coerce")
            continue

        # Heuristic path — only process if column likely contains numbers
        sample = series.dropna()
        if sample.empty:
            continue
        if not sample.str.contains(r"[\$\%\,]", regex=True).any():
            continue

        cleaned = series.str.replace(_STRIP_RE, "", regex=True).str.strip()
        numeric = pd.to_numeric(cleaned, errors="coerce")
        # Only replace if coercion worked for ≥50% of non-null values
        if numeric.notna().sum() >= series.notna().sum() * 0.5:
            df[col] = numeric

    return df


# Chunk size for large CSV reads — 200k rows at a time (up from 100k)
_CSV_CHUNKSIZE = 200_000


def _read_file(uploaded_file) -> pd.DataFrame:
    """
    Read an uploaded Streamlit file object (CSV or XLSX) into a DataFrame.

    Optimisations vs original:
    - dtype=str on CSV read: avoids pandas slow type-inference on 1M+ rows;
      numeric parsing is done once in _clean_numeric instead.
    - Chunk size doubled to 200k: fewer pd.concat calls on the 400MB file.
    - thousands kwarg removed from read_csv (it conflicts with dtype=str and
      is handled by _clean_numeric's comma stripping anyway).
    """
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()

    if name.endswith(".csv"):
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                buf = io.BytesIO(raw)
                chunks = pd.read_csv(
                    buf,
                    encoding=enc,
                    dtype=str,              # read everything as str → no type-inference
                    chunksize=_CSV_CHUNKSIZE,
                    low_memory=False,
                    na_values=["", "N/A", "n/a", "--", "—"],
                    keep_default_na=False,
                )
                df = pd.concat(chunks, ignore_index=True, copy=False)
                return df
            except Exception:
                continue
        raise ValueError("Could not decode CSV file.")

    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(raw), engine="openpyxl", dtype=str)
        return df

    else:
        raise ValueError(f"Unsupported file format: {uploaded_file.name}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_amazon_ads_report(uploaded_file) -> pd.DataFrame:
    """Parse an Amazon Advertising report. Returns normalised DataFrame."""
    df = _read_file(uploaded_file)
    df = _normalise_columns(df, AD_COLUMN_ALIASES)
    df = _clean_numeric(df)
    return df


def parse_vendor_central_report(uploaded_file) -> pd.DataFrame:
    """Parse a Vendor Central ASIN Sales report. Returns normalised DataFrame."""
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
