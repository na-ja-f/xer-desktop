import sys
import os
import pandas as pd

sys.path.append(os.path.abspath("."))
from modules.extractor import CompleteXERExtractor
from modules.scheduler import CPMScheduler

xer_path = "/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer"

extractor = CompleteXERExtractor(xer_path)
data = extractor.extract_all()
dfs = {t: pd.DataFrame(data.tables[t]) for t in data.tables if data.tables[t]}
tasks = dfs.get('TASK')

sched = CPMScheduler()
tasks_with_float = sched._apply_p6_stored_dates(tasks)

wbs = dfs.get('PROJWBS')
design_wbs = wbs[wbs['wbs_name'].str.upper() == 'DESIGN'].iloc[0]
design_wid = design_wbs['wbs_id']

# Get all children of DESIGN recursively
design_wbs_ids = [design_wid]
def get_children(parent_id):
    children = wbs[wbs['parent_wbs_id'] == parent_id]
    for _, c in children.iterrows():
        design_wbs_ids.append(c['wbs_id'])
        get_children(c['wbs_id'])

get_children(design_wid)

design_tasks = tasks_with_float[tasks_with_float['wbs_id'].isin(design_wbs_ids)]

print(f"\nDESIGN tasks count: {len(design_tasks)}")

for _, t in design_tasks.head(10).iterrows():
    print(f"[{t.get('status_code')}] {t.get('task_code')} | {t.get('task_type')} | float_hr: {t.get('total_float_hr_cnt')} | float_days: {t.get('total_float')}")
    
# Check how many have float 0
zeros = design_tasks[design_tasks['total_float'] == 0.0]
print(f"\nZero float tasks in DESIGN: {len(zeros)}")
for _, t in zeros.head(5).iterrows():
    print(f"[{t.get('status_code')}] {t.get('task_code')} | {t.get('task_type')} | float_hr: {t.get('total_float_hr_cnt')} | float_days: {t.get('total_float')}")

