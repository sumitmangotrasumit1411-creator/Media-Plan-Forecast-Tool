"""
utils/formatters.py — Shared display formatters (currency, percent, numbers).
Single source of truth — no more duplicated fmt_* helpers across files.
"""

from __future__ import annotations
import math
import numpy as np


def fmt_currency(val, decimals: int = 2) -> str:
    """Format a number as $X,XXX.XX  (returns 'N/A' for None/NaN)."""
    if val is None:
        return "N/A"
    try:
        v = float(val)
        if math.isnan(v) or math.isinf(v):
            return "N/A"
        if decimals == 0:
            return f"${v:,.0f}"
        return f"${v:,.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def fmt_pct(val, decimals: int = 2) -> str:
    """Format a number as XX.XX%  (returns 'N/A' for None/NaN)."""
    if val is None:
        return "N/A"
    try:
        v = float(val)
        if math.isnan(v) or math.isinf(v):
            return "N/A"
        return f"{v:.{decimals}f}%"
    except (TypeError, ValueError):
        return "N/A"


def fmt_num(val, decimals: int = 0) -> str:
    """Format a number with commas  (returns 'N/A' for None/NaN)."""
    if val is None:
        return "N/A"
    try:
        v = float(val)
        if math.isnan(v) or math.isinf(v):
            return "N/A"
        if decimals == 0:
            return f"{v:,.0f}"
        return f"{v:,.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def fmt_roas(val) -> str:
    """Format ROAS as X.XXx."""
    if val is None:
        return "N/A"
    try:
        v = float(val)
        if math.isnan(v) or math.isinf(v):
            return "N/A"
        return f"{v:.2f}x"
    except (TypeError, ValueError):
        return "N/A"


def fmt_compact(val) -> str:
    """
    Compact format: 1,234,567 → $1.2M, 12,345 → $12.3K.
    Useful for metric cards on small screens.
    """
    if val is None:
        return "N/A"
    try:
        v = abs(float(val))
        sign = "-" if float(val) < 0 else ""
        if v >= 1_000_000:
            return f"{sign}${v/1_000_000:.1f}M"
        elif v >= 1_000:
            return f"{sign}${v/1_000:.1f}K"
        else:
            return f"{sign}${v:.0f}"
    except (TypeError, ValueError):
        return "N/A"


def colour_acos(val) -> str:
    """CSS colour string for ACOS value (green/orange/red)."""
    try:
        v = float(val)
        if v < 20:
            return "color: #15803d"    # green
        elif v < 35:
            return "color: #d97706"    # amber
        else:
            return "color: #b91c1c"    # red
    except Exception:
        return ""


def delta_badge(new_val, old_val, higher_is_better: bool = True, is_pp: bool = False) -> str:
    """
    Return an HTML badge pill showing absolute or % change.
    is_pp=True shows percentage-point change (for ACOS, TACOS, etc.)
    """
    NEUTRAL = (
        '<span style="background:#f3f4f6;color:#6b7280;border-radius:20px;'
        'padding:3px 9px;font-size:12px;font-weight:700;">— Unchanged</span>'
    )
    if old_val is None or new_val is None:
        return NEUTRAL
    try:
        new_v = float(new_val) if new_val is not None else 0.0
        old_v = float(old_val) if old_val is not None else 0.0
    except (TypeError, ValueError):
        return NEUTRAL

    delta = new_v - old_v
    pct   = (delta / abs(old_v) * 100) if old_v != 0 else 0.0

    if is_pp:
        if abs(delta) < 0.001:
            return NEUTRAL
    else:
        if abs(pct) < 0.01:
            return NEUTRAL

    good  = (delta > 0) == higher_is_better
    bg    = "#dcfce7" if good else "#fee2e2"
    color = "#15803d" if good else "#b91c1c"
    arrow = "▲" if delta > 0 else "▼"
    sign  = "+" if delta > 0 else ""

    change_str = f"{sign}{delta:.2f}pp" if is_pp else f"{sign}{pct:.1f}%"
    return (
        f'<span style="background:{bg};color:{color};border-radius:20px;'
        f'padding:3px 9px;font-size:12px;font-weight:800;white-space:nowrap;">'
        f'{arrow} {change_str}</span>'
    )
