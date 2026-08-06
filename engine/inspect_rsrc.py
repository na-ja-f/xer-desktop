import sys
import os

sys.path.append(os.path.abspath("."))
from main import app, analyzer
import json

# analyzer has data_store
store = analyzer.data_store
ctx = store.contexts["controller"]
active_v = ctx["versions"].get(ctx["active_version_id"])
if active_v:
    df = active_v["df"]["rsrc"]
    types = df["rsrc_type"].unique()
    print("rsrc_types in dataframe:", types)
else:
    print("No active version found")
