"""
Resource Engine — Primavera P6 XER Resource Management Module
Parses RSRC, TASKRSRC, TASK, PROJWBS tables for full resource visibility.
"""
import logging
from typing import Dict, List, Optional, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class ResourceEngine:
    """
    Extracts and computes all resource-level data from parsed XER data.
    Used as a Single Source of Truth for resource metrics and assignments.
    """

    def __init__(self, data_store):
        self.data_store = data_store

    def _get_source(self, context: str = "audit") -> Optional[Dict]:
        return self.data_store.get_latest(context=context)

    def _get_df(self, source: Dict, table: str):
        """Safely retrieve a DataFrame from the source version."""
        return source.get("df", {}).get(table.lower())

    # ─────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────────

    def get_resource_summary(self, context: str = "audit") -> Dict:
        """
        Returns total, assigned, and unassigned resource counts.
        """
        source = self._get_source(context)
        if not source:
            return {"success": False, "error": "No schedule data loaded."}

        rsrc_df = self._get_df(source, "rsrc")
        taskrsrc_df = self._get_df(source, "taskrsrc")

        total_resources = len(rsrc_df) if rsrc_df is not None else 0

        if taskrsrc_df is not None and rsrc_df is not None and total_resources > 0:
            assigned_ids = set(taskrsrc_df["rsrc_id"].dropna().astype(str).tolist())
            all_ids = set(rsrc_df["rsrc_id"].dropna().astype(str).tolist())
            assigned_count = len(assigned_ids & all_ids)
            unassigned_count = total_resources - assigned_count
        else:
            assigned_count = 0
            unassigned_count = total_resources

        summary = {
            "total_resources": total_resources,
            "assigned_resources": assigned_count,
            "unassigned_resources": unassigned_count,
        }

        return {
            "success": True,
            "total_count": 1,
            "displayed_count": 1,
            "data": [summary],
            "display_items": [summary],
            "all_items": [summary],
            "stats": summary,
            "template_type": "resource_summary",
        }

    def get_resource_assignments(
        self, limit: int = 500, context: str = "audit", activity_filter: str = ""
    ) -> Dict:
        """
        Returns activity-level resource assignments with WBS, role, units, and dates.
        If activity_filter is provided, only returns resources for matching activities.
        """
        source = self._get_source(context)
        if not source:
            return {"success": False, "error": "No schedule data loaded."}

        taskrsrc_df = self._get_df(source, "taskrsrc")
        rsrc_df     = self._get_df(source, "rsrc")
        tasks_df    = self._get_df(source, "tasks")
        wbs_df      = self._get_df(source, "projwbs")

        if taskrsrc_df is None or taskrsrc_df.empty:
            return {
                "success": True,
                "total_count": 0,
                "displayed_count": 0,
                "data": [],
                "display_items": [],
                "all_items": [],
                "stats": {"total_assignments": 0},
                "template_type": "resource_assignments",
            }

        # Build resource lookup: rsrc_id -> {name, role}
        rsrc_map: Dict[str, Dict] = {}
        if rsrc_df is not None:
            for _, r in rsrc_df.iterrows():
                rid = str(r.get("rsrc_id", ""))
                rsrc_map[rid] = {
                    "name": r.get("rsrc_name") or r.get("rsrc_short_name", ""),
                    "role": r.get("rsrc_type", "Labor"),
                }

        # Build WBS lookup: wbs_id -> wbs_name
        wbs_map: Dict[str, str] = {}
        if wbs_df is not None:
            for _, w in wbs_df.iterrows():
                wid = str(w.get("wbs_id", ""))
                wbs_map[wid] = w.get("wbs_name", "") or w.get("wbs_short_name", "")

        # Build task lookup: task_id -> {name, wbs_id}
        task_map: Dict[str, Dict] = {}
        if tasks_df is not None:
            for _, t in tasks_df.iterrows():
                tid = str(t.get("task_id", ""))
                wid = str(t.get("wbs_id", ""))
                task_map[tid] = {
                    "name": t.get("task_name", ""),
                    "wbs_id": wid,
                    "wbs_name": wbs_map.get(wid, ""),
                }

        assignments = []
        for _, row in taskrsrc_df.iterrows():
            rid = str(row.get("rsrc_id", ""))
            tid = str(row.get("task_id", ""))
            rsrc_info = rsrc_map.get(rid, {})
            task_info = task_map.get(tid, {})

            # Units — try multiple field names P6 uses
            units_raw = (
                row.get("target_qty")
                or row.get("remain_qty")
                or row.get("act_reg_qty")
                or 0
            )
            try:
                units = round(float(units_raw), 2)
            except (TypeError, ValueError):
                units = 0.0

            start  = str(row.get("target_start_date") or row.get("act_start_date") or "")[:10]
            finish = str(row.get("target_end_date")   or row.get("act_end_date")   or "")[:10]

            assignments.append({
                "activity_id":   tid,
                "activity_name": task_info.get("name", tid),
                "wbs_name":      task_info.get("wbs_name", ""),
                "resource_name": rsrc_info.get("name", rid),
                "role":          rsrc_info.get("role", "Labor"),
                "units":         units,
                "start":         start,
                "finish":        finish,
            })

        # Filter by activity name if requested
        if activity_filter and activity_filter.strip():
            filter_lower = activity_filter.strip().lower()
            # Try exact code match first, then name substring
            filtered = [a for a in assignments if filter_lower == a["activity_name"].lower() 
                        or filter_lower in a["activity_name"].lower()
                        or filter_lower == a.get("activity_id", "").lower()]
            if not filtered:
                # Fuzzy fallback
                import difflib
                names = list({a["activity_name"] for a in assignments})
                close = difflib.get_close_matches(activity_filter, names, n=3, cutoff=0.5)
                if close:
                    filtered = [a for a in assignments if a["activity_name"] in close]
            if filtered:
                assignments = filtered

        # Sort: resource → wbs → activity
        assignments.sort(key=lambda x: (x["resource_name"], x["wbs_name"], x["activity_name"]))
        preview = assignments[:limit]

        # Build unique filter lists
        unique_resources = sorted({a["resource_name"] for a in assignments if a["resource_name"]})
        unique_wbs       = sorted({a["wbs_name"]      for a in assignments if a["wbs_name"]})

        return {
            "success": True,
            "total_count": len(assignments),
            "displayed_count": len(preview),
            "is_truncated": len(assignments) > limit,
            "data": preview,
            "display_items": preview,
            "all_items": assignments,
            "stats": {
                "total_assignments": len(assignments),
                "unique_resources": unique_resources,
                "unique_wbs": unique_wbs,
            },
            "template_type": "resource_assignments",
        }

    def get_resource_load(self, context: str = "audit") -> Dict:
        """
        Returns time-phased resource loading grouped by resource and period.
        Approximates from assignment date ranges.
        """
        source = self._get_source(context)
        if not source:
            return {"success": False, "error": "No schedule data loaded."}

        taskrsrc_df = self._get_df(source, "taskrsrc")
        rsrc_df = self._get_df(source, "rsrc")

        if taskrsrc_df is None or taskrsrc_df.empty:
            return {
                "success": True,
                "total_count": 0,
                "displayed_count": 0,
                "data": [],
                "display_items": [],
                "all_items": [],
                "stats": {"total_load_records": 0},
                "template_type": "resource_load",
            }

        rsrc_map: Dict[str, str] = {}
        if rsrc_df is not None:
            for _, r in rsrc_df.iterrows():
                rid = str(r.get("rsrc_id", ""))
                rsrc_map[rid] = r.get("rsrc_name") or r.get("rsrc_short_name", rid)

        # Group by resource, derive monthly load from target_qty and date range
        load_by_resource: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for _, row in taskrsrc_df.iterrows():
            rid = str(row.get("rsrc_id", ""))
            rsrc_name = rsrc_map.get(rid, rid)

            try:
                units_raw = float(
                    row.get("target_qty") or row.get("remain_qty") or 0
                )
            except (TypeError, ValueError):
                units_raw = 0.0

            start_str = str(row.get("target_start_date") or row.get("act_start_date") or "")[:10]
            finish_str = str(row.get("target_end_date") or row.get("act_end_date") or "")[:10]

            if start_str and finish_str and start_str != "nan" and finish_str != "nan":
                try:
                    from datetime import date, timedelta
                    import datetime as dt
                    s = dt.date.fromisoformat(start_str)
                    f = dt.date.fromisoformat(finish_str)
                    months = max(1, ((f.year - s.year) * 12 + f.month - s.month) + 1)
                    monthly_units = round(units_raw / months, 2)

                    current = s
                    for _ in range(months):
                        period = current.strftime("%Y-%m")
                        load_by_resource[rsrc_name][period] += monthly_units
                        # advance by 1 month
                        if current.month == 12:
                            current = current.replace(year=current.year + 1, month=1)
                        else:
                            current = current.replace(month=current.month + 1)
                except Exception:
                    pass

        load_records = []
        for rsrc_name, periods in load_by_resource.items():
            for period, units in sorted(periods.items()):
                load_records.append({
                    "resource_name": rsrc_name,
                    "date": period,
                    "units": round(units, 2),
                })

        return {
            "success": True,
            "total_count": len(load_records),
            "displayed_count": len(load_records),
            "data": load_records,
            "display_items": load_records,
            "all_items": load_records,
            "stats": {
                "total_load_records": len(load_records),
                "unique_resources": len(load_by_resource),
            },
            "template_type": "resource_load",
        }
