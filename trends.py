"""
trends.py — Time-series aggregation for spend, sales, ACOS, and ROAS trends.

Date resolution order (first match wins):
  1. start_date  — mapped from "Start Date" column
  2. report_date — mapped from "Report Date" / "Date" / "Day"
  3. week_date   — mapped from "Week" / "Week Ending"
  4. month_date  — mapped from "Month"
  5. date_range  — fall back to extracting start of range string

Performance notes
-----------------
* _resolve_date_column now uses pd.to_datetime() vectorized parsing for direct
  date columns — one C-level call instead of a Python-level .apply() over 1M rows.
* date_range parsing uses vectorized str.extract() to pull the start-date portion
  with a compiled regex, then a single pd.to_datetime() call.  The full-year-range
  filter uses a vectorized end-date extraction + timedelta comparison instead of
  per-row Python logic.
* build_trend_df uses sort=False on groupby — the final sort_values call is the
  only sort needed.
"""

from __future__ import annotations
import pandas as pd
import numpy as np
import re


# ---------------------------------------------------------------------------
# Date parsing helpers
# ---------------------------------------------------------------------------

# Pre-compiled regex patterns for vectorized extraction
_RE_ISO_RANGE   = re.compile(r"(\d{4}-\d{2}-\d{2})\s*[-–]\s*(\d{4}-\d{2}-\d{2})")
_RE_MONTH_RANGE = re.compile(
    r"([A-Za-z]+\s+\d{1,2},?\s*\d{4})\s*[-–]\s*([A-Za-z]+\s+\d{1,2},?\s*\d{4})"
)


def _parse_date_range_series(series: pd.Series) -> pd.Series:
    """
    Vectorized extraction of start dates from a Series of date-range strings.

    Handles:
      '2025-01-01 - 2025-01-31'          → 2025-01-01
      'Jan 1, 2025 - Jan 31, 2025'       → 2025-01-01
      'Jan 1, 2025 - Dec 31, 2025'       → NaT  (full-year range — not useful)

    Replaces the original per-row _parse_date_range + .apply() pattern.
    """
    # Work on string series; non-strings become NaN
    s = series.astype(str).str.strip()
    result = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")

    # ── ISO format: 2025-01-01 - 2025-01-31 ─────────────────────────────────
    iso = s.str.extract(_RE_ISO_RANGE, expand=True)
    iso_valid = iso[0].notna()
    if iso_valid.any():
        starts = pd.to_datetime(iso.loc[iso_valid, 0], errors="coerce")
        ends   = pd.to_datetime(iso.loc[iso_valid, 1], errors="coerce")
        # Discard full-year ranges (≥350 days) — they are report-level summaries
        keep = (ends - starts).dt.days < 350
        result.loc[iso_valid] = starts.where(keep)

    # ── Month-name format: Jan 1, 2025 - Dec 31, 2025 ───────────────────────
    mn = s.str.extract(_RE_MONTH_RANGE, expand=True)
    mn_valid = mn[0].notna() & result.isna()   # only fill gaps
    if mn_valid.any():
        starts = pd.to_datetime(mn.loc[mn_valid, 0], errors="coerce")
        ends   = pd.to_datetime(mn.loc[mn_valid, 1], errors="coerce")
        keep = (ends - starts).dt.days < 350
        result.loc[mn_valid] = starts.where(keep)

    # ── Single-date fallback ─────────────────────────────────────────────────
    still_na = result.isna() & iso[0].isna() & mn[0].isna()
    if still_na.any():
        result.loc[still_na] = pd.to_datetime(s.loc[still_na], errors="coerce")

    return result


def _resolve_date_column(df: pd.DataFrame) -> "pd.Series | None":
    """
    Return a Series of dates by trying columns in priority order.
    All parsing is vectorized — no Python-level row iteration.
    Returns None if no usable date column exists.
    """
    # Priority: direct date columns first
    for col in ["start_date", "report_date", "week_date", "month_date"]:
        if col in df.columns:
            parsed = pd.to_datetime(df[col], errors="coerce", infer_datetime_format=True)
            if parsed.notna().sum() > 0:
                return parsed

    # Fall back to date_range string parsing (vectorized)
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

    Multi-year data is preserved — callers can filter by year as needed.
    """
    work = df.copy()
    date_series = _resolve_date_column(work)

    if date_series is None:
        return pd.DataFrame()

    work["_date"] = date_series
    work = work.dropna(subset=["_date"])

    if work.empty:
        return pd.DataFrame()

    work["_period"] = work["_date"].dt.to_period(freq)

    agg = {c: "sum" for c in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"] if c in work.columns}
    if not agg:
        return pd.DataFrame()

    trend = work.groupby("_period", sort=True).agg(agg).reset_index()
    trend["_period_dt"] = trend["_period"].dt.to_timestamp()

    if "spend" in trend.columns and "ad_sales" in trend.columns:
        safe_sales  = trend["ad_sales"].replace(0, np.nan)
        safe_spend  = trend["spend"].replace(0, np.nan)
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
    """Monthly spend trend broken down by ad product (SP / SB / SD)."""
    if "campaign_type" not in df.columns:
        return pd.DataFrame()

    work = df.copy()
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
