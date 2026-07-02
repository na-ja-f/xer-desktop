import sys, os
import pandas as pd
import json

sys.path.append(os.path.abspath('backend'))
from modules.data_store import XERDataStore
from modules.extractor import CompleteXERExtractor

store = XERDataStore()
update_path = '/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer'
baseline_path = '/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer'

ext_bl = CompleteXERExtractor(baseline_path, 'baseline')
ext_bl.extract_all()
store.add_version(ext_bl.get_complete_data(), 'AMR-BL-R00-2', '2025-11-29', type='baseline', context='val1')

ext_upd = CompleteXERExtractor(update_path, 'update')
ext_upd.extract_all()
store.add_version(ext_upd.get_complete_data(), 'AMR-UPD-29-Nov 25', '2025-11-29', type='update', context='val1')

dashboard = store.get_dashboard_data(context='val1')

print("\n====== VALIDATION REPORT - B-042 ======\n")

# PART 2: Path Completeness
cp = dashboard.get('current_critical_path', {})
ncp = dashboard.get('next_critical_path', {})

print("=== PART 1 & 2: Current Critical Path ===")
print(f"Activity Count   : {cp.get('count')}")
print(f"Duration         : {cp.get('duration')} days")
print(f"Worst Float      : {cp.get('worst_float')} days")
print(f"First Activity   : {cp.get('first_activity_id')} | {cp.get('first_activity')}")
print(f"Last Activity    : {cp.get('last_activity_id')} | {cp.get('last_activity')}")
seq = cp.get('path_sequence', [])
print(f"Sequence Length  : {len(seq)}")
if seq:
    print(f"  [1] {seq[0]['id']} | {seq[0]['name'][:40]} | ES: {seq[0]['es']} | Float: {seq[0]['float']}d")
    if len(seq) > 1:
        print(f"  [2] {seq[1]['id']} | {seq[1]['name'][:40]} | ES: {seq[1]['es']} | Float: {seq[1]['float']}d")
    print(f"  [{len(seq)}] {seq[-1]['id']} | {seq[-1]['name'][:40]} | EF: {seq[-1]['ef']} | Float: {seq[-1]['float']}d")

print()
print("=== PART 3: Next Critical Path ===")
print(f"Activity Count   : {ncp.get('count')}")
print(f"Duration         : {ncp.get('duration')} days")
print(f"Min Float        : {ncp.get('min_float')} days")
print(f"First Activity   : {ncp.get('first_activity_id')} | {ncp.get('first_activity')}")
print(f"Last Activity    : {ncp.get('last_activity_id')} | {ncp.get('last_activity')}")

# PART 3: Float path summary from raw analysis
print()
print("=== PART 3: Float Path Summary (First 10 Paths) ===")
analysis = store.get_deterministic_analysis(store.get_latest('val1')['id'], context='val1')
act_data = analysis.get('activityAnalysis', {})

paths = {}
for tid, m in act_data.items():
    pid = m.get('path_id')
    if pid is None or pd.isna(pid): continue
    pid = int(float(pid)) if pid else None
    if pid is None: continue
    fh = m.get('float_hrs', 0) or 0
    fd = fh / 8.0
    fp_order = m.get('float_path_order')
    dt_start = m.get('_dt_current_start_date')
    dt_end = m.get('_dt_current_end_date')
    if pid not in paths:
        paths[pid] = {'tasks': [], 'floats': []}
    paths[pid]['tasks'].append({'fp_order': float(fp_order) if fp_order else None, 'start': dt_start, 'end': dt_end})
    paths[pid]['floats'].append(fd)

for pid in sorted(paths.keys())[:10]:
    p = paths[pid]
    starts = [pd.to_datetime(t['start']) for t in p['tasks'] if t.get('start') and pd.notnull(pd.to_datetime(t['start'], errors='coerce'))]
    ends = [pd.to_datetime(t['end']) for t in p['tasks'] if t.get('end') and pd.notnull(pd.to_datetime(t['end'], errors='coerce'))]
    dur = (max(ends) - min(starts)).days if starts and ends else 0
    worst_float = min(p['floats']) if p['floats'] else 0
    print(f"  Path {pid:2d}: Count={len(p['tasks']):4d} | Dur={dur:5d}d | WorstFloat={worst_float:8.1f}d")

# PART 5: Critical Count reconciliation
print()
print("=== PART 6: Critical Activity Count Reconciliation ===")
total_tasks = len(act_data)
all_critical_old = sum(1 for m in act_data.values() if m.get('status_enum') != 'COMPLETED' and (m.get('float_hrs', 0) or 0) <= 0)
all_critical_new = sum(1 for m in act_data.values()
    if m.get('status_enum') != 'COMPLETED'
    and (m.get('float_hrs', 0) or 0) <= 0
    and m.get('task_type', '') not in ('TT_LOE', 'TT_WBS', 'TT_Mile', 'TT_FinMile')
)
print(f"  Old count (incl. milestones/LOE) : {all_critical_old}")
print(f"  New count (working tasks only)   : {all_critical_new}")
print(f"  Reduction                        : {all_critical_old - all_critical_new}")
print(f"  Dashboard now shows              : {dashboard.get('critical_count')}")

# PART 4: WBS Delay Table naming examples
print()
print("=== PART 5: WBS Delay Table - Parent > Child Naming Examples ===")
for row in (dashboard.get('wbs_delay') or [])[:8]:
    print(f"  WBS ID: {row.get('wbs_id'):10} | Display: {row.get('wbs')}")

print()
print("====== VALIDATION COMPLETE ======")
