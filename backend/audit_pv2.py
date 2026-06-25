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

# Let's get the actual PV from the backend get_table_data method!
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
total_pv = sum(a.get("pv_cost", 0) for a in design_acts)
print(f"XerAgent DESIGN PV: {total_pv:.2f}")

# Find which ones have PV > 0
print(f"{'Activity':<18} | {'WBS Path':<40} | {'BAC':<10} | {'PV':<12}")
for a in design_acts:
    pv = a.get("pv_cost", 0)
    bac = a.get("bl_project_cost", 0)
    if pv > 0:
        print(f"{a.get('task_code'):<18} | {a.get('_wbs_path')[:38]:<40} | {bac:<10.2f} | {pv:<12.2f}")

