# Forecast enhancement verification

Verified on 29 September 2026 against repository base `9303f56` using Python 3.12 and the repository's pinned Streamlit 1.64.0.

## Changes

- Full uploaded filenames wrap and HTML-special characters render literally.
- Three sliders rebalance on a 0.1 percentage-point grid with strict SP > SB > SD and a total of 100%. Enter a complete allocation in **Enter an exact allocation**, then **Apply exact allocation** to preserve 70/20/10 exactly. Infeasible individual slider requests are constrained to feasible bounds.
- Custom revenue and ad-sales targets are retained. Spend precedence is explicit ad spend > ROAS > TACOS > growth calculation. Lower-priority spend targets are ignored; displayed ratios reflect achieved results. Zero clears an optional target.
- One forecast selector drives projected KPIs, channel allocation charts, monthly tables, and exports. Editing or clearing custom targets selects the updated default. Comparison charts/tables continue showing all scenarios.
- Annual spend, monthly spend, and channel amounts reconcile to the cent. The selected scenario is first in Excel, including custom scenarios.
- Forecast comparison and monthly-table ROAS use dollar formatting, including Excel, while preserving numeric values.

## Verification

`python -m pytest tests -q`: **17 passed**. Includes 3,003 slider transitions, exact-allocation validation, live Streamlit callback/rerun behavior, custom target changes and clearing, scenario selection, uploaded-file integration, rendered table formatting, allocation chart values, and Excel inspection.

Real-report smoke check: **passed** on a 604,625,101-byte Ads CSV (1,266,922 rows) and Vendor Central workbook (22,812 rows). Large-file mode remained active, Actuals year was 2025, monthly Actuals reconciled with the report totals, and forecast monthly totals reconciled with the annual scenario.

Run with your reports:

```sh
python tests/smoke_reports.py /path/to/2025_ads.csv /path/to/vendor.xlsx
```

Application compilation, Git whitespace checks, and local Streamlit health check passed. One existing pandas deprecation warning remains in the unchanged parser (`pd.concat(copy=False)`).

`parser.py`, `metrics.py`, `trends.py`, and upload caching logic were not modified. Source reports and the older local checkout were not modified.

## Delivery state

User authorized publishing the tested changes to the public GitHub repository and updating the Streamlit app. This verification covers the application changes, removal of Performance Gauges, and updated welcome cards 3 and 6.
