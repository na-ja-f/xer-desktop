import sys
sys.path.append('.')
from backend.modules.data_store import AuditDataStore

store = AuditDataStore()
source = store.get_version(context="controller")
if source:
    print(f"Data loaded, tasks: {len(source['df'].get('tasks', []))}")
    dashboard = store.get_dashboard_data(context="controller")
    print(f"Longest Path Count: {dashboard.get('current_cp', {}).get('count')}")
    print(f"First Task: {dashboard.get('current_cp', {}).get('first_activity')}")
    print(f"Last Task: {dashboard.get('current_cp', {}).get('last_activity')}")
    
    print(f"Near Critical Count: {dashboard.get('next_cp', {}).get('count')}")
else:
    print("No data in controller context")
