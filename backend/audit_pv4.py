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

bl_rsrc_budget = store._get_baseline_cost_map('test')

# Manual PV calc to see the difference between 'target_start_date' and 'early_start_date'
print(f"{'Activity':<18} | {'BAC':<10} | {'early_start_date':<18} | {'target_start_date':<18} | {'Used BS':<18} | {'Used BF':<18} | {'PV':<12}")

data_date = pd.to_datetime(upd_source.get('data_date'))
total_pv = 0

for a in design_acts:
    code = a.get('task_code')
    budget = bl_rsrc_budget.get(code, 0)
    if budget <= 0: continue
    
    brow = bl_tasks[bl_tasks['task_code'] == code]
    if brow.empty: continue
    brow = brow.iloc[0]
    
    bs = pd.to_datetime(brow.get('early_start') or brow.get('target_start_date'), errors='coerce')
    bf = pd.to_datetime(brow.get('early_finish') or brow.get('target_end_date'), errors='coerce')
    
    # Try another BS/BF using Primavera exact logic
    bs_prime = pd.to_datetime(brow.get('act_start_date') or brow.get('early_start_date') or brow.get('target_start_date'), errors='coerce')
    bf_prime = pd.to_datetime(brow.get('act_end_date') or brow.get('early_end_date') or brow.get('target_end_date'), errors='coerce')
    
    clndr_id = str(brow.get('clndr_id', ''))
    
    if bs_prime != bs or bf_prime != bf:
        print(f"{code:<18} | {budget:<10.2f} | {str(brow.get('early_start_date')):<18} | {str(brow.get('target_start_date')):<18} | {str(bs)[:10]:<18} | {str(bf)[:10]:<18} | {a.get('pv_cost'):<12.2f}")

