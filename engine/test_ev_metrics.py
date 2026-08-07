import sys, os
import pandas as pd
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor

from modules.data_store import XERDataStore

store = XERDataStore()

ext_bl = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer', 'baseline')
ext_bl.extract_all()
data_bl = ext_bl.get_complete_data()
store.add_version(data_bl, data_bl['project']['project_name'], data_bl['project']['data_date'], type='baseline', context='test')

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

tid_to_code = tasks.set_index('task_id')['task_code'].to_dict()
bl_tid_to_code = bl_tasks.set_index('task_id')['task_code'].to_dict()

bl_taskrsrc['target_cost'] = pd.to_numeric(bl_taskrsrc['target_cost'], errors='coerce').fillna(0)
bac_by_task = bl_taskrsrc.groupby('task_id')['target_cost'].sum().to_dict()
bac_by_code = {bl_tid_to_code.get(tid): bac for tid, bac in bac_by_task.items() if bl_tid_to_code.get(tid)}

taskrsrc['act_reg_cost'] = pd.to_numeric(taskrsrc['act_reg_cost'], errors='coerce').fillna(0)
ac_by_task = taskrsrc.groupby('task_id')['act_reg_cost'].sum().to_dict()

# Let's get actual/target qty to compute Units % Complete
taskrsrc['target_qty'] = pd.to_numeric(taskrsrc['target_qty'], errors='coerce').fillna(0)
taskrsrc['act_reg_qty'] = pd.to_numeric(taskrsrc['act_reg_qty'], errors='coerce').fillna(0)
target_qty_by_task = taskrsrc.groupby('task_id')['target_qty'].sum().to_dict()
act_qty_by_task = taskrsrc.groupby('task_id')['act_reg_qty'].sum().to_dict()

in_prog = tasks[(tasks['status_code'] == 'TK_Active') | (tasks['status_code'] == 'TK_Complete')]

samples = []

for _, row in in_prog.iterrows():
    tid = row['task_id']
    code = row['task_code']
    bac = bac_by_code.get(code, 0)
    ac = ac_by_task.get(tid, 0)
    
    if bac == 0 and ac == 0: continue
    
    pct_type = row.get('complete_pct_type', '')
    phys_pct = pd.to_numeric(row.get('phys_complete_pct', 0), errors='coerce') / 100.0
    
    orig_dur = pd.to_numeric(row.get('target_drtn_hr_cnt', 0), errors='coerce')
    rem_dur = pd.to_numeric(row.get('remain_drtn_hr_cnt', 0), errors='coerce')
    act_dur = pd.to_numeric(row.get('act_drtn_hr_cnt', 0), errors='coerce')
    
    dur_pct = 0.0
    if orig_dur > 0:
        dur_pct = (orig_dur - rem_dur) / orig_dur
    elif row.get('status_code') == 'TK_Complete':
        dur_pct = 1.0
        
    dur_pct = max(0.0, min(1.0, dur_pct))
    
    t_qty = target_qty_by_task.get(tid, 0)
    a_qty = act_qty_by_task.get(tid, 0)
    units_pct = (a_qty / t_qty) if t_qty > 0 else (1.0 if row.get('status_code') == 'TK_Complete' else 0.0)
    
    # Activity % Complete follows the setting
    act_pct = 0.0
    if pct_type == 'CP_Phys': act_pct = phys_pct
    elif pct_type == 'CP_Drtn': act_pct = dur_pct
    elif pct_type == 'CP_Units': act_pct = units_pct
    
    # We will compute the possibilities:
    ev_phys = bac * phys_pct
    ev_dur = bac * dur_pct
    ev_units = bac * units_pct
    ev_act = bac * act_pct
    
    if ac > 0 or bac > 0:
        samples.append({
            'code': code,
            'pct_type': pct_type,
            'bac': bac,
            'ac': ac,
            'phys_pct': phys_pct,
            'dur_pct': dur_pct,
            'units_pct': units_pct,
            'act_pct': act_pct,
            'ev_phys': ev_phys,
            'ev_dur': ev_dur,
            'ev_units': ev_units,
            'ev_act': ev_act
        })
        if len(samples) >= 20: break

print("-" * 120)
print(f"{'Activity ID':<18} | {'Type':<8} | {'BAC':<10} | {'AC (P6 EV?)':<11} | {'Phys Pct':<8} | {'Dur Pct':<8} | {'Units Pct':<9} | {'Act Pct':<8}")
print(f"{'':<18} | {'':<8} | {'':<10} | {'':<11} | {'EV_Phys':<8} | {'EV_Dur':<8} | {'EV_Units':<9} | {'EV_Act':<8}")
print("-" * 120)

for s in samples:
    print(f"{s['code']:<18} | {s['pct_type']:<8} | {s['bac']:<10.2f} | {s['ac']:<11.2f} | {s['phys_pct']:<8.2%} | {s['dur_pct']:<8.2%} | {s['units_pct']:<9.2%} | {s['act_pct']:<8.2%}")
    print(f"{'':<18} | {'':<8} | {'':<10} | {'':<11} | {s['ev_phys']:<8.2f} | {s['ev_dur']:<8.2f} | {s['ev_units']:<9.2f} | {s['ev_act']:<8.2f}")
    print("-" * 120)
