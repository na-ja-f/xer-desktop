"""
DS7 findings orchestration (B-014).

Maps the existing M1 (DCMA-14 audit) and M2 (schedule variance/delay/at-risk/
critical-path) analysis already computed by XERDataStore.get_deterministic_analysis
into DS7 `findings` rows and persists them via modules.db.insert_finding.

Called once per upload (see main.py's /upload-xer), not on every read —
get_deterministic_analysis is re-run on every /health or /ask call and would
otherwise produce duplicate finding rows per read.
"""
from typing import Dict, List, Optional, Tuple

from . import db

# Machine-readable pass/fail cutoffs for the 14 DCMA points, mirroring the
# inline constants in XERDataStore.get_deterministic_analysis (data_store.py).
# Not new business rules — just a structured restatement of the same cutoffs.
_DCMA_THRESHOLDS = {
    1: {"fail_if": "> 5%"},
    2: {"fail_if": "> 0%"},
    3: {"fail_if": "> 5%"},
    4: {"fail_if": "< 90%"},
    5: {"fail_if": "> 5%"},
    6: {"fail_if": "> 5%"},
    7: {"fail_if": "> 0%"},
    8: {"fail_if": "> 5%"},
    9: {"fail_if": "> 0%"},
    10: {"fail_if": "< 100%"},
    11: {"fail_if": "> 5%"},
    12: {"fail_if": "no critical path"},
    13: {"fail_if": "< 0.95"},
    14: {"fail_if": "no baseline assigned"},
}

_DCMA_UNITS = {13: "ratio"}


def project_identity(version: Dict, data_store=None, context: str = "audit") -> Tuple[str, str]:
    """Resolves the DS7 project_id/snapshot_id for a version.

    A baseline starts a new trend "root" (its own version id is the
    project_id). An update inherits its project_id from its validated paired
    baseline (data_store.get_baseline, the existing B-040 activity-overlap
    check) so DCMA history accumulates as one continuous trend across a
    baseline and its updates, regardless of proj_short_name differences
    between them. Falls back to proj_short_name/name when there's no
    data_store or no validated pairing, so an orphaned/unrelated update still
    gets tracked (just not merged into a baseline's trend it doesn't match).
    """
    snapshot_id = version["id"]

    if version.get("type") == "update" and data_store is not None:
        baseline = data_store.get_baseline(context=context)
        if baseline:
            return baseline["id"], snapshot_id

    if version.get("type") == "baseline":
        return version["id"], snapshot_id

    return version.get("proj_short_name") or version.get("name") or "unknown", snapshot_id


def build_m1_findings(analysis: Dict, project_id: str, snapshot_id: str) -> List[Dict]:
    """Maps the 14-point DCMA `assessment` list into DS7 finding rows.

    Severity is a simple pass/fail derived from the existing boolean `status` —
    the raw DCMA computation has no 3-tier warning band, so none is invented here.
    """
    assessment = analysis.get("projectSummary", {}).get("assessment", [])
    findings = []
    for point in assessment:
        check_id = point["id"]
        status = bool(point.get("status"))
        val = point.get("val")
        explanation = point.get("explanation") or point.get("measure", "")
        narrative = f"{val:.1f}% — {explanation}" if isinstance(val, (int, float)) else explanation

        findings.append({
            "project_id": project_id,
            "snapshot_id": snapshot_id,
            "finding_category": "audit",
            "check_id": f"dcma-{check_id}",
            "check_name": point["name"],
            "check_source": "dcma",
            "severity": "pass" if status else "fail",
            "value_numeric": float(val) if isinstance(val, (int, float)) else None,
            "unit": _DCMA_UNITS.get(check_id, "percent"),
            "threshold_json": _DCMA_THRESHOLDS.get(check_id, {}),
            "activities_affected_count": point.get("affected_count"),
            "activities_affected_ids": point.get("affected_ids") or [],
            "attribution_json": {},
            "narrative_hint": narrative,
        })
    return findings


def _variance_finding(check_id, check_name, count, affected_ids, value_numeric, unit, threshold_json, narrative, severity_fail):
    return {
        "finding_category": "variance",
        "check_id": check_id,
        "check_name": check_name,
        "check_source": "schedule_variance",
        "severity": "fail" if severity_fail else "pass",
        "value_numeric": value_numeric,
        "unit": unit,
        "threshold_json": threshold_json,
        "activities_affected_count": count,
        "activities_affected_ids": affected_ids,
        "attribution_json": {},
        "narrative_hint": narrative,
    }


def build_m2_findings(analysis: Dict, project_id: str, snapshot_id: str, dependency_graph: Optional[Dict] = None) -> List[Dict]:
    """Derives one aggregate finding row per check type (delayed, at-risk,
    negative-float, critical-path-continuity, project-delay) from
    `activityAnalysis` + `projectSummary` — not one row per activity."""
    from .scheduler_metrics import SchedulerMetrics

    acts = analysis.get("activityAnalysis", {})
    summary = analysis.get("projectSummary", {})

    def ids_where(pred):
        return [a.get("task_code") for a in acts.values() if pred(a)]

    findings = []

    delayed = [a for a in acts.values() if a.get("classification") == "DELAYED"]
    delayed_ids = [a.get("task_code") for a in delayed]
    max_delay = max((a.get("delay_days") or 0 for a in delayed), default=0)
    findings.append(_variance_finding(
        "variance-delayed-activities", "Delayed Activities", len(delayed_ids), delayed_ids,
        len(delayed_ids), "count", {"fail_if": "> 0"},
        f"{len(delayed_ids)} activities delayed vs baseline, max {max_delay} days",
        severity_fail=len(delayed_ids) > 0,
    ))

    at_risk_ids = ids_where(lambda a: a.get("classification") == "AT_RISK")
    findings.append(_variance_finding(
        "variance-at-risk-activities", "At-Risk Activities", len(at_risk_ids), at_risk_ids,
        len(at_risk_ids), "count", {"fail_if": "> 0"},
        f"{len(at_risk_ids)} activities forecast to miss baseline dates (float consumption > 75%)",
        severity_fail=len(at_risk_ids) > 0,
    ))

    neg_float_ids = ids_where(lambda a: (a.get("float_hrs") or 0) < 0)
    findings.append(_variance_finding(
        "variance-negative-float", "Negative Float Activities", len(neg_float_ids), neg_float_ids,
        len(neg_float_ids), "count", {"fail_if": "> 0"},
        f"{len(neg_float_ids)} activities have negative total float",
        severity_fail=len(neg_float_ids) > 0,
    ))

    metrics = SchedulerMetrics.compute_core_metrics(acts, dependency_graph or {})
    continuity = SchedulerMetrics.evaluate_critical_path_continuity(metrics)
    continuity_status = continuity.get("continuity_status", "FAIL")
    critical_ids = [a.get("task_code") for a in metrics.get("critical_activities", [])]
    findings.append(_variance_finding(
        "variance-critical-path-continuity", "Critical Path Continuity", metrics.get("critical_count", 0), critical_ids,
        metrics.get("critical_count", 0), "count", {"fail_if": "discontinuous"},
        continuity.get("reason") or f"Critical path continuity: {continuity_status}",
        severity_fail=(continuity_status != "PASS"),
    ))

    project_delay_days = summary.get("projectDelayDays")
    findings.append(_variance_finding(
        "variance-project-delay", "Project Delay", None, [],
        project_delay_days, "days", {"fail_if": "> 0"},
        f"Project finish is {project_delay_days} days behind baseline" if project_delay_days else "Project finish is on or ahead of baseline",
        severity_fail=bool(project_delay_days and project_delay_days > 0),
    ))

    for finding in findings:
        finding["project_id"] = project_id
        finding["snapshot_id"] = snapshot_id

    return findings


def write_findings_for_version(data_store, version_id: str, context: str, file_type: str) -> Dict[str, int]:
    """Computes and persists DS7 findings for a single just-uploaded schedule
    version. M1 (audit) always runs; M2 (variance) only runs for an `update`
    with a validly-paired baseline (same B-040 rule the /ask tools use)."""
    version = data_store.get_version(version_id, context=context)
    if not version:
        return {"m1_written": 0, "m2_written": 0}

    project_id, snapshot_id = project_identity(version, data_store=data_store, context=context)
    analysis = data_store.get_deterministic_analysis(version_id=version_id, context=context)
    if not analysis:
        return {"m1_written": 0, "m2_written": 0}

    m1_written = 0
    for finding in build_m1_findings(analysis, project_id, snapshot_id):
        db.insert_finding(finding)
        m1_written += 1

    m2_written = 0
    if file_type == "update" and data_store.get_baseline(context=context):
        dependency_graph = version.get("dependency_graph", {})
        for finding in build_m2_findings(analysis, project_id, snapshot_id, dependency_graph):
            db.insert_finding(finding)
            m2_written += 1

    return {"m1_written": m1_written, "m2_written": m2_written}
