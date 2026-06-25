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

# Get BAC for each task
bl_tr_cost = pd.to_numeric(bl_taskrsrc['target_cost'], errors='coerce').fillna(0)
bac_by_task = bl_taskrsrc.groupby('task_id')['target_cost'].apply(lambda x: pd.to_numeric(x, errors='coerce').sum()).to_dict()

# Let's map current task_id to task_code, and baseline task_code to BAC
cur_tid_to_code = tasks.set_index('task_id')['task_code'].to_dict()
bl_tasks = bl_source['df']['tasks']
bl_tid_to_code = bl_tasks.set_index('task_id')['task_code'].to_dict()
bac_by_code = {}
for tid, bac in bac_by_task.items():
    code = bl_tid_to_code.get(tid)
    if code: bac_by_code[code] = bac

ev_total_physical = 0
ev_total_p6_act_cost = 0

for _, row in tasks.iterrows():
    tid = row['task_id']
    code = cur_tid_to_code.get(tid)
    bac = bac_by_code.get(code, 0)
    
    phys = pd.to_numeric(row.get('phys_complete_pct', 0), errors='coerce') / 100.0
    ev_physical = bac * phys
    ev_total_physical += ev_physical

tr_act_reg = pd.to_numeric(taskrsrc['act_reg_cost'], errors='coerce').fillna(0)
ev_total_p6_act_cost = tr_act_reg.sum()

print(f"Total BAC: ${sum(bac_by_code.values()):,.2f}")
print(f"Total EV (if derived from phys_complete_pct * BAC): ${ev_total_physical:,.2f}")
print(f"Total AC (from act_reg_cost): ${ev_total_p6_act_cost:,.2f}")
