"""
exporter.py — Generate a downloadable Excel media plan workbook.

Phase 5 additions:
  Sheet 6 — ASIN Health Scores (from tab_intelligence health_df)
  Sheet 7 — Monthly Media Plan (12-month spend/sales calendar)
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
      3. Campaign Recommendations
      4. Campaign Performance
      5. ASIN Analysis
      6. ASIN Health Scores     (Phase 5 — optional)
      7. Monthly Media Plan     (Phase 5 — optional)
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

        # ==================================================================
        # Sheet 3 — Campaign Recommendations (best scenario = +10%)
        # ==================================================================
        if scenarios:
            target_scenario = next(
                (s for s in scenarios if s["growth_pct"] == 10), scenarios[0]
            )
            if target_scenario.get("campaign_recommendations"):
                cr_df = pd.DataFrame(target_scenario["campaign_recommendations"])
                cr_df.columns = [c.replace("_", " ").title() for c in cr_df.columns]
                cr_df.to_excel(writer, sheet_name="Campaign Recommendations", index=False)
                ws3 = writer.sheets["Campaign Recommendations"]
                ws3.set_row(0, 20, header_fmt)
                ws3.set_column("A:Z", 24)

        # ==================================================================
        # Sheet 4 — Campaign Performance
        # ==================================================================
        if campaign_df is not None and not campaign_df.empty:
            campaign_df.to_excel(writer, sheet_name="Campaign Performance", index=False)
            ws4 = writer.sheets["Campaign Performance"]
            ws4.set_row(0, 20, header_fmt)
            ws4.set_column("A:Z", 20)

        # ==================================================================
        # Sheet 5 — ASIN Analysis
        # ==================================================================
        if asin_merged_df is not None and not asin_merged_df.empty:
            asin_merged_df.to_excel(writer, sheet_name="ASIN Analysis", index=False)
            ws5 = writer.sheets["ASIN Analysis"]
            ws5.set_row(0, 20, header_fmt)
            ws5.set_column("A:Z", 20)

        # ==================================================================
        # Sheet 6 — ASIN Health Scores  (Phase 5)
        # ==================================================================
        if health_df is not None and not health_df.empty:
            # Select and rename display columns
            health_export_cols = [c for c in [
                "asin", "score", "tier", "spend", "ad_sales", "roas",
                "acos_%", "cvr_%", "ntb_%", "impressions",
                "ordered_revenue", "ordered_units",
            ] if c in health_df.columns]
            h_df = health_df[health_export_cols].copy()

            rename_h = {
                "asin": "ASIN", "score": "Health Score (0–100)", "tier": "Tier",
                "spend": "Ad Spend ($)", "ad_sales": "Ad Sales ($)",
                "roas": "ROAS", "acos_%": "ACOS (%)", "cvr_%": "CVR (%)",
                "ntb_%": "NTB (%)", "impressions": "Impressions",
                "ordered_revenue": "Ordered Revenue ($)",
                "ordered_units": "Ordered Units",
            }
            h_df = h_df.rename(columns={k: v for k, v in rename_h.items() if k in h_df.columns})
            h_df.to_excel(writer, sheet_name="ASIN Health Scores", index=False)

            ws6 = writer.sheets["ASIN Health Scores"]
            ws6.set_row(0, 20, header_orange_fmt)
            ws6.set_column("A:A", 16)   # ASIN
            ws6.set_column("B:B", 20)   # Score
            ws6.set_column("C:C", 12)   # Tier
            ws6.set_column("D:L", 18)

            # Colour-code rows by tier (conditional format simulation via row-level write)
            tier_row_fmts = {
                "Scale":    wb.add_format({"bg_color": "#E2EFDA", "border": 1}),
                "Optimise": wb.add_format({"bg_color": "#FFF2CC", "border": 1}),
                "Review":   wb.add_format({"bg_color": "#FCE4D6", "border": 1}),
                "Pause":    wb.add_format({"bg_color": "#FFE0E0", "border": 1, "bold": True}),
            }
            for row_idx, (_, row) in enumerate(h_df.iterrows(), start=1):
                tier_val = row.get("Tier", "")
                fmt_t = tier_row_fmts.get(tier_val, plain_fmt)
                for col_idx, val in enumerate(row.values):
                    ws6.write(row_idx, col_idx, val, fmt_t)

        # ==================================================================
        # Sheet 7 — Monthly Media Plan  (Phase 5)
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
