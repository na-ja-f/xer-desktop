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

def print_wbs(nodes, path=""):
    for n in nodes:
        w_name = n.get("wbs_name", "")
        current = path + "/" + w_name if path else w_name
        s = n.get("summary", {})
        print(f"\n{current}")
        print(f"  SPI: {s.get('spi_coverage_label')}")
        print(f"  CPI: {s.get('cpi_coverage_label')}")
        print(f"  CV: {s.get('cv_cost')}")
        print(f"  SV: {s.get('sv_cost')}")
        print(f"  AC Coverage: {s.get('ac_coverage_label')}")
        print(f"  EV Coverage: {s.get('ev_coverage_label')}")
        print(f"  PV Coverage: {s.get('pv_coverage_label')}")
        print_wbs(n.get("children", []), current)

print_wbs(nodes[:2])
