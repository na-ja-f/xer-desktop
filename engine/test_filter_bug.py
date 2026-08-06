import sys, os
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.abspath('backend'))
from modules.data_store import XERDataStore
store = XERDataStore()
store.load_from_db('AMR-UPD-29-Nov 25.db', context='audit')
source = store.get_latest(context='audit')
table_resp = store.get_table_data(table_type="TASK", limit=999999, context="audit", source_id=source['id'])
acts = table_resp.get("data", [])
ami = next((a for a in acts if a.get("task_code") == "AMI-FXCH-1080"), None)
print("AMI-FXCH-1080 data:")
if ami:
    print(f"Status: {ami.get('status_enum')}")
    print(f"BL Cost: {ami.get('bl_project_cost')}")
    print(f"Budget Cost: {ami.get('budget_cost')}")
    print(f"cost_loaded flag: {ami.get('cost_loaded')}")
