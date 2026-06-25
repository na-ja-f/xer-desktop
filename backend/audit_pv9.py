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

code = "P1 - 2950"
if code not in bl_tasks['task_code'].values:
    code = "P1-2950"

brow = bl_tasks[bl_tasks['task_code'] == code].iloc[0]
urow = upd_tasks[upd_tasks['task_code'] == code].iloc[0]

bl_calendars_df = baseline_src['df'].get('calendar', baseline_src['df'].get('CALENDAR'))
bl_calendars_map = {}
if bl_calendars_df is not None and not bl_calendars_df.empty:
    for _, row in bl_calendars_df.iterrows():
        bl_calendars_map[str(row.get('clndr_id'))] = P6Calendar(row.to_dict())

bl_proj_clndr_id = str(baseline_src['df'].get('project', baseline_src['df'].get('PROJECT')).iloc[0].get('clndr_id', ''))
bl_default_cal = bl_calendars_map.get(bl_proj_clndr_id, P6Calendar())

bl_rsrc_budget = store._get_baseline_cost_map('test')
budget = bl_rsrc_budget.get(code, 0)
data_date = pd.to_datetime(upd_source.get('project', {}).get('data_date', '2025-11-29'))

bs = pd.to_datetime(brow.get('act_start_date') or brow.get('early_start_date') or brow.get('target_start_date'), errors='coerce')
bf = pd.to_datetime(brow.get('act_end_date') or brow.get('early_end_date') or brow.get('target_end_date'), errors='coerce')

clndr_id = str(brow.get('clndr_id', ''))
cal = bl_calendars_map.get(clndr_id, bl_default_cal)

target_drtn_hr_cnt = float(brow.get('target_drtn_hr_cnt', 0))
remain_drtn_hr_cnt = float(brow.get('remain_drtn_hr_cnt', 0))
sched_pct_comp = float(urow.get('sched_pct_comp', 0))

elapsed_workdays = cal.workdays_between(bs, data_date)
total_workdays = cal.workdays_between(bs, bf)
elapsed_hours = elapsed_workdays * cal.hours_per_day

print("="*60)
print(f"target_drtn_hr_cnt: {target_drtn_hr_cnt}")
print(f"remain_drtn_hr_cnt: {remain_drtn_hr_cnt}")
print(f"planned elapsed duration hours at Data Date: {elapsed_hours}")
print(f"planned elapsed duration days: {elapsed_workdays}")
print(f"calendar workdays between start and finish: {total_workdays}")
print(f"duration used by XerAgent: {total_workdays} days")
print(f"duration used by Primavera: {target_drtn_hr_cnt / cal.hours_per_day} days")

pv_A = budget * (elapsed_workdays / total_workdays) if total_workdays > 0 else budget
pv_B = budget * (elapsed_hours / target_drtn_hr_cnt) if target_drtn_hr_cnt > 0 else budget
pv_C = budget * (sched_pct_comp / 100.0)

print("\n--- PV Method Comparisons ---")
print(f"Method A (XerAgent Days): {pv_A:.2f}")
print(f"Method B (Primavera Duration Hours): {pv_B:.2f}")
print(f"Method C (Primavera Schedule % Complete): {pv_C:.2f}")

