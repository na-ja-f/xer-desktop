import sys, os
import pandas as pd
import numpy as np

sys.path.append(os.path.abspath('backend'))
from modules.data_store import XERDataStore
from modules.extractor import CompleteXERExtractor

store = XERDataStore()
baseline_path = '/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer'
update_path = '/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer'

ext_bl = CompleteXERExtractor(baseline_path, 'baseline')
ext_bl.extract_all()
store.add_version(ext_bl.get_complete_data(), 'AMR-BL-R00-2', '2025-11-29', type='baseline', context='test')

ext_upd = CompleteXERExtractor(update_path, 'update')
ext_upd.extract_all()
store.add_version(ext_upd.get_complete_data(), 'AMR-UPD-29-Nov 25', '2025-11-29', type='update', context='test')

bl_ver = store.get_baseline(context='test')
upd_ver = store.get_latest(context='test')

df_bl = bl_ver['df']['tasks'].copy()
df_upd = upd_ver['df']['tasks'].copy()
df_wbs = upd_ver['df']['projwbs'].copy()

# Date mapping
date_mapping = {
    '_dt_target_start_date': ['target_start_date', 'plan_start_date', 'start_date'],
    '_dt_target_end_date': ['target_end_date', 'plan_end_date', 'finish_date', 'scd_end_date'],
    '_dt_act_start_date': ['act_start_date', 'actual_start_date', 'as_date'],
    '_dt_act_end_date': ['act_end_date', 'actual_finish_date', 'af_date']
}
for internal_col, xer_cols in date_mapping.items():
    val_bl = None
    for col in xer_cols:
        if col in df_bl.columns:
            val_bl = pd.to_datetime(df_bl[col], errors='coerce')
            break
    df_bl[internal_col] = val_bl
    val_upd = None
    for col in xer_cols:
        if col in df_upd.columns:
            val_upd = pd.to_datetime(df_upd[col], errors='coerce')
            break
    df_upd[internal_col] = val_upd

# Float math
df_bl['bl_float_hrs'] = pd.to_numeric(df_bl['total_float_hr_cnt'], errors='coerce').fillna(0.0)
df_upd['current_float_hrs'] = pd.to_numeric(df_upd['total_float_hr_cnt'], errors='coerce').fillna(0.0)
bl_float_map = df_bl.set_index('task_code')['bl_float_hrs'].to_dict()
df_upd['bl_float_hrs'] = df_upd['task_code'].map(bl_float_map).fillna(0.0)

# Hours to days
hpd = upd_ver.get('hours_per_day', 8.0)
df_upd['bl_float_days'] = df_upd['bl_float_hrs'] / hpd
df_upd['current_float_days'] = df_upd['current_float_hrs'] / hpd

def calc_float_consumption(row):
    bl_f = row['bl_float_hrs']
    curr_f = row['current_float_hrs']
    if curr_f <= 0.0: return 1.0
    if bl_f <= 0.0: return 0.0
    return float((bl_f - curr_f) / bl_f)

df_upd['float_consumption_pct'] = df_upd.apply(calc_float_consumption, axis=1)

def classify_float_risk(row):
    curr_f = row['current_float_hrs']
    pct = row['float_consumption_pct']
    if curr_f <= 0.0: return "Critical"
    elif pct > 0.75: return "At Risk"
    elif pct >= 0.50: return "Watching"
    else: return "Stable"

df_upd['float_class'] = df_upd.apply(classify_float_risk, axis=1)

# Find root WBS
root_wbs = df_wbs[df_wbs['parent_wbs_id'].isnull() | (df_wbs['parent_wbs_id'].astype(str) == 'nan')]
if root_wbs.empty:
    # Fallback to node with min parent
    root_id = str(df_wbs['wbs_id'].iloc[0])
else:
    root_id = str(root_wbs['wbs_id'].iloc[0])

print(f"Project WBS Root ID: {root_id}, Name: {wbs_id_to_name.get(root_id) if 'wbs_id_to_name' in locals() else root_id}")

wbs_id_to_name = {}
wbs_id_to_parent = {}
for _, row in df_wbs.iterrows():
    wid = str(row.get("wbs_id", ""))
    wbs_id_to_name[wid] = str(row.get("wbs_name") or row.get("wbs_short_name") or wid)
    parent = row.get("parent_wbs_id")
    wbs_id_to_parent[wid] = str(int(parent)) if parent and str(parent) != 'nan' and pd.notnull(parent) else None

# Find direct children of root_id
direct_children = [wid for wid, parent in wbs_id_to_parent.items() if parent == root_id]
print(f"Direct children of root WBS ({len(direct_children)} branches):")
for child in direct_children:
    print(f" - {child}: {wbs_id_to_name.get(child)}")

# Helper to map any WBS node to its Level 1 branch (the child of the root)
def get_level1_wbs_child(wid: str, visited=None) -> str:
    if visited is None:
        visited = set()
    if wid in visited:
        return wid
    visited.add(wid)
    parent = wbs_id_to_parent.get(wid)
    if not parent:
        return wid  # This is the root node
    if parent == root_id:
        return wid  # This node is a direct child of the root
    return get_level1_wbs_child(parent, visited)

df_upd['branch_id'] = df_upd['wbs_id'].astype(str).apply(get_level1_wbs_child)
df_upd['branch_name'] = df_upd['branch_id'].map(wbs_id_to_name)

print("\n### DISTRIBUTION BY WBS BRANCH (LEVEL 1 CHILDREN) ###")
print("| WBS Branch | Total Acts | Critical | At Risk | Watching | Stable |")
print("|---|---|---|---|---|---|")
wbs_groups = df_upd.groupby('branch_name')
for name, group in wbs_groups:
    g_total = len(group)
    g_counts = group['float_class'].value_counts()
    c_cnt = g_counts.get("Critical", 0)
    ar_cnt = g_counts.get("At Risk", 0)
    w_cnt = g_counts.get("Watching", 0)
    s_cnt = g_counts.get("Stable", 0)
    print(f"| {name} | {g_total} | {c_cnt} ({c_cnt/g_total*100:.1f}%) | {ar_cnt} ({ar_cnt/g_total*100:.1f}%) | {w_cnt} ({w_cnt/g_total*100:.1f}%) | {s_cnt} ({s_cnt/g_total*100:.1f}%) |")
