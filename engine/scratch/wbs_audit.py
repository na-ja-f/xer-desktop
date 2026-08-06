import sys, os
import pandas as pd
import json

sys.path.append(os.path.abspath('backend'))
from modules.data_store import XERDataStore
from modules.extractor import CompleteXERExtractor

store = XERDataStore()
baseline_path = '/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer'
update_path = '/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer'

ext_bl = CompleteXERExtractor(baseline_path, 'baseline')
ext_bl.extract_all()
store.add_version(ext_bl.get_complete_data(), 'AMR-BL-R00-2', '2025-11-29', type='baseline', context='audit2')

ext_upd = CompleteXERExtractor(update_path, 'update')
ext_upd.extract_all()
store.add_version(ext_upd.get_complete_data(), 'AMR-UPD-29-Nov 25', '2025-11-29', type='update', context='audit2')

# Get hierarchy
wbs_tree = store.get_wbs_hierarchy(store.get_latest('audit2')['id'], context='audit2')

# Search for the target branches
targets = ['SUBMITTALS', 'GENERAL SUBMITTALS', 'APPROVALS']

def search_tree(nodes):
    for node in nodes:
        if node['wbs_name'] in targets:
            print(f"\n--- WBS: {node['wbs_name']} ---")
            print(f"Summary Early Finish: {node['summary'].get('early_finish')}")
            print(f"Summary Baseline Finish: {node['summary'].get('baseline_finish')}")
            print(f"Variance: {node['summary'].get('branch_variance_days')}")
            print("Activities in this node:")
            for a in node.get('_analytics_activities', []):
                print(f"  - {a.get('task_code')}: {a.get('task_name')} | ES: {a['_analysis'].get('early_start')} EF: {a['_analysis'].get('early_finish')} | Status: {a['_analysis'].get('status')}")
            
        if node.get('children'):
            search_tree(node['children'])

search_tree(wbs_tree['records'])
