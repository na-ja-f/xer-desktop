import sys
import os
import glob
sys.path.append(os.path.abspath("."))
from modules.extractor import CompleteXERExtractor

xer_path = max(glob.glob("../*.xer"), key=os.path.getmtime)
print(f"Reading {xer_path}")

extractor = CompleteXERExtractor(xer_path)
data = extractor.extract_all()
tasks = data['tables'].get('TASK', [])
if tasks:
    print(list(tasks[0].keys()))
