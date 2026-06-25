import sys, os
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore
from modules.scheduler import P6Calendar

store = XERDataStore()
ext_bl = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer', 'baseline')
ext_bl.extract_all()
store.add_version(ext_bl.get_complete_data(), 'AMR-BL-R00-2', '2025-11-29', type='baseline', context='test')
baseline_src = store.get_baseline(context='test')

bl_calendars_df = baseline_src['df'].get('calendar', baseline_src['df'].get('CALENDAR'))
for _, row in bl_calendars_df.iterrows():
    if str(row.get('clndr_id')) == '1231':
        cal = P6Calendar(row.to_dict())
        print(f"Calendar 1231 Work Days: {cal.work_days}")
        print(f"Calendar 1231 clndr_data: {row.get('clndr_data')}")
