#!/usr/bin/env python3
"""
EVM Field Audit — Inspect Al Amrah XER files for Earned Value fields.
Checks both TASK and TASKRSRC tables for cost/unit/% complete fields.
"""
import sys, os, json
sys.path.append(os.path.abspath("."))
import pandas as pd
from modules.extractor import CompleteXERExtractor

XER_BASELINE = "/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer"
XER_UPDATE = "/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer"

def analyze_xer(path, label):
    print(f"\n{'='*100}")
    print(f"  {label}: {os.path.basename(path)}")
    print(f"{'='*100}")
    
    ext = CompleteXERExtractor(path, "baseline" if "Baseline" in path else "update")
    ext.extract_all()
    
    # Show all tables and row counts
    print(f"\n  All tables in XER:")
    for tbl, rows in sorted(ext.tables.items(), key=lambda x: -len(x[1])):
        print(f"    {tbl:<20} {len(rows):>6} rows")
    
    # ── TASK TABLE ──────────────────────────────────────────────
    tasks = ext.tables.get('TASK', [])
    if tasks:
        df = pd.DataFrame(tasks)
        print(f"\n  ── TASK TABLE ({len(df)} rows, {len(df.columns)} columns) ──")
        print(f"  All columns: {sorted(df.columns.tolist())}")
        
        # EVM-related columns to check
        evm_cols = [
            'phys_complete_pct',    # Physical % Complete
            'complete_pct',         # Activity % Complete (overall)
            'target_work_qty',      # Budgeted Labor Units
            'act_work_qty',         # Actual Labor Units
            'remain_work_qty',      # Remaining Labor Units
            'target_equip_qty',     # Budgeted Equipment Units
            'act_equip_qty',        # Actual Equipment Units
            'remain_equip_qty',     # Remaining Equipment Units
            'bcwp',                 # Budgeted Cost of Work Performed (EV)
            'bcws',                 # Budgeted Cost of Work Scheduled (PV)
            'acwp',                 # Actual Cost of Work Performed (AC)
            'target_cost',          # Budgeted Cost / Planned Value
            'act_this_per_cost',    # Actual Cost This Period
            'act_reg_cost',         # Actual Regular Cost
            'target_tot_cost',      # Total Target Cost
            'act_tot_cost',         # Actual Total Cost
            'remain_tot_cost',      # Remaining Total Cost
            'target_drtn_hr_cnt',   # Target Duration Hours
            'remain_drtn_hr_cnt',   # Remaining Duration Hours
            'act_drtn_hr_cnt',      # Actual Duration Hours
            'cpl_type',             # % Complete Type
        ]
        
        print(f"\n  ── EVM-RELATED FIELDS IN TASK TABLE ──")
        print(f"  {'Column':<25} {'Present':>8} {'Non-Empty':>10} {'Non-Zero':>10} {'Sample Values'}")
        print(f"  {'-'*95}")
        
        for col in evm_cols:
            if col in df.columns:
                non_empty = df[col].dropna().replace('', pd.NA).dropna()
                numeric = pd.to_numeric(non_empty, errors='coerce').dropna()
                non_zero = numeric[numeric != 0]
                samples = non_empty.head(5).tolist()
                print(f"  {col:<25} {'YES':>8} {len(non_empty):>10} {len(non_zero):>10} {samples}")
            else:
                print(f"  {col:<25} {'NO':>8} {'—':>10} {'—':>10}")
        
        # Check cpl_type (% Complete Type)
        if 'cpl_type' in df.columns:
            print(f"\n  % Complete Types used: {df['cpl_type'].value_counts().to_dict()}")
    
    # ── TASKRSRC TABLE ──────────────────────────────────────────
    taskrsrc = ext.tables.get('TASKRSRC', [])
    if taskrsrc:
        df_rsrc = pd.DataFrame(taskrsrc)
        print(f"\n  ── TASKRSRC TABLE ({len(df_rsrc)} rows, {len(df_rsrc.columns)} columns) ──")
        print(f"  All columns: {sorted(df_rsrc.columns.tolist())}")
        
        rsrc_evm_cols = [
            'target_qty',           # Budgeted Units
            'remain_qty',           # Remaining Units
            'act_reg_qty',          # Actual Regular Units
            'act_ot_qty',           # Actual Overtime Units
            'target_cost',          # Budgeted Cost
            'act_reg_cost',         # Actual Regular Cost
            'act_ot_cost',          # Actual Overtime Cost
            'remain_cost',          # Remaining Cost
            'target_start_date',    # Resource Target Start
            'target_end_date',      # Resource Target End
            'act_start_date',       # Resource Actual Start
            'act_end_date',         # Resource Actual End
            'pobs_id',              # Estimate/Budget ID
            'rollup_dates_flag',    # Rollup flag
            'target_lag_drtn_hr_cnt',
            'target_crv_id',        # Resource Curve ID
            'remain_crv_id',
            'act_this_per_cost',    # Actual This Period Cost
            'act_this_per_qty',     # Actual This Period Qty
        ]
        
        print(f"\n  ── EVM-RELATED FIELDS IN TASKRSRC TABLE ──")
        print(f"  {'Column':<25} {'Present':>8} {'Non-Empty':>10} {'Non-Zero':>10} {'Sample Values'}")
        print(f"  {'-'*95}")
        
        for col in rsrc_evm_cols:
            if col in df_rsrc.columns:
                non_empty = df_rsrc[col].dropna().replace('', pd.NA).dropna()
                numeric = pd.to_numeric(non_empty, errors='coerce').dropna()
                non_zero = numeric[numeric != 0]
                samples = non_empty.head(5).tolist()
                print(f"  {col:<25} {'YES':>8} {len(non_empty):>10} {len(non_zero):>10} {samples}")
            else:
                print(f"  {col:<25} {'NO':>8} {'—':>10} {'—':>10}")
    
    # ── PROJCOST TABLE (Project-level cost/EV) ──────────────────
    projcost = ext.tables.get('PROJCOST', [])
    if projcost:
        df_cost = pd.DataFrame(projcost)
        print(f"\n  ── PROJCOST TABLE ({len(df_cost)} rows, {len(df_cost.columns)} columns) ──")
        print(f"  All columns: {sorted(df_cost.columns.tolist())}")
        print(f"  Sample rows:")
        print(df_cost.head(5).to_string(index=False))
    else:
        print(f"\n  ── PROJCOST TABLE: NOT PRESENT ──")
    
    # ── TRSRCFIN TABLE (Resource Financial Period) ──────────────
    trsrcfin = ext.tables.get('TRSRCFIN', [])
    if trsrcfin:
        df_fin = pd.DataFrame(trsrcfin)
        print(f"\n  ── TRSRCFIN TABLE ({len(df_fin)} rows, {len(df_fin.columns)} columns) ──")
        print(f"  All columns: {sorted(df_fin.columns.tolist())}")
        print(f"  Sample rows:")
        print(df_fin.head(3).to_string(index=False))
    else:
        print(f"\n  ── TRSRCFIN TABLE: NOT PRESENT ──")
    
    # ── FINDATES TABLE (Financial Periods) ──────────────────────
    findates = ext.tables.get('FINDATES', [])
    if findates:
        df_fin = pd.DataFrame(findates)
        print(f"\n  ── FINDATES TABLE ({len(df_fin)} rows, {len(df_fin.columns)} columns) ──")
        print(f"  All columns: {sorted(df_fin.columns.tolist())}")
        print(f"  First 3 rows:")
        print(df_fin.head(3).to_string(index=False))
    else:
        print(f"\n  ── FINDATES TABLE: NOT PRESENT ──")
    
    # ── RSRC TABLE ──────────────────────────────────────────────
    rsrc = ext.tables.get('RSRC', [])
    if rsrc:
        df_r = pd.DataFrame(rsrc)
        print(f"\n  ── RSRC TABLE ({len(df_r)} rows) ──")
        rsrc_type_cols = ['rsrc_type', 'rsrc_name', 'rsrc_short_name', 'unit_qty']
        for col in rsrc_type_cols:
            if col in df_r.columns:
                print(f"    {col}: {df_r[col].value_counts().head(5).to_dict()}")
    
    # ── UDFVALUE TABLE (User Defined Fields) ────────────────────
    udfvalue = ext.tables.get('UDFVALUE', [])
    if udfvalue:
        df_udf = pd.DataFrame(udfvalue)
        print(f"\n  ── UDFVALUE TABLE ({len(df_udf)} rows, {len(df_udf.columns)} columns) ──")
        print(f"  All columns: {sorted(df_udf.columns.tolist())}")
        if 'udf_type_id' in df_udf.columns:
            print(f"  UDF type IDs: {df_udf['udf_type_id'].value_counts().to_dict()}")
    
    # ── UDFTYPE TABLE ───────────────────────────────────────────
    udftype = ext.tables.get('UDFTYPE', [])
    if udftype:
        df_udft = pd.DataFrame(udftype)
        print(f"\n  ── UDFTYPE TABLE ({len(df_udft)} rows) ──")
        for _, row in df_udft.iterrows():
            print(f"    ID={row.get('udf_type_id','?')}  label={row.get('udf_type_label','?')}  table={row.get('table_name','?')}  type={row.get('logical_data_type','?')}")
    
    # ── Specific Activity Example ───────────────────────────────
    if tasks:
        df = pd.DataFrame(tasks)
        # Pick a non-milestone activity
        sample = df[df['task_type'] == 'TT_Task'].head(1)
        if not sample.empty:
            row = sample.iloc[0]
            print(f"\n  ── SAMPLE ACTIVITY (Full Record) ──")
            print(f"  Activity: {row.get('task_code')} — {row.get('task_name')}")
            for col in sorted(df.columns):
                val = row.get(col, '')
                if val and str(val).strip() and str(val) != 'nan':
                    print(f"    {col:<35} = {val}")
    
    return ext

print("Analyzing Al Amrah XER files for EVM field availability...\n")
ext_bl = analyze_xer(XER_BASELINE, "BASELINE")
ext_upd = analyze_xer(XER_UPDATE, "UPDATE")

# ── Cross-reference: Same activity in BL vs UPD ────────────────
print(f"\n{'='*100}")
print(f"  CROSS-VERSION COMPARISON")
print(f"{'='*100}")

bl_tasks = pd.DataFrame(ext_bl.tables['TASK'])
upd_tasks = pd.DataFrame(ext_upd.tables['TASK'])

# Find a task that exists in both
common_codes = set(bl_tasks['task_code']) & set(upd_tasks['task_code'])
print(f"\n  Tasks in baseline: {len(bl_tasks)}")
print(f"  Tasks in update:   {len(upd_tasks)}")
print(f"  Common task_codes: {len(common_codes)}")

# Pick a sample
sample_code = sorted(common_codes)[0]
bl_row = bl_tasks[bl_tasks['task_code'] == sample_code].iloc[0]
upd_row = upd_tasks[upd_tasks['task_code'] == sample_code].iloc[0]

print(f"\n  Sample: {sample_code}")

cost_fields = ['phys_complete_pct', 'target_work_qty', 'act_work_qty', 'remain_work_qty',
               'target_drtn_hr_cnt', 'remain_drtn_hr_cnt', 'target_cost', 'act_tot_cost',
               'target_end_date', 'act_end_date', 'status_code', 'cpl_type']

print(f"  {'Field':<25} {'Baseline':>20} {'Update':>20}")
print(f"  {'-'*70}")
for f in cost_fields:
    bv = bl_row.get(f, '—')
    uv = upd_row.get(f, '—')
    if not bv or str(bv) == 'nan': bv = '—'
    if not uv or str(uv) == 'nan': uv = '—'
    print(f"  {f:<25} {str(bv):>20} {str(uv):>20}")

# ── TASKRSRC cross-reference ────────────────────────────────────
bl_trsrc = pd.DataFrame(ext_bl.tables.get('TASKRSRC', []))
upd_trsrc = pd.DataFrame(ext_upd.tables.get('TASKRSRC', []))

if not bl_trsrc.empty and not upd_trsrc.empty:
    # Find task_id for our sample
    bl_tid = bl_row['task_id']
    upd_tid = upd_row['task_id']
    
    bl_rsrc = bl_trsrc[bl_trsrc['task_id'] == bl_tid]
    upd_rsrc = upd_trsrc[upd_trsrc['task_id'] == upd_tid]
    
    print(f"\n  Resource assignments for {sample_code}:")
    print(f"    Baseline: {len(bl_rsrc)} assignments")
    print(f"    Update:   {len(upd_rsrc)} assignments")
    
    if not bl_rsrc.empty:
        r = bl_rsrc.iloc[0]
        print(f"\n    Baseline first assignment:")
        rsrc_fields = ['target_qty', 'remain_qty', 'act_reg_qty', 'target_cost', 
                       'act_reg_cost', 'remain_cost', 'target_start_date', 'target_end_date']
        for f in rsrc_fields:
            print(f"      {f:<25} = {r.get(f, '—')}")
    
    if not upd_rsrc.empty:
        r = upd_rsrc.iloc[0]
        print(f"\n    Update first assignment:")
        for f in rsrc_fields:
            print(f"      {f:<25} = {r.get(f, '—')}")
