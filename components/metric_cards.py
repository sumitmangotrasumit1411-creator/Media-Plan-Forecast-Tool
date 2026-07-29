"""
components/metric_cards.py — Reusable metric card HTML builders.
All formatting uses utils.formatters so there's a single source of truth.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.formatters import fmt_currency, fmt_pct, fmt_num, delta_badge


def metric_card(label: str, value: str, delta: str = None) -> str:
    """Simple KPI card — label / value / optional delta line."""
    delta_html = f'<div class="metric-delta">{delta}</div>' if delta else ""
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>"""


def impact_tile(
    label: str,
    curr,
    proj,
    fmt_fn,
    higher_is_better: bool = True,
    is_pct_metric: bool = False,
) -> str:
    """Current → Projected tile with a coloured delta badge."""
    badge     = delta_badge(proj, curr, higher_is_better, is_pct_metric)
    changed   = abs(proj - (curr or 0)) > 0.001 if curr else False
    border    = "#4f46e5" if changed else "#e5e7eb"
    border_top = "4px solid #4f46e5" if changed else "4px solid #e5e7eb"
    return f"""
    <div style="background:#ffffff;border:1px solid {border};border-top:{border_top};
                border-radius:10px;padding:14px 16px;box-shadow:0 2px 8px rgba(0,0,0,0.05);
                height:100%;">
        <div style="font-size:12px;font-weight:700;color:#6b7280;letter-spacing:.4px;margin-bottom:10px;">{label}</div>
        <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:8px;">
            <div>
                <div style="font-size:10px;color:#9ca3af;font-weight:600;text-transform:uppercase;letter-spacing:.5px;">Current</div>
                <div style="font-size:15px;font-weight:700;color:#6b7280;">{fmt_fn(curr)}</div>
            </div>
            <div style="font-size:16px;color:#9ca3af;margin-bottom:2px;">→</div>
            <div style="text-align:right;">
                <div style="font-size:10px;color:#4f46e5;font-weight:700;text-transform:uppercase;letter-spacing:.5px;">Projected</div>
                <div style="font-size:20px;font-weight:900;color:#1e1b4b;">{fmt_fn(proj)}</div>
            </div>
        </div>
        <div style="border-top:1px solid #f3f4f6;padding-top:7px;text-align:center;">{badge}</div>
    </div>"""


def channel_tile(name: str, budget: float, share_pct: float, color: str) -> str:
    """Budget tile for Sponsored Products / Brands / Display."""
    return f"""
    <div style="background:#ffffff;border-top:4px solid {color};border-radius:10px;
                padding:14px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <div style="font-size:12px;font-weight:800;color:{color};">{name}</div>
        <div style="font-size:24px;font-weight:900;color:#1e1b4b;margin:6px 0;">{fmt_currency(budget)}</div>
        <div style="font-size:13px;color:#6b7280;">{share_pct:.1f}% of total budget</div>
    </div>"""
