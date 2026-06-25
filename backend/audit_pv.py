import sys, os
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore
from modules.scheduler import P6Calendar

store = XERDataStore()
ext_bl = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer', 'baseline')
ext_bl.extract_all()
store.add_version(ext_bl.get_complete_data(), 'AMR-BL-R00-2', '2025-11-29', type='baseline', context='test')

ext_upd = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer', 'update')
ext_upd.extract_all()
store.add_version(ext_upd.get_complete_data(), 'AMR-UPD-29-Nov 25', '2025-11-29', type='update', context='test')

baseline_src = store.get_baseline(context='test')
upd_source = store.get_latest(context='test')

bl_tasks = baseline_src['df']['tasks']
upd_tasks = upd_source['df']['tasks']

bl_calendars_df = baseline_src['df'].get('calendar', baseline_src['df'].get('CALENDAR'))
bl_calendars_map = {}
if bl_calendars_df is not None and not bl_calendars_df.empty:
    for _, row in bl_calendars_df.iterrows():
        bl_calendars_map[str(row.get('clndr_id'))] = P6Calendar(row.to_dict())

bl_proj_clndr_id = str(baseline_src['df'].get('project', baseline_src['df'].get('PROJECT')).iloc[0].get('clndr_id', ''))
bl_default_cal = bl_calendars_map.get(bl_proj_clndr_id, P6Calendar())

bl_taskrsrc = baseline_src['df'].get('taskrsrc')
bl_rc = bl_taskrsrc.copy()
bl_rc['target_cost'] = pd.to_numeric(bl_rc.get('target_cost', 0), errors='coerce').fillna(0)
bl_rsrc_agg = bl_rc.groupby('task_id')['target_cost'].sum()
bl_tid_to_code = bl_tasks.set_index('task_id')['task_code'].to_dict()
bl_rsrc_budget = {bl_tid_to_code[tid]: cost for tid, cost in bl_rsrc_agg.items() if tid in bl_tid_to_code}

data_date = pd.to_datetime(upd_source.get('data_date'))
print(f"Data Date: {data_date}")

# Map WBS names
projwbs = upd_source['df']['projwbs']
wbs_id_to_name = projwbs.set_index('wbs_id')['wbs_name'].to_dict()

cur_code_to_wbs = upd_tasks.set_index('task_code')['wbs_id'].to_dict()
cur_code_to_name = upd_tasks.set_index('task_code')['task_name'].to_dict()

# Identify DESIGN activities
design_activities = []
for code, wbs_id in cur_code_to_wbs.items():
    wbs_name = wbs_id_to_name.get(wbs_id, "")
    if wbs_name == "DESIGN" or "DESIGN" in wbs_name.upper():
        design_activities.append(code)

print(f"Found {len(design_activities)} activities in DESIGN")

diff_found = 0
total_pv = 0

print("-" * 140)
print(f"{'Activity':<18} | {'BAC':<10} | {'Start':<10} | {'Finish':<10} | {'Cal':<10} | {'Pct':<6} | {'PV':<12}")
print("-" * 140)

for code in design_activities:
    budget = bl_rsrc_budget.get(code, 0)
    if budget <= 0: continue
    
    brow = bl_tasks[bl_tasks['task_code'] == code]
    if brow.empty: continue
    brow = brow.iloc[0]
    
    bs = pd.to_datetime(brow.get('early_start') or brow.get('target_start_date'), errors='coerce')
    bf = pd.to_datetime(brow.get('early_finish') or brow.get('target_end_date'), errors='coerce')
    clndr_id = str(brow.get('clndr_id', ''))
    
    cal = bl_calendars_map.get(clndr_id, bl_default_cal)
    
    if data_date >= bf:
        pv = budget
        pct = 1.0
    elif data_date <= bs:
        pv = 0.0
        pct = 0.0
    else:
        total_dur_days = cal.workdays_between(bs, bf)
        elapsed_days = cal.workdays_between(bs, data_date)
        if total_dur_days > 0:
            pct = elapsed_days / total_dur_days
            pv = budget * pct
        else:
            pct = 1.0
            pv = budget
            
    total_pv += pv
            
    print(f"{code:<18} | {budget:<10.2f} | {bs.strftime('%Y-%m-%d') if pd.notnull(bs) else '':<10} | {bf.strftime('%Y-%m-%d') if pd.notnull(bf) else '':<10} | {clndr_id:<10} | {pct:<6.2%} | {pv:<12.2f}")

print("-" * 140)
print(f"TOTAL PV for DESIGN: {total_pv:.2f}")
