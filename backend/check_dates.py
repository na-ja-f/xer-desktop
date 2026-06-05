import sys, os
sys.path.append(os.path.abspath("."))
from modules.extractor import CompleteXERExtractor
import pandas as pd

xer_path = "/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer"
extractor = CompleteXERExtractor(xer_path)
data = extractor.extract_all()
df = pd.DataFrame(data.tables['TASK'])
date_cols = [c for c in df.columns if 'start' in c.lower() or 'end' in c.lower() or 'finish' in c.lower()]
print("Date columns in TASK:", date_cols)
row = df.iloc[0]
for c in date_cols:
    print(f"  {c}: {row[c]}")
