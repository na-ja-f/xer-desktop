import sys, os
import pandas as pd
import random
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore

# 1. Load data
store = XERDataStore()
baseline_path = '/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer'
update_path = '/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer'

ext_bl = CompleteXERExtractor(baseline_path, 'baseline')
ext_bl.extract_all()
store.add_version(ext_bl.get_complete_data(), 'AMR-BL-R00-2', '2025-11-29', type='baseline', context='test')

ext_upd = CompleteXERExtractor(update_path, 'update')
ext_upd.extract_all()
store.add_version(ext_upd.get_complete_data(), 'AMR-UPD-29-Nov 25', '2025-11-29', type='update', context='test')

baseline_version = store.get_baseline(context='test')
update_version = store.get_latest(context='test')

# Raw tables
raw_bl_tasks = baseline_version['data']['tables']['TASK']
raw_upd_tasks = update_version['data']['tables']['TASK']

df_bl = baseline_version['df']['tasks'].copy()
df_upd = update_version['df']['tasks'].copy()
df_pred = update_version['df'].get('taskpred', pd.DataFrame()).copy()

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

# Base mappings
hpd = update_version.get('hours_per_day', 8.0)
baseline_start_map = df_bl.set_index('task_code')['_dt_target_start_date'].to_dict()
baseline_finish_map = df_bl.set_index('task_code')['_dt_target_end_date'].to_dict()

dur_col = 'target_drtn_hr_cnt' if 'target_drtn_hr_cnt' in df_bl.columns else 'orig_dur_hr_cnt'
df_bl['bl_duration_days'] = pd.to_numeric(df_bl[dur_col], errors='coerce').fillna(0) / hpd
baseline_duration_map = df_bl.set_index('task_code')['bl_duration_days'].to_dict()

df_upd['bl_start_date'] = df_upd['task_code'].map(baseline_start_map)
df_upd['bl_finish_date'] = df_upd['task_code'].map(baseline_finish_map)
df_upd['bl_duration_days'] = df_upd['task_code'].map(baseline_duration_map).fillna(0)

# Status
def calc_status(row):
    is_completed = pd.notnull(row.get('_dt_act_end_date'))
    is_in_progress = pd.notnull(row.get('_dt_act_start_date')) and not is_completed
    if is_completed: return "COMPLETED"
    if is_in_progress: return "IN_PROGRESS"
    return "NOT_STARTED"

df_upd['status_enum'] = df_upd.apply(calc_status, axis=1)

# Current finish
def get_current_finish(row):
    act = row.get('_dt_act_end_date')
    if pd.notnull(act): return act
    return row.get('_dt_target_end_date')

df_upd['current_finish'] = df_upd.apply(get_current_finish, axis=1)

# Delay days
def calc_p6_delay(row):
    code = row.get('task_code')
    baseline_finish = baseline_finish_map.get(code)
    current_finish = row.get('current_finish')
    if pd.isnull(baseline_finish) or pd.isnull(current_finish):
        return 0
    if current_finish <= baseline_finish:
        return 0
    diff = current_finish - baseline_finish
    return int(diff.days) if hasattr(diff, 'days') else 0

df_upd['delay_days'] = df_upd.apply(calc_p6_delay, axis=1)

# Data Date
data_date = pd.to_datetime('2025-11-29')

# Classifications
def check_execution_delayed(row):
    st = row['status_enum']
    bl_start = row['bl_start_date']
    bl_finish = row['bl_finish_date']
    if st == 'COMPLETED': return False
    if st == 'NOT_STARTED' and pd.notnull(bl_start) and bl_start <= data_date: return True
    if pd.notnull(bl_finish) and bl_finish <= data_date: return True
    return False

df_upd['is_execution_delayed'] = df_upd.apply(check_execution_delayed, axis=1)

df_upd['forecast_slip_days'] = df_upd['delay_days']
df_upd['threshold_days'] = df_upd['bl_duration_days'].apply(lambda d: max(5.0, 0.05 * d))

def check_at_risk_threshold(row):
    if row['is_execution_delayed']: return False
    return row['forecast_slip_days'] > row['threshold_days']

df_upd['is_at_risk'] = df_upd.apply(check_at_risk_threshold, axis=1)

# ----------------------------------------------------
# 1. Select 10 random At Risk activities
# ----------------------------------------------------
random.seed(42)  # For deterministic execution
at_risk_indices = df_upd[df_upd['is_at_risk']].index.tolist()
sampled_indices = random.sample(at_risk_indices, 10)
sampled_df = df_upd.loc[sampled_indices]

print("\n=== VERIFICATION: 10 AT RISK ACTIVITIES ===")
for i, (idx, row) in enumerate(sampled_df.iterrows(), 1):
    code = row['task_code']
    print(f"\n{i}. Activity Code: {code}")
    print(f"   Name: {row['task_name']}")
    print(f"   Baseline Start: {str(row['bl_start_date'])[:10]} | Baseline Finish: {str(row['bl_finish_date'])[:10]}")
    print(f"   Current Early Start: {str(row['_dt_target_start_date'])[:10]} | Current Early Finish: {str(row['_dt_target_end_date'])[:10]}")
    print(f"   Forecast Finish Used: {str(row['current_finish'])[:10]}")
    print(f"   Calculated Slip Days: {row['forecast_slip_days']} (Threshold: {row['threshold_days']:.1f} days, BL Duration: {row['bl_duration_days']:.1f} days)")
    print(f"   Status: {row['status_enum']}")
    
    # Check exact raw database fields in update & baseline
    raw_upd_row = next((r for r in raw_upd_tasks if r.get('task_code') == code), {})
    raw_bl_row = next((r for r in raw_bl_tasks if r.get('task_code') == code), {})
    
    print("   Update Raw XER Fields:")
    for field in ['target_start_date', 'plan_start_date', 'target_end_date', 'plan_end_date', 'act_start_date', 'act_end_date', 'target_drtn_hr_cnt']:
        if field in raw_upd_row:
            print(f"     - {field}: '{raw_upd_row[field]}'")
    print("   Baseline Raw XER Fields:")
    for field in ['target_start_date', 'plan_start_date', 'target_end_date', 'plan_end_date', 'act_start_date', 'act_end_date', 'target_drtn_hr_cnt']:
        if field in raw_bl_row:
            print(f"     - {field}: '{raw_bl_row[field]}'")

# ----------------------------------------------------
# 2. Histogram of forecast slippage
# ----------------------------------------------------
bin_slip = [0, 5, 15, 30, 50, 100, float('inf')]
labels_slip = ['0–5 days', '5–15 days', '15–30 days', '30–50 days', '50–100 days', '100+ days']
slip_all = df_upd[df_upd['forecast_slip_days'] > 0]['forecast_slip_days']
slip_hist = pd.cut(slip_all, bins=bin_slip, labels=labels_slip, right=True).value_counts().sort_index()

print("\n=== FORECAST SLIPPAGE HISTOGRAM ===")
for label, count in slip_hist.items():
    print(f"  {label:<12} : {count} activities")

# ----------------------------------------------------
# 3. Top 20 activities with largest forecast slip
# ----------------------------------------------------
print("\n=== TOP 20 ACTIVITIES WITH LARGEST SLIP ===")
print(f"{'Task Code':<15} | {'Task Name':<45} | {'BL Finish':<10} | {'Forecast Fin':<10} | {'Slip Days':<10} | {'Status':<10}")
print("-" * 105)
for _, row in df_upd.sort_values(by='forecast_slip_days', ascending=False).head(20).iterrows():
    print(f"{row['task_code']:<15} | {row['task_name'][:45]:<45} | {str(row['bl_finish_date'])[:10]:<10} | {str(row['current_finish'])[:10]:<10} | {row['forecast_slip_days']:<10} | {row['status_enum']:<10}")

# ----------------------------------------------------
# 4. Check common predecessor chain / driving path
# ----------------------------------------------------
print("\n=== ANALYZING THE 20-50 DAY SLIP BUCKET ===")
bucket_20_50 = df_upd[(df_upd['forecast_slip_days'] >= 20) & (df_upd['forecast_slip_days'] <= 50)]
print(f"Number of activities in 20-50 day slip bucket: {len(bucket_20_50)}")
print("Slip Value Frequencies in this bucket:")
freqs = bucket_20_50['forecast_slip_days'].value_counts().sort_index(ascending=False)
for slip, freq in freqs.items():
    print(f"  {slip} days slip: {freq} activities")

# Execution Delayed activities (the roots)
exec_del_ids = set(df_upd[df_upd['is_execution_delayed']]['task_id'].tolist())
print(f"\nNumber of Execution Delayed activities (potential roots): {len(exec_del_ids)}")

# Let's inspect the execution delayed activities and print their slips/status
print("\nExecution Delayed activities (first 15):")
print(f"{'Task Code':<15} | {'Task Name':<45} | {'BL Start':<10} | {'BL Finish':<10} | {'Status':<12}")
print("-" * 100)
for _, row in df_upd[df_upd['is_execution_delayed']].head(15).iterrows():
    print(f"{row['task_code']:<15} | {row['task_name'][:45]:<45} | {str(row['bl_start_date'])[:10]:<10} | {str(row['bl_finish_date'])[:10]:<10} | {row['status_enum']:<12}")

# Trace if they share common predecessors.
# Let's build a simple predecessor adjacency list
pred_adj = {}
for _, row in df_pred.iterrows():
    tid = row['task_id']
    pid = row['pred_task_id']
    if tid not in pred_adj:
        pred_adj[tid] = []
    pred_adj[tid].append(pid)

# Function to get all ancestors of a task
def get_ancestors(tid, memo=None):
    if memo is None:
        memo = {}
    if tid in memo:
        return memo[tid]
    
    ancestors = set()
    preds = pred_adj.get(tid, [])
    for p in preds:
        ancestors.add(p)
        ancestors.update(get_ancestors(p, memo))
    
    memo[tid] = ancestors
    return ancestors

# Let's check how many tasks in the 20-50 day bucket have at least one of the 79 execution delayed tasks in their predecessor history
ancestors_memo = {}
common_exec_del_predecessors = {}
for _, row in bucket_20_50.iterrows():
    tid = row['task_id']
    anc = get_ancestors(tid, ancestors_memo)
    # Intersect with execution delayed task IDs
    roots = anc.intersection(exec_del_ids)
    if roots:
        for r in roots:
            common_exec_del_predecessors[r] = common_exec_del_predecessors.get(r, 0) + 1

print("\n--- PREDECESSOR CHAIN ANALYSIS ---")
# Count how many of the 4138 activities have a predecessor chain back to an Execution Delayed task
has_exec_del_pred_count = 0
for _, row in bucket_20_50.iterrows():
    tid = row['task_id']
    anc = ancestors_memo.get(tid, set())
    if anc.intersection(exec_del_ids):
        has_exec_del_pred_count += 1

print(f"Of the {len(bucket_20_50)} activities in the 20-50 day bucket:")
print(f"  - {has_exec_del_pred_count} activities ({has_exec_del_pred_count/len(bucket_20_50)*100:.2f}%) have at least one Execution Delayed activity in their predecessor history!")

if common_exec_del_predecessors:
    print("\nMost common Execution Delayed ancestors driving the successor network:")
    # Map task_id -> task_code / name
    id_to_code = df_upd.set_index('task_id')['task_code'].to_dict()
    id_to_name = df_upd.set_index('task_id')['task_name'].to_dict()
    
    sorted_roots = sorted(common_exec_del_predecessors.items(), key=lambda x: x[1], reverse=True)
    for rid, count in sorted_roots[:10]:
        print(f"  - {id_to_code.get(rid)} ({id_to_name.get(rid)[:40]}): affects {count} downstream activities")

# Let's inspect the project duration and relationships
print(f"\nTotal relations in schedule: {len(df_pred)}")

