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
store.add_version(ext_bl.get_complete_data(), 'AMR-BL-R00-2', '2025-11-29', type='baseline', context='controller')

ext_upd = CompleteXERExtractor(update_path, 'update')
ext_upd.extract_all()
store.add_version(ext_upd.get_complete_data(), 'AMR-UPD-29-Nov 25', '2025-11-29', type='update', context='controller')

dashboard = store.get_dashboard_data(context="controller")

print("--- MODE ---")
print(dashboard.get("mode"))

if dashboard.get("mode") != "ERROR":
    print("\n--- CURRENT CRITICAL PATH ---")
    print(json.dumps(dashboard.get("current_critical_path"), indent=2))

    print("\n--- NEXT CRITICAL PATH ---")
    print(json.dumps(dashboard.get("next_critical_path"), indent=2))

    print("\n--- WBS DELAY (First 5) ---")
    if dashboard.get("wbs_delay"):
        for i, w in enumerate(dashboard["wbs_delay"][:5]):
            print(f"{i+1}. {w}")
    else:
        print("No wbs_delay")
else:
    print("Error:", dashboard.get("error"))
