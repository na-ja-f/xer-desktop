"""
DS7 findings + DS8 changes tables — local SQLite pilot.

Schema is adapted from AI_Planner_Facts_Table_Schema_v0.1.docx sections 7
(findings) and 8 (changes) (Postgres JSONB -> TEXT holding json.dumps,
DECIMAL -> REAL, VARCHAR(n) -> TEXT). Both tables live in the same SQLite
file, so they share one connection/init module.

This module only defines storage + CRUD; the diff engine that actually
computes DS8 rows by comparing two snapshots lives in changes.py (B-044),
same as findings.py computes DS7 rows.
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

_CREATE_ACTIVITY_CODE_CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS activity_code_config (
    config_id      TEXT NOT NULL,
    org_id         TEXT NOT NULL,
    project_id     TEXT NOT NULL,
    config_type    TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    raw_name       TEXT NOT NULL,
    value_json     TEXT,
    source         TEXT NOT NULL,
    updated_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (org_id, project_id, config_type, raw_name)
);
"""
# Keyed by raw_name (the detected category as it appears in this project's XER),
# not canonical_name — the identity being configured is "this raw category has
# one current canonical mapping", editable over time. Keying by canonical_name
# instead would let a user "rename" a category's mapping into a second row
# rather than replacing the first.
# config_type: 'synonym' (B-204, activity-code category name normalization) today;
# reserved for future config_type values (e.g. zone/trade mapping, B-205) without
# a schema change — value_json is an unused free-form payload slot until then.

_CREATE_ACTIVITY_CODE_CONFIG_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_activity_code_config_project ON activity_code_config(org_id, project_id, config_type);",
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
        conn.execute(_CREATE_ACTIVITY_CODE_CONFIG_TABLE)
        for stmt in _CREATE_ACTIVITY_CODE_CONFIG_INDEX:
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
    omitted. old_value/new_value/attribution_json are always json.dumps'd
    here, unconditionally — unlike insert_finding's JSON columns (always
    dict/list in practice), old_value/new_value are frequently plain
    scalars (e.g. a relationship_type string like "FS", a calendar id), so
    an isinstance(str)-skips-encoding shortcut would store an unquoted raw
    string that isn't valid JSON and breaks on read. old_value/new_value
    stay NULL when omitted (both nullable in the schema); attribution_json
    defaults to "{}" since it's NOT NULL.
    """
    row = dict(change)
    row.setdefault("change_id", str(uuid.uuid4()))
    row.setdefault("org_id", "local")

    for col in _CHANGES_JSON_COLUMNS:
        if col in row and row[col] is not None:
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


def delete_changes_for_pair(project_id: str, from_snapshot_id: str, to_snapshot_id: str) -> int:
    """Removes DS8 rows for one (from_snapshot_id, to_snapshot_id) pair.
    write_changes_for_version calls this before inserting fresh rows so a
    re-run of the diff on the same pair is idempotent (schema doc section
    8.3) instead of accumulating duplicate change rows."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM changes WHERE project_id = ? AND from_snapshot_id = ? AND to_snapshot_id = ?",
            (project_id, from_snapshot_id, to_snapshot_id),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def upsert_activity_code_config(row: Dict[str, Any]) -> str:
    """Inserts or updates one activity-code config row (e.g. a canonical-name
    synonym mapping for one raw category name in one project). Auto-suggest
    (source='auto_suggested') must never clobber a user's manual edit — the
    caller is responsible for checking existing rows before calling this with
    source='auto_suggested' (see suggest_synonyms in activity_code_config.py);
    this function itself always upserts unconditionally once called."""
    row = dict(row)
    row.setdefault("config_id", str(uuid.uuid4()))
    row.setdefault("org_id", "local")
    row.setdefault("value_json", None)
    if row.get("value_json") is not None and not isinstance(row["value_json"], str):
        row["value_json"] = json.dumps(row["value_json"])

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO activity_code_config
                (config_id, org_id, project_id, config_type, canonical_name, raw_name, value_json, source, updated_at)
            VALUES (:config_id, :org_id, :project_id, :config_type, :canonical_name, :raw_name, :value_json, :source, CURRENT_TIMESTAMP)
            ON CONFLICT(org_id, project_id, config_type, raw_name) DO UPDATE SET
                canonical_name = excluded.canonical_name,
                value_json = excluded.value_json,
                source = excluded.source,
                updated_at = CURRENT_TIMESTAMP
            """,
            row,
        )
        conn.commit()
    finally:
        conn.close()
    return row["config_id"]


def get_activity_code_config(project_id: str, config_type: str = "synonym") -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT * FROM activity_code_config WHERE project_id = ? AND config_type = ? ORDER BY raw_name",
            (project_id, config_type),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    results = []
    for row in rows:
        result = dict(row)
        if result.get("value_json"):
            result["value_json"] = json.loads(result["value_json"])
        results.append(result)
    return results


def list_changes_for_pair(
    project_id: str,
    from_snapshot_id: str,
    to_snapshot_id: str,
    change_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """All DS8 rows for one specific snapshot pair, optionally filtered to a
    single change_type. Used by the diff engine's verification script to
    inspect/spot-check what a run produced."""
    conn = get_connection()
    try:
        type_clause = "AND change_type = ?" if change_type else ""
        params = [project_id, from_snapshot_id, to_snapshot_id]
        if change_type:
            params.append(change_type)
        cur = conn.execute(
            f"""
            SELECT * FROM changes
            WHERE project_id = ? AND from_snapshot_id = ? AND to_snapshot_id = ?
            {type_clause}
            ORDER BY entity_type, entity_id
            """,
            params,
        )
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
