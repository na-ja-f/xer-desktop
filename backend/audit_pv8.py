import sys, os
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor

from modules.data_store import XERDataStore

store = XERDataStore()
ext_bl = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer', 'baseline')
ext_bl.extract_all()
store.add_version(ext_bl.get_complete_data(), 'AMR-BL-R00-2', '2025-11-29', type='baseline', context='test')

baseline_src = store.get_baseline(context='test')
bl_tasks = baseline_src['df']['tasks']
code = "P1 - 2950"
if code not in bl_tasks['task_code'].values:
    code = "P1-2950"

brow = bl_tasks[bl_tasks['task_code'] == code].iloc[0]

print("Duration fields in Baseline:")
for col in bl_tasks.columns:
    if 'drtn' in col or 'duration' in col or 'hr_cnt' in col:
        print(f"{col}: {brow.get(col)}")
