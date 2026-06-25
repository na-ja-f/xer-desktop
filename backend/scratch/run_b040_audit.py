import json
import urllib.request
import urllib.error

base_url = "http://127.0.0.1:8000"

print("Fetching versions...")
try:
    req = urllib.request.Request(f"{base_url}/versions?context=controller")
    with urllib.request.urlopen(req) as response:
        res_data = json.loads(response.read().decode())
    
    if isinstance(res_data, list):
        versions = res_data
    elif isinstance(res_data, dict):
        versions = res_data.get('versions', [])
        # in case it returns dict mapping id -> info
        if isinstance(versions, dict):
            versions = list(versions.values())
        if not versions and not res_data.get('versions'):
            versions = list(res_data.values()) if any(isinstance(v, dict) and 'id' in v for v in res_data.values()) else []
    else:
        versions = []
except Exception as e:
    print(f"Error fetching versions: {e}")
    versions = []

print(f"\n--- Loaded Versions ---")
for v in versions:
    print(f"ID: {v.get('id')}, Type: {v.get('type')}, Date: {v.get('data_date')}, Name: {v.get('name')}")

print("\n--- Testing Edge Cases ---")
update_versions = [v for v in versions if v.get('type') == 'update']
baseline_versions = [v for v in versions if v.get('type') == 'baseline']

if update_versions:
    uv = update_versions[-1]['id']
    print(f"\nTesting Edge Case A: Requesting variance with Update file ({uv})")
    try:
        req = urllib.request.Request(f"{base_url}/project-analysis?version_id={uv}&context=controller")
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            print(f"Status Code: {response.getcode()}")
            print(f"Success: {data.get('success')}")
            if data.get('error'):
                print(f"Error Message: {data.get('error')}")
            else:
                print("Variance computation proceeded.")
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} - {e.reason}")
        if e.code == 500:
            error_data = e.read().decode()
            print(f"Server Error Details: {error_data}")
    except Exception as e:
        print(f"Error: {e}")

if baseline_versions:
    bv = baseline_versions[-1]['id']
    print(f"\nTesting Edge Case C: Requesting variance with Baseline file ({bv})")
    try:
        req = urllib.request.Request(f"{base_url}/project-analysis?version_id={bv}&context=controller")
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            print(f"Status Code: {response.getcode()}")
            print(f"Success: {data.get('success')}")
            if data.get('error'):
                print(f"Error Message: {data.get('error')}")
            else:
                print("Variance computation proceeded on baseline?")
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} - {e.reason}")
    except Exception as e:
        print(f"Error: {e}")

print("\n--- Inspecting Pairing Logic in DataStore ---")
try:
    with open('/Users/shibilmuhammad/Documents/Career/Coding /Projects/Work_Projects/openCoders/xeragent_desktop/backend/modules/data_store.py', 'r') as f:
        content = f.read()
        if 'overlap' in content:
            print("- Found 'overlap' in data_store.py")
        else:
            print("- 'overlap' NOT found in data_store.py")
        if 'proj_short_name' in content:
            print("- Found 'proj_short_name' in data_store.py")
        else:
            print("- 'proj_short_name' NOT found in data_store.py")
except Exception as e:
    print(f"Error reading file: {e}")

