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
root_nodes = tree_resp.get("records", [])

def get_totals(nodes):
    total_acts = 0
    cost_loaded_acts = 0
    ev_acts = 0
    for n in nodes:
        s = n.get("summary", {})
        total_acts += s.get('activity_count', 0)
        cost_loaded_acts += s.get('ev_elig_count', 0)
        ev_acts += s.get('has_ev_count', 0)
        # Note: children are already rolled up into root summary!
    return total_acts, cost_loaded_acts, ev_acts

# Root nodes contain the rolled-up totals for their entire branch.
# We sum across all roots.
total, cost_loaded, ev = get_totals(root_nodes)

print(f"Total Activities: {total}")
print(f"Cost-Loaded Activities: {cost_loaded}")
print(f"Activities with EV > 0: {ev}")

cov_all = ev / total if total > 0 else 0
cov_cost_loaded = ev / cost_loaded if cost_loaded > 0 else 0

print(f"\ncoverage_all = {cov_all:.2%}")
print(f"coverage_cost_loaded = {cov_cost_loaded:.2%}")
