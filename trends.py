"""
trends.py — Time-series aggregation for spend, sales, ACOS, and ROAS trends.

Date resolution order (first match wins):
  1. start_date  — mapped from "Start Date" column
  2. report_date — mapped from "Report Date" / "Date" / "Day"
  3. week_date   — mapped from "Week" / "Week Ending"
  4. month_date  — mapped from "Month"
  5. date_range  — fall back to extracting start of range string

Performance notes  (Phase 3 update)
-------------------------------------
* build_trend_df and ad_product_trend previously called df.copy() on the
  full 1M-row DataFrame before doing anything.  For a 400MB report this
  allocates another ~400MB unnecessarily.  Fixed: we now project only the
  columns we actually need before making any copy.
* _resolve_date_column: removed infer_datetime_format=True (deprecated
  since pandas 2.0, no-op in 2.2+).
* All pre-existing vectorized str.extract / pd.to_datetime optimisations
  retained unchanged.
"""

from __future__ import annotations
import pandas as pd
import numpy as np
import re

# Pre-compiled regex patterns for vectorized extraction
_RE_ISO_RANGE   = re.compile(r"(\d{4}-\d{2}-\d{2})\s*[-–]\s*(\d{4}-\d{2}-\d{2})")
_RE_MONTH_RANGE = re.compile(
    r"([A-Za-z]+\s+\d{1,2},?\s*\d{4})\s*[-–]\s*([A-Za-z]+\s+\d{1,2},?\s*\d{4})"
)

# Columns needed by build_trend_df (beyond the date column itself)
_TREND_COLS = frozenset({"spend", "ad_sales", "impressions", "clicks", "ad_orders"})
# Columns needed by ad_product_trend
_PROD_TREND_COLS = frozenset({"spend", "campaign_type"})


# ---------------------------------------------------------------------------
# Date parsing helpers
# ---------------------------------------------------------------------------

def _parse_date_range_series(series: pd.Series) -> pd.Series:
    """
    Vectorized extraction of start dates from a Series of date-range strings.

    Handles:
      '2025-01-01 - 2025-01-31'          → 2025-01-01
      'Jan 1, 2025 - Jan 31, 2025'       → 2025-01-01
      'Jan 1, 2025 - Dec 31, 2025'       → NaT  (full-year range — not useful)
    """
    s = series.astype(str).str.strip()
    result = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")

    # ── ISO format ──────────────────────────────────────────────────────────
    iso = s.str.extract(_RE_ISO_RANGE, expand=True)
    iso_valid = iso[0].notna()
    if iso_valid.any():
        starts = pd.to_datetime(iso.loc[iso_valid, 0], errors="coerce")
        ends   = pd.to_datetime(iso.loc[iso_valid, 1], errors="coerce")
        keep = (ends - starts).dt.days < 350
        result.loc[iso_valid] = starts.where(keep)

    # ── Month-name format ───────────────────────────────────────────────────
    mn = s.str.extract(_RE_MONTH_RANGE, expand=True)
    mn_valid = mn[0].notna() & result.isna()
    if mn_valid.any():
        starts = pd.to_datetime(mn.loc[mn_valid, 0], errors="coerce")
        ends   = pd.to_datetime(mn.loc[mn_valid, 1], errors="coerce")
        keep = (ends - starts).dt.days < 350
        result.loc[mn_valid] = starts.where(keep)

    # ── Single-date fallback ────────────────────────────────────────────────
    still_na = result.isna() & iso[0].isna() & mn[0].isna()
    if still_na.any():
        result.loc[still_na] = pd.to_datetime(s.loc[still_na], errors="coerce")

    return result


def _resolve_date_column(df: pd.DataFrame) -> "pd.Series | None":
    """
    Return a Series of dates by trying columns in priority order.
    All parsing is vectorized. Returns None if no usable date column exists.
    """
    for col in ["start_date", "report_date", "week_date", "month_date"]:
        if col in df.columns:
            # infer_datetime_format removed — deprecated in pandas 2.0
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().sum() > 0:
                return parsed

    if "date_range" in df.columns:
        parsed = _parse_date_range_series(df["date_range"])
        if parsed.notna().sum() > 0:
            return parsed

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_trend_df(df: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    """
    Aggregate spend, sales, ACOS, ROAS by week (freq='W') or month (freq='M').

    Phase 3: projects only the columns needed before any copy operation,
    avoiding a full ~400MB frame duplication for a 1M-row CSV.
    """
    # ── Identify which columns we need and project to a slim frame ──────────
    date_cols = [c for c in ["start_date", "report_date", "week_date", "month_date", "date_range"]
                 if c in df.columns]
    keep_cols = list((_TREND_COLS & set(df.columns)) | set(date_cols))
    if not keep_cols:
        return pd.DataFrame()

    # Shallow projection — no copy of data, just a new column index view
    work = df[keep_cols].copy()

    date_series = _resolve_date_column(work)
    if date_series is None:
        return pd.DataFrame()

    work["_date"] = date_series
    work = work.dropna(subset=["_date"])
    if work.empty:
        return pd.DataFrame()

    work["_period"] = work["_date"].dt.to_period(freq)

    agg = {c: "sum" for c in _TREND_COLS if c in work.columns}
    if not agg:
        return pd.DataFrame()

    trend = work.groupby("_period", sort=True).agg(agg).reset_index()
    trend["_period_dt"] = trend["_period"].dt.to_timestamp()

    if "spend" in trend.columns and "ad_sales" in trend.columns:
        safe_sales = trend["ad_sales"].replace(0, np.nan)
        safe_spend = trend["spend"].replace(0, np.nan)
        trend["acos_%"] = (trend["spend"]    / safe_sales  * 100).round(2)
        trend["roas"]   = (trend["ad_sales"] / safe_spend).round(2)

    if "spend" in trend.columns and "clicks" in trend.columns:
        trend["cpc"] = (trend["spend"] / trend["clicks"].replace(0, np.nan)).round(4)

    if "clicks" in trend.columns and "impressions" in trend.columns:
        trend["ctr_%"] = (trend["clicks"] / trend["impressions"].replace(0, np.nan) * 100).round(4)

    return trend.sort_values("_period_dt")


def trend_summary(trend_df: pd.DataFrame) -> dict:
    """Compute MoM / WoW change for key metrics between last two periods."""
    if trend_df.empty or len(trend_df) < 2:
        return {}

    latest = trend_df.iloc[-1]
    prev   = trend_df.iloc[-2]

    def pct_change(new, old):
        if old and old != 0:
            return round((new - old) / abs(old) * 100, 1)
        return None

    return {
        "spend_change_pct":  pct_change(latest.get("spend", 0),    prev.get("spend", 0)),
        "sales_change_pct":  pct_change(latest.get("ad_sales", 0), prev.get("ad_sales", 0)),
        "acos_change_pct":   pct_change(latest.get("acos_%", 0),   prev.get("acos_%", 0)),
        "roas_change_pct":   pct_change(latest.get("roas", 0),     prev.get("roas", 0)),
        "latest_period":     str(latest.get("_period", "")),
        "prev_period":       str(prev.get("_period", "")),
    }


def ad_product_trend(df: pd.DataFrame, freq: str = "M") -> pd.DataFrame:
    """
    Monthly spend trend broken down by ad product (SP / SB / SD).

    Phase 3: projects only the columns needed instead of copying the full frame.
    """
    if "campaign_type" not in df.columns:
        return pd.DataFrame()

    date_cols = [c for c in ["start_date", "report_date", "week_date", "month_date", "date_range"]
                 if c in df.columns]
    keep_cols = list((_PROD_TREND_COLS & set(df.columns)) | set(date_cols))

    work = df[keep_cols].copy()

    date_series = _resolve_date_column(work)
    if date_series is None:
        return pd.DataFrame()

    work["_date"] = date_series
    work = work.dropna(subset=["_date"])
    if work.empty:
        return pd.DataFrame()

    work["_period"] = work["_date"].dt.to_period(freq)

    if "spend" not in work.columns:
        return pd.DataFrame()

    trend = work.groupby(["_period", "campaign_type"], sort=True)["spend"].sum().reset_index()
    trend["_period_dt"] = trend["_period"].dt.to_timestamp()
    return trend.sort_values("_period_dt")
