import sys, os
sys.path.append("/Users/shibilmuhammad/Documents/Career/Coding /Projects/Work_Projects/openCoders/xeragent_desktop/backend/modules")
from analyzer import AgentAnalyzer

a = AgentAnalyzer()
a.data_store.load_from_memory("baseline_20260623103041")
print(a.get_calendar_exceptions(calendar_name="AMR-P1- 5 DAY", month=6, year=2026))
