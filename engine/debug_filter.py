import sys, os
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore
from modules.analyzer import XERAnalyzer

store = XERDataStore()
ext_upd = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer', 'update')
ext_upd.extract_all()
data_upd = ext_upd.get_complete_data()
store.add_version(data_upd, data_upd['project']['project_name'], data_upd['project']['data_date'], type='update', context='test')

analyzer = XERAnalyzer()
analyzer.data_store = store

# Execute the query
result = analyzer.get_filtered_activities(limit=20, status="IN_PROGRESS", cost_loaded=True, context='test')

debug_info = result.get('stats', {}).get('debug', {})
print("Step 1: Total activities loaded (acts from table_resp)")
print(f"Count: {debug_info.get('1_total_table_acts')}")

print("\nStep 2: Count after allowed_tids")
print(f"Count: {debug_info.get('3_after_allowed_tids')}")

print("\nStep 3: Count after status == IN_PROGRESS")
print(f"Count: {debug_info.get('4_after_status')}")

print("\nStep 4: Count after cost_loaded == True")
print(f"Count: {debug_info.get('5_after_cost_loaded')}")

print("\nFinal Count Returned:", result.get('total_count'))

print("\n--- Inspecting AMI-FXCH-1080 ---")
print(f"Initial: {debug_info.get('ami_initial')}")
print(f"After allowed_tids: {debug_info.get('ami_after_allowed')}")
print(f"After status: {debug_info.get('ami_after_status')}")
print(f"After cost_loaded: {debug_info.get('ami_after_cost')}")

# print first 5 returned:
print("\nFirst 5 matching activities:")
for a in result.get('data', [])[:5]:
    print(a.get("code"), a.get("status"), "BAC:", a.get("bl_project_cost"), "Cost Loaded:", a.get("cost_loaded"))

