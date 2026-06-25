import sys, os
import pandas as pd
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore

store = XERDataStore()

ext_bl = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer', 'baseline')
ext_bl.extract_all()
data_bl = ext_bl.get_complete_data()
store.add_version(data_bl, data_bl['project']['project_name'], data_bl['project']['data_date'], type='baseline', context='test')

ext_upd = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer', 'update')
ext_upd.extract_all()
data_upd = ext_upd.get_complete_data()
store.add_version(data_upd, data_upd['project']['project_name'], data_upd['project']['data_date'], type='update', context='test')

upd_source = store.get_version(context='test')
bl_source = store.get_baseline(context='test')

tasks = upd_source['df']['tasks']
taskrsrc = upd_source['df']['taskrsrc']

print("Columns in TASK table related to EV/cost:")
cost_cols = [c for c in tasks.columns if 'cost' in c.lower() or 'ev' in c.lower() or 'earned' in c.lower() or 'bcwp' in c.lower() or 'bcws' in c.lower() or 'acwp' in c.lower() or 'act_' in c.lower() or 'perf' in c.lower() or 'pct' in c.lower()]
print(cost_cols)

# We want BAC, PV, EV, AC for each activity.
# Since EV should be BAC * Performance % Complete
# In P6, Activity % Complete is stored in a column, maybe `phys_complete_pct` or we calculate it.
print("\nSample TASK data:")
has_act = tasks[pd.to_numeric(tasks['act_cost'], errors='coerce') > 0] if 'act_cost' in tasks.columns else tasks.head(20)
print(has_act[[c for c in ['task_code', 'act_cost', 'target_cost', 'phys_complete_pct', 'complete_pct_type', 'act_this_per_cost', 'ev_cost', 'bcwp', 'bcws', 'acwp', 'earned_value'] if c in has_act.columns]].head())

# Let's see how many have act_reg_cost > 0 in TASKRSRC
tr_act_reg = pd.to_numeric(taskrsrc['act_reg_cost'], errors='coerce').fillna(0)
print(f"\nNumber of TASKRSRC assignments with act_reg_cost > 0: {(tr_act_reg > 0).sum()}")
print(f"Number of TASKRSRC assignments with act_reg_cost = 0: {(tr_act_reg == 0).sum()}")

# Let's show 20 activities with BAC, PV, EV, AC, SPI, CPI from the CURRENT data_store output
# I will use data_store.get_table_data with HIERARCHY to see the leaf nodes
leaves = store.get_table_data('HIERARCHY', page=1, page_size=20, search='', version_id=upd_source['id'], context='test', filter_type='ALL')

print("\nSample of 20 activities with calculated metrics:")
print(f"{'Activity ID':<20} | {'BAC':<12} | {'PV':<12} | {'EV':<12} | {'AC':<12} | {'SPI':<5} | {'CPI':<5}")
print("-" * 95)
def print_tree(nodes):
    for n in nodes:
        if not n.get('is_branch'):
            m = n.get('metrics', {})
            bac = m.get('budget_cost', 0)
            pv = m.get('pv_cost', 0)
            ev = m.get('ev_cost', 0)
            ac = m.get('actual_cost', 0)
            spi = m.get('spi', 0)
            cpi = m.get('cpi', 0)
            if bac > 0 or ac > 0:
                print(f"{n.get('id'):<20} | ${bac:<11.2f} | ${pv:<11.2f} | ${ev:<11.2f} | ${ac:<11.2f} | {spi:<5.2f} | {cpi:<5.2f}")
        if 'children' in n:
            print_tree(n['children'])

print_tree(leaves.get('data', []))
