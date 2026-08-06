import sys
import os
import pandas as pd

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.data_store import DataStore
from modules.xer_parser import parse_xer

# Create data store
ds = DataStore()

# 1. Print loaded versions
print("### 1. INITIALIZING DATA STORE ###")
print(f"Loaded contexts: {list(ds.contexts.keys())}")

# Let's inspect the controller context
ctx = ds.contexts.get('controller', {})
versions = ctx.get('versions', {})

print(f"\nLoaded versions in 'controller' context: {len(versions)}")
for vid, v in versions.items():
    print(f"- {vid}: Type={v['type']}, Name={v.get('name')}, DataDate={v.get('data_date')}")

# 2. Let's find out how pairing works exactly in code
print("\n### 2. PAIRING CRITERIA ###")
print("Looking at DataStore.get_baseline():")
print("def get_baseline(self, context: str = 'audit') -> Optional[Dict]:")
print("    ctx = self.contexts.get(context, self.contexts['audit'])")
print("    # Find the first version of type 'baseline'")
print("    for v in ctx['versions'].values():")
print("        if v['type'] == 'baseline':")
print("            return v")
print("    return None")
print("\nConclusion: NO PAIRING LOGIC EXISTS.")
print("The backend simply returns the FIRST version marked as 'baseline'.")
print("It does NOT check proj_short_name, activity overlap, or dates.")

