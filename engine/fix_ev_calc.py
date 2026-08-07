import sys, os
import pandas as pd
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore

store = XERDataStore()

upd_source = store.get_version(context='test')
bl_source = store.get_baseline(context='test')

tasks = upd_source['df']['tasks']
taskrsrc = upd_source['df']['taskrsrc']
bl_taskrsrc = bl_source['df']['taskrsrc']

# Get BAC for each task
bl_taskrsrc['target_cost'] = pd.to_numeric(bl_taskrsrc['target_cost'], errors='coerce').fillna(0)
bac_by_task = bl_taskrsrc.groupby('task_id')['target_cost'].sum().to_dict()

cur_tid_to_code = tasks.set_index('task_id')['task_code'].to_dict()
bl_tasks = bl_source['df']['tasks']
bl_tid_to_code = bl_tasks.set_index('task_id')['task_code'].to_dict()
bac_by_code = {}
for tid, bac in bac_by_task.items():
    code = bl_tid_to_code.get(tid)
    if code: bac_by_code[code] = bac

# Calculate AC by task
taskrsrc['act_reg_cost'] = pd.to_numeric(taskrsrc['act_reg_cost'], errors='coerce').fillna(0)
ac_by_task = taskrsrc.groupby('task_id')['act_reg_cost'].sum().to_dict()

samples = []

for _, row in tasks.iterrows():
    tid = row['task_id']
    code = cur_tid_to_code.get(tid)
    bac = bac_by_code.get(code, 0)
    ac = ac_by_task.get(tid, 0)
    
    if bac == 0 and ac == 0: continue
    
    pct_type = row.get('complete_pct_type', 'CP_Drtn')
    perf_pct = 0.0
    
    if pct_type == 'CP_Phys':
        perf_pct = pd.to_numeric(row.get('phys_complete_pct', 0), errors='coerce') / 100.0
    elif pct_type == 'CP_Drtn':
        orig_dur = pd.to_numeric(row.get('target_drtn_hr_cnt', 0), errors='coerce')
        rem_dur = pd.to_numeric(row.get('remain_drtn_hr_cnt', 0), errors='coerce')
        if orig_dur > 0:
            perf_pct = (orig_dur - rem_dur) / orig_dur
            if perf_pct < 0: perf_pct = 0.0
            if perf_pct > 1: perf_pct = 1.0
        elif row.get('status_code') == 'TK_Complete':
            perf_pct = 1.0
            
    # For CP_Units, we'd need units, but let's simplify for now
    ev = bac * perf_pct
    
    if bac > 0 and ac > 0 and code.startswith('AMR-UPD-29-Nov 25.PRLM1'):
        samples.append({
            'ID': code,
            'BAC': bac,
            'AC': ac,
            'EV': ev,
            'Type': pct_type,
            'Perf%': perf_pct
        })
        
print("Sample Activities with BAC/AC/EV:")
for s in samples[:10]:
    print(f"{s['ID']} | BAC: {s['BAC']:,.2f} | AC: {s['AC']:,.2f} | EV: {s['EV']:,.2f} | CPI: {(s['EV']/s['AC'] if s['AC']>0 else 0):.2f}")

