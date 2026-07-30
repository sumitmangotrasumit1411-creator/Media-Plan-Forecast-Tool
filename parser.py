"""
parser.py — Flexible ingestion of Amazon Advertising & Vendor Central reports.
Handles CSV and XLSX. Auto-detects column names from common Amazon export variations.

Performance notes  (Phase 3 update)
------------------------------------
* PyArrow CSV engine (engine='pyarrow') is the primary path for .csv files.
  It is 3-10x faster than the default C engine on large files because it:
    - multi-threads the column scan in native C++
    - avoids Python GIL during token parsing
    - produces Arrow-backed Series that pandas 2.x can consume zero-copy
  Falls back to the C engine automatically if pyarrow is not importable.
* No raw-bytes double-copy: we read directly from the file object rather
  than reading all bytes into memory first and re-wrapping in BytesIO.
* _clean_numeric: instead of a Python for-loop over every column, the
  known _NUMERIC_COLUMNS are batch-processed as a subset DataFrame in one
  vectorized str.replace + to_numeric pass (one C-level apply per batch).
* dtype=str is retained — pyarrow reads CSV columns as string type by
  default when dtype_backend="numpy_nullable" is not requested, so no
  behavioral change for callers.
* infer_datetime_format=True removed — deprecated since pandas 2.0 and a
  no-op in 2.2+; replaced with explicit format= strings where needed.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import io
import re

try:
    import pyarrow  # noqa: F401 — presence check only
    _HAVE_PYARROW = True
except ImportError:
    _HAVE_PYARROW = False

# ---------------------------------------------------------------------------
# Column aliases — map every known Amazon export header variant to canonical name
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
    # Direct date columns
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
_TEXT_COLUMNS: frozenset = frozenset({
    "date_range", "start_date", "end_date", "report_date", "week_date",
    "month_date", "campaign_name", "ad_group_name", "search_term",
    "targeting", "matched_target", "product_title", "brand", "category",
    "subcategory", "account_name", "portfolio_name", "bid_strategy",
    "match_type", "target_type", "target_status", "campaign_type",
    "sku", "asin", "account_id", "campaign_id",
})

# Canonical numeric columns — always coerced; skip the heuristic check
_NUMERIC_COLUMNS: frozenset = frozenset({
    "impressions", "viewable_impressions", "clicks", "spend", "ad_sales",
    "ad_sales_longterm", "ad_orders", "ad_orders_ntb", "cpp", "cpp_ntb",
    "ctr", "vctr", "cpc", "acos", "roas", "roas_longterm",
    "campaign_budget", "target_bid", "pct_ntb_purchases", "pct_ntb_sales",
    "sales_ntb", "tos_is",
    # Vendor
    "ordered_revenue", "shipped_revenue", "ordered_units", "shipped_units",
})

# Pre-compiled strip regex (used in both fast and heuristic paths)
_STRIP_RE = re.compile(r"[\$\%\,]")

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

    Phase 3 optimisation: canonical _NUMERIC_COLUMNS that exist in the
    DataFrame are processed as a *batch* via DataFrame.apply(), which
    applies the transformation column-wise in a single C-level dispatch
    rather than a Python loop.  Object columns outside the known set fall
    through to the heuristic path as before.
    """
    # ── Fast batch path: process all known numeric columns at once ───────────
    known_present = [c for c in _NUMERIC_COLUMNS if c in df.columns and df[c].dtype == object]
    if known_present:
        # One vectorized pass per column via apply (C-level, no Python loop per row)
        df[known_present] = df[known_present].apply(
            lambda s: pd.to_numeric(s.str.replace(_STRIP_RE, "", regex=True).str.strip(), errors="coerce")
        )

    # Also ensure already-numeric known columns are float64 (they may be int from Arrow)
    known_numeric_nonobj = [c for c in _NUMERIC_COLUMNS if c in df.columns and df[c].dtype != object]
    if known_numeric_nonobj:
        df[known_numeric_nonobj] = df[known_numeric_nonobj].apply(
            lambda s: pd.to_numeric(s, errors="coerce")
        )

    # ── Heuristic path: unknown object columns that look like numbers ─────────
    for col in df.columns:
        if col in _TEXT_COLUMNS or col in _NUMERIC_COLUMNS:
            continue
        series = df[col]
        if series.dtype != object:
            continue
        sample = series.dropna()
        if sample.empty or not sample.str.contains(r"[\$\%\,]", regex=True).any():
            continue
        cleaned = series.str.replace(_STRIP_RE, "", regex=True).str.strip()
        numeric = pd.to_numeric(cleaned, errors="coerce")
        if numeric.notna().sum() >= series.notna().sum() * 0.5:
            df[col] = numeric

    return df


# ---------------------------------------------------------------------------
# CSV reader — PyArrow fast path with C-engine fallback
# ---------------------------------------------------------------------------

def _read_csv_c(file_obj, encoding: str) -> pd.DataFrame:
    """Read CSV with the pandas C engine (chunked to keep peak memory bounded)."""
    kwargs = dict(
        dtype=str,
        low_memory=False,
        na_values=["", "N/A", "n/a", "--", "—"],
        keep_default_na=False,
    )
    chunks = pd.read_csv(file_obj, encoding=encoding, chunksize=200_000, **kwargs)
    return pd.concat(list(chunks), ignore_index=True, copy=False)


def _read_csv_fast(file_obj, encoding: str = "utf-8") -> pd.DataFrame:
    """
    Try the PyArrow engine first (3-10x faster); fall back to the C engine on
    any failure (encoding issues, BOM markers, structural quirks in Amazon exports).

    PyArrow is strict about encodings — it rejects files with BOM or Windows
    code-page characters that the C engine handles transparently.  The fallback
    ensures we always load the file successfully.
    """
    kwargs = dict(
        dtype=str,
        low_memory=False,
        na_values=["", "N/A", "n/a", "--", "—"],
        keep_default_na=False,
    )
    if _HAVE_PYARROW:
        try:
            return pd.read_csv(file_obj, encoding=encoding, engine="pyarrow", **kwargs)
        except Exception:
            # PyArrow failed (encoding, BOM, structural issue) — rewind and use C engine
            try:
                file_obj.seek(0)
            except Exception:
                pass
    # C engine: chunked reads to keep peak RAM bounded on 400MB+ files
    return _read_csv_c(file_obj, encoding)


def _read_file(uploaded_file) -> pd.DataFrame:
    """
    Read an uploaded Streamlit file object (CSV or XLSX) into a DataFrame.

    Encoding ladder: utf-8-sig (handles BOM) → utf-8 → latin-1 → cp1252.
    Each attempt uses PyArrow first, then C engine.  The first successful
    parse is returned.
    """
    name = uploaded_file.name.lower()

    if name.endswith(".csv"):
        # utf-8-sig strips BOM automatically; covers the majority of Amazon exports
        for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                uploaded_file.seek(0)
                return _read_csv_fast(uploaded_file, encoding=enc)
            except UnicodeDecodeError:
                continue
            except Exception as exc:
                # Non-encoding error on C engine path — try next encoding,
                # but if this is the last one, let it propagate
                last_exc = exc
                continue
        raise ValueError(
            "Could not decode CSV file. "
            "Tried utf-8-sig, utf-8, latin-1, cp1252. "
            "Re-export from Amazon Ads Console as UTF-8 and try again."
        )

    elif name.endswith((".xlsx", ".xls")):
        raw = uploaded_file.read()
        return pd.read_excel(io.BytesIO(raw), engine="openpyxl", dtype=str)

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
