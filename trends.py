"""
trends.py — Time-series aggregation for spend, sales, ACOS, and ROAS trends.

Date resolution order (first match wins):
  1. start_date  — mapped from "Start Date" column
  2. report_date — mapped from "Report Date" / "Date" / "Day"
  3. week_date   — mapped from "Week" / "Week Ending"
  4. month_date  — mapped from "Month"
  5. date_range  — fall back to extracting start of range string
"""

from __future__ import annotations
import pandas as pd
import numpy as np
import re


# ---------------------------------------------------------------------------
# Date parsing helpers
# ---------------------------------------------------------------------------

def _parse_date_range(val: str):
    """
    Extract the start date from range strings:
      '2025-01-01 - 2025-01-07'
      'Jan 1, 2025 - Jan 7, 2025'
      'Jan 1, 2025 - Dec 31, 2025'   ← single annual range (returns None — not useful)
    When start == end year and the range spans a full year, return None so the
    caller falls back to seasonal distribution rather than collapsing all rows
    into a single period.
    """
    if not isinstance(val, str):
        return None
    val = val.strip()

    # ISO format: 2025-01-01 - 2025-01-31
    m = re.match(r"(\d{4}-\d{2}-\d{2})\s*[-–]\s*(\d{4}-\d{2}-\d{2})", val)
    if m:
        try:
            start = pd.to_datetime(m.group(1))
            end   = pd.to_datetime(m.group(2))
            # If span is a full year or nearly so, this is a report-level range — skip
            if (end - start).days >= 350:
                return None
            return start
        except Exception:
            return None

    # Month-name format: Jan 1, 2025 - Dec 31, 2025
    m2 = re.match(
        r"([A-Za-z]+\s+\d{1,2},?\s*\d{4})\s*[-–]\s*([A-Za-z]+\s+\d{1,2},?\s*\d{4})",
        val,
    )
    if m2:
        try:
            start = pd.to_datetime(m2.group(1))
            end   = pd.to_datetime(m2.group(2))
            if (end - start).days >= 350:
                return None
            return start
        except Exception:
            return None

    # Single date: try direct parse
    try:
        return pd.to_datetime(val)
    except Exception:
        return None


def _resolve_date_column(df: pd.DataFrame):
    """
    Return a Series of dates by trying columns in priority order.
    Returns None if no usable date column exists.
    """
    priority = ["start_date", "report_date", "week_date", "month_date"]
    for col in priority:
        if col in df.columns:
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().sum() > 0:
                return parsed

    # Fall back to date_range string parsing
    if "date_range" in df.columns:
        parsed = df["date_range"].apply(_parse_date_range)
        parsed = pd.to_datetime(parsed, errors="coerce")
        if parsed.notna().sum() > 0:
            return parsed

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_trend_df(df: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    """
    Aggregate spend, sales, ACOS, ROAS by week (freq='W') or month (freq='M').

    Parameters
    ----------
    df   : normalised ads DataFrame
    freq : 'W' for weekly, 'M' for monthly

    Returns a DataFrame indexed by period with aggregated metrics.
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

    agg = {}
    for col in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"]:
        if col in work.columns:
            agg[col] = "sum"

    if not agg:
        return pd.DataFrame()

    trend = work.groupby("_period").agg(agg).reset_index()
    trend["_period_dt"] = trend["_period"].dt.to_timestamp()

    if "spend" in trend.columns and "ad_sales" in trend.columns:
        trend["acos_%"] = (trend["spend"] / trend["ad_sales"].replace(0, np.nan) * 100).round(2)
        trend["roas"]   = (trend["ad_sales"] / trend["spend"].replace(0, np.nan)).round(2)

    if "spend" in trend.columns and "clicks" in trend.columns:
        trend["cpc"] = (trend["spend"] / trend["clicks"].replace(0, np.nan)).round(4)

    if "clicks" in trend.columns and "impressions" in trend.columns:
        trend["ctr_%"] = (trend["clicks"] / trend["impressions"].replace(0, np.nan) * 100).round(4)

    return trend.sort_values("_period_dt")


def trend_summary(trend_df: pd.DataFrame) -> dict:
    """
    Compute MoM / WoW change for key metrics between last two periods.
    """
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
    """
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

    trend = work.groupby(["_period", "campaign_type"])["spend"].sum().reset_index()
    trend["_period_dt"] = trend["_period"].dt.to_timestamp()
    return trend.sort_values("_period_dt")
