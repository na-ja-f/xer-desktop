import urllib.request
import json
import sys

v_id = "baseline_20260508155522"
req2 = urllib.request.Request(f"http://127.0.0.1:8000/xer-data?table=HIERARCHY&page=1&search=&version_id={v_id}&filter=ALL&context=controller")

try:
    with urllib.request.urlopen(req2) as resp2:
        data = json.loads(resp2.read().decode())
        records = data.get("records", [])
        
        # Look for DESIGN
        design_node = None
        def find_design(nodes):
            for n in nodes:
                if n.get("wbs_name") == "DESIGN":
                    return n
                res = find_design(n.get("children", []))
                if res: return res
            return None
            
        design = find_design(records)
        
        if design:
            print("DESIGN found!")
            print("min_float:", design.get("summary", {}).get("min_float"))
            acts = design.get("activities", [])
            print(f"Activities in DESIGN: {len(acts)}")
            for act in acts:
                an = act.get("_analysis", {})
                print(f"  Act {act.get('task_code')}:")
                print(f"    status: {an.get('status')}")
                print(f"    task_type: {act.get('task_type')}")
                print(f"    _analysis.total_float: {an.get('total_float')}")
                print(f"    raw float hr: {act.get('total_float_hr_cnt')}")
        else:
            print("DESIGN not found in HIERARCHY")
            
except Exception as e:
    print("Error:", e)

