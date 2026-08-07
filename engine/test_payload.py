import sys, os, json
sys.path.append(os.path.abspath("."))
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore
from modules.analyzer import XERAnalyzer

XER_BASELINE = "/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer"

store = XERDataStore()
extractor = CompleteXERExtractor(XER_BASELINE, "baseline")
extractor.extract_all()
data = extractor.get_complete_data()
version_id = store.add_version(
    data,
    data['project']['project_name'],
    data['project']['data_date'],
    type="baseline",
    context="controller"
)

analyzer = XERAnalyzer()
analyzer.data_store = store

original_create = analyzer.client.chat.completions.create

def mock_create(*args, **kwargs):
    messages = kwargs.get("messages", [])
    is_explainer = any("You are the Lead Primavera P6 Scheduling Analyst" in str(m.get("content", "")) for m in messages)
    
    if is_explainer:
        print("\n=== EXACT MESSAGES ARRAY SENT TO OPENAI (EXPLAIINER) ===")
        print(json.dumps(messages, indent=2, default=str))
        print("=======================================================\n")
        sys.exit(0)
    else:
        # For routing, just return a mock response to route to get_critical_path
        class MockChoice:
            class MockMessage:
                content = '{"query_type": "DATA_QUERY", "tool": "get_critical_path", "arguments": {"limit": 20}}'
            message = MockMessage()
        class MockResponse:
            choices = [MockChoice()]
        return MockResponse()

analyzer.client.chat.completions.create = mock_create

analyzer.analyze("Show critical path activities", context={"current_view": "controller"})
