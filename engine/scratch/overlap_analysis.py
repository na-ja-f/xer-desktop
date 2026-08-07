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

df_bl = store.get_baseline(context='test')['df']['tasks'].copy()
df_upd = store.get_latest(context='test')['df']['tasks'].copy()

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

# Hours per day
hpd = 8.0
bl_start_map = df_bl.set_index('task_code')['_dt_target_start_date'].to_dict()
bl_finish_map = df_bl.set_index('task_code')['_dt_target_end_date'].to_dict()
df_bl['bl_float_hrs'] = pd.to_numeric(df_bl['total_float_hr_cnt'], errors='coerce').fillna(0.0)
bl_float_map = df_bl.set_index('task_code')['bl_float_hrs'].to_dict()

dur_col = 'target_drtn_hr_cnt' if 'target_drtn_hr_cnt' in df_bl.columns else 'orig_dur_hr_cnt'
df_bl['bl_duration_days'] = pd.to_numeric(df_bl[dur_col], errors='coerce').fillna(0.0) / hpd
baseline_duration_map = df_bl.set_index('task_code')['bl_duration_days'].to_dict()

# Merge baseline variables into update
df_upd['bl_start_date'] = df_upd['task_code'].map(bl_start_map)
df_upd['bl_finish_date'] = df_upd['task_code'].map(bl_finish_map)
df_upd['bl_duration_days'] = df_upd['task_code'].map(baseline_duration_map).fillna(0.0)
df_upd['bl_float_hrs'] = df_upd['task_code'].map(bl_float_map).fillna(0.0)

# Current variables
df_upd['current_float_hrs'] = pd.to_numeric(df_upd['total_float_hr_cnt'], errors='coerce').fillna(0.0)
df_upd['bl_float_days'] = df_upd['bl_float_hrs'] / hpd
df_upd['current_float_days'] = df_upd['current_float_hrs'] / hpd

# Execution status
data_date = pd.to_datetime('2025-11-29')
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

# Current forecast finish
def get_current_finish(row):
    act = row.get('_dt_act_end_date')
    if pd.notnull(act): return act
    return row.get('_dt_target_end_date')

df_upd['current_finish'] = df_upd.apply(get_current_finish, axis=1)

# Forecast slip days
def calc_p6_delay(row):
    code = row.get('task_code')
    baseline_finish = bl_finish_map.get(code)
    current_finish = row.get('current_finish')
    if pd.isnull(baseline_finish) or pd.isnull(current_finish):
        return 0
    if current_finish <= baseline_finish:
        return 0
    diff = current_finish - baseline_finish
    return int(diff.days) if hasattr(diff, 'days') else 0

df_upd['forecast_slip_days'] = df_upd.apply(calc_p6_delay, axis=1)
df_upd['threshold_days'] = df_upd['bl_duration_days'].apply(lambda d: max(5.0, 0.05 * d))

# -------------------------------------------------------------------------
# Method A definitions
# -------------------------------------------------------------------------
# Dashboard At Risk: excludes completed and execution delayed
df_upd['dashboard_at_risk_current'] = df_upd.apply(
    lambda r: (not r['is_execution_delayed']) and (r['status_enum'] != 'COMPLETED') and (r['forecast_slip_days'] > r['threshold_days']),
    axis=1
)

# Raw Forecast Slip metric: Forecast Slip > Threshold
df_upd['raw_slip_metric'] = df_upd.apply(
    lambda r: r['forecast_slip_days'] > r['threshold_days'],
    axis=1
)

# -------------------------------------------------------------------------
# Method B definitions
# -------------------------------------------------------------------------
def calc_float_consumption(row):
    bl_f = row['bl_float_hrs']
    curr_f = row['current_float_hrs']
    if curr_f <= 0.0: return 1.0
    if bl_f <= 0.0: return 0.0
    return float((bl_f - curr_f) / bl_f)

df_upd['float_consumption_pct'] = df_upd.apply(calc_float_consumption, axis=1)

# B-039 At Risk: Float Consumption > 75%, Current Float > 0
df_upd['b039_at_risk'] = df_upd.apply(
    lambda r: r['current_float_hrs'] > 0.0 and r['float_consumption_pct'] > 0.75,
    axis=1
)

print("--- ANALYSIS 1: DASHBOARD-LEVEL OVERLAP ---")
both_db = len(df_upd[df_upd['dashboard_at_risk_current'] & df_upd['b039_at_risk']])
only_db_slip = len(df_upd[df_upd['dashboard_at_risk_current'] & ~df_upd['b039_at_risk']])
only_db_float = len(df_upd[~df_upd['dashboard_at_risk_current'] & df_upd['b039_at_risk']])
print(f"Dashboard-level At Risk count: Current={df_upd['dashboard_at_risk_current'].sum()}, B-039={df_upd['b039_at_risk'].sum()}")
print(f"Flagged by BOTH: {both_db}")
print(f"Flagged ONLY by Current (Forecast Slip): {only_db_slip}")
print(f"Flagged ONLY by B-039 (Float Consumption): {only_db_float}")

print("\n--- ANALYSIS 2: RAW METRIC OVERLAP (Uncompleted Activities) ---")
df_uncompleted = df_upd[df_upd['status_enum'] != 'COMPLETED'].copy()
both_raw = len(df_uncompleted[df_uncompleted['raw_slip_metric'] & df_uncompleted['b039_at_risk']])
only_raw_slip = len(df_uncompleted[df_uncompleted['raw_slip_metric'] & ~df_uncompleted['b039_at_risk']])
only_raw_float = len(df_uncompleted[~df_uncompleted['raw_slip_metric'] & df_uncompleted['b039_at_risk']])
print(f"Uncompleted Activities: {len(df_uncompleted)}")
print(f"Raw Slip > Threshold count: {df_uncompleted['raw_slip_metric'].sum()}")
print(f"B-039 At Risk count: {df_uncompleted['b039_at_risk'].sum()}")
print(f"Flagged by BOTH: {both_raw}")
print(f"Flagged ONLY by Forecast Slip > Threshold: {only_raw_slip}")
print(f"Flagged ONLY by Float Consumption > 75%: {only_raw_float}")

print("\n--- DETAILS OF THE ONLY_RAW_FLOAT ACTIVITIES ---")
only_raw_float_df = df_uncompleted[~df_uncompleted['raw_slip_metric'] & df_uncompleted['b039_at_risk']].copy()
print(f"Number of activities in only_raw_float: {len(only_raw_float_df)}")
for _, row in only_raw_float_df.iterrows():
    print(f"ID: {row['task_code']}, Name: {row['task_name']}, BL Float: {row['bl_float_days']:.2f}, Curr Float: {row['current_float_days']:.2f}, Consumed %: {row['float_consumption_pct']*100:.1f}%, Slip: {row['forecast_slip_days']}, Status: {row['status_enum']}")

print("\n--- DETAILS OF THE ONLY_DB_FLOAT ACTIVITIES ---")
only_db_float_df = df_upd[~df_upd['dashboard_at_risk_current'] & df_upd['b039_at_risk']].copy()
print(f"Number of activities in only_db_float: {len(only_db_float_df)}")
for _, row in only_db_float_df.iterrows():
    print(f"ID: {row['task_code']}, Name: {row['task_name']}, BL Float: {row['bl_float_days']:.2f}, Curr Float: {row['current_float_days']:.2f}, Consumed %: {row['float_consumption_pct']*100:.1f}%, Slip: {row['forecast_slip_days']}, Status: {row['status_enum']}, Execution Delayed: {row['is_execution_delayed']}")
