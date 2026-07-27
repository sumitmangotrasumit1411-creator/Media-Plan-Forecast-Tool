"""
exporter.py — Generate a downloadable Excel media plan workbook.
"""

import io
import pandas as pd


def build_excel_media_plan(
    ads_metrics: dict,
    vendor_metrics: dict,
    scenarios: list[dict],
    campaign_df: pd.DataFrame,
    asin_merged_df: pd.DataFrame,
) -> bytes:
    """
    Build a multi-sheet Excel workbook summarising the media plan.
    Returns raw bytes suitable for st.download_button.
    """
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        wb = writer.book

        # ---- Formats -------------------------------------------------------
        header_fmt = wb.add_format({
            "bold": True, "bg_color": "#1F3864", "font_color": "white",
            "border": 1, "align": "center", "valign": "vcenter",
        })
        currency_fmt = wb.add_format({"num_format": "$#,##0.00", "border": 1})
        pct_fmt = wb.add_format({"num_format": "0.00%", "border": 1})
        number_fmt = wb.add_format({"num_format": "#,##0", "border": 1})
        plain_fmt = wb.add_format({"border": 1})
        highlight_fmt = wb.add_format({
            "bold": True, "bg_color": "#E8F4FD", "border": 1, "num_format": "$#,##0.00",
        })
        title_fmt = wb.add_format({
            "bold": True, "font_size": 14, "font_color": "#1F3864",
        })

        # ==================================================================
        # Sheet 1 — Executive Summary
        # ==================================================================
        ws = writer.sheets.get("Executive Summary")
        es_data = [
            ["MEDIA PLAN FORECAST — EXECUTIVE SUMMARY"],
            [],
            ["CURRENT BASELINE METRICS"],
            ["Total Ordered Revenue (Vendor)", vendor_metrics.get("total_ordered_revenue", "N/A")],
            ["Total Ad Spend", ads_metrics.get("total_spend", "N/A")],
            ["Total Ad-Attributed Sales", ads_metrics.get("total_ad_sales", "N/A")],
            ["Overall ACOS (%)", (ads_metrics.get("overall_acos") or 0) / 100],
            ["Overall ROAS", ads_metrics.get("overall_roas", "N/A")],
            ["Total Impressions", ads_metrics.get("total_impressions", "N/A")],
            ["Total Clicks", ads_metrics.get("total_clicks", "N/A")],
            ["Overall CTR (%)", (ads_metrics.get("overall_ctr") or 0) / 100],
            ["CPC ($)", ads_metrics.get("overall_cpc", "N/A")],
            ["Avg Selling Price ($)", vendor_metrics.get("avg_selling_price", "N/A")],
            [],
            ["GROWTH SCENARIO COMPARISON"],
        ]
        es_df = pd.DataFrame(es_data)
        es_df.to_excel(writer, sheet_name="Executive Summary", index=False, header=False)
        ws = writer.sheets["Executive Summary"]
        ws.set_column("A:A", 40)
        ws.set_column("B:B", 20)
        ws.write("A1", "MEDIA PLAN FORECAST — EXECUTIVE SUMMARY", title_fmt)

        # Scenario table starting at row 16
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
            # Channel split
            for ch, alloc in s["channel_allocation"].items():
                row[f"{ch} Budget ($)"] = alloc["budget"]
                row[f"{ch} Incr. ($)"] = alloc["incremental_budget"]
            rows.append(row)

        pd.DataFrame(rows).to_excel(writer, sheet_name="Scenarios", index=False)
        ws2 = writer.sheets["Scenarios"]
        ws2.set_row(0, 20, header_fmt)
        ws2.set_column("A:Z", 22)

        # ==================================================================
        # Sheet 3 — Campaign Recommendations (best scenario = +10%)
        # ==================================================================
        target_scenario = next((s for s in scenarios if s["growth_pct"] == 10), scenarios[0])
        if target_scenario["campaign_recommendations"]:
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

    return output.getvalue()
