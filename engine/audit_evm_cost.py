#!/usr/bin/env python3
"""Targeted check for cost rate tables and EV calculation sources."""
import sys, os
sys.path.append(os.path.abspath("."))
import pandas as pd
from modules.extractor import CompleteXERExtractor

XER_BL = "/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer"
XER_UPD = "/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer"

for label, path in [("BASELINE", XER_BL), ("UPDATE", XER_UPD)]:
    ext = CompleteXERExtractor(path)
    ext.extract_all()
    
    print(f"\n{'='*80}")
    print(f"  {label}")
    print(f"{'='*80}")
    
    # 1. Check RSRCRATE table
    rsrcrate = ext.tables.get('RSRCRATE', [])
    if rsrcrate:
        df = pd.DataFrame(rsrcrate)
        print(f"\n  RSRCRATE TABLE: {len(df)} rows")
        print(f"  Columns: {sorted(df.columns.tolist())}")
        print(f"\n  Sample rows:")
        print(df.head(5).to_string(index=False))
        # Check for non-zero cost rates
        for col in df.columns:
            if 'cost' in col.lower() or 'rate' in col.lower() or 'price' in col.lower():
                numeric = pd.to_numeric(df[col], errors='coerce').dropna()
                nz = numeric[numeric != 0]
                print(f"  {col}: {len(nz)} non-zero out of {len(numeric)}")
    else:
        print(f"\n  RSRCRATE TABLE: NOT PRESENT")
    
    # 2. Check PROJECT table for EV settings
    proj = ext.tables.get('PROJECT', [])
    if proj:
        p = proj[0]
        print(f"\n  PROJECT TABLE — EV-related settings:")
        ev_fields = ['sum_base_proj_id', 'task_complete_pct_type', 'sum_assign_level', 
                     'def_cost_per_qty', 'last_recalc_date', 'plan_start_date', 
                     'plan_end_date', 'scd_end_date', 'sum_base_proj_id',
                     'def_complete_pct_type', 'step_complete_wt_pct']
        for f in ev_fields:
            if f in p:
                print(f"    {f:<30} = {p[f]}")
        # Also dump ALL project fields that might relate to EV/cost
        for k, v in sorted(p.items()):
            if v and str(v).strip() and str(v) != '0' and str(v) != 'nan':
                if any(x in k.lower() for x in ['cost', 'earn', 'plan', 'budg', 'ev', 'pv', 'ac', 'wt', 'pct', 'base', 'sum']):
                    print(f"    {k:<30} = {v}")
    
    # 3. RSRC table — check for rates
    rsrc = ext.tables.get('RSRC', [])
    if rsrc:
        df_r = pd.DataFrame(rsrc)
        print(f"\n  RSRC TABLE: {len(df_r)} rows")
        rate_cols = [c for c in df_r.columns if any(x in c.lower() for x in ['cost', 'rate', 'price', 'unit'])]
        print(f"  Rate-related columns: {rate_cols}")
        for col in rate_cols:
            non_empty = df_r[col].dropna().replace('', pd.NA).dropna()
            numeric = pd.to_numeric(non_empty, errors='coerce').dropna()
            nz = numeric[numeric != 0]
            samples = non_empty.head(3).tolist()
            print(f"    {col:<25} non-zero: {len(nz):>5}  samples: {samples}")
    
    # 4. TASKRSRC — deeper cost check  
    trsrc = ext.tables.get('TASKRSRC', [])
    if trsrc:
        df_tr = pd.DataFrame(trsrc)
        print(f"\n  TASKRSRC TABLE: {len(df_tr)} rows")
        cost_cols = [c for c in df_tr.columns if any(x in c.lower() for x in ['cost', 'qty', 'rate'])]
        print(f"  Cost/qty columns: {sorted(cost_cols)}")
        for col in sorted(cost_cols):
            numeric = pd.to_numeric(df_tr[col], errors='coerce').dropna()
            nz = numeric[numeric != 0]
            if len(nz) > 0:
                print(f"    {col:<30} non-zero: {len(nz):>6}  min={nz.min():.2f}  max={nz.max():.2f}  sum={nz.sum():.2f}")
            else:
                print(f"    {col:<30} ALL ZERO")
    
    # 5. Check complete_pct_type distribution
    tasks = ext.tables.get('TASK', [])
    if tasks:
        df_t = pd.DataFrame(tasks)
        if 'complete_pct_type' in df_t.columns:
            print(f"\n  TASK complete_pct_type distribution:")
            print(f"    {df_t['complete_pct_type'].value_counts().to_dict()}")
        
        # Check for activities with actual progress
        if 'status_code' in df_t.columns:
            print(f"\n  TASK status distribution:")
            print(f"    {df_t['status_code'].value_counts().to_dict()}")
        
        # Duration % Complete calculation check
        if all(c in df_t.columns for c in ['target_drtn_hr_cnt', 'remain_drtn_hr_cnt']):
            df_t['_target'] = pd.to_numeric(df_t['target_drtn_hr_cnt'], errors='coerce').fillna(0)
            df_t['_remain'] = pd.to_numeric(df_t['remain_drtn_hr_cnt'], errors='coerce').fillna(0)
            df_t['_dur_pct'] = ((df_t['_target'] - df_t['_remain']) / df_t['_target'] * 100).fillna(0)
            df_t['_dur_pct'] = df_t['_dur_pct'].clip(0, 100)
            
            with_progress = df_t[df_t['_dur_pct'] > 0]
            completed = df_t[df_t['_dur_pct'] >= 100]
            print(f"\n  Duration % Complete calculation:")
            print(f"    Activities with progress > 0%: {len(with_progress)}")
            print(f"    Activities at 100%: {len(completed)}")
            print(f"    Sample (first 5 with progress):")
            for _, row in with_progress.head(5).iterrows():
                print(f"      {row['task_code']:<30} target={row['_target']:.0f}h  remain={row['_remain']:.0f}h  dur%={row['_dur_pct']:.1f}%")
        
        # PV/EV Labor Units feasibility
        if 'target_work_qty' in df_t.columns:
            twq = pd.to_numeric(df_t['target_work_qty'], errors='coerce').fillna(0)
            awq = pd.to_numeric(df_t['act_work_qty'], errors='coerce').fillna(0)
            rwq = pd.to_numeric(df_t['remain_work_qty'], errors='coerce').fillna(0)
            print(f"\n  Labor Units Summary:")
            print(f"    Total Budgeted (target_work_qty): {twq.sum():,.2f}")
            print(f"    Total Actual (act_work_qty):      {awq.sum():,.2f}")
            print(f"    Total Remaining (remain_work_qty):{rwq.sum():,.2f}")
            print(f"    Activities with budgeted units:    {(twq > 0).sum()}")
            print(f"    Activities with actual units:      {(awq > 0).sum()}")

    # 6. Check for PROJCOST, TRSRCFIN (time-phased data)
    for tbl_name in ['PROJCOST', 'TRSRCFIN', 'TASKFIN', 'ACTVCODE', 'FINTMPL']:
        tbl = ext.tables.get(tbl_name, [])
        if tbl:
            print(f"\n  {tbl_name} TABLE: {len(tbl)} rows — Columns: {sorted(pd.DataFrame(tbl).columns.tolist())}")
        else:
            print(f"\n  {tbl_name} TABLE: NOT PRESENT")
