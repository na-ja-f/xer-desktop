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

# Date mapping from raw cols to internal datetime cols
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

# Parse floats to numeric hours
df_bl['bl_float_hrs'] = pd.to_numeric(df_bl['total_float_hr_cnt'], errors='coerce').fillna(0.0)
df_upd['current_float_hrs'] = pd.to_numeric(df_upd['total_float_hr_cnt'], errors='coerce').fillna(0.0)

# Build baseline float map
bl_float_map = df_bl.set_index('task_code')['bl_float_hrs'].to_dict()

# Merge baseline float into update tasks
df_upd['bl_float_hrs'] = df_upd['task_code'].map(bl_float_map).fillna(0.0)

# Hours per day
hpd = upd_ver.get('hours_per_day', 8.0)
df_upd['bl_float_days'] = df_upd['bl_float_hrs'] / hpd
df_upd['current_float_days'] = df_upd['current_float_hrs'] / hpd

# Calculate Float Consumption %
def calc_float_consumption(row):
    bl_f = row['bl_float_hrs']
    curr_f = row['current_float_hrs']
    
    if curr_f <= 0.0:
        return 1.0
        
    if bl_f <= 0.0:
        return 0.0
        
    consumption = (bl_f - curr_f) / bl_f
    return float(consumption)

df_upd['float_consumption_pct'] = df_upd.apply(calc_float_consumption, axis=1)

# Classify tasks
def classify_float_risk(row):
    curr_f = row['current_float_hrs']
    pct = row['float_consumption_pct']
    
    if curr_f <= 0.0:
        return "Critical"
    elif pct > 0.75:
        return "At Risk"
    elif pct >= 0.50:
        return "Watching"
    else:
        return "Stable"

df_upd['float_class'] = df_upd.apply(classify_float_risk, axis=1)

# Status logic (Execution Delay check)
data_date = pd.to_datetime('2025-11-29')

bl_start_map = df_bl.set_index('task_code')['_dt_target_start_date'].to_dict()
bl_finish_map = df_bl.set_index('task_code')['_dt_target_end_date'].to_dict()
df_upd['bl_start_date'] = df_upd['task_code'].map(bl_start_map)
df_upd['bl_finish_date'] = df_upd['task_code'].map(bl_finish_map)

# Status parsing
def calc_status(row):
    is_completed = pd.notnull(row.get('_dt_act_end_date'))
    is_in_progress = pd.notnull(row.get('_dt_act_start_date')) and not is_completed
    if is_completed: return "COMPLETED"
    if is_in_progress: return "IN_PROGRESS"
    return "NOT_STARTED"

df_upd['status_enum'] = df_upd.apply(calc_status, axis=1)

def check_execution_delayed(row):
    st = row['status_enum']
    bl_start = row['bl_start_date']
    bl_finish = row['bl_finish_date']
    if st == 'COMPLETED': return False
    if st == 'NOT_STARTED' and pd.notnull(bl_start) and bl_start <= data_date: return True
    if pd.notnull(bl_finish) and bl_finish <= data_date: return True
    return False

df_upd['is_execution_delayed'] = df_upd.apply(check_execution_delayed, axis=1)

# Build WBS parent mapping for Level-1 resolution
wbs_id_to_name = {}
wbs_id_to_parent = {}
for _, row in df_wbs.iterrows():
    wid = str(row.get("wbs_id", ""))
    wbs_id_to_name[wid] = str(row.get("wbs_name") or row.get("wbs_short_name") or wid)
    parent = row.get("parent_wbs_id")
    wbs_id_to_parent[wid] = str(parent) if parent and str(parent) != "nan" else None

def get_level1_branch(wid: str, visited=None) -> str:
    if visited is None:
        visited = set()
    if wid in visited:
        return wid
    visited.add(wid)
    parent = wbs_id_to_parent.get(wid)
    if not parent:
        return wid
    grandparent = wbs_id_to_parent.get(parent)
    if not grandparent:
        return wid
    return get_level1_branch(parent, visited)

df_upd['level1_wbs_id'] = df_upd['wbs_id'].astype(str).apply(get_level1_branch)
df_upd['level1_wbs_name'] = df_upd['level1_wbs_id'].map(wbs_id_to_name)

print("### FLOAT CONSUMPTION AUDIT RESULTS FOR AL AMRAH ###")
print(f"Total Activities Analyzed: {len(df_upd)}\n")

# Distribution table
counts = df_upd['float_class'].value_counts()
pcts = df_upd['float_class'].value_counts(normalize=True) * 100
print("| Category | Count | Percentage | Definition |")
print("|---|---|---|---|")
for cat in ["Critical", "At Risk", "Watching", "Stable"]:
    print(f"| **{cat}** | {counts.get(cat, 0)} | {pcts.get(cat, 0.0):.2f}% | Current Float <= 0 for Critical, consumption rules for others |")

# Check execution delayed overlap with float consumption classes
print("\n### OVERLAP: WHERE DO THE 79 EXECUTION-DELAYED ACTIVITIES FALL? ###")
delayed_df = df_upd[df_upd['is_execution_delayed']]
delayed_classes = delayed_df['float_class'].value_counts()
for cat in ["Critical", "At Risk", "Watching", "Stable"]:
    print(f"Delayed in {cat}: {delayed_classes.get(cat, 0)}")

# Distribution by WBS Branch
print("\n### DISTRIBUTION BY WBS BRANCH (LEVEL 1) ###")
print("| WBS Branch | Total Acts | Critical | At Risk | Watching | Stable |")
print("|---|---|---|---|---|---|")
wbs_groups = df_upd.groupby('level1_wbs_name')
for name, group in wbs_groups:
    g_total = len(group)
    g_counts = group['float_class'].value_counts()
    c_cnt = g_counts.get("Critical", 0)
    ar_cnt = g_counts.get("At Risk", 0)
    w_cnt = g_counts.get("Watching", 0)
    s_cnt = g_counts.get("Stable", 0)
    print(f"| {name} | {g_total} | {c_cnt} ({c_cnt/g_total*100:.1f}%) | {ar_cnt} ({ar_cnt/g_total*100:.1f}%) | {w_cnt} ({w_cnt/g_total*100:.1f}%) | {s_cnt} ({s_cnt/g_total*100:.1f}%) |")

# Top 20 activities with highest float consumption (excludes baseline critical)
print("\n### TOP 20 ACTIVITIES WITH HIGHEST FLOAT CONSUMPTION ###")
df_filter_consumed = df_upd[(df_upd['bl_float_hrs'] > 0.0) & (df_upd['current_float_hrs'] > 0.0)].copy()
top_20 = df_filter_consumed.sort_values(by='float_consumption_pct', ascending=False).head(20)
print("| Task Code | Task Name | BL Float (Days) | Current Float (Days) | Consumed % | Category |")
print("|---|---|---|---|---|---|")
for _, row in top_20.iterrows():
    print(f"| {row['task_code']} | {row['task_name'][:50]} | {row['bl_float_days']:.1f} | {row['current_float_days']:.1f} | {row['float_consumption_pct']*100:.1f}% | {row['float_class']} |")
