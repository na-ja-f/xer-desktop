"""
DS7 forensic findings orchestration (B-045).

Nine checks that interpret DS8 `changes` rows (B-044) — plus a couple of
fields DS8 deliberately doesn't track (actual dates, float; see changes.py's
own docstring for why) read directly off the pristine baseline/update
dataframes here instead — to flag schedule-manipulation patterns: baseline
dates modified on already-started work, logic changed on critical/
near-critical activities, constraints added instead of fixing logic,
duration compressed on remaining work, calendar swapped to gain working
days, actuals changed retroactively, float manipulation, deleted activities
that were behind schedule, and added activities landing on the critical
path.

Each check writes one aggregate finding row (finding_category="forensic",
check_source="forensic") — same shape as the DCMA-14 / M2 variance findings
in findings.py: a "0 flagged" result is a pass row, not an omitted one.

Deliberately does not touch changes.py/DS8's schema — that engine was
verified against real data before this ticket started (B-044) and stays
untouched here; only a few of its small generic helpers are reused.

Called once per upload, right after write_changes_for_version (DS8 rows for
this snapshot pair must already exist) — see main.py's /upload-xer.
"""
from typing import Dict, List

import pandas as pd

from . import db
from .changes import _blank, _date
from .findings import project_identity

# Placeholder pending planner sign-off — no near-critical float band exists
# anywhere else in the codebase (only an unimplemented docstring mention in
# activity_resolver.py). DCMA Check 6 uses 44 days for "high float" (the
# opposite direction); this is a much tighter band meant to catch activities
# close enough to critical that a logic change could push them onto it.
NEAR_CRITICAL_FLOAT_DAYS = 10  # PLACEHOLDER — adjust with planner

# Placeholder pending planner sign-off — magnitude of float growth treated
# as a standalone "float manipulation" signal.
FLOAT_MANIPULATION_THRESHOLD_DAYS = 10  # PLACEHOLDER — adjust with planner

_MANDATORY_CONSTRAINT_TYPES = {"CS_MSO", "CS_MFO", "CS_MEOB", "CS_MEO"}


def _finding(check_id: str, check_name: str, affected_ids: List[str], narrative: str, severity_fail: bool) -> Dict:
    ids = list(affected_ids)
    return {
        "finding_category": "forensic",
        "check_id": check_id,
        "check_name": check_name,
        "check_source": "forensic",
        "severity": "fail" if severity_fail else "pass",
        "value_numeric": len(ids),
        "unit": "count",
        "threshold_json": {"fail_if": "> 0"},
        "activities_affected_count": len(ids),
        "activities_affected_ids": ids[:100],
        "attribution_json": {},
        "narrative_hint": narrative,
    }


def _build_field_map(task_df, fields) -> Dict[str, Dict]:
    """task_code -> {requested raw fields}, for one version's pristine TASK table."""
    if task_df is None or task_df.empty or "task_code" not in task_df.columns:
        return {}
    present = [f for f in fields if f in task_df.columns]
    result = {}
    for _, row in task_df.iterrows():
        code = row.get("task_code")
        if _blank(code):
            continue
        result[code] = {f: row.get(f) for f in present}
    return result


def _build_calendar_hours_map(calendar_df) -> Dict[str, float]:
    """clndr_name -> week_hr_cnt for one version's pristine CALENDAR table."""
    if calendar_df is None or calendar_df.empty:
        return {}
    if "clndr_name" not in calendar_df.columns or "week_hr_cnt" not in calendar_df.columns:
        return {}
    out = {}
    for _, row in calendar_df.iterrows():
        name = row.get("clndr_name")
        if _blank(name):
            continue
        hrs = pd.to_numeric(row.get("week_hr_cnt"), errors="coerce")
        if pd.notna(hrs):
            out[name] = float(hrs)
    return out


def _is_progressed(fields: Dict) -> bool:
    """Mirrors main.py's upload-time progress heuristic: has an actual start,
    or its status says it's active/complete."""
    has_actual_start = not _blank(fields.get("act_start_date"))
    status = str(fields.get("status_code") or "")
    return has_actual_start or status in ("TK_Active", "TK_Complete")


def _check_baseline_dates_modified(ds8_rows: List[Dict], baseline_fields: Dict) -> Dict:
    flagged = set()
    for row in ds8_rows:
        if row["change_type"] not in ("start_date_changed", "finish_date_changed"):
            continue
        code = row["entity_id"]
        fields = baseline_fields.get(code)
        if fields and _is_progressed(fields):
            flagged.add(code)
    ids = sorted(flagged)
    narrative = (
        f"{len(ids)} activities had their planned dates changed after already starting or completing "
        "in the baseline — target dates on progressed work shouldn't move."
        if ids else
        "No planned-date changes found on activities that had already started or completed in the baseline."
    )
    return _finding("forensic-baseline-dates-modified", "Baseline Dates Modified On Progressed Work",
                     ids, narrative, severity_fail=bool(ids))


def _check_logic_on_critical(ds8_rows: List[Dict], update_by_code: Dict, hpd: float) -> Dict:
    def is_crit_or_near(code: str) -> bool:
        a = update_by_code.get(code)
        if not a:
            return False
        if a.get("is_critical_p6"):
            return True
        fh = a.get("float_hrs")
        if fh is None:
            return False
        days = fh / hpd
        return 0 < days <= NEAR_CRITICAL_FLOAT_DAYS

    flagged = set()
    for row in ds8_rows:
        if row["change_type"] not in ("logic_removed", "logic_modified"):
            continue
        pred_code, _, succ_code = row["entity_id"].partition("::")
        if is_crit_or_near(pred_code) or is_crit_or_near(succ_code):
            flagged.add(row["entity_id"])
    ids = sorted(flagged)
    narrative = (
        f"{len(ids)} relationship changes (removed or modified) touch an activity that is critical or "
        f"within {NEAR_CRITICAL_FLOAT_DAYS} days of critical — verify these weren't used to relieve pressure."
        if ids else
        "No logic changes found on critical or near-critical activities."
    )
    return _finding("forensic-logic-on-critical", "Logic Changed On Critical Or Near-Critical Activities",
                     ids, narrative, severity_fail=bool(ids))


def _check_constraints_forcing_dates(ds8_rows: List[Dict]) -> Dict:
    flagged = set()
    mandatory = set()
    for row in ds8_rows:
        if row["change_type"] != "constraint_added":
            continue
        flagged.add(row["entity_id"])
        new_val = row.get("new_value") or {}
        if new_val.get("cstr_type") in _MANDATORY_CONSTRAINT_TYPES:
            mandatory.add(row["entity_id"])
    ids = sorted(flagged)
    if ids:
        extra = f" ({len(mandatory)} using a mandatory constraint type)" if mandatory else ""
        narrative = f"{len(ids)} activities had a new constraint added instead of fixing the driving logic{extra}."
    else:
        narrative = "No new constraints were added in this update."
    return _finding("forensic-constraints-forcing-dates", "Constraints Added Instead Of Fixing Logic",
                     ids, narrative, severity_fail=bool(ids))


def _check_duration_compression(ds8_rows: List[Dict], update_by_code: Dict) -> Dict:
    flagged = set()
    for row in ds8_rows:
        if row["change_type"] != "duration_shortened":
            continue
        code = row["entity_id"]
        a = update_by_code.get(code)
        if a and a.get("status_enum") != "COMPLETED":
            flagged.add(code)
    ids = sorted(flagged)
    narrative = (
        f"{len(ids)} not-yet-complete activities had their duration shortened — verify this reflects real "
        "re-estimation and isn't compressing remaining work to mask delay."
        if ids else
        "No duration compression found on remaining (not-yet-complete) work."
    )
    return _finding("forensic-duration-compression", "Duration Compression On Remaining Work",
                     ids, narrative, severity_fail=bool(ids))


def _check_calendar_swap(ds8_rows: List[Dict], baseline_cal_hours: Dict, update_cal_hours: Dict) -> Dict:
    flagged = set()
    for row in ds8_rows:
        if row["change_type"] != "calendar_changed":
            continue
        old_hrs = baseline_cal_hours.get(row.get("old_value"))
        new_hrs = update_cal_hours.get(row.get("new_value"))
        if old_hrs is not None and new_hrs is not None and new_hrs > old_hrs:
            flagged.add(row["entity_id"])
    ids = sorted(flagged)
    narrative = (
        f"{len(ids)} activities were swapped to a calendar with more weekly working hours than before."
        if ids else
        "No calendar swaps that increased weekly working hours were found."
    )
    return _finding("forensic-calendar-swap", "Calendar Swapped To Gain Working Days",
                     ids, narrative, severity_fail=bool(ids))


def _check_retroactive_actuals(baseline_fields: Dict, update_fields: Dict) -> Dict:
    flagged = set()
    for code in set(baseline_fields) & set(update_fields):
        b, u = baseline_fields[code], update_fields[code]
        for field in ("act_start_date", "act_end_date"):
            bv, uv = _date(b.get(field)), _date(u.get(field))
            if bv is not None and uv is not None and bv != uv:
                flagged.add(code)
                break
    ids = sorted(flagged)
    narrative = (
        f"{len(ids)} activities have an actual start/finish date that differs from the baseline's "
        "already-recorded value — actual dates shouldn't change once recorded."
        if ids else
        "No already-recorded actual dates changed between snapshots."
    )
    return _finding("forensic-retroactive-actuals", "Actuals Changed Retroactively",
                     ids, narrative, severity_fail=bool(ids))


def _check_float_manipulation(baseline_fields: Dict, update_by_code: Dict, hpd: float) -> Dict:
    flagged = set()
    for code, b in baseline_fields.items():
        old_hrs = pd.to_numeric(b.get("total_float_hr_cnt"), errors="coerce")
        if pd.isna(old_hrs):
            continue
        a = update_by_code.get(code)
        new_hrs = a.get("float_hrs") if a else None
        if new_hrs is None:
            continue
        old_days = float(old_hrs) / hpd
        new_days = float(new_hrs) / hpd
        if (new_days - old_days) > FLOAT_MANIPULATION_THRESHOLD_DAYS:
            flagged.add(code)
    ids = sorted(flagged)
    narrative = (
        f"{len(ids)} activities gained more than {FLOAT_MANIPULATION_THRESHOLD_DAYS} days of float between "
        "snapshots — verify the gain traces to a legitimate cause."
        if ids else
        f"No activities gained more than {FLOAT_MANIPULATION_THRESHOLD_DAYS} days of float between snapshots."
    )
    return _finding("forensic-float-manipulation", "Float Manipulation Pattern",
                     ids, narrative, severity_fail=bool(ids))


def _check_deleted_behind_schedule(ds8_rows: List[Dict], baseline_fields: Dict) -> Dict:
    flagged = set()
    for row in ds8_rows:
        if row["change_type"] != "activity_deleted":
            continue
        code = row["entity_id"]
        fields = baseline_fields.get(code)
        if not fields:
            continue
        tf = pd.to_numeric(fields.get("total_float_hr_cnt"), errors="coerce")
        was_critical = pd.notna(tf) and tf <= 0
        was_in_progress = not _blank(fields.get("act_start_date")) and _blank(fields.get("act_end_date"))
        if was_critical or was_in_progress:
            flagged.add(code)
    ids = sorted(flagged)
    narrative = (
        f"{len(ids)} deleted activities were already critical or in-progress in the baseline."
        if ids else
        "No deleted activities were behind schedule (critical or in-progress) in the baseline."
    )
    return _finding("forensic-deleted-behind-schedule", "Deleted Activities That Were Behind Schedule",
                     ids, narrative, severity_fail=bool(ids))


def _check_added_resequence_critical(ds8_rows: List[Dict], update_by_code: Dict) -> Dict:
    flagged = set()
    for row in ds8_rows:
        if row["change_type"] != "activity_added":
            continue
        code = row["entity_id"]
        a = update_by_code.get(code)
        if a and a.get("is_critical_p6"):
            flagged.add(code)
    ids = sorted(flagged)
    narrative = (
        f"{len(ids)} newly added activities are already on the critical path in this update."
        if ids else
        "No newly added activities landed on the critical path."
    )
    return _finding("forensic-added-resequence-critical", "Added Activities That Resequence The Critical Path",
                     ids, narrative, severity_fail=bool(ids))


def build_forensic_findings(data_store, baseline: Dict, update: Dict, project_id: str,
                             from_snapshot_id: str, to_snapshot_id: str, context: str) -> List[Dict]:
    """Runs all 9 forensic checks for one baseline/update pair. Pure aside
    from the two read calls (DS8 rows, deterministic analysis) — no writes."""
    ds8_rows = db.list_changes_for_pair(project_id, from_snapshot_id, to_snapshot_id)

    analysis = data_store.get_deterministic_analysis(version_id=to_snapshot_id, context=context) or {}
    update_by_code = {
        a["task_code"]: a
        for a in (analysis.get("activityAnalysis") or {}).values()
        if a.get("task_code")
    }

    baseline_task_df = baseline.get("df", {}).get("task")
    update_task_df = update.get("df", {}).get("task")
    baseline_cal_df = baseline.get("df", {}).get("calendar")
    update_cal_df = update.get("df", {}).get("calendar")

    baseline_fields = _build_field_map(
        baseline_task_df, ["act_start_date", "act_end_date", "status_code", "total_float_hr_cnt"]
    )
    update_fields = _build_field_map(update_task_df, ["act_start_date", "act_end_date"])

    baseline_cal_hours = _build_calendar_hours_map(baseline_cal_df)
    update_cal_hours = _build_calendar_hours_map(update_cal_df)

    hpd = update.get("hours_per_day") or baseline.get("hours_per_day") or 8.0

    return [
        _check_baseline_dates_modified(ds8_rows, baseline_fields),
        _check_logic_on_critical(ds8_rows, update_by_code, hpd),
        _check_constraints_forcing_dates(ds8_rows),
        _check_duration_compression(ds8_rows, update_by_code),
        _check_calendar_swap(ds8_rows, baseline_cal_hours, update_cal_hours),
        _check_retroactive_actuals(baseline_fields, update_fields),
        _check_float_manipulation(baseline_fields, update_by_code, hpd),
        _check_deleted_behind_schedule(ds8_rows, baseline_fields),
        _check_added_resequence_critical(ds8_rows, update_by_code),
    ]


def write_forensic_findings_for_version(data_store, version_id: str, context: str, file_type: str) -> Dict[str, int]:
    """Computes and persists the 9 DS7 forensic findings for a single
    just-uploaded `update` version. Same gate as write_changes_for_version
    (nothing to check without a valid baseline pair), and must run after it
    — reads back the DS8 rows it just wrote."""
    if file_type != "update":
        return {"forensic_written": 0}

    baseline = data_store.get_baseline(context=context)
    if not baseline:
        return {"forensic_written": 0}

    update = data_store.get_version(version_id, context=context)
    if not update:
        return {"forensic_written": 0}

    project_id, to_snapshot_id = project_identity(update, data_store=data_store, context=context)
    from_snapshot_id = baseline["id"]

    findings = build_forensic_findings(
        data_store, baseline, update, project_id, from_snapshot_id, to_snapshot_id, context
    )

    for finding in findings:
        finding["project_id"] = project_id
        finding["snapshot_id"] = to_snapshot_id
        db.insert_finding(finding)

    return {
        "forensic_written": len(findings),
        "flagged_checks": sum(1 for f in findings if f["severity"] == "fail"),
    }
