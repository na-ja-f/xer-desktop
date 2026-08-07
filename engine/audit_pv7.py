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
bl_rsrc_budget = {bl_tid_to_code.get(tid): cost for tid, cost in bl_rsrc_agg.items() if bl_tid_to_code.get(tid)}

data_date = pd.to_datetime(upd_source.get('project', {}).get('data_date', '2025-11-29'))

code = "P1 - 2950"
if code not in bl_tasks['task_code'].values:
    code = "P1-2950"

brow = bl_tasks[bl_tasks['task_code'] == code].iloc[0]
urow = upd_tasks[upd_tasks['task_code'] == code].iloc[0]

budget = bl_rsrc_budget.get(code, 0)
print("="*60)
print(f"Activity ID: {code}")
print(f"Activity Name: {brow.get('task_name')}")
print(f"BAC: {budget}")
print(f"Data Date: {data_date}")

bs_cur = pd.to_datetime(brow.get('early_start') or brow.get('target_start_date'), errors='coerce')
bf_cur = pd.to_datetime(brow.get('early_finish') or brow.get('target_end_date'), errors='coerce')

bs_pri = pd.to_datetime(brow.get('act_start_date') or brow.get('early_start_date') or brow.get('target_start_date'), errors='coerce')
bf_pri = pd.to_datetime(brow.get('act_end_date') or brow.get('early_end_date') or brow.get('target_end_date'), errors='coerce')

clndr_id = str(brow.get('clndr_id', ''))
cal = bl_calendars_map.get(clndr_id, bl_default_cal)

print(f"\nCalendar ID: {clndr_id}")

def calc(start, finish):
    if pd.isnull(start) or pd.isnull(finish): return 0, 0, 0, 0
    total = cal.workdays_between(start, finish)
    elapsed = cal.workdays_between(start, data_date)
    if data_date >= finish: pct = 1.0
    elif data_date <= start: pct = 0.0
    else: pct = elapsed / total if total > 0 else 1.0
    return total, elapsed, pct, budget * pct

c_tot, c_el, c_pct, c_pv = calc(bs_cur, bf_cur)
p_tot, p_el, p_pct, p_pv = calc(bs_pri, bf_pri)

print("\n--- BEFORE FIX (Current Logic) ---")
print(f"Start date used: {bs_cur}")
print(f"Finish date used: {bf_cur}")
print(f"Total Baseline Days: {c_tot}")
print(f"Planned Elapsed Days: {c_el}")
print(f"Planned Elapsed %: {c_pct:.4%}")
print(f"PV: {c_pv:.2f}")

print("\n--- AFTER FIX (Prime Logic) ---")
print(f"Start date used: {bs_pri}")
print(f"Finish date used: {bf_pri}")
print(f"Total Baseline Days: {p_tot}")
print(f"Planned Elapsed Days: {p_el}")
print(f"Planned Elapsed %: {p_pct:.4%}")
print(f"PV: {p_pv:.2f}")

print("\nRaw XER Dates for Baseline Task:")
for col in ['target_start_date', 'target_end_date', 'early_start_date', 'early_end_date', 'act_start_date', 'act_end_date', 'late_start_date', 'late_end_date']:
    print(f"{col}: {brow.get(col)}")

