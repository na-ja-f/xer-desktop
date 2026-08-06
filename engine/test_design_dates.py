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

design_wbs_ids = [design_wid]
def get_children(parent_id):
    children = wbs[wbs['parent_wbs_id'] == parent_id]
    for _, c in children.iterrows():
        design_wbs_ids.append(c['wbs_id'])
        get_children(c['wbs_id'])

get_children(design_wid)

design_tasks = tasks_with_float[tasks_with_float['wbs_id'].isin(design_wbs_ids)]

print("Max LF in DESIGN:", design_tasks['late_end_date'].max())
print("Min ES in DESIGN:", design_tasks['early_start_date'].min())
print("Max EF in DESIGN:", design_tasks['early_end_date'].max())

max_lf_task = design_tasks.loc[design_tasks['late_end_date'].idxmax()]
print("\nTask with Max LF in DESIGN:")
print("Code:", max_lf_task['task_code'])
print("Name:", max_lf_task['task_name'])
print("LF:", max_lf_task['late_end_date'])
print("EF:", max_lf_task['early_end_date'])
print("total_float_hr_cnt:", max_lf_task['total_float_hr_cnt'])

