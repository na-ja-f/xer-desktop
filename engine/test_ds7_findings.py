"""
Standalone verification for the DS7 findings table (SQLite pilot).
Run with: venv_desktop/Scripts/python.exe backend/test_ds7_findings.py
Not a pytest suite (this repo has no test runner wired up) — just asserts and prints.
"""
from modules.db import init_db, insert_finding, get_finding, DB_PATH

init_db()
print(f"DB initialized at: {DB_PATH}")

sample = {
    "project_id": "AL_AMRA_DEMO",
    "snapshot_id": "SNAP-0001",
    "finding_category": "audit",
    "check_id": "dcma-high-float",
    "check_name": "High Float Activities",
    "check_source": "dcma",
    "severity": "warning",
    "value_numeric": 12.4,
    "unit": "percent",
    "threshold_json": {"pass": 5, "warning": 10, "fail": 20},
    "activities_affected_count": 34,
    "activities_affected_ids": ["A1000", "A1010", "A1020"],
    "attribution_json": {"trade_breakdown": {"mechanical": 20, "electrical": 14}},
    "primary_driver_dimension": "trade",
    "primary_driver_value": "mechanical",
    "narrative_hint": "12.4% of activities show unusually high float, concentrated in mechanical scope.",
}

finding_id = insert_finding(sample)
print(f"Inserted finding_id: {finding_id}")

row = get_finding(finding_id)
assert row is not None, "Round-trip read returned nothing"
assert row["check_id"] == sample["check_id"]
assert row["severity"] == sample["severity"]
assert row["threshold_json"] == sample["threshold_json"], "threshold_json did not round-trip as JSON"
assert row["activities_affected_ids"] == sample["activities_affected_ids"], "activities_affected_ids did not round-trip as JSON"
assert row["attribution_json"] == sample["attribution_json"], "attribution_json did not round-trip as JSON"
assert row["org_id"] == "local", "org_id default not applied"
assert row["computed_at"], "computed_at was not populated"

print("Round-trip verified OK:")
print(row)
