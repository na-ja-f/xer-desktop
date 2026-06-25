import sys
sys.path.append('.')
from backend.modules.data_store import AuditDataStore
store = AuditDataStore()
source = store.get_version(context="controller")
if source and 'taskpred' in source['df']:
    print(source['df']['taskpred'].columns.tolist())
else:
    print("No taskpred")
