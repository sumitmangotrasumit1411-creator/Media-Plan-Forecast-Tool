"""
metrics.py — Extract and aggregate key performance metrics from parsed reports.

Performance notes  (Phase 3 update)
--------------------------------------
* extract_ads_metrics: single vectorized df[cols].sum() — unchanged.
* campaign_breakdown / asin_ads_breakdown / asin_vendor_breakdown: for DataFrames
  larger than _DUCKDB_THRESHOLD rows, a DuckDB in-process SQL query replaces the
  pandas groupby.  DuckDB uses vectorized SIMD execution and multi-threading,
  giving 5-20x speedup on groupby-agg over 100k+ rows.
  For smaller frames the pandas path is used as before (lower overhead).
* _add_derived_ad_cols unchanged — already vectorized, no benefit from DuckDB here.
* DuckDB is an optional dependency; if not importable the pandas path runs instead.
"""

import pandas as pd
import numpy as np

try:
    import duckdb as _duckdb
    _HAVE_DUCKDB = True
except ImportError:
    _HAVE_DUCKDB = False

# Use DuckDB for groupby when the DataFrame has more than this many rows
_DUCKDB_THRESHOLD = 100_000


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
# DuckDB groupby helper
# ---------------------------------------------------------------------------

def _duckdb_groupby(
    df: pd.DataFrame,
    group_col: str,
    sum_cols: list,
    _con=None,          # optional: pass an open DuckDB connection to avoid open/close overhead
) -> pd.DataFrame:
    """
    Execute a GROUP BY + SUM via DuckDB when available.

    DuckDB registers the DataFrame as a virtual table (zero-copy Arrow scan)
    and runs a single multi-threaded aggregation.  The result is returned as
    a pandas DataFrame.  Falls back to pandas groupby if DuckDB raises.

    Pass _con to reuse an already-open connection (avoids repeated connect()
    overhead when calling this function many times in the same request).
    """
    if not _HAVE_DUCKDB or len(df) < _DUCKDB_THRESHOLD:
        agg = {c: "sum" for c in sum_cols if c in df.columns}
        return df.groupby(group_col, sort=False).agg(agg).reset_index()

    cols_present = [c for c in sum_cols if c in df.columns]
    if not cols_present:
        return df[[group_col]].drop_duplicates()

    sum_exprs = ", ".join(f'SUM("{c}") AS "{c}"' for c in cols_present)
    sql = f'SELECT "{group_col}", {sum_exprs} FROM df GROUP BY "{group_col}"'

    own_con = _con is None
    try:
        con = _duckdb.connect() if own_con else _con
        result = con.execute(sql).df()
        return result
    except Exception:
        agg = {c: "sum" for c in cols_present}
        return df.groupby(group_col, sort=False).agg(agg).reset_index()
    finally:
        if own_con and _HAVE_DUCKDB:
            try:
                con.close()
            except Exception:
                pass


def _duckdb_all_breakdowns(df: pd.DataFrame) -> dict:
    """
    Run ALL DuckDB groupby operations for the ads DataFrame in a single
    open connection — eliminates repeated connect/close overhead.

    Returns a dict with keys: campaign_df, asin_df, match_df, bid_df, ad_prod_df
    Falls back gracefully per-operation if DuckDB raises.
    """
    results = {}

    # Columns needed across all groupbys — project to a slim frame first
    _ALL_SUM = ["spend", "ad_sales", "impressions", "clicks", "ad_orders",
                "ad_orders_ntb", "ad_sales_longterm"]
    _GROUP_COLS = ["campaign_name", "campaign_type", "ad_group_name",
                   "targeting", "asin", "match_type", "bid_strategy"]

    slim_cols = list(set(
        [c for c in _ALL_SUM if c in df.columns] +
        [c for c in _GROUP_COLS if c in df.columns]
    ))
    slim = df[slim_cols] if slim_cols else df

    if not _HAVE_DUCKDB or len(df) < _DUCKDB_THRESHOLD:
        # pandas path — no connection needed
        return results   # caller will fall through to individual functions

    try:
        con = _duckdb.connect()

        # Register the slim frame once — all queries below reuse it
        con.register("slim", slim)

        _sum_cols = [c for c in _ALL_SUM if c in slim.columns]
        _sum_exprs = ", ".join(f'SUM("{c}") AS "{c}"' for c in _sum_cols)

        def _q(group_col):
            if group_col not in slim.columns:
                return None
            try:
                return con.execute(
                    f'SELECT "{group_col}", {_sum_exprs} FROM slim GROUP BY "{group_col}"'
                ).df()
            except Exception:
                return None

        results["campaign_raw"] = _q(
            next((c for c in ["campaign_name", "campaign_type", "ad_group_name", "targeting"]
                  if c in slim.columns), None)
        )
        results["asin_raw"]     = _q("asin")
        results["match_raw"]    = _q("match_type")
        results["bid_raw"]      = _q("bid_strategy")
        results["ad_prod_raw"]  = _q("campaign_type")

        con.close()
    except Exception:
        pass   # caller falls back to individual pandas groupbys

    return results


# ---------------------------------------------------------------------------
# Amazon Ads Metrics
# ---------------------------------------------------------------------------

def extract_ads_metrics(df: pd.DataFrame) -> dict:
    """
    Compute top-level aggregated metrics from the Amazon Ads report.
    Single vectorized df[cols].sum() call — one pass over the DataFrame.
    """
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
    """
    Group by campaign_name and aggregate spend + sales.
    Uses DuckDB for >100k-row DataFrames, pandas otherwise.
    """
    group_col = next(
        (c for c in ["campaign_name", "campaign_type", "targeting", "ad_group_name"]
         if c in df.columns),
        None,
    )
    if group_col is None:
        return pd.DataFrame()

    sum_cols = ["spend", "ad_sales", "impressions", "clicks", "ad_orders"]
    result = _duckdb_groupby(df, group_col, sum_cols)
    result = _add_derived_ad_cols(result)

    sort_col = "spend" if "spend" in result.columns else result.columns[-1]
    return result.sort_values(sort_col, ascending=False)


def asin_ads_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-ASIN aggregate from the ads report.
    Uses DuckDB for >100k-row DataFrames, pandas otherwise.
    """
    if "asin" not in df.columns:
        return pd.DataFrame()

    sum_cols = ["spend", "ad_sales", "impressions", "clicks", "ad_orders"]
    result = _duckdb_groupby(df, "asin", sum_cols)
    result = _add_derived_ad_cols(result)

    sort_col = "ad_sales" if "ad_sales" in result.columns else result.columns[-1]
    return result.sort_values(sort_col, ascending=False)


# ---------------------------------------------------------------------------
# Vendor Central Metrics
# ---------------------------------------------------------------------------

def extract_vendor_metrics(df: pd.DataFrame) -> dict:
    """Compute top-level aggregated metrics from the Vendor Central report."""
    sum_cols = [c for c in [
        "ordered_revenue", "shipped_revenue", "ordered_units", "shipped_units",
        "glance_views",
    ] if c in df.columns]
    totals = df[sum_cols].sum() if sum_cols else pd.Series(dtype=float)

    def _get(col):
        return float(totals[col]) if col in totals else 0.0

    m = {
        "total_ordered_revenue": _get("ordered_revenue"),
        "total_shipped_revenue": _get("shipped_revenue"),
        "total_ordered_units":   _get("ordered_units"),
        "total_shipped_units":   _get("shipped_units"),
        "total_glance_views":    _get("glance_views"),
    }

    # avg_selling_price: prefer direct column (new Vendor format has it as a column),
    # fall back to computing from revenue / units
    if "avg_selling_price" in df.columns:
        asp_val = pd.to_numeric(df["avg_selling_price"], errors="coerce").mean()
        m["avg_selling_price"] = round(float(asp_val), 2) if pd.notna(asp_val) else None
    elif m["total_ordered_units"] > 0 and m["total_ordered_revenue"] > 0:
        m["avg_selling_price"] = round(m["total_ordered_revenue"] / m["total_ordered_units"], 2)
    else:
        m["avg_selling_price"] = None

    return m


def asin_vendor_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-ASIN revenue and units from Vendor Central.
    Uses DuckDB for >100k-row DataFrames, pandas otherwise.
    """
    if "asin" not in df.columns:
        return pd.DataFrame()

    sum_cols = ["ordered_revenue", "shipped_revenue", "ordered_units", "shipped_units"]
    extra_cols = [c for c in ["product_title", "category", "brand"] if c in df.columns]

    result = _duckdb_groupby(df, "asin", sum_cols)

    if extra_cols:
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
