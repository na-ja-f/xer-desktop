import sys
import os

# Adjust path to find modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from modules.analyzer import XERAnalyzer

analyzer = XERAnalyzer()
context = "controller"

versions = analyzer.data_store.contexts.get(context, {}).get("versions", {})
print("Loaded versions for context 'controller':")
for vid in versions:
    print(f"  - {vid}")

# Get the latest version ID
latest_version_id = None
if versions:
    latest_version_id = list(versions.keys())[-1]

if not latest_version_id:
    print("No version loaded in 'controller' context.")
    sys.exit(1)

print(f"Querying HIERARCHY table for version_id: {latest_version_id}")

try:
    data = analyzer.data_store.get_table_data(
        table_type="HIERARCHY",
        search="",
        limit=100,
        offset=0,
        source_id=latest_version_id,
        filter_type="ALL",
        context=context
    )
    print("Success! Retrieved hierarchy data.")
except Exception as e:
    import traceback
    print("FAILED with exception:")
    traceback.print_exc()
