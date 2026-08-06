import urllib.request
import json
import sys

req = urllib.request.Request("http://127.0.0.1:8000/versions?context=controller")
with urllib.request.urlopen(req) as response:
    versions = json.loads(response.read().decode())
    v_id = versions[0]["id"]
    
    req2 = urllib.request.Request(f"http://127.0.0.1:8000/xer-data?table=TASKS&page=1&search=&version_id={v_id}&filter=ALL&context=controller")
    with urllib.request.urlopen(req2) as resp2:
        data = json.loads(resp2.read().decode())
        tasks = data.get("records", [])
        
        for t in tasks[:5]:
            print(f"Task: {t.get('task_code')}")
            print(f"  wbs_name: {t.get('wbs_name')}")
            print(f"  raw total_float_hr_cnt: {t.get('total_float_hr_cnt')}")
            print(f"  raw tf_hr_cnt: {t.get('tf_hr_cnt')}")
            print(f"  _analysis.total_float: {t.get('_analysis', {}).get('total_float')}")
            print("---")
            
