import sys, os
sys.path.append(os.path.abspath("."))
from modules.extractor import CompleteXERExtractor
import pandas as pd

xer_path = "/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer"
extractor = CompleteXERExtractor(xer_path)
data = extractor.extract_all()
dfs = {t: pd.DataFrame(data.tables[t]) for t in data.tables if data.tables[t]}

print("TASK Columns:", dfs['TASK'].columns.tolist())
