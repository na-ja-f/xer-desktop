import sys, os
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore

ext_upd = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer', 'update')
ext_upd.extract_all()
df = ext_upd.get_complete_data()

tasks = pd.DataFrame(df.get('tasks', []))

if tasks is not None:
    # 1. Budgeted Labor Units > 0
    labor_loaded = tasks[pd.to_numeric(tasks['target_work_qty'], errors='coerce') > 0]
    
    # Cost > 0 vs Cost = 0
    # need to check target_cost or bl_project_cost etc. 
    # tasks['target_tot_cost'] might be the one. let's check planned_tot_cost or target_cost
    # I'll just parse target_tot_cost, planned_tot_cost, target_cost as done in data_store.py
    
    def get_cost(row):
        return pd.to_numeric(row.get('target_cost') or row.get('target_tot_cost') or row.get('planned_tot_cost', 0), errors='coerce') or 0
        
    labor_loaded = labor_loaded.copy()
    labor_loaded['budget_cost'] = labor_loaded.apply(get_cost, axis=1)
    
    cnt_all = len(labor_loaded)
    cnt_with_cost = len(labor_loaded[labor_loaded['budget_cost'] > 0])
    cnt_no_cost = len(labor_loaded[labor_loaded['budget_cost'] == 0])
    
    print(f"Count of activities with Budgeted Labor Units > 0: {cnt_all}")
    print(f"Count of activities with Budgeted Labor Units > 0 and Budgeted Cost > 0: {cnt_with_cost}")
    print(f"Count of activities with Budgeted Labor Units > 0 but Budgeted Cost = 0: {cnt_no_cost}")
    
    print("\nDistribution of complete_pct_type among labor-loaded activities:")
    print(labor_loaded['complete_pct_type'].value_counts())
    
    print("\nSample EV Units Calculation for 10 activities:")
    sample = labor_loaded[pd.to_numeric(labor_loaded['act_work_qty'], errors='coerce') > 0].head(10)
    if len(sample) < 10:
        # supplement with non-started if needed
        sample = pd.concat([sample, labor_loaded.head(10 - len(sample))])
        
    for _, row in sample.iterrows():
        tid = row['task_code']
        pct_type = row['complete_pct_type']
        target_labor = float(row['target_work_qty'])
        actual_labor = float(row['act_work_qty']) if pd.notnull(row['act_work_qty']) else 0.0
        
        # Method B: Units %
        pct_units = actual_labor / target_labor if target_labor > 0 else 0.0
        ev_method_b = target_labor * pct_units
        
        # Method A: Progress determined by pct_type
        pct_a = 0.0
        if pct_type == 'CP_Phys':
            phys = pd.to_numeric(row.get('phys_complete_pct'), errors='coerce')
            pct_a = phys / 100.0 if pd.notnull(phys) else 0.0
        elif pct_type == 'CP_Drtn':
            orig = pd.to_numeric(row.get('target_drtn_hr_cnt'), errors='coerce')
            rem = pd.to_numeric(row.get('remain_drtn_hr_cnt'), errors='coerce')
            if pd.notnull(orig) and orig > 0:
                pct_a = (orig - (rem if pd.notnull(rem) else 0)) / orig
        elif pct_type == 'CP_Units':
            pct_a = pct_units
            
        ev_method_a = target_labor * pct_a
        
        print(f"Task: {tid} | Type: {pct_type} | Budget Lbr: {target_labor:.1f} | Act Lbr: {actual_labor:.1f}")
        print(f"  Method A (pct_type driven): {ev_method_a:.1f} ({pct_a:.1%})")
        print(f"  Method B (Units %):         {ev_method_b:.1f} ({pct_units:.1%})")
        print("-" * 40)
