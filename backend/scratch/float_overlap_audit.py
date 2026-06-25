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

# Mappings from baseline
hpd = upd_ver.get('hours_per_day', 8.0)
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
# Method A: Current At Risk (Forecast Slip > Threshold, not execution delayed)
# -------------------------------------------------------------------------
def check_method_a_at_risk(row):
    if row['is_execution_delayed']: return False
    if row['status_enum'] == 'COMPLETED': return False
    return row['forecast_slip_days'] > row['threshold_days']

df_upd['method_a_at_risk'] = df_upd.apply(check_method_a_at_risk, axis=1)

# -------------------------------------------------------------------------
# Method B: B-039 At Risk (Float Consumption > 75%, Current Float > 0)
# -------------------------------------------------------------------------
def calc_float_consumption(row):
    bl_f = row['bl_float_hrs']
    curr_f = row['current_float_hrs']
    if curr_f <= 0.0: return 1.0
    if bl_f <= 0.0: return 0.0
    return float((bl_f - curr_f) / bl_f)

df_upd['float_consumption_pct'] = df_upd.apply(calc_float_consumption, axis=1)

def check_method_b_at_risk(row):
    curr_f = row['current_float_hrs']
    pct = row['float_consumption_pct']
    if curr_f <= 0.0: return False  # Exclude critical
    return pct > 0.75

df_upd['method_b_at_risk'] = df_upd.apply(check_method_b_at_risk, axis=1)

# Counts
both_count = len(df_upd[df_upd['method_a_at_risk'] & df_upd['method_b_at_risk']])
only_a_count = len(df_upd[df_upd['method_a_at_risk'] & ~df_upd['method_b_at_risk']])
only_b_count = len(df_upd[~df_upd['method_a_at_risk'] & df_upd['method_b_at_risk']])

print("### OVERLAP COMPARISON RESULTS ###")
print(f"Total Activities in Update: {len(df_upd)}")
print(f"Flagged by BOTH methods: {both_count}")
print(f"Flagged ONLY by Current (Forecast Slip): {only_a_count}")
print(f"Flagged ONLY by B-039 (Float Consumption): {only_b_count}")

# Let's inspect the top 20 activities that are At Risk under B-039 but NOT under Forecast Slip
only_b_df = df_upd[~df_upd['method_a_at_risk'] & df_upd['method_b_at_risk']].copy()
top_only_b = only_b_df.sort_values(by='float_consumption_pct', ascending=False).head(20)

print("\n=== TOP 20 ACTIVITIES FLAGGED BY B-039 BUT NOT BY FORECAST SLIP ===")
print("| Activity ID | Activity Name | BL Float (d) | Curr Float (d) | Consumed % | Slip Days | Status |")
print("|---|---|---|---|---|---|---|")
for _, row in top_only_b.iterrows():
    print(f"| {row['task_code']} | {row['task_name'][:50]} | {row['bl_float_days']:.1f} | {row['current_float_days']:.1f} | {row['float_consumption_pct']*100:.1f}% | {row['forecast_slip_days']} | {row['status_enum']} |")
