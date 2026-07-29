"""
components/charts.py — Reusable Plotly chart builders.

All chart construction is isolated here so:
  * app.py only calls chart functions (no go.Figure boilerplate in UI code)
  * Charts can be cached with @st.cache_data using their data inputs
  * Chart logic can be tested independently
"""

from __future__ import annotations
from typing import Optional
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import settings

C = settings   # colour shorthand


def gauge_acos(value: float) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        title={"text": "ACOS (%)"},
        delta={"reference": 25, "decreasing": {"color": "green"}, "increasing": {"color": "red"}},
        gauge={
            "axis": {"range": [0, 80]},
            "bar":  {"color": "#293C5B"},
            "steps": [
                {"range": [0, 20],  "color": "#d1fae5"},
                {"range": [20, 35], "color": "#fef3c7"},
                {"range": [35, 80], "color": "#fee2e2"},
            ],
            "threshold": {"line": {"color": "red", "width": 2}, "thickness": 0.75, "value": 35},
        },
    ))
    fig.update_layout(height=280, margin=dict(t=40, b=10, l=20, r=20))
    return fig


def gauge_roas(value: float) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        title={"text": "ROAS"},
        delta={"reference": 4, "increasing": {"color": "green"}, "decreasing": {"color": "red"}},
        gauge={
            "axis": {"range": [0, 10]},
            "bar":  {"color": "#e71d36"},
            "steps": [
                {"range": [0, 2],  "color": "#fee2e2"},
                {"range": [2, 4],  "color": "#fef3c7"},
                {"range": [4, 10], "color": "#d1fae5"},
            ],
            "threshold": {"line": {"color": "green", "width": 2}, "thickness": 0.75, "value": 4},
        },
    ))
    fig.update_layout(height=280, margin=dict(t=40, b=10, l=20, r=20))
    return fig


def bar_spend_vs_sales(df: pd.DataFrame, name_col: str, title: str = "Spend vs Sales") -> go.Figure:
    top10 = df.head(10)
    fig = go.Figure()
    if "spend" in top10.columns:
        fig.add_trace(go.Bar(x=top10[name_col], y=top10["spend"],    name="Ad Spend", marker_color=C.c_primary))
    if "ad_sales" in top10.columns:
        fig.add_trace(go.Bar(x=top10[name_col], y=top10["ad_sales"], name="Ad Sales", marker_color=C.c_accent))
    fig.update_layout(
        barmode="group", title=title,
        xaxis_tickangle=-35, height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=80),
    )
    return fig


def scatter_acos_vs_spend(df: pd.DataFrame, name_col: str) -> go.Figure:
    fig = px.scatter(
        df.head(20), x="spend", y="acos_%",
        size="spend", color="roas" if "roas" in df.columns else None,
        hover_name=name_col,
        title="ACOS vs Spend (bubble = spend size)",
        labels={"spend": "Ad Spend ($)", "acos_%": "ACOS (%)"},
        color_continuous_scale="RdYlGn_r",
    )
    fig.add_hline(y=25, line_dash="dash", line_color="orange", annotation_text="25% ACOS benchmark")
    fig.update_layout(height=380, margin=dict(t=60))
    return fig


def line_trend(trend_df: pd.DataFrame, metric: str, title: str, color: str, height: int = 340) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trend_df["_period_dt"], y=trend_df[metric],
        mode="lines+markers", name=metric,
        line=dict(color=color, width=2), marker=dict(size=6),
    ))
    fig.update_layout(title=title, height=height, margin=dict(t=50, b=30),
                      xaxis_title="Period", yaxis_title=metric)
    return fig


def bar_scenario_comparison(
    labels: list, revenues: list, spends: list,
    rev_colors: list, spend_colors: list,
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=revenues, name="Revenue",  marker_color=rev_colors))
    fig.add_trace(go.Bar(x=labels, y=spends,   name="Ad Spend", marker_color=spend_colors))
    fig.update_layout(
        barmode="group", height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=40), yaxis_title="Amount ($)", xaxis_title="Scenario",
    )
    fig.add_vline(x=0.5, line_dash="dash", line_color="rgba(107,114,128,0.4)",
                  annotation_text="Forecast →", annotation_position="top right")
    return fig


def pie_channel_split(labels: list, values: list) -> go.Figure:
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.45,
        marker_colors=["#293C5B", "#e71d36", "#f59e0b"],
    ))
    fig.update_layout(title="Total Budget Split", height=320, margin=dict(t=50, b=10, l=10, r=10))
    return fig


def monthly_spend_chart(
    months: list, actual: list, projected: list, sales: list,
    is_event: list, scenario_label: str,
) -> go.Figure:
    bar_colors = ["#f97316" if e else C.c_primary for e in is_event]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=months, y=actual,    name="Actual Spend",    marker_color="#9ca3af", opacity=0.7))
    fig.add_trace(go.Bar(x=months, y=projected, name=f"Projected ({scenario_label})", marker_color=bar_colors, opacity=0.9))
    fig.add_trace(go.Scatter(x=months, y=sales, name="Projected Ad Sales", mode="lines+markers",
                             line=dict(color=C.c_green, width=2), marker=dict(size=8), yaxis="y2"))
    for i, (ev, _) in enumerate(zip(is_event, months)):
        if ev:
            fig.add_vrect(x0=i-0.5, x1=i+0.5, fillcolor="rgba(249,115,22,0.10)", layer="below", line_width=0)
    fig.update_layout(
        barmode="group", height=460,
        yaxis=dict(title="Spend ($)", tickprefix="$"),
        yaxis2=dict(title="Ad Sales ($)", overlaying="y", side="right", tickprefix="$", showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=40), xaxis_title="Month",
        title=f"Monthly Spend & Sales — {scenario_label}  |  🟠 = High-Sales Event Month",
    )
    return fig
