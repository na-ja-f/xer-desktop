import sys, os
sys.path.append(os.path.abspath("."))
from modules.extractor import CompleteXERExtractor
import pandas as pd
import json

xer_path = "/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer"
if not os.path.exists(xer_path):
    print(f"File not found: {xer_path}")
    sys.exit(1)

extractor = CompleteXERExtractor(xer_path)
data = extractor.extract_all()
dfs = {t: pd.DataFrame(data.tables[t]) for t in data.tables if data.tables[t]}

def summarize_df(name, df, columns):
    print(f"\n--- {name} Table ---")
    available_cols = [c for c in columns if c in df.columns]
    print(f"Available EV/Cost Columns: {available_cols}")
    if not available_cols: return
    
    for c in available_cols:
        # count non-null and non-zero
        try:
            numeric_vals = pd.to_numeric(df[c], errors='coerce').fillna(0)
            non_zero = (numeric_vals > 0).sum()
            print(f"  {c}: {non_zero} rows with value > 0 (out of {len(df)})")
        except:
            non_null = df[c].notna().sum()
            print(f"  {c}: {non_null} non-null rows")

        # sample
        sample = df[df[c].notna() & (df[c] != '') & (df[c] != '0') & (df[c] != 0)][c].head(3).tolist()
        if sample:
            print(f"    Sample values: {sample}")

project_cols = ['def_earned_value_pct_type', 'step_pct_cnt', 'def_rollup_dates_flag']
if 'PROJECT' in dfs:
    summarize_df('PROJECT', dfs['PROJECT'], project_cols)

task_cols = ['phys_pct_cnt', 'ev_compute_type', 'ev_user_pct', 'est_wt', 'act_start_date', 'act_end_date', 'target_drtn', 'rem_drtn', 'total_float_hr_cnt']
if 'TASK' in dfs:
    summarize_df('TASK', dfs['TASK'], task_cols)

taskrsrc_cols = ['target_cost', 'target_qty', 'act_reg_cost', 'act_reg_qty', 'remain_cost', 'remain_qty', 'act_this_per_cost', 'act_this_per_qty']
if 'TASKRSRC' in dfs:
    summarize_df('TASKRSRC', dfs['TASKRSRC'], taskrsrc_cols)

projcost_cols = ['target_cost', 'act_cost', 'remain_cost']
if 'PROJCOST' in dfs:
    summarize_df('PROJCOST', dfs['PROJCOST'], projcost_cols)

