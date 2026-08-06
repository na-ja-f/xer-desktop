import sys, os
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.abspath('backend'))
from modules.analyzer import XERAnalyzer
analyzer = XERAnalyzer()
context = "audit"
source = analyzer.data_store.get_latest(context=context)

print(f"Step 1: Fetching full table data...")
table_resp = analyzer.data_store.get_table_data(table_type="TASK", limit=999999, context=context, source_id=source['id'])
acts = table_resp.get("data", [])
print(f"Total acts returned: {len(acts)}")

ami = next((a for a in acts if a.get("task_code") == "AMI-FXCH-1080"), None)
if ami:
    print(f"\n[AMI-FXCH-1080 FOUND]")
    print(f"ID: {ami.get('task_id')} | Type: {type(ami.get('task_id'))}")
    print(f"status: {ami.get('_analysis', {}).get('status')}")
    print(f"cost_loaded: {ami.get('cost_loaded')}")
else:
    print("\n[AMI-FXCH-1080 NOT FOUND in acts]")

analysis = analyzer.data_store.get_deterministic_analysis(version_id=source['id'], context=context).get("activityAnalysis", {})
allowed_tids = set(analysis.keys())
print(f"analysis keys count: {len(allowed_tids)}")
if ami:
    print(f"ami task_id in allowed_tids: {ami.get('task_id') in allowed_tids}")
    print(f"ami task_id (str) in allowed_tids: {str(ami.get('task_id')) in allowed_tids}")

acts1 = [a for a in acts if a.get("task_id") in allowed_tids]
print(f"\nStep 2: After allowed_tids filter -> {len(acts1)}")

acts2 = [a for a in acts1 if a.get("_analysis", {}).get("status") == "IN_PROGRESS"]
print(f"Step 3: After status filter -> {len(acts2)}")

acts3 = [a for a in acts2 if a.get("cost_loaded", False)]
print(f"Step 4: After cost_loaded filter -> {len(acts3)}")

