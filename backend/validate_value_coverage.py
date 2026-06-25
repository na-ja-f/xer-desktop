import sys, os
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore

store = XERDataStore()
ext_bl = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer', 'baseline')
ext_bl.extract_all()
store.add_version(ext_bl.get_complete_data(), 'AMR-BL-R00-2', '2025-11-29', type='baseline', context='test')

ext_upd = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer', 'update')
ext_upd.extract_all()
store.add_version(ext_upd.get_complete_data(), 'AMR-UPD-29-Nov 25', '2025-11-29', type='update', context='test')

upd_source = store.get_latest(context='test')

tree_resp = store.get_table_data(table_type="HIERARCHY", limit=999999, context='test', source_id=upd_source['id'])
nodes = tree_resp.get("records", [])

def print_wbs(nodes, path="", level=0):
    for n in nodes:
        w_name = n.get("wbs_name", "")
        current = path + "/" + w_name if path else w_name
        s = n.get("summary", {})
        
        # Print project level or any branch with SPI coverage
        if level == 0 or s.get('spi_coverage_activity_count', 0) > 0:
            print(f"\n[{level}] {current}")
            print(f"  Branch Total BL Cost: ${s.get('bl_project_cost', 0):,.2f}")
            print(f"  BL Cost represented by EV-enabled activities: ${s.get('spi_coverage_bl_cost', 0):,.2f}")
            print(f"  Coverage %: {s.get('spi_coverage_pct')}%")
            print(f"  Activity counts: {s.get('spi_coverage_activity_count')} of {s.get('spi_coverage_total_activity_count')} activities")
            print(f"  Coverage Label: {s.get('spi_coverage_label')}")
            
        print_wbs(n.get("children", []), current, level + 1)

print("--- COVERAGE VALIDATION REPORT ---")
print_wbs(nodes)
