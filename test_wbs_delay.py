import sys
sys.path.append('.')
from backend.modules.data_store import AuditDataStore

store = AuditDataStore()
dashboard = store.get_dashboard_data(context="controller")
print("Mode:", dashboard.get("mode"))
if dashboard.get("wbs_delay"):
    for i, w in enumerate(dashboard["wbs_delay"][:5]):
        print(f"{i+1}. {w}")
else:
    print("No wbs_delay")
