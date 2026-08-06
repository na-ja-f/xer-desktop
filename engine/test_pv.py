import sys, os
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore
import pandas as pd
from modules.scheduler import P6Calendar

store = XERDataStore()

ext_bl = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer', 'baseline')
ext_bl.extract_all()
data_bl = ext_bl.get_complete_data()
store.add_version(data_bl, data_bl['project']['project_name'], data_bl['project']['data_date'], type='baseline', context='test')

bl_source = store.get_baseline(context='test')

# Let's get the exact data date
ext_upd = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer', 'update')
ext_upd.extract_all()
data_upd = ext_upd.get_complete_data()
data_date = pd.to_datetime(data_upd['project']['data_date'])

print(f"Exact data date string: {data_upd['project']['data_date']}")

calendars_df = bl_source['df'].get('calendar', bl_source['df'].get('CALENDAR'))
calendars_map = {}
if calendars_df is not None and not calendars_df.empty:
    for _, row in calendars_df.iterrows():
        calendars_map[str(row.get('clndr_id'))] = P6Calendar(row.to_dict())

proj_clndr_id = str(bl_source['df']['project'].iloc[0].get('clndr_id', ''))
default_cal = calendars_map.get(proj_clndr_id, P6Calendar())

bl_tasks = bl_source['df']['tasks']
bl_dates = {}
for _, brow in bl_tasks.iterrows():
    code = brow.get('task_code')
    bs = pd.to_datetime(brow.get('early_start') or brow.get('target_start_date'), errors='coerce')
    bf = pd.to_datetime(brow.get('early_finish') or brow.get('target_end_date'), errors='coerce')
    clndr = str(brow.get('clndr_id'))
    bl_dates[code] = (bs, bf, clndr)

bl_taskrsrc = bl_source['df']['taskrsrc']
bl_taskrsrc['target_cost'] = pd.to_numeric(bl_taskrsrc.get('target_cost', 0), errors='coerce').fillna(0)
bl_rsrc_agg = bl_taskrsrc.groupby('task_id')['target_cost'].sum()
bl_tid_to_code = bl_tasks.set_index('task_id')['task_code'].to_dict()
bl_rsrc_budget = {}
for btid, bcost in bl_rsrc_agg.items():
    bcode = bl_tid_to_code.get(btid)
    if bcode:
        bl_rsrc_budget[bcode] = float(bcost)

pv_total_cal_hours = 0
for code, (bs, bf, clndr_id) in bl_dates.items():
    budget = bl_rsrc_budget.get(code, 0)
    if budget <= 0: continue
    
    if data_date >= bf:
        pv_h = budget
    elif data_date <= bs:
        pv_h = 0.0
    else:
        cal = calendars_map.get(clndr_id, default_cal)
        total_dur_hrs = cal.work_hours_between(bs, bf)
        elapsed_hrs = cal.work_hours_between(bs, data_date)
        pv_h = budget * (elapsed_hrs / total_dur_hrs) if total_dur_hrs > 0 else budget
        
    pv_total_cal_hours += pv_h
    
print(f"Total PV (Calendar Hours): ${pv_total_cal_hours:,.2f}")

