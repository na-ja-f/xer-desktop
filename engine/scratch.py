import sys
sys.path.append("/Users/shibilmuhammad/Documents/Career/Coding /Projects/Work_Projects/openCoders/xeragent_desktop/backend/modules")
class MockDataStore:
    def get_calendar_info(self, **kwargs):
        return [{
            "name": "AMR-P1- 5 DAY",
            "effective_non_working_dates": ["2026-05-28", "2026-06-17", "2026-08-25"],
            "effective_working_overrides": [],
            "raw_non_working_dates": ["2026-05-28", "2026-06-17", "2026-08-25"],
            "raw_working_overrides": []
        }]

import analyzer
# monkey patch before instantiating
analyzer.AgentAnalyzer.__init__ = lambda self: setattr(self, 'data_store', MockDataStore())
a = analyzer.AgentAnalyzer()
a.data_store = MockDataStore()

res = a.get_calendar_exceptions(calendar_name="AMR-P1- 5 DAY", month="6", year="2026", exception_type="holiday")
print("TEST 1:", res)
