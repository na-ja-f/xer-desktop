import sys, os
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore
from modules.analyzer import XERAnalyzer

store = XERDataStore()
# Load baseline so costs exist
ext_bl = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer', 'baseline')
ext_bl.extract_all()
store.add_version(ext_bl.get_complete_data(), 'AMR-BL-R00-2', '2025-11-29', type='baseline', context='test')

ext_upd = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer', 'update')
ext_upd.extract_all()
store.add_version(ext_upd.get_complete_data(), 'AMR-UPD-29-Nov 25', '2025-11-29', type='update', context='test')

analyzer = XERAnalyzer()
analyzer.data_store = store

# Execute the query
result = analyzer.get_filtered_activities(limit=20, status="IN_PROGRESS", cost_loaded=True, context='test')

debug_info = result.get('stats', {}).get('debug', {})
print("Step 1: Total activities loaded")
print(f"Count: {debug_info.get('1_total_table_acts')}")

print("\nStep 2: Count after allowed_tids")
print(f"Count: {debug_info.get('3_after_allowed_tids')}")

print("\nStep 3: Count after status == IN_PROGRESS")
print(f"Count: {debug_info.get('4_after_status')}")

print("\nStep 4: Count after cost_loaded == True")
print(f"Count: {debug_info.get('5_after_cost_loaded')}")

print("\n--- Inspecting AMI-FXCH-1080 ---")
ami = debug_info.get('ami_initial', {})
print(f"budget_cost: {ami.get('budget_cost')}")
print(f"bl_project_cost: {ami.get('bl_project_cost')}")
print(f"cost_loaded: {ami.get('cost_loaded')}")

