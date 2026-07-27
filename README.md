# Media Plan Forecast Tool

A Streamlit web app for generating data-driven Amazon media plans from your advertising and Vendor Central reports.

---

## What it does

1. **Uploads** Amazon Advertising reports + Vendor Central ASIN Sales reports (CSV or XLSX)
2. **Extracts** all key metrics — ACOS, ROAS, CTR, CPC, Ordered Revenue, ASIN performance
3. **Models growth scenarios** (e.g. +10%, +20%, +30% sales growth) and recommends optimal ad spend
4. **Allocates budget** across Sponsored Products, Sponsored Brands, and Sponsored Display
5. **Recommends** which campaigns to scale, based on ROAS efficiency
6. **Exports** a full multi-sheet Excel media plan

---

## Quick Start

### 1. Install dependencies

```bash
cd media_plan_tool
pip install -r requirements.txt
```

### 2. Run the app

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501` in your browser.

---

## Sharing with your team

### Option A — Run locally (each person installs Python)
Share this folder. Each team member runs:
```bash
pip install -r requirements.txt
streamlit run app.py
```

### Option B — Deploy to Streamlit Community Cloud (free, no server needed)
1. Push this folder to a GitHub repo
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo and deploy — team gets a shareable URL

### Option C — Internal server / VM
```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```
Then share the server IP with your team.

---

## Reports Required

| Report | Where to export | Format |
|--------|----------------|--------|
| Amazon Advertising Report | Amazon Ads Console → Reports → Sponsored Products / Brands / Display | CSV or XLSX |
| Vendor Central ASIN Sales | Vendor Central → Analytics → Sales Diagnostics → Download | CSV or XLSX |

> **Tip:** The tool works with just one report if you only have one available.

---

## Project Structure

```
media_plan_tool/
├── app.py          # Streamlit UI — main entry point
├── parser.py       # File ingestion + column normalisation
├── metrics.py      # Metric extraction and aggregation
├── forecast.py     # Scenario-based forecast engine
├── exporter.py     # Excel media plan generator
├── requirements.txt
└── README.md
```

---

## Key Metrics Tracked

**Amazon Ads:** Impressions, Clicks, CTR, Ad Spend, Ad Sales, ACOS, ROAS, CPC, Conversion Rate  
**Vendor Central:** Ordered Revenue, Shipped Revenue, Ordered Units, Avg Selling Price  
**Blended:** TACOS (Total ACOS = Ad Spend / Total Ordered Revenue)

## Forecast Logic

- Baseline revenue taken from Vendor Central ordered revenue (falls back to ad-attributed sales)
- Ad contribution ratio calculated from your actual data (ad sales / total revenue)
- ACOS efficiency decay applied: +10% spend increase → ~+4% relative ACOS increase
- Incremental spend allocated proportionally to best-performing campaigns by ROAS
