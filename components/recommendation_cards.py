"""
components/recommendation_cards.py — HTML builders for recommendation / warning cards,
channel strategy cards, seasonal calendar, ASIN tier framework.
"""
from __future__ import annotations
import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.formatters import fmt_currency


def alert_card(message: str) -> str:
    return f'<div class="warning-card" style="margin-bottom:8px;">{message}</div>'


def success_card(message: str) -> str:
    return f'<div class="reco-card" style="margin-bottom:8px;">{message}</div>'


def scenario_action_card(s: dict, current_roas: float) -> str:
    gpct  = s["growth_pct"]
    delta = s["incremental_spend"]
    rec   = s["recommended_spend"]
    tacos = s.get("projected_tacos_pct") or 0
    proas = s.get("projected_roas") or 0
    alloc = s.get("channel_allocation", {})
    sp_b  = alloc.get("Sponsored Products", {}).get("budget", 0)
    sb_b  = alloc.get("Sponsored Brands",   {}).get("budget", 0)
    sd_b  = alloc.get("Sponsored Display",  {}).get("budget", 0)
    label = f"+{gpct:.0f}%" if gpct >= 0 else f"{gpct:.0f}%"
    badge = "🎯 Custom" if s.get("is_custom_scenario") else f"📈 {label} Growth"
    return f"""
    <div class="reco-card" style="margin-bottom:12px;">
        <div style="font-size:16px;font-weight:800;margin-bottom:6px;">{badge} — Target Revenue: {fmt_currency(s['target_revenue'])}</div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:10px 0;">
            <div style="background:#f0f2ff;border-radius:8px;padding:8px 12px;text-align:center;">
                <div style="font-size:11px;color:#6b7280;font-weight:600;">REC. AD SPEND</div>
                <div style="font-size:18px;font-weight:800;color:#4f46e5;">{fmt_currency(rec)}</div>
                <div style="font-size:11px;color:#f97316;">+{fmt_currency(delta)} incremental</div>
            </div>
            <div style="background:#f0f2ff;border-radius:8px;padding:8px 12px;text-align:center;">
                <div style="font-size:11px;color:#6b7280;font-weight:600;">PROJ. ROAS</div>
                <div style="font-size:18px;font-weight:800;color:#4f46e5;">{proas:.2f}x</div>
                <div style="font-size:11px;color:#6b7280;">vs current {(current_roas or 0):.2f}x</div>
            </div>
            <div style="background:#f0f2ff;border-radius:8px;padding:8px 12px;text-align:center;">
                <div style="font-size:11px;color:#6b7280;font-weight:600;">PROJ. TACOS</div>
                <div style="font-size:18px;font-weight:800;color:#f97316;">{tacos:.1f}%</div>
                <div style="font-size:11px;color:#6b7280;">total ad cost ratio</div>
            </div>
            <div style="background:#f0f2ff;border-radius:8px;padding:8px 12px;text-align:center;">
                <div style="font-size:11px;color:#6b7280;font-weight:600;">CHANNEL SPLIT</div>
                <div style="font-size:13px;font-weight:700;color:#1e1b4b;">SP {fmt_currency(sp_b)}</div>
                <div style="font-size:12px;color:#f97316;">SB {fmt_currency(sb_b)} · SD {fmt_currency(sd_b)}</div>
            </div>
        </div>
    </div>"""
