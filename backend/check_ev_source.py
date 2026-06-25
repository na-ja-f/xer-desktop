import sys, os
import pandas as pd
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore

store = XERDataStore()

print("Loading Baseline...")
ext_bl = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer', 'baseline')
ext_bl.extract_all()
data_bl = ext_bl.get_complete_data()
store.add_version(data_bl, data_bl['project']['project_name'], data_bl['project']['data_date'], type='baseline', context='test')

print("Loading Update...")
ext_upd = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer', 'update')
ext_upd.extract_all()
data_upd = ext_upd.get_complete_data()
store.add_version(data_upd, data_upd['project']['project_name'], data_upd['project']['data_date'], type='update', context='test')

upd_source = store.get_version(context='test')
bl_source = store.get_baseline(context='test')

tasks = upd_source['df']['tasks']
taskrsrc = upd_source['df']['taskrsrc']
bl_taskrsrc = bl_source['df']['taskrsrc']
bl_tasks = bl_source['df']['tasks']

# Map IDs to Codes
tid_to_code = tasks.set_index('task_id')['task_code'].to_dict()
bl_tid_to_code = bl_tasks.set_index('task_id')['task_code'].to_dict()

# Calculate BAC from Baseline
bl_taskrsrc['target_cost'] = pd.to_numeric(bl_taskrsrc['target_cost'], errors='coerce').fillna(0)
bac_by_task = bl_taskrsrc.groupby('task_id')['target_cost'].sum().to_dict()
bac_by_code = {bl_tid_to_code.get(tid): bac for tid, bac in bac_by_task.items() if bl_tid_to_code.get(tid)}

# Calculate AC from Update
taskrsrc['act_reg_cost'] = pd.to_numeric(taskrsrc['act_reg_cost'], errors='coerce').fillna(0)
ac_by_task = taskrsrc.groupby('task_id')['act_reg_cost'].sum().to_dict()

def print_act(code):
    row = tasks[tasks['task_code'] == code]
    if row.empty:
        print(f"Activity {code} not found.")
        return
    row = row.iloc[0]
    tid = row['task_id']
    bac = bac_by_code.get(code, 0)
    ac = ac_by_task.get(tid, 0)
    
    # Are there any EV-specific columns in TASK?
    ev_cols = [c for c in row.index if 'ev' in c.lower() or 'earned' in c.lower() or 'bcwp' in c.lower()]
    ev_vals = {c: row[c] for c in ev_cols}
    
    # Are there any EV-specific columns in TASKRSRC?
    tr = taskrsrc[taskrsrc['task_id'] == tid]
    tr_ev_cols = [c for c in taskrsrc.columns if 'ev' in c.lower() or 'earned' in c.lower() or 'bcwp' in c.lower()]
    tr_ev_vals = {}
    if not tr.empty:
        for c in tr_ev_cols:
            tr_ev_vals[c] = tr[c].tolist()
            
    pct_drtn = row.get('complete_pct_type', '')
    phys_pct = row.get('phys_complete_pct', '')
    
    # EV as we would correctly calculate it
    perf_pct = pd.to_numeric(phys_pct, errors='coerce') / 100.0 if pd.notnull(phys_pct) and str(phys_pct).strip() != '' else 0.0
    correct_ev = bac * perf_pct
    
    print(f"\nActivity: {code}")
    print(f"  BAC (TASKRSRC.target_cost in BL): ${bac:,.2f}")
    print(f"  AC  (TASKRSRC.act_reg_cost in UPD): ${ac:,.2f}")
    print(f"  Correct EV (BAC * Phys Pct): ${correct_ev:,.2f}")
    print(f"  Pct Type: {pct_drtn}, Phys Pct: {phys_pct}%")
    print(f"  EV columns in TASK: {ev_vals}")
    print(f"  EV columns in TASKRSRC: {tr_ev_vals}")

print("--- Checking AMI-FXCH-1130 ---")
print_act('AMI-FXCH-1130')

print("\n--- Checking 10 In-Progress Activities (With Costs) ---")
in_prog = tasks[tasks['status_code'] == 'TK_Active']
count = 0
for _, row in in_prog.iterrows():
    code = row['task_code']
    bac = bac_by_code.get(code, 0)
    ac = ac_by_task.get(row['task_id'], 0)
    if bac > 0 or ac > 0:
        print_act(code)
        count += 1
        if count >= 10: break

