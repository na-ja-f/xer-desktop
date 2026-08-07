import sys
import os
import pandas as pd
import numpy as np

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
proc_wbs = wbs[wbs['wbs_name'].str.upper() == 'PROCUREMENT'].iloc[0]
proc_wid = proc_wbs['wbs_id']

proc_wbs_ids = [proc_wid]
def get_children(parent_id):
    children = wbs[wbs['parent_wbs_id'] == parent_id]
    for _, c in children.iterrows():
        proc_wbs_ids.append(c['wbs_id'])
        get_children(c['wbs_id'])

get_children(proc_wid)

proc_tasks = tasks_with_float[tasks_with_float['wbs_id'].isin(proc_wbs_ids)]

s = proc_tasks['early_start_date'].min()
f = proc_tasks['early_end_date'].max()
ls = proc_tasks['late_start_date'].min()
lf = proc_tasks['late_end_date'].max()

print("s:", s)
print("f:", f)
print("ls:", ls)
print("lf:", lf)

start_float = np.busday_count(s.date(), ls.date())
finish_float = np.busday_count(f.date(), lf.date())

print("Start Float (approx workdays):", start_float)
print("Finish Float (approx workdays):", finish_float)

