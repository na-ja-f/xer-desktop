import sys, os
sys.path.append(os.path.abspath("."))
from modules.extractor import CompleteXERExtractor
import pandas as pd

xer_path = "/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer"
extractor = CompleteXERExtractor(xer_path)
data = extractor.extract_all()
dfs = {t: pd.DataFrame(data.tables[t]) for t in data.tables if data.tables[t]}

task = dfs['TASK']
proj = dfs['PROJECT']

# EV check
print("=== complete_pct_type distribution ===")
print(task['complete_pct_type'].value_counts())

print("\n=== phys_complete_pct > 0 ===")
pct = pd.to_numeric(task['phys_complete_pct'], errors='coerce').fillna(0)
print(f"  rows > 0: {(pct > 0).sum()} / {len(task)}")

print("\n=== TASKRSRC cost fields ===")
if 'TASKRSRC' in dfs:
    tr = dfs['TASKRSRC']
    for col in ['target_cost', 'act_reg_cost', 'remain_cost']:
        if col in tr.columns:
            vals = pd.to_numeric(tr[col], errors='coerce').fillna(0)
            print(f"  {col}: nonzero={( vals > 0).sum()}, max={vals.max():.2f}")

print("\n=== PROJECT EV settings ===")
ev_cols = [c for c in proj.columns if 'ev' in c.lower() or 'earn' in c.lower() or 'pct' in c.lower()]
print(f"  EV-related columns found: {ev_cols}")
for c in ev_cols:
    print(f"  {c}: {proj[c].tolist()}")

print("\n=== VERDICT ===")
pct_types = task['complete_pct_type'].unique().tolist()
if all(p == 'CP_Drtn' for p in pct_types):
    print("  RESULT: Duration % Complete only. EV/PV NOT calculable.")
elif 'CP_Phys' in pct_types:
    print("  RESULT: Physical % Complete detected. EV MAY be partially calculable.")
else:
    print(f"  RESULT: Mixed types: {pct_types}")
