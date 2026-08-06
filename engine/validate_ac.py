import sys, os
import pandas as pd
import numpy as np
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore

store = XERDataStore()
ext_bl = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer', 'baseline')
ext_bl.extract_all()
store.add_version(ext_bl.get_complete_data(), 'AMR-BL-R00-2', '2025-11-29', type='baseline', context='test')

ext_upd = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer', 'update')
ext_upd.extract_all()
store.add_version(ext_upd.get_complete_data(), 'AMR-UPD-29-Nov 25', '2025-11-29', type='update', context='test')

baseline_src = store.get_baseline(context='test')
upd_source = store.get_latest(context='test')

tree_resp = store.get_table_data(table_type="HIERARCHY", limit=999999, context='test', source_id=upd_source['id'])
nodes = tree_resp.get("records", [])

def flatten_wbs(nodes, path_name=""):
    res = []
    for n in nodes:
        w_name = n.get("wbs_name", "")
        current_path = path_name + "/" + w_name if path_name else w_name
        for a in n.get("activities", []):
            res.append({
                "id": a.get("activity_id", ""),
                "name": a.get("activity_name", ""),
                "bac": float(a.get("bl_project_cost", 0) or 0),
                "ev": float(a.get("ev_cost", 0) or 0),
                "ac": float(a.get("act_reg_cost", 0) or 0)
            })
        res.extend(flatten_wbs(n.get("children", []), current_path))
    return res

acts = flatten_wbs(nodes)

# Filter to activities with actual cost > 0
acts_with_ac = [a for a in acts if a["ac"] > 0]
acts_with_ev = [a for a in acts if a["ev"] > 0]

print(f"Total activities: {len(acts)}")
print(f"Activities with EV > 0: {len(acts_with_ev)}")
print(f"Activities with AC > 0: {len(acts_with_ac)}")

exact_matches = 0
close_matches = 0

for a in acts_with_ac:
    diff = abs(a["ev"] - a["ac"])
    pct_diff = diff / max(a["ev"], 1.0)
    
    if diff < 1.0:
        exact_matches += 1
    elif pct_diff < 0.05: # Within 5%
        close_matches += 1

print(f"\nAnalysis of {len(acts_with_ac)} activities with Actual Cost:")
print(f"Exact Matches (EV == AC): {exact_matches}")
print(f"Close Matches (within 5%): {close_matches}")

match_rate = (exact_matches + close_matches) / max(len(acts_with_ac), 1)
print(f"Synthetic AC Rate: {match_rate:.2%}")

if match_rate > 0.90:
    print("\nCONCLUSION: Actual Cost is SYNTHETIC (Auto-computed from EV). CPI/CV should be disabled.")
else:
    print("\nCONCLUSION: Actual Cost is REAL. CPI/CV should be enabled.")
