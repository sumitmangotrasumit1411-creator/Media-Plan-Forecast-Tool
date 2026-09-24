"""
exporter.py — Generate a downloadable Excel media plan workbook.

Phase 5 additions:
  Sheet 3 — Monthly Media Plan (12-month spend/sales calendar)
"""

from __future__ import annotations

import io
from typing import Optional

import pandas as pd


def build_excel_media_plan(
    ads_metrics: dict,
    vendor_metrics: dict,
    scenarios: list,
    campaign_df: pd.DataFrame,
    asin_merged_df: pd.DataFrame,
    health_df: Optional[pd.DataFrame] = None,
    monthly_df: Optional[pd.DataFrame] = None,
) -> bytes:
    """
    Build a multi-sheet Excel workbook summarising the media plan.
    Returns raw bytes suitable for st.download_button.

    Sheets:
      1. Executive Summary
      2. Scenarios
      3. Monthly Media Plan
    """
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        wb = writer.book

        # ── Common formats ──────────────────────────────────────────────────
        header_fmt = wb.add_format({
            "bold": True, "bg_color": "#1F3864", "font_color": "white",
            "border": 1, "align": "center", "valign": "vcenter",
        })
        header_orange_fmt = wb.add_format({
            "bold": True, "bg_color": "#C55A11", "font_color": "white",
            "border": 1, "align": "center", "valign": "vcenter",
        })
        currency_fmt  = wb.add_format({"num_format": "$#,##0.00", "border": 1})
        pct_fmt       = wb.add_format({"num_format": "0.00%", "border": 1})
        number_fmt    = wb.add_format({"num_format": "#,##0", "border": 1})
        plain_fmt     = wb.add_format({"border": 1})
        highlight_fmt = wb.add_format({
            "bold": True, "bg_color": "#E8F4FD", "border": 1,
            "num_format": "$#,##0.00",
        })
        title_fmt = wb.add_format({
            "bold": True, "font_size": 14, "font_color": "#1F3864",
        })
        green_row_fmt = wb.add_format({
            "bg_color": "#E2EFDA", "border": 1, "bold": True,
        })
        red_row_fmt = wb.add_format({
            "bg_color": "#FFE0E0", "border": 1,
        })
        event_row_fmt = wb.add_format({
            "bg_color": "#FFF2CC", "border": 1, "bold": True,
        })
        total_row_fmt = wb.add_format({
            "bold": True, "bg_color": "#1F3864", "font_color": "white",
            "border": 1, "num_format": "$#,##0",
        })

        # ==================================================================
        # Sheet 1 — Executive Summary
        # ==================================================================
        es_data = [
            ["MEDIA PLAN FORECAST — EXECUTIVE SUMMARY"],
            [],
            ["CURRENT BASELINE METRICS"],
            ["Total Ordered Revenue (Vendor)",
             (vendor_metrics or {}).get("total_ordered_revenue", "N/A")],
            ["Total Ad Spend", ads_metrics.get("total_spend", "N/A")],
            ["Total Ad-Attributed Sales", ads_metrics.get("total_ad_sales", "N/A")],
            ["Overall ACOS (%)", (ads_metrics.get("overall_acos") or 0) / 100],
            ["Overall ROAS", ads_metrics.get("overall_roas", "N/A")],
            ["Total Impressions", ads_metrics.get("total_impressions", "N/A")],
            ["Total Clicks", ads_metrics.get("total_clicks", "N/A")],
            ["Overall CTR (%)", (ads_metrics.get("overall_ctr") or 0) / 100],
            ["CPC ($)", ads_metrics.get("overall_cpc", "N/A")],
            ["Avg Selling Price ($)",
             (vendor_metrics or {}).get("avg_selling_price", "N/A")],
            [],
            ["GROWTH SCENARIO COMPARISON"],
        ]
        es_df = pd.DataFrame(es_data)
        es_df.to_excel(writer, sheet_name="Executive Summary", index=False, header=False)
        ws = writer.sheets["Executive Summary"]
        ws.set_column("A:A", 40)
        ws.set_column("B:B", 20)
        ws.write("A1", "MEDIA PLAN FORECAST — EXECUTIVE SUMMARY", title_fmt)

        from forecast import scenarios_to_dataframe
        sc_df = scenarios_to_dataframe(scenarios)
        sc_df.to_excel(writer, sheet_name="Executive Summary", index=False, startrow=15)
        ws.set_row(15, 20, header_fmt)

        # ==================================================================
        # Sheet 2 — Scenario Deep Dive
        # ==================================================================
        rows = []
        for s in scenarios:
            row = {
                "Growth Target": f"+{s['growth_pct']}%",
                "Baseline Revenue ($)": s["baseline_revenue"],
                "Target Revenue ($)": s["target_revenue"],
                "Revenue Gap ($)": s["revenue_gap"],
                "Current Ad Spend ($)": s["current_ad_spend"],
                "Recommended Ad Spend ($)": s["recommended_spend"],
                "Incremental Budget ($)": s["incremental_spend"],
                "Target Ad Sales ($)": s["target_ad_sales"],
                "Projected ACOS (%)": s["projected_acos_pct"],
                "Projected ROAS": s["projected_roas"],
                "Projected TACOS (%)": s["projected_tacos_pct"],
            }
            for ch, alloc in s["channel_allocation"].items():
                row[f"{ch} Budget ($)"] = alloc["budget"]
                row[f"{ch} Incr. ($)"]  = alloc["incremental_budget"]
            rows.append(row)

        pd.DataFrame(rows).to_excel(writer, sheet_name="Scenarios", index=False)
        ws2 = writer.sheets["Scenarios"]
        ws2.set_row(0, 20, header_fmt)
        ws2.set_column("A:Z", 22)

        # The workbook intentionally contains only the leadership-facing
        # outputs requested by the user: Executive Summary, Scenarios, and
        # Monthly Media Plan. Detailed campaign/ASIN sheets are omitted.
        
        # ==================================================================
        # Sheet 3 — Monthly Media Plan  (Phase 5)
        # ==================================================================
        if monthly_df is not None and not monthly_df.empty:
            monthly_export = monthly_df.copy()

            # Clean up column display
            rename_m = {
                "Month Name": "Month",
                "Events": "Key Events",
                "Actual Spend ($)": "Actual Spend ($)",
                "Actual Ad Sales ($)": "Actual Ad Sales ($)",
                "Actual ACOS (%)": "Actual ACOS (%)",
                "Actual ROAS": "Actual ROAS",
                "Projected Spend ($)": "Projected Spend ($)",
                "Projected Ad Sales ($)": "Projected Ad Sales ($)",
                "Projected ACOS (%)": "Projected ACOS (%)",
                "Projected ROAS": "Projected ROAS",
                "Spend Uplift %": "Spend Uplift %",
                "SP Budget ($)": "SP Budget ($)",
                "SB Budget ($)": "SB Budget ($)",
                "SD Budget ($)": "SD Budget ($)",
                "Is Event Month": "Event Month?",
            }
            monthly_export = monthly_export.rename(
                columns={k: v for k, v in rename_m.items() if k in monthly_export.columns}
            )

            # Drop internal month-number column if present
            if "Month" in monthly_export.columns and "Month Name" not in monthly_export.columns:
                pass  # Month is already the display name
            drop_cols = [c for c in ["Month"] if c in monthly_export.columns
                         and "Month Name" in rename_m.values() and "Month" in rename_m]
            monthly_export = monthly_export.drop(columns=drop_cols, errors="ignore")

            monthly_export.to_excel(writer, sheet_name="Monthly Media Plan", index=False)
            ws7 = writer.sheets["Monthly Media Plan"]
            ws7.set_row(0, 20, header_fmt)
            ws7.set_column("A:A", 6)    # Month number
            ws7.set_column("B:B", 14)   # Month name
            ws7.set_column("C:C", 22)   # Events
            ws7.set_column("D:P", 20)

            # Highlight event months and totals row
            if "Event Month?" in monthly_export.columns:
                for row_idx, (_, row) in enumerate(monthly_export.iterrows(), start=1):
                    is_event = row.get("Event Month?", False)
                    if is_event:
                        ws7.set_row(row_idx, None, event_row_fmt)

    return output.getvalue()
