"""
DS7 findings table — local SQLite pilot.

Schema is adapted from AI_Planner_Facts_Table_Schema_v0.1.docx section 7
(Postgres JSONB -> TEXT holding json.dumps, DECIMAL -> REAL, VARCHAR(n) -> TEXT).
This module only defines storage + a basic insert/read helper — nothing in
analyzer.py or data_store.py writes to it yet (M1/M2 wiring is a separate task).
"""
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "xeragent.db"

_JSON_COLUMNS = ("threshold_json", "activities_affected_ids", "attribution_json")

_CREATE_FINDINGS_TABLE = """
CREATE TABLE IF NOT EXISTS findings (
    finding_id                  TEXT NOT NULL,
    org_id                      TEXT NOT NULL,
    project_id                  TEXT NOT NULL,
    snapshot_id                 TEXT NOT NULL,
    finding_category            TEXT NOT NULL,
    check_id                    TEXT NOT NULL,
    check_name                  TEXT NOT NULL,
    check_source                TEXT NOT NULL,
    severity                    TEXT NOT NULL,
    value_numeric               REAL,
    value_string                TEXT,
    unit                        TEXT NOT NULL,
    threshold_json              TEXT NOT NULL,
    activities_affected_count   INTEGER,
    activities_affected_ids     TEXT,
    attribution_json            TEXT NOT NULL,
    primary_driver_dimension    TEXT,
    primary_driver_value        TEXT,
    narrative_hint              TEXT NOT NULL,
    refusal_reason              TEXT,
    trend_vs_previous           REAL,
    computed_at                 TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (org_id, project_id, snapshot_id, finding_id)
);
"""

_CREATE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_findings_category ON findings(org_id, project_id, snapshot_id, finding_category);",
    "CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(org_id, project_id, snapshot_id, severity);",
    "CREATE INDEX IF NOT EXISTS idx_findings_driver ON findings(org_id, project_id, snapshot_id, primary_driver_dimension, primary_driver_value);",
)


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Idempotent — safe to call on every backend startup."""
    conn = get_connection()
    try:
        conn.execute(_CREATE_FINDINGS_TABLE)
        for stmt in _CREATE_INDEXES:
            conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()


def insert_finding(finding: Dict[str, Any]) -> str:
    """
    Inserts a single finding row. `finding` should contain the DS7 columns;
    finding_id/org_id/computed_at are filled in with defaults if omitted.
    threshold_json/activities_affected_ids/attribution_json may be passed as
    Python objects (dict/list) — they get json.dumps'd here.
    """
    row = dict(finding)
    row.setdefault("finding_id", str(uuid.uuid4()))
    row.setdefault("org_id", "local")

    for col in _JSON_COLUMNS:
        if col in row and not isinstance(row[col], str):
            row[col] = json.dumps(row[col])
    row.setdefault("threshold_json", "{}")
    row.setdefault("attribution_json", "{}")

    columns = [c for c in row.keys() if c != "computed_at" or "computed_at" in row]
    placeholders = ", ".join(f":{c}" for c in columns)
    col_list = ", ".join(columns)

    conn = get_connection()
    try:
        conn.execute(f"INSERT INTO findings ({col_list}) VALUES ({placeholders})", row)
        conn.commit()
    finally:
        conn.close()
    return row["finding_id"]


def get_finding(finding_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM findings WHERE finding_id = ?", (finding_id,))
        row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    result = dict(row)
    for col in _JSON_COLUMNS:
        if result.get(col):
            result[col] = json.loads(result[col])
    return result


def list_findings(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM findings ORDER BY computed_at DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
    finally:
        conn.close()
    results = []
    for row in rows:
        result = dict(row)
        for col in _JSON_COLUMNS:
            if result.get(col):
                result[col] = json.loads(result[col])
        results.append(result)
    return results
