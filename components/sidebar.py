"""
components/sidebar.py — Sidebar UI: file upload, forecast settings, channel split,
custom scenario targets.  Returns all user inputs as a named tuple.
"""
from __future__ import annotations
import streamlit as st
from typing import NamedTuple, Optional


class SidebarInputs(NamedTuple):
    ads_file: object
    vendor_file: object
    growth_options: list
    channel_split: dict
    custom_targets: dict


def render_sidebar() -> SidebarInputs:
    st.sidebar.markdown("""
    <div style="text-align:center;padding:18px 0 14px;">
        <div style="font-size:22px;font-weight:900;color:#fff;letter-spacing:1px;">📊 Media Plan Engine</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:4px;letter-spacing:.5px;">AMAZON ADVERTISING ANALYTICS</div>
    </div>""", unsafe_allow_html=True)
    st.sidebar.markdown("---")

    # ── File uploads ─────────────────────────────────────────────────────────
    st.sidebar.markdown("### 📤 Upload Reports")
    st.sidebar.markdown("---")
    st.sidebar.markdown("<p style='color:#fff;font-size:13px;font-weight:600;margin-bottom:4px;'>Amazon Advertising Report</p>", unsafe_allow_html=True)
    ads_file = st.sidebar.file_uploader(
        "Amazon Advertising Report", type=["csv","xlsx","xls"],
        help="Export from Amazon Ads Console — up to 3 GB",
        label_visibility="collapsed",
    )
    st.sidebar.markdown("<p style='color:#fff;font-size:13px;font-weight:600;margin-bottom:4px;margin-top:12px;'>Vendor Central ASIN Sales Report</p>", unsafe_allow_html=True)
    vendor_file = st.sidebar.file_uploader(
        "Vendor Central ASIN Sales Report", type=["csv","xlsx","xls"],
        help="Export from Vendor Central → Analytics → Sales Diagnostics",
        label_visibility="collapsed",
    )

    # ── Forecast settings ─────────────────────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ Forecast Settings")
    growth_options = st.sidebar.multiselect(
        "Growth Scenarios", options=[5,10,15,20,25,30,40,50],
        default=[10,20,30], help="Select growth targets to model",
    )
    custom_growth = st.sidebar.number_input(
        "Custom Growth % (optional)", min_value=0, max_value=200, value=0, step=1,
    )
    if custom_growth > 0 and custom_growth not in growth_options:
        growth_options = sorted(list(set(growth_options + [custom_growth])))
    if not growth_options:
        growth_options = [10]

    # ── Channel budget split ──────────────────────────────────────────────────
    st.sidebar.markdown("### 🎯 Channel Budget Split")
    sp_pct = st.sidebar.slider("Sponsored Products %", 0, 100, 65)
    sb_pct = st.sidebar.slider("Sponsored Brands %",   0, 100, 25)
    sd_pct = st.sidebar.slider("Sponsored Display %",  0, 100, 10)
    _total = sp_pct + sb_pct + sd_pct
    if _total == 0:
        sp_w, sb_w, sd_w = 0.65, 0.25, 0.10
    else:
        sp_w, sb_w, sd_w = sp_pct/_total, sb_pct/_total, sd_pct/_total
    st.sidebar.caption(
        f"Effective split → SP: **{sp_w*100:.1f}%** · SB: **{sb_w*100:.1f}%** · SD: **{sd_w*100:.1f}%**"
        + ("" if _total == 100 else f"  *(normalised from {_total}%)*")
    )
    channel_split = {"Sponsored Products": sp_w, "Sponsored Brands": sb_w, "Sponsored Display": sd_w}

    # ── Custom scenario targets ───────────────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎯 Custom Scenario Targets")
    st.sidebar.caption("Enter any target — leave at 0 to use growth % math.")
    custom_target_revenue = st.sidebar.number_input("Target Revenue / OPS ($)", min_value=0.0, value=0.0, step=10000.0, format="%.0f")
    custom_ad_spend       = st.sidebar.number_input("Target Ad Spend ($)",       min_value=0.0, value=0.0, step=1000.0,  format="%.0f")
    custom_ad_sales       = st.sidebar.number_input("Target Ad Sales ($)",       min_value=0.0, value=0.0, step=10000.0, format="%.0f")
    custom_roas           = st.sidebar.number_input("Target ROAS",               min_value=0.0, value=0.0, step=0.1,     format="%.2f")
    custom_tacos          = st.sidebar.number_input("Target TACOS (%)",          min_value=0.0, value=0.0, step=0.5,     format="%.2f")

    custom_targets = {
        "target_revenue": custom_target_revenue if custom_target_revenue > 0 else None,
        "ad_spend":       custom_ad_spend       if custom_ad_spend       > 0 else None,
        "ad_sales":       custom_ad_sales       if custom_ad_sales       > 0 else None,
        "roas":           custom_roas           if custom_roas           > 0 else None,
        "tacos":          custom_tacos          if custom_tacos          > 0 else None,
    }
    return SidebarInputs(ads_file, vendor_file, growth_options, channel_split, custom_targets)
