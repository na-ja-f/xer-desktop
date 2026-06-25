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

bl_calendars_df = baseline_src['df'].get('calendar', baseline_src['df'].get('CALENDAR'))
bl_calendars_map = {}
if bl_calendars_df is not None and not bl_calendars_df.empty:
    for _, row in bl_calendars_df.iterrows():
        bl_calendars_map[str(row.get('clndr_id'))] = P6Calendar(row.to_dict())

bl_proj_clndr_id = str(baseline_src['df'].get('project', baseline_src['df'].get('PROJECT')).iloc[0].get('clndr_id', ''))
bl_default_cal = bl_calendars_map.get(bl_proj_clndr_id, P6Calendar())

code = "P1 - 2950"
if code not in bl_tasks['task_code'].values:
    code = "P1-2950"

brow = bl_tasks[bl_tasks['task_code'] == code].iloc[0]
clndr_id = str(brow.get('clndr_id', ''))
cal = bl_calendars_map.get(clndr_id, bl_default_cal)

print(f"### Activity: {code} ###")
print(f"Calendar ID: {clndr_id}")
print(f"Working exceptions parsed: {len(cal.working_exceptions)}")
print(f"Non-working exceptions parsed: {len(cal.holidays)}")

bl_rsrc_budget = store._get_baseline_cost_map('test')
data_date = pd.to_datetime(upd_source.get('project', {}).get('data_date', '2025-11-29'))

bs = pd.to_datetime(brow.get('act_start_date') or brow.get('early_start_date') or brow.get('target_start_date'), errors='coerce')
bf = pd.to_datetime(brow.get('act_end_date') or brow.get('early_end_date') or brow.get('target_end_date'), errors='coerce')
budget = bl_rsrc_budget.get(code, 0)
target_hours = float(brow.get('target_drtn_hr_cnt', 0))

elapsed_workdays = cal.workdays_between(bs, data_date)
elapsed_hours = elapsed_workdays * cal.hours_per_day

if target_hours > 0:
    planned_pct = elapsed_hours / target_hours
    pv = budget * planned_pct
else:
    planned_pct = 1.0
    pv = budget

print(f"Elapsed Hours = {elapsed_hours}")
print(f"Target Hours = {target_hours}")
print(f"Planned % = {planned_pct:.4%}")
print(f"PV = ${pv:,.2f}")


print("\n### Full PV Revalidation ###")
tree_resp = store.get_table_data(table_type="HIERARCHY", limit=999999, context='test', source_id=upd_source['id'])
nodes = tree_resp.get("records", [])

def flatten_wbs(nodes, path_name=""):
    res = []
    for n in nodes:
        w_name = n.get("wbs_name", "")
        current_path = path_name + "/" + w_name if path_name else w_name
        for a in n.get("activities", []):
            a["_wbs_path"] = current_path
            res.append(a)
        res.extend(flatten_wbs(n.get("children", []), current_path))
    return res

acts = flatten_wbs(nodes)

gen_acts = [a for a in acts if "GENERAL/PRELIMINARIES/MOBILIZATION" in a.get("_wbs_path", "").upper() or "GENERAL / PRELIMINARIES / MOBILIZATION" in a.get("_wbs_path", "").upper()]
design_acts = [a for a in acts if "DESIGN" in a.get("_wbs_path", "").upper()]

gen_pv = sum(a.get("pv_cost", 0) for a in gen_acts)
design_pv = sum(a.get("pv_cost", 0) for a in design_acts)
project_pv = sum(a.get("pv_cost", 0) for a in acts)

print(f"GENERAL/PRELIM PV: ${gen_pv:,.2f} (Primavera: $14,226,472)")
print(f"DESIGN PV: ${design_pv:,.2f} (Primavera: $10,473,570)")
print(f"PROJECT TOTAL PV: ${project_pv:,.2f} (Primavera: $24,700,042)")

print("\n### Additional Audit ###")
print(f"1. Total calendars found: {len(bl_calendars_map)}")
modern_cals = [c for c in bl_calendars_map.values() if len(c.working_exceptions) > 0 or len(c.holidays) > 0]
print(f"2. Calendars containing parsed exceptions: {len(modern_cals)}")
total_we = sum(len(c.working_exceptions) for c in bl_calendars_map.values())
total_nwe = sum(len(c.holidays) for c in bl_calendars_map.values())
print(f"3. Number of working exceptions parsed: {total_we}")
print(f"4. Number of non-working exceptions parsed: {total_nwe}")

