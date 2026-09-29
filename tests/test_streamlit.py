from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]


def test_sidebar_callbacks():
    at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=30).run()
    assert not at.exception
    for ch,pct in [('sp',60.),('sb',30.),('sd',15.)]:
        at.slider(key=f'_channel_{ch}_pct').set_value(pct).run()
        assert not at.exception
        vals=[at.session_state[f'channel_{c}_pct'] for c in ('sp','sb','sd')]
        assert round(sum(vals),1)==100
        assert vals[0]>vals[1]>vals[2]
        assert at.session_state[f'channel_{ch}_pct']==pct
    for ch,pct in [('sp',70.),('sb',20.),('sd',10.)]:
        at.number_input(key=f'exact_{ch}').set_value(pct)
    at.button(key='FormSubmitter:exact_allocation-Apply exact allocation').click().run()
    assert not at.exception
    assert [at.slider(key=f'_channel_{ch}_pct').value for ch in ('sp','sb','sd')]==[70,20,10]
    at.run()
    assert [at.slider(key=f'_channel_{ch}_pct').value for ch in ('sp','sb','sd')]==[70,20,10]


HARNESS='''
import streamlit as st
import pandas as pd
from pages.tab_forecast import render_forecast
from forecast import DEFAULT_CHANNEL_SPLIT
spend=st.number_input("Spend",value=0.)
revenue=st.number_input("Revenue",value=0.)
scenarios=render_forecast(
    {"total_spend":100000,"total_ad_sales":400000,"overall_acos":25,"overall_roas":4},
    {"total_ordered_revenue":1000000},pd.DataFrame(),[5,10,20],DEFAULT_CHANNEL_SPLIT,
    custom_targets={"ad_spend":spend or None,"target_revenue":revenue or None})
st.session_state["test_scenarios"]=scenarios
'''


def test_forecast_selection_and_targets():
    at=AppTest.from_string(HARNESS,default_timeout=30).run()
    assert not at.exception
    def check():
        assert not at.exception
        s=at.session_state['test_scenarios'][0]
        df=at.session_state['last_monthly_df']
        assert round(df['Projected Spend ($)'].sum(),2)==s['recommended_spend']
        assert round(df['Projected Ad Sales ($)'].sum(),2)==s['target_ad_sales']
        return s
    assert check()['growth_pct']==5
    at.selectbox(key='forecast_scenario').select('+20%').run()
    assert check()['growth_pct']==20
    at.number_input[0].set_value(150000.).run()
    assert at.selectbox(key='forecast_scenario').value=='Custom'
    assert check()['recommended_spend']==150000
    at.number_input[0].set_value(160000.).run()
    assert check()['recommended_spend']==160000
    at.number_input[1].set_value(1700000.).run()
    assert check()['target_revenue']==1700000
    at.number_input[0].set_value(0.).run()
    assert check()['recommended_spend']!=160000
    at.number_input[1].set_value(0.).run()
    assert not check()['is_custom_scenario']
    assert len(at.session_state['test_scenarios'])==3

UPLOAD_HARNESS='''
from unittest.mock import patch
from io import BytesIO
import streamlit as st
import app
class Upload(BytesIO):
    pass
ads=Upload(b"Month,Ad product,Total cost,Sales,Impressions,Clicks,Purchases\\n1,Sponsored Products,100,400,1000,50,10\\n2,Sponsored Brands,50,150,500,20,5\\n3,Sponsored Display,25,50,200,10,2\\n")
ads.name="2025_" + "long_filename_"*20 + "<&>.csv"
ads.size=300*1024*1024
ads.file_id="smoke-ads"
with patch.object(st.sidebar,"file_uploader",side_effect=[ads,None]):
    app.main()
'''

def test_uploaded_app_end_to_end():
    at=AppTest.from_string(UPLOAD_HARNESS,default_timeout=30).run()
    assert not at.exception
    assert not at.error
    assert any('long_filename_'*20 + '&lt;&amp;&gt;.csv' in m.value for m in at.markdown)
    before=at.session_state['last_monthly_df']['Projected Spend ($)'].sum()
    at.slider(key='_channel_sp_pct').set_value(60.).run()
    assert not at.exception
    assert not at.error
    after=at.session_state['last_monthly_df']['Projected Spend ($)'].sum()
    assert before!=after
    target=next(x for x in at.number_input if x.label=='Target Ad Spend ($)')
    target.set_value(500.).run()
    assert not at.exception
    assert not at.error
    assert round(at.session_state['last_monthly_df']['Projected Spend ($)'].sum(),2)==500

def test_forecast_tables_and_chart_match_selection():
    import json
    import pyarrow as pa
    at=AppTest.from_string(HARNESS,default_timeout=30).run()
    at.selectbox(key='forecast_scenario').select('+20%').run()
    assert not at.exception
    s=at.session_state['test_scenarios'][0]
    for table in at.dataframe:
        display=pa.ipc.open_stream(table.proto.arrow_data.styler.display_values).read_all().to_pandas()
        for col in display:
            if 'ROAS' in col:
                assert all(v.startswith('$') or v=='—' for v in display[col])
    charts=[json.loads(c.proto.spec) for c in at.get('plotly_chart')]
    pie=next(c['data'][0] for c in charts if c['data'][0]['type']=='pie')
    assert pie['values']==[x['budget'] for x in s['channel_allocation'].values()]
