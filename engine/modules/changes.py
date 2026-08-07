"""
DS8 changes orchestration (B-044).

Diffs a baseline against an update — matched by task_code, never the
internal task_id, since P6 assigns task_id per XER export and it is not
stable across uploads (a task_id from the baseline export can collide with
or simply not match the "same" activity's task_id in the update export,
even though its task_code is unchanged) — and writes one DS8 `changes` row
per detected difference: activity added/deleted, duration/date/constraint/
calendar field changes on matching activities, relationship added/
removed/type-changed/lag-changed, and activity code reassignment (B-204).

Diffs off the pristine raw TASK/TASKPRED dataframes (version['df']['task'] /
['taskpred'], singular keys — built once from the raw XER records and never
touched again), never version['df']['tasks'] (plural — gets CPM-computed
columns like early_start/total_float merged in by _run_cpm). Only genuine
schedule-input changes should be detected, not recomputed CPM output.

Called once per upload (see main.py's /upload-xer), same as findings.py.
"""
from typing import Dict, List, Optional, Tuple

import pandas as pd

from . import db
from .findings import project_identity

_TYPE_LABELS = {"PR_FS": "FS", "PR_SS": "SS", "PR_FF": "FF", "PR_SF": "SF"}

# clndr_id is handled separately (resolved to clndr_name via the version's
# own CALENDAR table) rather than being compared as a raw id — see
# _build_calendar_map / _build_activity_map.
_ACTIVITY_FIELDS = (
    "task_name", "target_drtn_hr_cnt", "cstr_type", "cstr_date",
    "target_start_date", "target_end_date",
)


def _blank(val) -> bool:
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    return str(val).strip() == ""


def _num(val) -> Optional[float]:
    n = pd.to_numeric(val, errors="coerce")
    return None if pd.isna(n) else float(n)


def _date(val):
    d = pd.to_datetime(val, errors="coerce")
    return None if pd.isna(d) else d


def _rel_type(raw) -> str:
    return _TYPE_LABELS.get(raw, raw)


def _change_row(change_type, entity_type, entity_id, field_changed=None,
                 old_value=None, new_value=None, delta_numeric=None, narrative_hint="") -> Dict:
    return {
        "change_type": change_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "field_changed": field_changed,
        "old_value": old_value,
        "new_value": new_value,
        "delta_numeric": delta_numeric,
        "attribution_json": {},
        "narrative_hint": narrative_hint,
    }


def _build_calendar_map(calendar_df: Optional[pd.DataFrame]) -> Dict:
    """clndr_id -> clndr_name for one version's pristine CALENDAR table.
    P6 assigns clndr_id per XER export too (same instability as task_id —
    confirmed on the Al Amra sample: 'AMR-P1- 6 DAY' is clndr_id 1233 in the
    baseline export and 751 in the update export), so calendar changes must
    be detected by name, never by comparing raw clndr_id across versions."""
    if calendar_df is None or calendar_df.empty or "clndr_id" not in calendar_df.columns:
        return {}
    return calendar_df.set_index("clndr_id")["clndr_name"].to_dict()


def _build_activity_map(task_df: Optional[pd.DataFrame], clndr_id_to_name: Dict) -> Dict[str, Dict]:
    """task_code -> raw schedule fields, for one version's pristine TASK table.
    clndr_id is resolved to clndr_name here (via this same version's own
    calendar map) so it's comparable across versions."""
    if task_df is None or task_df.empty or "task_code" not in task_df.columns:
        return {}
    present = [f for f in _ACTIVITY_FIELDS if f in task_df.columns]
    has_clndr = "clndr_id" in task_df.columns
    result = {}
    for _, row in task_df.iterrows():
        code = row.get("task_code")
        if _blank(code):
            continue
        entry = {f: row.get(f) for f in present}
        if has_clndr:
            raw_clndr = row.get("clndr_id")
            entry["clndr_name"] = None if _blank(raw_clndr) else clndr_id_to_name.get(raw_clndr, str(raw_clndr))
        result[code] = entry
    return result


def _build_relationship_map(taskpred_df: Optional[pd.DataFrame], task_id_to_code: Dict) -> Dict[Tuple[str, str], Dict]:
    """(pred_task_code, succ_task_code) -> {pred_type, lag_hr_cnt}, resolved
    through this SAME version's own task_id -> task_code map. Rows whose
    predecessor/successor id doesn't resolve (e.g. cross-project links) are
    skipped rather than guessed at."""
    if taskpred_df is None or taskpred_df.empty:
        return {}
    result = {}
    for _, row in taskpred_df.iterrows():
        pred_code = task_id_to_code.get(row.get("pred_task_id"))
        succ_code = task_id_to_code.get(row.get("task_id"))
        if _blank(pred_code) or _blank(succ_code):
            continue
        result[(pred_code, succ_code)] = {
            "pred_type": row.get("pred_type"),
            "lag_hr_cnt": row.get("lag_hr_cnt"),
        }
    return result


def _diff_activities(base_map: Dict, upd_map: Dict, hpd: float) -> List[Dict]:
    hpd = hpd or 8.0
    changes: List[Dict] = []
    base_codes, upd_codes = set(base_map), set(upd_map)

    for code in upd_codes - base_codes:
        a = upd_map[code]
        name = a.get("task_name") or ""
        changes.append(_change_row(
            "activity_added", "activity", code,
            new_value={"task_name": name},
            narrative_hint=f"New activity {code} — {name} added, not present in baseline.".strip(),
        ))

    for code in base_codes - upd_codes:
        a = base_map[code]
        name = a.get("task_name") or ""
        changes.append(_change_row(
            "activity_deleted", "activity", code,
            old_value={"task_name": name},
            narrative_hint=f"Activity {code} — {name} was in the baseline but is missing from this update.".strip(),
        ))

    for code in base_codes & upd_codes:
        b, u = base_map[code], upd_map[code]
        name = u.get("task_name") or b.get("task_name") or ""

        old_hrs = _num(b.get("target_drtn_hr_cnt"))
        new_hrs = _num(u.get("target_drtn_hr_cnt"))
        if old_hrs is not None and new_hrs is not None and round(old_hrs, 4) != round(new_hrs, 4):
            # Compare raw hours (the actual stored value) — converting each
            # side with its own version's hours_per_day before comparing
            # would flag a duration as "changed" purely because the two
            # exports' CALENDAR tables list their calendars in a different
            # order (hours_per_day is auto-picked as "whichever calendar is
            # first"), even when the underlying hours are identical. Days
            # are only for display, using one consistent divisor.
            old_dur, new_dur = old_hrs / hpd, new_hrs / hpd
            shortened = new_hrs < old_hrs
            changes.append(_change_row(
                "duration_shortened" if shortened else "duration_extended",
                "activity", code, field_changed="target_drtn_hr_cnt",
                old_value=round(old_dur, 2), new_value=round(new_dur, 2),
                delta_numeric=round(new_dur - old_dur, 2),
                narrative_hint=(
                    f"Duration {'shortened' if shortened else 'extended'} from "
                    f"{old_dur:.1f} to {new_dur:.1f} days for {code} — {name}."
                ),
            ))

        for field, ctype, label in (
            ("target_start_date", "start_date_changed", "Planned start"),
            ("target_end_date", "finish_date_changed", "Planned finish"),
        ):
            old_d, new_d = _date(b.get(field)), _date(u.get(field))
            if old_d is not None and new_d is not None and old_d != new_d:
                delta_days = (new_d - old_d).days
                changes.append(_change_row(
                    ctype, "activity", code, field_changed=field,
                    old_value=old_d.strftime("%Y-%m-%d"), new_value=new_d.strftime("%Y-%m-%d"),
                    delta_numeric=delta_days,
                    narrative_hint=(
                        f"{label} moved from {old_d:%d %b %Y} to {new_d:%d %b %Y} "
                        f"for {code} — {name} ({delta_days:+d}d)."
                    ),
                ))

        old_type, new_type = b.get("cstr_type"), u.get("cstr_type")
        old_date, new_date = b.get("cstr_date"), u.get("cstr_date")
        old_has, new_has = not _blank(old_type), not _blank(new_type)
        if not old_has and new_has:
            changes.append(_change_row(
                "constraint_added", "constraint", code,
                new_value={"cstr_type": new_type, "cstr_date": new_date},
                narrative_hint=f"Constraint {new_type} added on {code} — {name}.",
            ))
        elif old_has and not new_has:
            changes.append(_change_row(
                "constraint_removed", "constraint", code,
                old_value={"cstr_type": old_type, "cstr_date": old_date},
                narrative_hint=f"Constraint {old_type} removed from {code} — {name}.",
            ))
        elif old_has and new_has and (str(old_type) != str(new_type) or str(old_date) != str(new_date)):
            changes.append(_change_row(
                "constraint_modified", "constraint", code,
                old_value={"cstr_type": old_type, "cstr_date": old_date},
                new_value={"cstr_type": new_type, "cstr_date": new_date},
                narrative_hint=f"Constraint on {code} — {name} changed from {old_type} to {new_type}.",
            ))

        old_cal, new_cal = b.get("clndr_name"), u.get("clndr_name")
        if not _blank(old_cal) and not _blank(new_cal) and str(old_cal) != str(new_cal):
            changes.append(_change_row(
                "calendar_changed", "calendar", code, field_changed="clndr_id",
                old_value=str(old_cal), new_value=str(new_cal),
                narrative_hint=f"Calendar assignment changed from '{old_cal}' to '{new_cal}' for {code} — {name}.",
            ))

    return changes


def _diff_relationships(base_map: Dict, upd_map: Dict, hpd: float) -> List[Dict]:
    hpd = hpd or 8.0
    changes: List[Dict] = []
    base_keys, upd_keys = set(base_map), set(upd_map)

    for key in upd_keys - base_keys:
        pred_code, succ_code = key
        rtype = _rel_type(upd_map[key].get("pred_type"))
        changes.append(_change_row(
            "logic_added", "relationship", f"{pred_code}::{succ_code}",
            new_value={"relationship_type": rtype, "lag_hr_cnt": upd_map[key].get("lag_hr_cnt")},
            narrative_hint=f"New {rtype} relationship added: {pred_code} -> {succ_code}.",
        ))

    for key in base_keys - upd_keys:
        pred_code, succ_code = key
        rtype = _rel_type(base_map[key].get("pred_type"))
        changes.append(_change_row(
            "logic_removed", "relationship", f"{pred_code}::{succ_code}",
            old_value={"relationship_type": rtype, "lag_hr_cnt": base_map[key].get("lag_hr_cnt")},
            narrative_hint=f"Relationship removed: {pred_code} -> {succ_code} ({rtype}).",
        ))

    for key in base_keys & upd_keys:
        pred_code, succ_code = key
        b, u = base_map[key], upd_map[key]

        if b.get("pred_type") != u.get("pred_type"):
            old_t, new_t = _rel_type(b.get("pred_type")), _rel_type(u.get("pred_type"))
            changes.append(_change_row(
                "logic_modified", "relationship", f"{pred_code}::{succ_code}",
                field_changed="relationship_type", old_value=old_t, new_value=new_t,
                narrative_hint=f"Relationship type changed from {old_t} to {new_t}: {pred_code} -> {succ_code}.",
            ))

        old_lag_hrs = _num(b.get("lag_hr_cnt"))
        new_lag_hrs = _num(u.get("lag_hr_cnt"))
        if old_lag_hrs is not None and new_lag_hrs is not None and round(old_lag_hrs, 4) != round(new_lag_hrs, 4):
            # Same rationale as duration: gate on raw hours, convert with one
            # consistent hpd for the days shown in old_value/new_value.
            old_lag, new_lag = old_lag_hrs / hpd, new_lag_hrs / hpd
            changes.append(_change_row(
                "logic_modified", "relationship", f"{pred_code}::{succ_code}",
                field_changed="lag", old_value=round(old_lag, 2), new_value=round(new_lag, 2),
                delta_numeric=round(new_lag - old_lag, 2),
                narrative_hint=f"Lag changed from {old_lag:.1f}d to {new_lag:.1f}d: {pred_code} -> {succ_code}.",
            ))

    return changes


def _build_activity_code_map(tables: Dict, task_id_to_code: Dict) -> Dict[str, Dict[str, List[str]]]:
    """task_code -> {code_type_name: sorted [value_names]}, for one version's
    pristine TASKACTV/ACTVCODE/ACTVTYPE tables (B-204). Keyed by task_code (via
    this version's own task_id -> task_code map, same resolution diff_snapshots
    already builds for relationships) rather than task_id, for the same
    cross-export instability reason as everywhere else in this module — NOT a
    reuse of XERDataStore._build_activity_codes_map, which is task_id-keyed.
    Values are sorted so value-set comparison in _diff_activity_codes is
    independent of row order between the two XER exports."""
    taskactv = tables.get('TASKACTV')
    actvcode = tables.get('ACTVCODE')
    actvtype = tables.get('ACTVTYPE')
    if not taskactv or not actvcode or not actvtype:
        return {}

    taskactv_df = pd.DataFrame(taskactv)
    actvcode_df = pd.DataFrame(actvcode)
    actvtype_df = pd.DataFrame(actvtype)
    if taskactv_df.empty or actvcode_df.empty or actvtype_df.empty:
        return {}

    try:
        merged = taskactv_df.merge(
            actvcode_df[['actv_code_id', 'actv_code_name']], on='actv_code_id', how='left'
        )
        merged = merged.merge(
            actvtype_df[['actv_code_type_id', 'actv_code_type']], on='actv_code_type_id', how='left'
        )
        merged['actv_code_type'] = merged['actv_code_type'].astype(str).str.strip()
        merged['actv_code_name'] = merged['actv_code_name'].astype(str).str.strip()
        merged['task_code'] = merged['task_id'].map(task_id_to_code)
        merged = merged.dropna(subset=['task_code'])

        result: Dict[str, Dict[str, List[str]]] = {}
        for _, row in merged.iterrows():
            result.setdefault(row['task_code'], {}).setdefault(row['actv_code_type'], []).append(row['actv_code_name'])
        for types in result.values():
            for type_name in types:
                types[type_name] = sorted(types[type_name])
        return result
    except Exception:
        return {}


def _diff_activity_codes(base_map: Dict, upd_map: Dict) -> List[Dict]:
    """Detects activity-code reassignment between baseline and update, for
    activities present in both (added/deleted activities are already fully
    covered by _diff_activities — this only handles 'same activity, code
    assignment changed', e.g. moved from Sector 1A to Sector 1B, or a
    multi-select category's value set changed)."""
    changes: List[Dict] = []
    for code in set(base_map) & set(upd_map):
        b_types, u_types = base_map[code], upd_map[code]
        for type_name in set(b_types) | set(u_types):
            old_vals = b_types.get(type_name, [])
            new_vals = u_types.get(type_name, [])
            if old_vals == new_vals:
                continue

            if not old_vals and new_vals:
                change_type = "activity_code_added"
            elif old_vals and not new_vals:
                change_type = "activity_code_removed"
            else:
                change_type = "activity_code_changed"

            changes.append(_change_row(
                change_type, "activity_code", code, field_changed=type_name,
                old_value=old_vals, new_value=new_vals,
                narrative_hint=(
                    f"Activity code '{type_name}' changed from "
                    f"{', '.join(old_vals) or '(none)'} to {', '.join(new_vals) or '(none)'} for {code}."
                ),
            ))
    return changes


def diff_snapshots(baseline: Dict, update: Dict) -> List[Dict]:
    """Pure diff between two already-loaded version dicts (as returned by
    XERDataStore.get_version/get_baseline) — no DB access, no project/
    snapshot id resolution. Returns a list of DS8-shaped row dicts (missing
    only project_id/from_snapshot_id/to_snapshot_id, which the caller
    stamps on since those depend on how the pair was resolved)."""
    base_task_df = baseline.get("df", {}).get("task")
    upd_task_df = update.get("df", {}).get("task")
    base_pred_df = baseline.get("df", {}).get("taskpred")
    upd_pred_df = update.get("df", {}).get("taskpred")
    base_cal_df = baseline.get("df", {}).get("calendar")
    upd_cal_df = update.get("df", {}).get("calendar")

    # A single conversion factor for both sides (display only — see
    # _diff_activities) rather than each version's own hours_per_day, which
    # is auto-picked from "whichever calendar comes first" and can differ
    # between exports even when nothing schedule-relevant changed.
    hpd = update.get("hours_per_day") or baseline.get("hours_per_day") or 8.0

    base_id_to_code = (
        base_task_df.set_index("task_id")["task_code"].to_dict()
        if base_task_df is not None and not base_task_df.empty else {}
    )
    upd_id_to_code = (
        upd_task_df.set_index("task_id")["task_code"].to_dict()
        if upd_task_df is not None and not upd_task_df.empty else {}
    )

    base_cal_map = _build_calendar_map(base_cal_df)
    upd_cal_map = _build_calendar_map(upd_cal_df)

    base_activity_map = _build_activity_map(base_task_df, base_cal_map)
    upd_activity_map = _build_activity_map(upd_task_df, upd_cal_map)
    base_rel_map = _build_relationship_map(base_pred_df, base_id_to_code)
    upd_rel_map = _build_relationship_map(upd_pred_df, upd_id_to_code)
    base_actv_code_map = _build_activity_code_map(baseline.get("data", {}).get("tables", {}), base_id_to_code)
    upd_actv_code_map = _build_activity_code_map(update.get("data", {}).get("tables", {}), upd_id_to_code)

    rows = _diff_activities(base_activity_map, upd_activity_map, hpd)
    rows += _diff_relationships(base_rel_map, upd_rel_map, hpd)
    rows += _diff_activity_codes(base_actv_code_map, upd_actv_code_map)
    return rows


def write_changes_for_version(data_store, version_id: str, context: str, file_type: str) -> Dict[str, int]:
    """Computes and persists DS8 changes for a single just-uploaded `update`
    version, diffed against its validated paired baseline (same B-040 gate
    DS7's M2/variance findings use — nothing to diff without a valid pair).
    Idempotent: deletes any prior rows for this exact snapshot pair before
    writing, so re-running (e.g. a re-upload) doesn't duplicate rows."""
    if file_type != "update":
        return {"changes_written": 0}

    baseline = data_store.get_baseline(context=context)
    if not baseline:
        return {"changes_written": 0}

    update = data_store.get_version(version_id, context=context)
    if not update:
        return {"changes_written": 0}

    project_id, to_snapshot_id = project_identity(update, data_store=data_store, context=context)
    from_snapshot_id = baseline["id"]

    rows = diff_snapshots(baseline, update)

    db.delete_changes_for_pair(project_id, from_snapshot_id, to_snapshot_id)
    for row in rows:
        row["project_id"] = project_id
        row["from_snapshot_id"] = from_snapshot_id
        row["to_snapshot_id"] = to_snapshot_id
        db.insert_change(row)

    return {"changes_written": len(rows)}
