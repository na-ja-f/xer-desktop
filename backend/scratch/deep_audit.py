import sys, os
import pandas as pd
import json
from datetime import datetime

sys.path.append(os.path.abspath('backend'))
from modules.data_store import XERDataStore
from modules.extractor import CompleteXERExtractor

store = XERDataStore()
baseline_path = '/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer'
update_path = '/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer'

ext_bl = CompleteXERExtractor(baseline_path, 'baseline')
ext_bl.extract_all()
store.add_version(ext_bl.get_complete_data(), 'AMR-BL-R00-2', '2025-11-29', type='baseline', context='audit3')

ext_upd = CompleteXERExtractor(update_path, 'update')
ext_upd.extract_all()
store.add_version(ext_upd.get_complete_data(), 'AMR-UPD-29-Nov 25', '2025-11-29', type='update', context='audit3')

# 1. Dashboard data for paths
dashboard = store.get_dashboard_data(context='audit3')
analysis = store.get_deterministic_analysis(store.get_latest('audit3')['id'], context='audit3')
activity_data = analysis.get("activityAnalysis", {})

# Extract paths
paths = {}
for tid, m in activity_data.items():
    pid = m.get("path_id")
    if pid is not None:
        if pid not in paths:
            paths[pid] = []
        
        # Determine duration
        es = pd.to_datetime(m.get("_dt_current_start_date"), errors='coerce')
        ef = pd.to_datetime(m.get("_dt_current_end_date"), errors='coerce')
        
        paths[pid].append({
            "id": m.get("task_code"),
            "name": m.get("task_name"),
            "es": es,
            "ef": ef,
            "ls": m.get("late_start"),
            "lf": m.get("late_finish"),
            "float": m.get("float_hrs", 0) / 8.0
        })

print("\n--- 1. Path 1 (Longest Path) Full Trace ---")
if 1 in paths:
    p1 = paths[1]
    # sort by es
    p1.sort(key=lambda x: x["es"] if pd.notnull(x["es"]) else pd.Timestamp.max)
    for a in p1:
        es_str = a["es"].strftime("%d %b %Y") if pd.notnull(a["es"]) else "-"
        ef_str = a["ef"].strftime("%d %b %Y") if pd.notnull(a["ef"]) else "-"
        print(f"{a['id']} | {a['name'][:40]} | ES: {es_str} | EF: {ef_str} | LS: {a['ls']} | LF: {a['lf']} | Float: {a['float']}d")

print("\n--- 2. Project Start / Finish ---")
all_tasks = store.get_latest('audit3')['df']['tasks']
all_tasks['_dt_start'] = pd.to_datetime(all_tasks['target_start_date'], errors='coerce')
all_tasks['_dt_end'] = pd.to_datetime(all_tasks['target_end_date'], errors='coerce')
start_task = all_tasks.loc[all_tasks['_dt_start'].idxmin()]
end_task = all_tasks.loc[all_tasks['_dt_end'].idxmax()]
print(f"Project Start Task: {start_task['task_code']} - {start_task['task_name']} ({start_task['_dt_start']})")
print(f"Project Finish Task: {end_task['task_code']} - {end_task['task_name']} ({end_task['_dt_end']})")
print(f"Path 1 Start Date: {p1[0]['es'] if 1 in paths else '-'}")
print(f"Path 1 Finish Date: {p1[-1]['ef'] if 1 in paths else '-'}")

print("\n--- 3. First 10 Float Paths ---")
for pid in sorted(paths.keys())[:10]:
    p = paths[pid]
    p.sort(key=lambda x: x["es"] if pd.notnull(x["es"]) else pd.Timestamp.max)
    first_es = p[0]['es']
    last_ef = p[-1]['ef']
    duration = (last_ef - first_es).days if pd.notnull(first_es) and pd.notnull(last_ef) else 0
    worst_float = min([a["float"] for a in p]) if p else 0
    print(f"Path {pid}: Count={len(p)}, Dur={duration}d, WorstFloat={worst_float}d, First={p[0]['name'][:20]}, Last={p[-1]['name'][:20]}")

print("\n--- 5. Path 2 Full Trace ---")
if 2 in paths:
    p2 = paths[2]
    p2.sort(key=lambda x: x["es"] if pd.notnull(x["es"]) else pd.Timestamp.max)
    for a in p2:
        es_str = a["es"].strftime("%d %b %Y") if pd.notnull(a["es"]) else "-"
        ef_str = a["ef"].strftime("%d %b %Y") if pd.notnull(a["ef"]) else "-"
        print(f"{a['id']} | {a['name'][:40]} | ES: {es_str} | EF: {ef_str} | LS: {a['ls']} | LF: {a['lf']} | Float: {a['float']}d")

print("\n--- 6. WBS Hierarchy Audit ---")
wbs_df = store.get_latest('audit3')['df']['projwbs']
wbs_map = wbs_df.set_index('wbs_id').to_dict('index')

def get_full_path(wbs_id):
    path = []
    curr = str(wbs_id)
    while curr and curr in wbs_map:
        node = wbs_map[curr]
        path.append(node.get('wbs_name', ''))
        curr = str(node.get('parent_wbs_id', ''))
        if curr == 'nan' or not curr: break
    return " > ".join(reversed(path))

for wbs_item in dashboard.get('wbs_delay', [])[:5]:
    wid = str(wbs_item.get('wbs_id'))
    print(f"WBS ID: {wid}")
    print(f"Short Name: {wbs_item.get('wbs')}")
    print(f"Full Path: {get_full_path(wid)}")
    print("-")
