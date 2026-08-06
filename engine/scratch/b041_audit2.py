import json

print("--- 1. Parsed Calendars ---")
try:
    with open('/Users/shibilmuhammad/Documents/Career/Coding /Projects/Work_Projects/openCoders/xeragent_desktop/backend/data/xer_context.json', 'r') as f:
        data = json.load(f)
    
    versions = data.get('audit', {}).get('versions', {})
    if not versions:
        versions = data.get('controller', {}).get('versions', {})
        
    if versions:
        latest = sorted(versions.values(), key=lambda x: x['data_date'])[-1]
        cals = latest['data'].get('tables', {}).get('CALENDAR', [])
        print(f"Total Calendars found in XER: {len(cals)}")
        for c in cals[:10]:
            print(f"ID: {c.get('clndr_id')}, Name: {c.get('clndr_name')}, Hours/Day: {c.get('day_hr_cnt')}, Type: {c.get('clndr_type')}")
            # missing workweek type
        
        print("\n--- 2. Random Activities Calendars ---")
        tasks = latest['data'].get('tables', {}).get('TASK', [])
        if tasks:
            import random
            sample = random.sample(tasks, min(20, len(tasks)))
            for row in sample:
                print(f"Act ID: {row.get('task_code')}, Name: {row.get('task_name')[:30]}, Calendar ID: {row.get('clndr_id')}")
        else:
            print("No tasks found.")
            
    print("\n--- 4. Duration Calculations Check ---")
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
    with open('/Users/shibilmuhammad/Documents/Career/Coding /Projects/Work_Projects/openCoders/xeragent_desktop/backend/modules/analyzer.py', 'r') as f:
        analyzer_content = f.read()
        if '7-day' in analyzer_content.lower() or 'holiday' in analyzer_content.lower():
            print("Found holiday or 7-day query capabilities in analyzer prompt.")
        else:
            print("Missing advanced calendar AI intents (like holiday, 7-day).")
except Exception as e:
    print(f"Error during audit: {e}")

