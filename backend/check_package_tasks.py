import sys, os
sys.path.append(os.path.abspath("."))
from modules.extractor import CompleteXERExtractor
import pandas as pd

xer_path = "/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer"
extractor = CompleteXERExtractor(xer_path)
data = extractor.extract_all()
dfs = {t: pd.DataFrame(data.tables[t]) for t in data.tables if data.tables[t]}

actvcode_df = dfs.get('ACTVCODE')
taskactv_df = dfs.get('TASKACTV')
task_df = dfs.get('TASK')

# Find PACKAGE 1A code ID
pkg1a_id = actvcode_df[actvcode_df['actv_code_name'] == 'PACKAGE 1A']['actv_code_id'].iloc[0]

# Find tasks with this code
assigned_task_ids = taskactv_df[taskactv_df['actv_code_id'] == pkg1a_id]['task_id'].tolist()

# Get task details
assigned_tasks = task_df[task_df['task_id'].isin(assigned_task_ids)][['task_code', 'task_name']]

print(f"Total tasks assigned to PACKAGE 1A: {len(assigned_tasks)}")
print(assigned_tasks.head(10))
