import sys
import pandas as pd
from pprint import pprint

sys.path.insert(0, '/Users/shibilmuhammad/Documents/Career/Coding /Projects/Work_Projects/openCoders/xeragent_desktop/backend')
from modules.data_store import DataStore
from modules.scheduler import P6Calendar, CPMEngine

print("--- 1. Parsed Calendars ---")
try:
    with open('/Users/shibilmuhammad/Documents/Career/Coding /Projects/Work_Projects/openCoders/xeragent_desktop/backend/data/xer_context.json', 'r') as f:
        pass
    
    # Let's load the latest from data_store manually using extraction logic if we can't hit API
    ds = DataStore()
    versions = ds.contexts.get('audit', {}).get('versions', {})
    if not versions:
        # fallback to controller context
        versions = ds.contexts.get('controller', {}).get('versions', {})
    
    if versions:
        latest = sorted(versions.values(), key=lambda x: x['data_date'])[-1]
        cals = ds.get_calendar_info(version_id=latest['id'], context='controller')
        for c in cals:
            print(f"ID: {c.get('id')}, Name: {c.get('name')}, Hours/Day: {c.get('hours_per_day')}, Type: {c.get('type')}")
            # missing workweek type
        
        print("\n--- 2. Random Activities Calendars ---")
        tasks_df = latest['df'].get('tasks', pd.DataFrame())
        if not tasks_df.empty:
            sample = tasks_df.sample(min(20, len(tasks_df)))
            for _, row in sample.iterrows():
                print(f"Act ID: {row.get('task_code')}, Name: {row.get('task_name')[:30]}, Calendar ID: {row.get('clndr_id')}")
        else:
            print("No tasks found.")
            
        print("\n--- 4. Duration Calculations Check ---")
        print("Checking scheduler.py CPMEngine logic for calendar usage:")
        with open('/Users/shibilmuhammad/Documents/Career/Coding /Projects/Work_Projects/openCoders/xeragent_desktop/backend/modules/scheduler.py', 'r') as f:
            content = f.read()
            if 'self._get_calendar' in content:
                print("CPMEngine USES activity-specific calendars (cal_id_map -> _get_calendar) for duration calculations.")
            else:
                print("CPMEngine does NOT use activity-specific calendars.")
                
            if 'ramadan' in content.lower():
                print("Found Ramadan detection in scheduler.py")
            else:
                print("Ramadan detection NOT found in scheduler.py")
                
            if 'holiday' in content.lower() or 'exception' in content.lower():
                print("Found holiday/exception detection in scheduler.py")
            else:
                print("Holiday/exception detection NOT found in scheduler.py")
                
        print("\n--- 5. Test AI Capabilities Check ---")
        print("Checking analyzer.py for calendar query intents:")
        with open('/Users/shibilmuhammad/Documents/Career/Coding /Projects/Work_Projects/openCoders/xeragent_desktop/backend/modules/analyzer.py', 'r') as f:
            analyzer_content = f.read()
            if '7-day' in analyzer_content.lower() or 'holiday' in analyzer_content.lower():
                print("Found holiday or 7-day query capabilities in analyzer prompt.")
            else:
                print("Missing advanced calendar AI intents (like holiday, 7-day).")
except Exception as e:
    print(f"Error during audit: {e}")

