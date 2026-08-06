import sys, os, re
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore

store = XERDataStore()
ext_bl = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer', 'baseline')
ext_bl.extract_all()
store.add_version(ext_bl.get_complete_data(), 'AMR-BL-R00-2', '2025-11-29', type='baseline', context='test')
baseline_src = store.get_baseline(context='test')

bl_calendars_df = baseline_src['df'].get('calendar', baseline_src['df'].get('CALENDAR'))
for _, row in bl_calendars_df.iterrows():
    if str(row.get('clndr_id')) == '1231':
        data = row.get('clndr_data', '')
        
        # P6 epoch is usually Jan 1, 1900 or Jan 1, 1984?
        # In SQLite, it's sometimes different. Let's assume Excel epoch (Dec 30, 1899)
        def p6_to_date(days):
            return datetime(1899, 12, 30) + timedelta(days=int(days))
            
        print("Exceptions between Nov 1 2025 and Jan 31 2026:")
        
        # Matches (d|XXXXX)
        matches = re.finditer(r'\(d\|(\d+)\)', data)
        for m in matches:
            days = int(m.group(1))
            dt = p6_to_date(days)
            if datetime(2025, 11, 1) <= dt <= datetime(2026, 1, 31):
                block = data[m.end(): m.end() + 100]
                has_shift = 's|' in block
                print(f"Date: {dt.strftime('%Y-%m-%d')} ({dt.strftime('%A')}) | P6 Code: {days} | Is Working Exception? {has_shift}")
