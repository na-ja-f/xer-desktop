import sys, os
import pandas as pd
from datetime import timedelta
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

ext_upd = CompleteXERExtractor('/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer', 'update')
ext_upd.extract_all()
store.add_version(ext_upd.get_complete_data(), 'AMR-UPD-29-Nov 25', '2025-11-29', type='update', context='test')

baseline_src = store.get_baseline(context='test')
upd_source = store.get_latest(context='test')

bl_tasks = baseline_src['df']['tasks']

code = "P1 - 2950"
if code not in bl_tasks['task_code'].values:
    code = "P1-2950"

brow = bl_tasks[bl_tasks['task_code'] == code].iloc[0]

bl_calendars_df = baseline_src['df'].get('calendar', baseline_src['df'].get('CALENDAR'))
bl_calendars_map = {}
if bl_calendars_df is not None and not bl_calendars_df.empty:
    for _, row in bl_calendars_df.iterrows():
        bl_calendars_map[str(row.get('clndr_id'))] = P6Calendar(row.to_dict())

clndr_id = str(brow.get('clndr_id', ''))
cal = bl_calendars_map.get(clndr_id, P6Calendar())

bs = pd.to_datetime(brow.get('act_start_date') or brow.get('early_start_date') or brow.get('target_start_date'), errors='coerce')
bf = pd.to_datetime(brow.get('act_end_date') or brow.get('early_end_date') or brow.get('target_end_date'), errors='coerce')
data_date = pd.to_datetime(upd_source.get('project', {}).get('data_date', '2025-11-29'))

print("### Calendar Audit ###\n")
print(f"Activity: {code}")
print(f"Calendar ID: {clndr_id}")
print(f"Hours per day: {cal.hours_per_day}")
print("\nDate       | Working | Hours | Reason")
print("-" * 50)

current_dt = bs
total_days = 0
total_hours = 0

while current_dt <= data_date:
    is_w = cal.is_workday(current_dt)
    w_str = "Yes" if is_w else "No"
    h = cal.hours_per_day if is_w else 0
    
    reason = "Normal workday"
    if current_dt.date() in cal.holidays:
        reason = "Holiday/Exception"
    elif not is_w:
        reason = "Weekend"
        
    print(f"{current_dt.strftime('%Y-%m-%d')} | {w_str:<7} | {h:<5} | {reason}")
    if is_w:
        total_days += 1
        total_hours += h
    current_dt += timedelta(days=1)

print("-" * 50)
print(f"Total working days counted: {total_days}")
print(f"Total working hours counted: {total_hours}\n")

print("### Duration Engine Audit ###\n")
print(f"Activity Start Date/Time: {bs}")
print(f"Activity Finish Date/Time: {bf}")
print(f"Data Date/Time: {data_date}")
print(f"Calendar Used: {clndr_id}")

xer_days = cal.workdays_between(bs, data_date)
xer_hours = xer_days * cal.hours_per_day

print(f"Elapsed Days (XerAgent workdays_between): {xer_days}")
print(f"Elapsed Hours (XerAgent): {xer_hours}\n")

print("### Boundary Condition Audit ###\n")
# Method A: Exclude start day (by advancing start by 1 day)
method_a = cal.workdays_between(bs + timedelta(days=1), data_date) * cal.hours_per_day

# Method B: Include start day (exact workdays_between, if bs time <= 08:00 it usually excludes the day mathematically depending on engine logic)
# Let's count manually.
def count_days(start, end, inclusive_start=False, inclusive_end=False):
    d = 0
    c = start
    while c <= end:
        if cal.is_workday(c):
            if c.date() == start.date() and not inclusive_start:
                pass
            elif c.date() == end.date() and not inclusive_end:
                pass
            else:
                d += 1
        c += timedelta(days=1)
    return d * cal.hours_per_day

print(f"Method A (Exclude start day): {count_days(bs, data_date, False, True)}")
print(f"Method B (Include start day): {count_days(bs, data_date, True, False)}")
print(f"Method C (Include partial first day): Not perfectly defined without hour logic, but approx {count_days(bs, data_date, True, False)}")
print(f"Method D (Include Data Date boundary): {count_days(bs, data_date, True, True)}\n")

print("### Primavera Comparison ###\n")
bac = float(store._get_baseline_cost_map('test').get(code, 0))
pv = 32274.22
pv_pct = pv / bac if bac else 0

target_hr = float(brow.get('target_drtn_hr_cnt', 0))
req_hours = target_hr * pv_pct

print(f"BAC: {bac:.2f}")
print(f"Primavera PV: {pv:.2f}")
print(f"PV%: {pv_pct:.4%}")
print(f"Required elapsed hours: {req_hours:.2f}")

