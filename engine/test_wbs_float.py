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

wbs = dfs.get('PROJWBS')
t0 = tasks[tasks['task_code'] == 'AMI-1A-IFC-1000'].iloc[0]
print("Task WBS ID:", t0['wbs_id'])

task_wbs = wbs[wbs['wbs_id'] == t0['wbs_id']].iloc[0]
print("Task WBS Name:", task_wbs['wbs_name'])

parent_id = task_wbs['parent_wbs_id']
while pd.notna(parent_id):
    parent = wbs[wbs['wbs_id'] == parent_id].iloc[0]
    print(" -> Parent WBS Name:", parent['wbs_name'])
    parent_id = parent['parent_wbs_id']

