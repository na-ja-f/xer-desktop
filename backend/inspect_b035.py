import sys, os
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore

store = XERDataStore()
ext_upd = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer', 'update')
ext_upd.extract_all()
store.add_version(ext_upd.get_complete_data(), 'AMR-UPD-29-Nov 25', '2025-11-29', type='update', context='test')

upd_source = store.get_latest(context='test')
df = upd_source['df']

with open('inspect_b035.txt', 'w') as f:
    tasks = df.get('tasks')
    if tasks is not None:
        f.write("\n--- TASK TABLE FIELDS ---\n")
        cols = list(tasks.columns)
        for c in sorted(cols):
            if 'qty' in c.lower() or 'pct' in c.lower() or 'unit' in c.lower() or 'drtn' in c.lower() or 'labor' in c.lower() or 'work' in c.lower() or 'cost' in c.lower():
                vals = tasks[c].dropna().unique()[:5]
                f.write(f"TASK.{c}: {vals}\n")

    rsrc = df.get('taskrsrc')
    if rsrc is not None:
        f.write("\n--- TASKRSRC TABLE FIELDS ---\n")
        cols = list(rsrc.columns)
        for c in sorted(cols):
            if 'qty' in c.lower() or 'pct' in c.lower() or 'unit' in c.lower() or 'labor' in c.lower() or 'work' in c.lower() or 'cost' in c.lower():
                vals = rsrc[c].dropna().unique()[:5]
                f.write(f"TASKRSRC.{c}: {vals}\n")
