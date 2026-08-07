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

# Print columns that might hold percent complete
pct_cols = [c for c in tasks.columns if 'pct' in c.lower() or 'percent' in c.lower() or 'complete' in c.lower()]
print(f"TASK columns containing 'pct' or 'complete': {pct_cols}")

bl_taskrsrc['target_cost'] = pd.to_numeric(bl_taskrsrc['target_cost'], errors='coerce').fillna(0)
bac_by_task = bl_taskrsrc.groupby('task_id')['target_cost'].sum().to_dict()

taskrsrc['target_cost'] = pd.to_numeric(taskrsrc['target_cost'], errors='coerce').fillna(0)
budgeted_by_task = taskrsrc.groupby('task_id')['target_cost'].sum().to_dict()

bl_tid_to_code = bl_tasks.set_index('task_id')['task_code'].to_dict()
bac_by_code = {bl_tid_to_code.get(tid): bac for tid, bac in bac_by_task.items() if bl_tid_to_code.get(tid)}

taskrsrc['act_reg_cost'] = pd.to_numeric(taskrsrc['act_reg_cost'], errors='coerce').fillna(0)
ac_by_task = taskrsrc.groupby('task_id')['act_reg_cost'].sum().to_dict()

taskrsrc['target_qty'] = pd.to_numeric(taskrsrc['target_qty'], errors='coerce').fillna(0)
taskrsrc['act_reg_qty'] = pd.to_numeric(taskrsrc['act_reg_qty'], errors='coerce').fillna(0)
target_qty_by_task = taskrsrc.groupby('task_id')['target_qty'].sum().to_dict()
act_qty_by_task = taskrsrc.groupby('task_id')['act_reg_qty'].sum().to_dict()

in_prog = tasks[tasks['status_code'] == 'TK_Active']

print("\n-----------------------------------------------------------------------------------------------------------------------------------------")
print(f"{'Activity ID':<18} | {'% Type':<8} | {'Sel%':<6} | {'BL Cost':<12} | {'Budg Cost':<12} | {'P6 EV':<12} | {'EV_A (BL)':<12} | {'EV_B (Budg)':<12}")
print("-----------------------------------------------------------------------------------------------------------------------------------------")

count = 0
diff_count = 0
for _, row in in_prog.iterrows():
    tid = row['task_id']
    code = row['task_code']
    bac = bac_by_code.get(code, 0)
    budgeted = budgeted_by_task.get(tid, 0)
    current_ev = ac_by_task.get(tid, 0)
    
    if bac == 0 and current_ev == 0 and budgeted == 0: continue
    
    pct_type = row.get('complete_pct_type', '')
    phys_pct = pd.to_numeric(row.get('phys_complete_pct', 0), errors='coerce') / 100.0
    
    orig_dur = pd.to_numeric(row.get('target_drtn_hr_cnt', 0), errors='coerce')
    rem_dur = pd.to_numeric(row.get('remain_drtn_hr_cnt', 0), errors='coerce')
    dur_pct = (orig_dur - rem_dur) / orig_dur if orig_dur > 0 else 0.0
    dur_pct = max(0.0, min(1.0, dur_pct))
    
    t_qty = target_qty_by_task.get(tid, 0)
    a_qty = act_qty_by_task.get(tid, 0)
    units_pct = (a_qty / t_qty) if t_qty > 0 else 0.0
    
    selected_pct = 0.0
    if pct_type == 'CP_Phys': selected_pct = phys_pct
    elif pct_type == 'CP_Drtn': selected_pct = dur_pct
    elif pct_type == 'CP_Units': selected_pct = units_pct
    
    ev_a = bac * selected_pct
    ev_b = budgeted * selected_pct
    
    # Prioritize printing activities where BL Cost != Budgeted Cost
    if abs(bac - budgeted) > 0.01:
        print(f"{code:<18} | {pct_type:<8} | {selected_pct:<6.2%} | ${bac:<11.2f} | ${budgeted:<11.2f} | ${current_ev:<11.2f} | ${ev_a:<11.2f} | ${ev_b:<11.2f}")
        diff_count += 1

print(f"Total activities where BL Cost != Budgeted Cost: {diff_count}")

if diff_count < 20:
    print("\nFilling remainder with matching cost activities:")
    for _, row in in_prog.iterrows():
        tid = row['task_id']
        code = row['task_code']
        bac = bac_by_code.get(code, 0)
        budgeted = budgeted_by_task.get(tid, 0)
        current_ev = ac_by_task.get(tid, 0)
        
        if abs(bac - budgeted) <= 0.01 and bac > 0:
            pct_type = row.get('complete_pct_type', '')
            phys_pct = pd.to_numeric(row.get('phys_complete_pct', 0), errors='coerce') / 100.0
            
            orig_dur = pd.to_numeric(row.get('target_drtn_hr_cnt', 0), errors='coerce')
            rem_dur = pd.to_numeric(row.get('remain_drtn_hr_cnt', 0), errors='coerce')
            dur_pct = (orig_dur - rem_dur) / orig_dur if orig_dur > 0 else 0.0
            dur_pct = max(0.0, min(1.0, dur_pct))
            
            selected_pct = 0.0
            if pct_type == 'CP_Phys': selected_pct = phys_pct
            elif pct_type == 'CP_Drtn': selected_pct = dur_pct
            
            ev_a = bac * selected_pct
            ev_b = budgeted * selected_pct
            
            print(f"{code:<18} | {pct_type:<8} | {selected_pct:<6.2%} | ${bac:<11.2f} | ${budgeted:<11.2f} | ${current_ev:<11.2f} | ${ev_a:<11.2f} | ${ev_b:<11.2f}")
            diff_count += 1
            if diff_count >= 20: break

EOF
