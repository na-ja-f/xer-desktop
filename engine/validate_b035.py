import sys, os
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore

store = XERDataStore()
ext_upd = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer', 'update')
ext_upd.extract_all()
store.add_version(ext_upd.get_complete_data(), 'AMR-UPD-29-Nov 25', '2025-11-29', type='update', context='test')

# Ensure baseline is mapped (I'll extract baseline as well)
ext_bl = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer', 'baseline')
ext_bl.extract_all()
store.add_version(ext_bl.get_complete_data(), 'AMR-BL-R00-2', '2025-06-09', type='baseline', context='test')

upd_source = store.get_latest(context='test')
hierarchy = store.get_wbs_hierarchy(source_id=upd_source['id'], search='', filter_type='ALL', include_activities=True, context='test')

def audit_hierarchy(nodes, level=0, path=""):
    for n in nodes:
        w_name = n.get('wbs_name', '')
        current = path + "/" + w_name if path else w_name
        s = n.get("summary", {})
        
        if level <= 1 or s.get('spi_labor_coverage_activity_count', 0) > 0:
            print(f"\n[{level}] {current}")
            print(f"  Branch Total Labor Units: {s.get('target_labor', 0):,.1f}")
            print(f"  Labor EV: {s.get('ev_labor', 0):,.1f}")
            print(f"  Labor PV: {s.get('pv_labor', 0):,.1f}")
            print(f"  Labor SV: {s.get('sv_labor', 0):,.1f}")
            print(f"  {s.get('spi_labor_coverage_label', '')}")
            
        audit_hierarchy(n.get("children", []), level + 1, current)

print("==== HIERARCHY AGGREGATION AUDIT ====")
audit_hierarchy(hierarchy.get("records", []))

print("\n==== ACTIVITY AUDIT ====")
upd_source = store.get_latest(context='test')
tasks = pd.DataFrame(upd_source['df'].get('tasks', []))
labor_loaded = tasks[pd.to_numeric(tasks['target_work_qty'], errors='coerce') > 0]

print(f"Count of labor-loaded activities: {len(labor_loaded)}")
print("Count by complete_pct_type:")
print(labor_loaded['complete_pct_type'].value_counts())

# We want samples for CP_Drtn, CP_Phys, and CP_Units
# Note: we need to find them directly from `hierarchy` activities so we can see the python output!
samples = {'CP_Drtn': [], 'CP_Phys': [], 'CP_Units': []}
def find_samples(nodes):
    for n in nodes:
        for act in n.get('activities', []):
            pt = act.get('ev_method')
            if pt in samples and len(samples[pt]) < 3:
                if act.get('target_labor', 0) > 0:
                    samples[pt].append(act)
        find_samples(n.get('children', []))
        
find_samples(hierarchy.get("records", []))

for pt, acts in samples.items():
    print(f"\n--- {pt} Samples ---")
    if not acts:
        print("  (None found)")
    for act in acts:
        print(f"Task: {act.get('task_code')} | Budget Lbr: {act.get('target_labor')} | Planned %: {(act.get('pv_labor')/act.get('target_labor')) if act.get('target_labor')>0 else 0:.1%} | PV Lbr: {act.get('pv_labor'):.1f}")
        print(f"  EV Method: {act.get('ev_method')} | EV %: {act.get('ev_percent')}% | EV Lbr: {act.get('ev_labor'):.1f}")
