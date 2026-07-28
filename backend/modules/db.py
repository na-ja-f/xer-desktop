"""
DS7 findings + DS8 changes tables — local SQLite pilot.

Schema is adapted from AI_Planner_Facts_Table_Schema_v0.1.docx sections 7
(findings) and 8 (changes) (Postgres JSONB -> TEXT holding json.dumps,
DECIMAL -> REAL, VARCHAR(n) -> TEXT). Both tables live in the same SQLite
file, so they share one connection/init module.

DS8 (changes) only has storage + a basic insert/read helper here — the diff
engine that actually computes and writes rows (comparing two snapshots) is a
separate follow-on task, same as DS7's findings.py was for DS7.
"""
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

_CHANGES_JSON_COLUMNS = ("old_value", "new_value", "attribution_json")

_CREATE_CHANGES_TABLE = """
CREATE TABLE IF NOT EXISTS changes (
    change_id         TEXT NOT NULL,
    org_id            TEXT NOT NULL,
    project_id        TEXT NOT NULL,
    from_snapshot_id  TEXT NOT NULL,
    to_snapshot_id    TEXT NOT NULL,
    change_type       TEXT NOT NULL,
    entity_type       TEXT NOT NULL,
    entity_id         TEXT NOT NULL,
    field_changed     TEXT,
    old_value         TEXT,
    new_value         TEXT,
    delta_numeric     REAL,
    attribution_json  TEXT NOT NULL,
    narrative_hint    TEXT NOT NULL,
    computed_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (org_id, project_id, change_id)
);
"""

_CREATE_CHANGES_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_changes_snapshots ON changes(org_id, project_id, from_snapshot_id, to_snapshot_id);",
    "CREATE INDEX IF NOT EXISTS idx_changes_type ON changes(org_id, project_id, change_type);",
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
        conn.execute(_CREATE_CHANGES_TABLE)
        for stmt in _CREATE_CHANGES_INDEXES:
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


def get_findings_history(
    project_id: str,
    finding_category: str = "audit",
    check_source: str = "dcma",
) -> Dict[str, List[Dict[str, Any]]]:
    """Returns DS7 history for every check_id matching the filters, grouped by
    check_id and ordered oldest -> newest. Read-only; does not filter by
    snapshot count (that's a display decision left to the caller)."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT check_id, snapshot_id, computed_at, value_numeric, severity
            FROM findings
            WHERE project_id = ? AND finding_category = ? AND check_source = ?
            ORDER BY check_id ASC, computed_at ASC
            """,
            (project_id, finding_category, check_source),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    history: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        r = dict(row)
        history.setdefault(r["check_id"], []).append({
            "snapshot_id": r["snapshot_id"],
            "computed_at": r["computed_at"],
            "value_numeric": r["value_numeric"],
            "severity": r["severity"],
        })
    return history


def delete_findings_for_snapshot(project_id: str, snapshot_id: str) -> int:
    """Removes DS7 rows for one deleted version. Without this, DELETE
    /versions/{id} only cleared in-memory state — the deleted version's
    findings stayed in DS7 forever and kept showing up as a "ghost" entry
    in get_score_history/get_findings_history, silently skewing trends
    computed after it (e.g. a re-uploaded update comparing itself against
    the invisible, supposedly-deleted prior upload)."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM findings WHERE project_id = ? AND snapshot_id = ?",
            (project_id, snapshot_id),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_score_history(
    project_id: str,
    finding_category: str = "audit",
    check_source: str = "dcma",
    exclude_check_ids: Tuple[str, ...] = (),
) -> List[Dict[str, Any]]:
    """One pass/total score per snapshot, oldest -> newest.

    Always excludes severity='n/a' rows (checks that weren't evaluable for a
    given snapshot, e.g. BEI before an update file is loaded) so "evaluated"
    stays data-driven rather than keyed off a hardcoded check id."""
    conn = get_connection()
    try:
        exclude_clause = ""
        params: List[Any] = [project_id, finding_category, check_source]
        if exclude_check_ids:
            placeholders = ", ".join("?" for _ in exclude_check_ids)
            exclude_clause = f"AND check_id NOT IN ({placeholders})"
            params.extend(exclude_check_ids)
        cur = conn.execute(
            f"""
            SELECT snapshot_id, severity, computed_at
            FROM findings
            WHERE project_id = ? AND finding_category = ? AND check_source = ?
              AND severity != 'n/a'
              {exclude_clause}
            ORDER BY computed_at ASC
            """,
            params,
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    snapshots: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for row in rows:
        r = dict(row)
        sid = r["snapshot_id"]
        if sid not in snapshots:
            snapshots[sid] = {"pass": 0, "total": 0, "computed_at": r["computed_at"]}
            order.append(sid)
        snapshots[sid]["total"] += 1
        if r["severity"] == "pass":
            snapshots[sid]["pass"] += 1

    return [
        {
            "snapshot_id": sid,
            "computed_at": snapshots[sid]["computed_at"],
            "score": round(snapshots[sid]["pass"] / snapshots[sid]["total"] * 100)
            if snapshots[sid]["total"]
            else None,
        }
        for sid in order
    ]


def get_findings_for_snapshot(
    project_id: str,
    snapshot_id: str,
    finding_category: str = "audit",
    check_source: str = "dcma",
    exclude_check_ids: Tuple[str, ...] = (),
) -> List[Dict[str, Any]]:
    """All DS7 findings rows for one specific (project_id, snapshot_id) — the
    complete point-in-time DCMA finding set for the M4 narrative to describe
    (B-019). Unlike get_findings_history (grouped across all snapshots) this
    returns exactly the rows for one snapshot, ordered by check_id for stable
    prompt construction.

    Unlike get_score_history, this does NOT filter out severity='n/a' rows —
    the narrative should still see e.g. a not-yet-evaluable BEI row (with its
    refusal_reason) so it can describe that status accurately instead of
    silently omitting the check."""
    conn = get_connection()
    try:
        placeholders = ", ".join("?" for _ in exclude_check_ids)
        exclude_clause = f"AND check_id NOT IN ({placeholders})" if exclude_check_ids else ""
        cur = conn.execute(
            f"""
            SELECT check_id, check_name, severity, value_numeric, unit, narrative_hint
            FROM findings
            WHERE project_id = ? AND snapshot_id = ? AND finding_category = ? AND check_source = ?
            {exclude_clause}
            ORDER BY check_id
            """,
            (project_id, snapshot_id, finding_category, check_source, *exclude_check_ids),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


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


def insert_change(change: Dict[str, Any]) -> str:
    """
    Inserts a single DS8 change row. `change` should contain the DS8
    columns; change_id/org_id/computed_at are filled in with defaults if
    omitted. old_value/new_value/attribution_json may be passed as Python
    objects (dict/list) — they get json.dumps'd here. old_value/new_value
    stay NULL when omitted (both nullable in the schema); attribution_json
    defaults to "{}" since it's NOT NULL.
    """
    row = dict(change)
    row.setdefault("change_id", str(uuid.uuid4()))
    row.setdefault("org_id", "local")

    for col in _CHANGES_JSON_COLUMNS:
        if col in row and not isinstance(row[col], str):
            row[col] = json.dumps(row[col])
    row.setdefault("attribution_json", "{}")

    columns = list(row.keys())
    placeholders = ", ".join(f":{c}" for c in columns)
    col_list = ", ".join(columns)

    conn = get_connection()
    try:
        conn.execute(f"INSERT INTO changes ({col_list}) VALUES ({placeholders})", row)
        conn.commit()
    finally:
        conn.close()
    return row["change_id"]


def get_change(change_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM changes WHERE change_id = ?", (change_id,))
        row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    result = dict(row)
    for col in _CHANGES_JSON_COLUMNS:
        if result.get(col):
            result[col] = json.loads(result[col])
    return result


def list_changes(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM changes ORDER BY computed_at DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
    finally:
        conn.close()
    results = []
    for row in rows:
        result = dict(row)
        for col in _CHANGES_JSON_COLUMNS:
            if result.get(col):
                result[col] = json.loads(result[col])
        results.append(result)
    return results
