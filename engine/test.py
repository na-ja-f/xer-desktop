import sys
sys.path.append("/Users/shibilmuhammad/Documents/Career/Coding /Projects/Work_Projects/openCoders/xeragent_desktop/backend/modules")
from analyzer import AgentAnalyzer
a = AgentAnalyzer()
class MockDataStore:
    def get_calendar_info(self, **kwargs):
        return [{
            "name": "AMR-P1- 5 DAY",
            "effective_non_working_dates": ["2026-05-28", "2026-06-17", "2026-08-25"],
            "effective_working_overrides": []
        }]
a.data_store = MockDataStore()
res = a.get_calendar_exceptions(calendar_name="AMR-P1- 5 DAY", month="6", year="2026", exception_type="holiday")
print("TEST 1 (holiday):", res)
res2 = a.get_calendar_exceptions(calendar_name="AMR-P1- 5 DAY", month="6", year="2026", exception_type="non_working")
print("TEST 2 (non_working):", res2)
res3 = a.get_calendar_exceptions(calendar_name="AMR-P1- 5 DAY", month="6", year="2026")
print("TEST 3 (None):", res3)
