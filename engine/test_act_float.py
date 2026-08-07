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

t0 = tasks_with_float[tasks_with_float['task_code'] == 'AMI-1A-IFC-1000'].iloc[0]
print("Task:", t0['task_code'])
print("ES:", t0['early_start_date'])
print("EF:", t0['early_end_date'])
print("LS:", t0['late_start_date'])
print("LF:", t0['late_end_date'])
print("total_float_hr_cnt:", t0['total_float_hr_cnt'])

# Check P1 - 1110
t1 = tasks_with_float[tasks_with_float['task_code'] == 'P1 - 1110'].iloc[0]
print("\nTask:", t1['task_code'])
print("ES:", t1['early_start_date'])
print("EF:", t1['early_end_date'])
print("LS:", t1['late_start_date'])
print("LF:", t1['late_end_date'])
print("total_float_hr_cnt:", t1['total_float_hr_cnt'])

