"""
services/processing_service.py — DuckDB-accelerated analytics layer.

Why DuckDB?
-----------
DuckDB is an in-process OLAP engine that:
  * Reads Parquet/CSV directly without loading into Python memory
  * Executes aggregations in parallel using all CPU cores
  * Uses vectorized execution with SIMD instructions
  * Supports SQL on Pandas DataFrames (zero-copy via Arrow)
  * Has a free, embedded deployment model (no server needed)

For a 400 MB / 1M-row CSV, DuckDB aggregations are typically 5–20× faster
than equivalent pandas groupby operations.

This service wraps the heavy aggregations from metrics.py, insights.py, and
trends.py with DuckDB SQL equivalents.  It falls back to the pandas path if
DuckDB is not installed or if the DataFrame is small.

Usage:
    from services.processing_service import ProcessingService
    svc = ProcessingService(df)
    metrics  = svc.ads_metrics()
    campaign = svc.campaign_breakdown()
    trend    = svc.monthly_trend()
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

try:
    import duckdb
    _HAS_DUCKDB = True
except ImportError:
    _HAS_DUCKDB = False

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import settings

log = logging.getLogger(__name__)

# Row threshold below which we skip DuckDB overhead and use pandas directly
_DUCKDB_MIN_ROWS = 50_000


class ProcessingService:
    """
    Unified analytics layer over a normalised ads DataFrame.

    Automatically chooses DuckDB (fast, parallel) or pandas (small data).
    All existing metric names and column names are preserved exactly so that
    the rest of the app (metrics.py, insights.py) continues to work unchanged.
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self._df   = df
        self._conn: Optional["duckdb.DuckDBPyConnection"] = None
        self._use_duck = (
            _HAS_DUCKDB
            and len(df) >= _DUCKDB_MIN_ROWS
        )
        if self._use_duck:
            self._conn = duckdb.connect(":memory:")
            self._conn.execute(f"SET threads TO {settings.duckdb_threads}")
            self._conn.execute(f"SET memory_limit = '{settings.duckdb_memory_limit}'")
            # Register the DataFrame as a virtual table — zero-copy via Arrow
            self._conn.register("ads", df)
            log.info("ProcessingService: using DuckDB (%d rows)", len(df))
        else:
            log.info("ProcessingService: using pandas (%d rows)", len(df))

    def close(self) -> None:
        """Release DuckDB connection."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def __del__(self) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sql(self, query: str) -> pd.DataFrame:
        """Execute a DuckDB SQL query and return a DataFrame."""
        return self._conn.execute(query).df()

    def _col(self, name: str) -> bool:
        """Check if column exists in the DataFrame."""
        return name in self._df.columns

    def _safe_sum(self, col: str) -> float:
        return float(self._df[col].sum()) if self._col(col) else 0.0

    # ------------------------------------------------------------------
    # Top-level metrics
    # ------------------------------------------------------------------

    def ads_metrics(self) -> dict:
        """
        Compute overall aggregated KPIs.
        DuckDB path: single SQL query over all rows.
        Pandas path: single df[cols].sum() call.
        """
        if not self._use_duck:
            return self._pandas_ads_metrics()

        sum_cols = [c for c in [
            "impressions", "clicks", "spend", "ad_sales", "ad_orders",
            "ad_orders_ntb", "sales_ntb", "ad_sales_longterm",
        ] if self._col(c)]

        if not sum_cols:
            return {}

        select = ", ".join(f'SUM("{c}") AS "{c}"' for c in sum_cols)
        row = self._sql(f"SELECT {select} FROM ads").iloc[0]

        def g(col):
            return float(row[col]) if col in row else 0.0

        return self._derive_ads_metrics(g)

    def _pandas_ads_metrics(self) -> dict:
        sum_cols = [c for c in [
            "impressions", "clicks", "spend", "ad_sales", "ad_orders",
            "ad_orders_ntb", "sales_ntb", "ad_sales_longterm",
        ] if self._col(c)]
        totals = self._df[sum_cols].sum() if sum_cols else pd.Series(dtype=float)

        def g(col):
            return float(totals[col]) if col in totals else 0.0

        return self._derive_ads_metrics(g)

    @staticmethod
    def _derive_ads_metrics(g) -> dict:
        """Compute derived KPIs from raw sums — shared by DuckDB and pandas paths."""
        m = {
            "total_impressions":       g("impressions"),
            "total_clicks":            g("clicks"),
            "total_spend":             g("spend"),
            "total_ad_sales":          g("ad_sales"),
            "total_ad_orders":         g("ad_orders"),
            "total_ad_orders_ntb":     g("ad_orders_ntb"),
            "total_ad_sales_ntb":      g("sales_ntb"),
            "total_ad_sales_longterm": g("ad_sales_longterm"),
        }
        s, a, c, i, o, ntb, lt = (
            m["total_spend"], m["total_ad_sales"], m["total_clicks"],
            m["total_impressions"], m["total_ad_orders"],
            m["total_ad_orders_ntb"], m["total_ad_sales_longterm"],
        )
        m["overall_acos"]   = round(s / a * 100, 2) if a > 0 else None
        m["overall_roas"]   = round(a / s, 2)        if s > 0 and a > 0 else None
        m["overall_ctr"]    = round(c / i * 100, 4)  if i > 0 and c > 0 else None
        m["overall_cpc"]    = round(s / c, 4)         if c > 0 else None
        m["conversion_rate"]= round(o / c * 100, 2)  if c > 0 and o > 0 else None
        m["ntb_order_pct"]  = round(ntb / o * 100, 1) if o > 0 and ntb > 0 else None
        m["longterm_roas"]  = round(lt / s, 2)        if s > 0 and lt > 0 else None
        m["cost_per_order"] = round(s / o, 2)         if o > 0 and s > 0 else None
        return m

    # ------------------------------------------------------------------
    # Campaign breakdown
    # ------------------------------------------------------------------

    def campaign_breakdown(self, group_col: Optional[str] = None) -> pd.DataFrame:
        if group_col is None:
            group_col = next(
                (c for c in ["campaign_name", "campaign_type", "targeting", "ad_group_name"]
                 if self._col(c)), None
            )
        if group_col is None:
            return pd.DataFrame()

        sum_cols = [c for c in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"]
                    if self._col(c)]

        if not self._use_duck:
            return self._pandas_groupby(group_col, sum_cols, sort_col="spend")

        select = ", ".join(f'SUM("{c}") AS "{c}"' for c in sum_cols)
        result = self._sql(
            f'SELECT "{group_col}", {select} FROM ads GROUP BY "{group_col}"'
        )
        return self._add_derived(result).sort_values("spend", ascending=False)

    # ------------------------------------------------------------------
    # ASIN breakdown
    # ------------------------------------------------------------------

    def asin_ads_breakdown(self) -> pd.DataFrame:
        if not self._col("asin"):
            return pd.DataFrame()
        sum_cols = [c for c in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"]
                    if self._col(c)]

        if not self._use_duck:
            return self._pandas_groupby("asin", sum_cols, sort_col="ad_sales")

        select = ", ".join(f'SUM("{c}") AS "{c}"' for c in sum_cols)
        result = self._sql(
            f'SELECT "asin", {select} FROM ads GROUP BY "asin"'
        )
        return self._add_derived(result).sort_values("ad_sales", ascending=False)

    # ------------------------------------------------------------------
    # Monthly trend
    # ------------------------------------------------------------------

    def monthly_trend(self, date_col: str = "_date") -> pd.DataFrame:
        """
        Return monthly aggregated spend/sales trend.
        Expects the DataFrame to already have a parsed '_date' column.
        """
        if date_col not in self._df.columns:
            return pd.DataFrame()

        work = self._df.copy()
        work["_month"] = pd.to_datetime(work[date_col]).dt.to_period("M")

        sum_cols = [c for c in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"]
                    if self._col(c)]
        agg = {c: "sum" for c in sum_cols}
        trend = work.groupby("_month", sort=True).agg(agg).reset_index()
        trend["_period_dt"] = trend["_month"].dt.to_timestamp()

        if "spend" in trend.columns and "ad_sales" in trend.columns:
            safe_s = trend["ad_sales"].replace(0, np.nan)
            safe_p = trend["spend"].replace(0, np.nan)
            trend["acos_%"] = (trend["spend"] / safe_s * 100).round(2)
            trend["roas"]   = (trend["ad_sales"] / safe_p).round(2)

        return trend.rename(columns={"_month": "_period"}).sort_values("_period_dt")

    # ------------------------------------------------------------------
    # Match type / bid strategy / ad product
    # ------------------------------------------------------------------

    def _grouped_breakdown(self, group_col: str, sort_col: str = "spend") -> pd.DataFrame:
        if not self._col(group_col):
            return pd.DataFrame()
        sum_cols = [c for c in ["spend", "ad_sales", "impressions", "clicks", "ad_orders"]
                    if self._col(c)]

        if not self._use_duck:
            return self._pandas_groupby(group_col, sum_cols, sort_col=sort_col)

        select = ", ".join(f'SUM("{c}") AS "{c}"' for c in sum_cols)
        result = self._sql(
            f'SELECT "{group_col}", {select} FROM ads GROUP BY "{group_col}"'
        )
        return self._add_derived(result).sort_values(sort_col, ascending=False)

    def match_type_breakdown(self) -> pd.DataFrame:
        return self._grouped_breakdown("match_type")

    def bid_strategy_breakdown(self) -> pd.DataFrame:
        return self._grouped_breakdown("bid_strategy")

    def ad_product_breakdown(self) -> pd.DataFrame:
        result = self._grouped_breakdown("campaign_type")
        if not result.empty:
            result = result.rename(columns={"campaign_type": "ad_product"})
            if "spend" in result.columns:
                total = result["spend"].sum()
                result["spend_share_%"] = (result["spend"] / total * 100).round(1) if total > 0 else 0.0
        return result

    # ------------------------------------------------------------------
    # Internal pandas helpers
    # ------------------------------------------------------------------

    def _pandas_groupby(
        self, group_col: str, sum_cols: list, sort_col: str = "spend"
    ) -> pd.DataFrame:
        agg = {c: "sum" for c in sum_cols}
        result = self._df.groupby(group_col, sort=False).agg(agg).reset_index()
        result = self._add_derived(result)
        if sort_col in result.columns:
            result = result.sort_values(sort_col, ascending=False)
        return result

    @staticmethod
    def _add_derived(df: pd.DataFrame) -> pd.DataFrame:
        """Add acos_%, roas, cpc, cvr_% derived columns in-place."""
        if "spend" in df.columns and "ad_sales" in df.columns:
            df["acos_%"] = (df["spend"]    / df["ad_sales"].replace(0, np.nan) * 100).round(2)
            df["roas"]   = (df["ad_sales"] / df["spend"].replace(0, np.nan)).round(2)
        if "spend" in df.columns and "clicks" in df.columns:
            df["cpc"]    = (df["spend"]    / df["clicks"].replace(0, np.nan)).round(4)
        if "clicks" in df.columns and "ad_orders" in df.columns:
            df["cvr_%"]  = (df["ad_orders"]/ df["clicks"].replace(0, np.nan) * 100).round(2)
        return df


# ---------------------------------------------------------------------------
# Vendor Central processing
# ---------------------------------------------------------------------------

class VendorProcessingService:
    """Analytics layer for Vendor Central ASIN sales data."""

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def _col(self, c: str) -> bool:
        return c in self._df.columns

    def vendor_metrics(self) -> dict:
        sum_cols = [c for c in ["ordered_revenue", "shipped_revenue", "ordered_units", "shipped_units"]
                    if self._col(c)]
        totals = self._df[sum_cols].sum() if sum_cols else pd.Series(dtype=float)

        def g(c):
            return float(totals[c]) if c in totals else 0.0

        m = {
            "total_ordered_revenue": g("ordered_revenue"),
            "total_shipped_revenue": g("shipped_revenue"),
            "total_ordered_units":   g("ordered_units"),
            "total_shipped_units":   g("shipped_units"),
        }
        if m["total_ordered_units"] > 0 and m["total_ordered_revenue"] > 0:
            m["avg_selling_price"] = round(m["total_ordered_revenue"] / m["total_ordered_units"], 2)
        else:
            m["avg_selling_price"] = None
        return m

    def asin_breakdown(self) -> pd.DataFrame:
        if not self._col("asin"):
            return pd.DataFrame()
        sum_cols = {c: "sum" for c in ["ordered_revenue", "shipped_revenue", "ordered_units", "shipped_units"]
                    if self._col(c)}
        extra = [c for c in ["product_title", "category", "brand"] if self._col(c)]
        result = self._df.groupby("asin", sort=False).agg(sum_cols).reset_index()
        if extra:
            first_vals = self._df.groupby("asin", sort=False)[extra].first().reset_index()
            result = result.merge(first_vals, on="asin", how="left")
        if self._col("ordered_units") and self._col("ordered_revenue"):
            result["avg_price"] = (
                result["ordered_revenue"] / result["ordered_units"].replace(0, np.nan)
            ).round(2)
        return result.sort_values("ordered_revenue", ascending=False)
