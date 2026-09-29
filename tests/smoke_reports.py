"""Optional smoke test: python tests/smoke_reports.py ADS_CSV VENDOR_XLSX."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from parser import parse_amazon_ads_report, parse_vendor_central_report
from metrics import extract_ads_metrics, extract_vendor_metrics
from trends import build_trend_df
from forecast import run_forecast, monthly_forecast, exact_channel_split

with open(sys.argv[1],'rb') as f:
    f.size=Path(sys.argv[1]).stat().st_size
    ads=parse_amazon_ads_report(f)
with open(sys.argv[2],'rb') as f:
    f.size=Path(sys.argv[2]).stat().st_size
    vendor=parse_vendor_central_report(f)
a=extract_ads_metrics(ads);v=extract_vendor_metrics(vendor)
trend=build_trend_df(ads, freq="M")
assert not trend.empty
split=exact_channel_split(70,20,10)
s=run_forecast(v['total_ordered_revenue'],a['total_spend'],a['total_ad_sales'],20,split)
m,year=monthly_forecast(trend,20,v['total_ordered_revenue'],split,s['recommended_spend'],s['target_ad_sales'])
assert year==2025
assert abs(m['Actual Spend ($)'].sum()-a['total_spend'])<.02
assert abs(m['Actual Ad Sales ($)'].sum()-a['total_ad_sales'])<.02
assert round(m['Projected Spend ($)'].sum(),2)==s['recommended_spend']
assert round(m['Projected Ad Sales ($)'].sum(),2)==s['target_ad_sales']
print({'ads_rows':len(ads),'vendor_rows':len(vendor),'forecast_only':ads.attrs.get('forecast_only'),'actuals_year':year,'monthly_reconciliation':'passed'})
