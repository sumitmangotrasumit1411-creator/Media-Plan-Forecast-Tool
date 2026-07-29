"""
components/tables.py — Reusable styled DataFrame table renderers.
"""
from __future__ import annotations
import pandas as pd
import streamlit as st


def styled_dataframe(df: pd.DataFrame, height: int = 360, **kwargs) -> None:
    """Render a plain dataframe with consistent styling."""
    st.dataframe(df, use_container_width=True, height=height, **kwargs)


def campaign_table(df: pd.DataFrame, name_col: str) -> None:
    display_cols = [c for c in [name_col, "spend", "ad_sales", "acos_%", "roas", "cpc", "impressions", "clicks"] if c in df.columns]
    disp = df[display_cols].head(20).copy()
    disp.columns = [c.replace("_", " ").title() for c in disp.columns]
    st.dataframe(disp, use_container_width=True, height=320)


def asin_table(df: pd.DataFrame) -> None:
    display_cols = [c for c in ["asin", "product_title", "ordered_revenue", "spend", "ad_sales",
                                 "tacos_%", "acos_%", "roas", "ordered_units"] if c in df.columns]
    disp = df[display_cols].head(30).copy()
    disp.columns = [c.replace("_", " ").replace("%", "Pct").title() for c in disp.columns]
    st.dataframe(disp, use_container_width=True, height=360)


def scenario_table(full_df: pd.DataFrame) -> None:
    fmt = {
        "Target Revenue ($)":    "${:,.0f}",
        "Target Ad Sales ($)":   "${:,.0f}",
        "Revenue Gap ($)":       "${:,.0f}",
        "Rec. Ad Spend ($)":     "${:,.0f}",
        "Incremental Spend ($)": "${:,.0f}",
        "Projected ACOS (%)":    "{:.2f}%",
        "Projected ROAS":        "{:.2f}x",
        "Projected TACOS (%)":   "{:.2f}%",
    }
    def _row_style(row):
        if row["Growth Target"] == "✅ Current (Achieved)":
            return ["background-color:#f0fdf4;font-weight:700"] * len(row)
        if str(row["Growth Target"]).startswith("🎯 Custom"):
            return ["background-color:#eff6ff;font-weight:700;color:#1d4ed8"] * len(row)
        return [""] * len(row)
    st.dataframe(
        full_df.style.format(fmt, na_rep="—").apply(_row_style, axis=1),
        use_container_width=True,
    )


def monthly_plan_table(disp_df: pd.DataFrame) -> None:
    fmt_map = {}
    for c in disp_df.columns:
        if "$" in c:        fmt_map[c] = "${:,.0f}"
        elif "ACOS" in c:   fmt_map[c] = "{:.1f}%"
        elif "ROAS" in c:   fmt_map[c] = "{:.2f}x"
        elif "Uplift" in c: fmt_map[c] = "+{:.0f}%"

    def _style_row(row):
        if row.name == "TOTAL":
            return ["background-color:#1e1b4b;color:#ffffff;font-weight:800;font-size:13px;border-top:2px solid #f97316;"] * len(row)
        if row.get("Events", "—") != "—":
            return ["background-color:#fffbeb;font-weight:600"] * len(row)
        return [""] * len(row)

    styled = disp_df.style.format(fmt_map, na_rep="—").apply(_style_row, axis=1)
    st.dataframe(styled, use_container_width=True, height=494)
