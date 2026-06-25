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
design_acts = [a for a in acts if "DESIGN" in a.get("_wbs_path", "").upper()]

bl_calendars_df = baseline_src['df'].get('calendar', baseline_src['df'].get('CALENDAR'))
bl_calendars_map = {}
if bl_calendars_df is not None and not bl_calendars_df.empty:
    for _, row in bl_calendars_df.iterrows():
        bl_calendars_map[str(row.get('clndr_id'))] = P6Calendar(row.to_dict())

bl_proj_clndr_id = str(baseline_src['df'].get('project', baseline_src['df'].get('PROJECT')).iloc[0].get('clndr_id', ''))
bl_default_cal = bl_calendars_map.get(bl_proj_clndr_id, P6Calendar())

bl_rsrc_budget = store._get_baseline_cost_map('test')
data_date = pd.to_datetime(upd_source.get('data_date'))

total_pv_current = 0
total_pv_prime = 0
diffs = []

for a in design_acts:
    code = a.get('task_code')
    budget = bl_rsrc_budget.get(code, 0)
    if budget <= 0: continue
    
    brow = bl_tasks[bl_tasks['task_code'] == code]
    if brow.empty: continue
    brow = brow.iloc[0]
    
    # XerAgent's current dates
    bs = pd.to_datetime(brow.get('early_start') or brow.get('target_start_date'), errors='coerce')
    bf = pd.to_datetime(brow.get('early_finish') or brow.get('target_end_date'), errors='coerce')
    
    # True Baseline exact dates (what P6 would use)
    bs_prime = pd.to_datetime(brow.get('act_start_date') or brow.get('early_start_date') or brow.get('target_start_date'), errors='coerce')
    bf_prime = pd.to_datetime(brow.get('act_end_date') or brow.get('early_end_date') or brow.get('target_end_date'), errors='coerce')
    
    clndr_id = str(brow.get('clndr_id', ''))
    cal = bl_calendars_map.get(clndr_id, bl_default_cal)
    
    def calc_pv(start, finish):
        if pd.isnull(start) or pd.isnull(finish): return 0.0
        if data_date >= finish: return budget
        elif data_date <= start: return 0.0
        else:
            total = cal.workdays_between(start, finish)
            elapsed = cal.workdays_between(start, data_date)
            return budget * (elapsed / total) if total > 0 else budget
            
    pv = calc_pv(bs, bf)
    pv_prime = calc_pv(bs_prime, bf_prime)
    
    total_pv_current += pv
    total_pv_prime += pv_prime
    
    if abs(pv - pv_prime) > 0.1:
        diffs.append((code, budget, pv, pv_prime, pv_prime - pv))

print(f"Total PV (Current Logic): {total_pv_current:.2f}")
print(f"Total PV (Prime Logic): {total_pv_prime:.2f}")
print(f"Difference: {total_pv_prime - total_pv_current:.2f}")

print("\nActivities causing the difference:")
for d in diffs:
    print(f"{d[0]:<18} | BAC: {d[1]:<10.2f} | PV_Cur: {d[2]:<10.2f} | PV_Pri: {d[3]:<10.2f} | Diff: {d[4]:<10.2f}")

