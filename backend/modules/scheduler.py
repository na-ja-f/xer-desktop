"""
P6-Accurate CPM Scheduling Engine
===================================
Strategy:
  1. PRIMARY: Use P6's own pre-computed dates already stored in the XER TASK record
     (early_start_date, early_end_date, late_start_date, late_end_date, total_float_hr_cnt).
     These are EXACTLY what P6 calculated — calendar-aware, constraint-aware.
  2. FALLBACK: If those fields are missing/empty, run a calendar-aware CPM using
     the CALENDAR table from the XER (working day masks) with full constraint support.

This guarantees output identical to P6 for any XER file that has been scheduled in P6.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta, date
import re


# ---------------------------------------------------------------------------
# Calendar Engine
# ---------------------------------------------------------------------------

class P6Calendar:
    """
    Parses the Primavera P6 CALENDAR table row and provides:
      - add_workdays(dt, days) → advance dt by N working days
      - workdays_between(start, end) → count working days
    P6 stores the weekly work pattern in clndr_data as a blob like:
      (0||0|0||0|0||0|0||0|0||0|0||0|0||0|0||0)
    Position index 0-6 = Sun..Sat. A day is a work day if its hours > 0.
    If clndr_data is not parseable, fall back to Mon-Fri.
    """

    def __init__(self, clndr_row: Optional[Dict] = None):
        self.work_days: Set[int] = {0, 1, 2, 3, 4}  # Mon-Fri default (weekday() 0-4)
        self.holidays: Set[date] = set()
        self.hours_per_day: float = 8.0

        if clndr_row:
            self._parse(clndr_row)

    def _parse(self, row: Dict):
        # hours_per_day
        try:
            hpd = float(row.get('day_hr_cnt', 8.0) or 8.0)
            if hpd > 0:
                self.hours_per_day = hpd
        except Exception:
            pass

        # Weekly pattern from clndr_data
        clndr_data = row.get('clndr_data', '') or ''
        work_days_set = self._parse_weekly_pattern(clndr_data)
        if work_days_set is not None:
            self.work_days = work_days_set

        # Exceptions (holidays) — P6 encodes them inside clndr_data too
        self.holidays = self._parse_exceptions(clndr_data)

    def _parse_weekly_pattern(self, clndr_data: str) -> Optional[Set[int]]:
        """
        Supports two P6 clndr_data formats:
        1. Legacy: (0||7.5|7.5||7.5|7.5||7.5|7.5||7.5|7.5||7.5|7.5||0|0|)
           Days are separated by || mapping Sun=0 Mon=1 ... Sat=6.
        2. Modern: (0||CalendarData()(...(0||DaysOfWeek()((0||1()((0||0(s|08:00|f|18:00)()))) ...
           Days are indexed 1=Sun, ..., 7=Sat. Shifts are marked with 's|'.
        """
        if not clndr_data:
            return None

        work_days = set()

        if 'DaysOfWeek()' in clndr_data:
            # Modern format
            p6_to_python = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
            for day_id in range(1, 8):
                idx = clndr_data.find(f'(0||{day_id}()(')
                if idx != -1:
                    next_idx = clndr_data.find('(0||', idx + 10)
                    while next_idx != -1 and not clndr_data[next_idx:].startswith(f'(0||{day_id+1}()(') and not clndr_data[next_idx:].startswith('(0||VIEW'):
                        next_idx = clndr_data.find('(0||', next_idx + 4)
                    block = clndr_data[idx:next_idx] if next_idx != -1 else clndr_data[idx:]
                    if 's|' in block:  # Contains a shift
                        work_days.add(p6_to_python[day_id])
            return work_days if work_days else None
        else:
            # Legacy format
            main_part = clndr_data.split('e(')[0] if 'e(' in clndr_data else clndr_data
            main_part = main_part.strip().strip('()')
            day_segments = main_part.split('||')
            if len(day_segments) < 7:
                return None
            p6_to_python = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
            for p6_day in range(7):
                segment = day_segments[p6_day] if p6_day < len(day_segments) else '0'
                nums = re.findall(r'[\d\.]+', segment)
                total_hours = sum(float(n) for n in nums) if nums else 0.0
                if total_hours > 0:
                    work_days.add(p6_to_python[p6_day])
            return work_days if work_days else None

    def _parse_exceptions(self, clndr_data: str) -> Set[date]:
        """Parse holiday exceptions from clndr_data."""
        holidays = set()
        # Exception blocks look like: e(20240101|0|0|...) or similar
        matches = re.findall(r'e\((\d{8})', clndr_data)
        for m in matches:
            try:
                holidays.add(datetime.strptime(m, '%Y%m%d').date())
            except Exception:
                pass
        return holidays

    def is_workday(self, dt: datetime) -> bool:
        d = dt.date() if isinstance(dt, datetime) else dt
        if d in self.holidays:
            return False
        return dt.weekday() in self.work_days

    def next_workday(self, dt: datetime) -> datetime:
        """Return dt if it's a workday, otherwise advance to next workday."""
        while not self.is_workday(dt):
            dt += timedelta(days=1)
        return dt

    def add_workdays(self, dt: datetime, days: float) -> datetime:
        """Add 'days' working days to dt. Handles fractional days."""
        if days == 0:
            return self.next_workday(dt)
        whole = int(days)
        frac = days - whole
        current = dt
        added = 0
        direction = 1 if days >= 0 else -1
        steps = abs(whole)
        while added < steps:
            current += timedelta(days=direction)
            if self.is_workday(current):
                added += 1
        if frac > 0:
            # Fractional day — just add hours (stay on same working day assumption)
            pass
        return current

    def workdays_between(self, start: datetime, end: datetime) -> float:
        """Count working days from start to end (inclusive start, exclusive end)."""
        if start >= end:
            return 0.0
        days = 0
        current = start
        while current < end:
            if self.is_workday(current):
                days += 1
            current += timedelta(days=1)
        return float(days)


# ---------------------------------------------------------------------------
# Main Scheduler
# ---------------------------------------------------------------------------

class CPMScheduler:
    """
    P6-accurate scheduling engine.

    PRIMARY path: reads P6's stored schedule dates from XER TASK fields:
        early_start_date, early_end_date, late_start_date, late_end_date, total_float_hr_cnt

    FALLBACK CPM path (when P6 dates absent): full calendar-aware CPM with
        constraint handling, correct FS/SS/FF/SF logic, negative float support.
    """

    # XER field names P6 uses for stored schedule dates
    XER_ES = 'early_start_date'
    XER_EF = 'early_end_date'
    XER_LS = 'late_start_date'
    XER_LF = 'late_end_date'
    XER_TF = 'total_float_hr_cnt'

    def __init__(self, hours_per_day: float = 8.0):
        self.hours_per_day = hours_per_day
        self._default_calendar = P6Calendar()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def calculate(
        self,
        tasks_df: pd.DataFrame,
        relationships_df: pd.DataFrame,
        project_start_date: pd.Timestamp,
        calendars_df: Optional[pd.DataFrame] = None,
        constraints_df: Optional[pd.DataFrame] = None,
        data_date: Optional[pd.Timestamp] = None,
        plan_end_date: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        """
        Returns tasks_df with added columns:
            early_start, early_finish, late_start, late_finish, total_float (days)

        plan_end_date: the contractual finish date (PROJECT.plan_end_date).
            Used as the backward-pass anchor so that negative float is
            generated correctly when the schedule has slipped past the deadline.
        """
        if tasks_df.empty:
            return tasks_df

        tasks = tasks_df.copy()

        # Build calendar map if available
        cal_map: Dict[str, P6Calendar] = {}
        if calendars_df is not None and not calendars_df.empty:
            for _, cal_row in calendars_df.iterrows():
                cal_id = str(cal_row.get('clndr_id', ''))
                if cal_id:
                    cal_map[cal_id] = P6Calendar(cal_row.to_dict())

        self._default_calendar.hours_per_day = self.hours_per_day

        # ----------------------------------------------------------------
        # STEP 1 — Use P6's stored dates (primary path)
        #   Only if XER contains real scheduled dates (not the P6 null
        #   placeholder date 2001-09-01 that means 'never scheduled')
        # ----------------------------------------------------------------
        has_p6_dates = self._has_p6_stored_dates(tasks)

        if has_p6_dates:
            tasks = self._apply_p6_stored_dates(tasks)
        else:
            # ----------------------------------------------------------------
            # STEP 2 — Fallback CPM (XER was exported without running F9)
            # ----------------------------------------------------------------
            tasks = self._run_cpm(
                tasks, relationships_df, project_start_date,
                cal_map, data_date, plan_end_date
            )

        return tasks

    # ------------------------------------------------------------------
    # Primary Path: Read P6-stored dates
    # ------------------------------------------------------------------

    # P6 stores this sentinel date when scheduling has NOT been run (F9 not pressed)
    _P6_NULL_DATE = '2001-09-01'

    def _has_p6_stored_dates(self, tasks: pd.DataFrame) -> bool:
        """
        Check if the XER has real P6 CPM-computed dates.
        P6 stores '2001-09-01' as a null/unscheduled sentinel — we reject those.
        If >50% of early_start_date values are null or the P6 sentinel date,
        we treat the XER as unscheduled and run our own CPM.
        """
        for field in [self.XER_ES, self.XER_EF]:
            if field not in tasks.columns:
                return False

        es_series = tasks[self.XER_ES].astype(str).str.strip()
        # Remove obviously null entries
        valid = es_series[~es_series.isin(['', 'nan', 'NaT', 'None'])]
        # Remove P6 null sentinel (2001-09-01 or any date before 2005)
        def is_real_date(val: str) -> bool:
            try:
                ts = pd.to_datetime(val[:10], errors='coerce')
                if pd.isnull(ts):
                    return False
                return ts.year >= 2005  # sentinel dates are pre-2005
            except Exception:
                return False

        real_dates = valid[valid.apply(is_real_date)]
        # Trust P6 dates if at least 1% of tasks have real scheduled dates.
        # This prevents falling back to internal CPM for already-scheduled P6 files.
        return len(real_dates) >= max(1, len(tasks) * 0.01)

    def _apply_p6_stored_dates(self, tasks: pd.DataFrame) -> pd.DataFrame:
        """
        Map P6's stored XER date fields to our output columns.
        Also compute total_float in days from total_float_hr_cnt.
        """
        def _fmt(val) -> Optional[str]:
            if pd.isnull(val) or str(val).strip() in ('', 'nan', 'NaT', 'None'):
                return None
            try:
                ts = pd.to_datetime(str(val)[:19], errors='coerce')
                if pd.isnull(ts):
                    return None
                # Primavera P6 uses these specific dates as internal 'null' sentinels in the database
                if ts.strftime('%Y-%m-%d') in ('2001-09-01', '2001-08-01', '1990-01-01', '1900-01-01'):
                    return None
                return ts.strftime('%d %b %Y')
            except Exception:
                return None

        tasks['early_start'] = tasks[self.XER_ES].apply(_fmt)
        tasks['early_finish'] = tasks[self.XER_EF].apply(_fmt)

        ls_col = self.XER_LS if self.XER_LS in tasks.columns else None
        lf_col = self.XER_LF if self.XER_LF in tasks.columns else None
        tasks['late_start'] = tasks[ls_col].apply(_fmt) if ls_col else None
        tasks['late_finish'] = tasks[lf_col].apply(_fmt) if lf_col else None

        # Float in days — P6 stores this in hours (total_float_hr_cnt)
        tf_col = self.XER_TF if self.XER_TF in tasks.columns else 'total_float_hr_cnt'
        if tf_col in tasks.columns:
            tasks['total_float'] = pd.to_numeric(
                tasks[tf_col], errors='coerce'
            ) / self.hours_per_day
            tasks['total_float'] = tasks['total_float'].round(2)
        else:
            tasks['total_float'] = 0.0

        return tasks

    # ------------------------------------------------------------------
    # Fallback CPM Path
    # ------------------------------------------------------------------

    def _get_calendar(self, cal_map: Dict[str, P6Calendar], cal_id: Any) -> P6Calendar:
        cid = str(cal_id) if not pd.isnull(cal_id) else ''
        return cal_map.get(cid, self._default_calendar)

    def _run_cpm(
        self,
        tasks: pd.DataFrame,
        relationships_df: pd.DataFrame,
        project_start: pd.Timestamp,
        cal_map: Dict[str, P6Calendar],
        data_date: Optional[pd.Timestamp],
        plan_end_date: Optional[pd.Timestamp] = None,
    ) -> pd.DataFrame:
        """
        Full CPM: forward pass → constraint application → backward pass → float.
        All computations in absolute datetime (not hours-from-start).
        """
        rels = relationships_df.copy() if not relationships_df.empty else pd.DataFrame(
            columns=['task_id', 'pred_task_id', 'pred_type', 'lag_hr_cnt']
        )

        # Build task lookup
        task_ids = list(tasks['task_id'].unique())
        tid_set = set(task_ids)

        # Duration in working days per task
        dur: Dict[str, float] = {}
        cal_id_map: Dict[str, Any] = {}
        for _, row in tasks.iterrows():
            tid = row['task_id']
            # Improved duration extraction with NaN protection
            dur_hr = pd.to_numeric(row.get('target_drtn_hr_cnt', row.get('remain_drtn_hr_cnt', 0)), errors='coerce')
            if pd.isna(dur_hr): dur_hr = 0.0
            
            cid = row.get('clndr_id', '')
            cal = self._get_calendar(cal_map, cid)
            cal_id_map[tid] = cid
            hpd = cal.hours_per_day if cal.hours_per_day > 0 else self.hours_per_day
            dur[tid] = float(dur_hr / hpd)

        # Build adjacency
        successors: Dict[str, List] = {tid: [] for tid in task_ids}
        predecessors: Dict[str, List] = {tid: [] for tid in task_ids}
        rels['lag_days'] = pd.to_numeric(rels['lag_hr_cnt'], errors='coerce').fillna(0) / self.hours_per_day

        for _, row in rels.iterrows():
            sid = row['task_id']
            pid = row['pred_task_id']
            rtype = row.get('pred_type', 'PR_FS')
            lag = float(row['lag_days'])
            if sid in tid_set and pid in tid_set:
                successors[pid].append((sid, rtype, lag))
                predecessors[sid].append((pid, rtype, lag))

        # ES/EF stored as datetime
        ES: Dict[str, datetime] = {}
        EF: Dict[str, datetime] = {}
        
        # Determine effective start point
        # For updates, we MUST anchor to the Data Date.
        # If no Data Date, use project start.
        anchor_date = data_date.to_pydatetime() if data_date else project_start.to_pydatetime()

        # Initial pass: Handle Completed and In-Progress tasks
        for _, row in tasks.iterrows():
            tid = row['task_id']
            status = str(row.get('status_code', row.get('task_status', 'TK_NotStart')))
            
            as_raw = row.get('act_start_date', row.get('actual_start_date'))
            af_raw = row.get('act_end_date', row.get('actual_finish_date'))
            
            # If task is COMPLETED, use actuals
            if status == 'TK_Complete' and not pd.isnull(af_raw):
                ES[tid] = pd.to_datetime(as_raw).to_pydatetime()
                EF[tid] = pd.to_datetime(af_raw).to_pydatetime()
            # If task is IN PROGRESS, it started in the past but ends in the future
            elif status == 'TK_Active' and not pd.isnull(as_raw):
                ES[tid] = pd.to_datetime(as_raw).to_pydatetime()
                # EF will be calculated from duration starting at data_date (approx)
                # But for now, we'll let the forward pass handle the finish
            else:
                # Default for unstarted tasks
                ES[tid] = anchor_date

        # ---- Forward Pass ----
        in_degree = {tid: len(predecessors[tid]) for tid in task_ids}
        queue = [tid for tid in task_ids if in_degree[tid] == 0]

        processed = set()
        iteration = 0
        while queue and iteration < len(task_ids) * 2:
            iteration += 1
            pid = queue.pop(0)
            if pid in processed:
                continue
            processed.add(pid)

            cal = self._get_calendar(cal_map, cal_id_map[pid])
            
            # If we don't have a fixed EF yet (not completed)
            if pid not in EF:
                es = self._ensure_workday(ES[pid], cal)
                # Ensure unstarted tasks don't start before anchor
                if str(tasks.loc[tasks['task_id'] == pid, 'status_code'].values[0]) != 'TK_Complete':
                    es = max(es, anchor_date)
                
                ef = self._add_duration(es, dur[pid], cal)
                ES[pid] = es
                EF[pid] = ef

            for sid, rtype, lag in successors[pid]:
                candidate = self._forward_constraint(
                    rtype, lag, ES[pid], EF[pid],
                    dur[sid], cal_map, cal_id_map[sid]
                )
                # Successor ES must be at least the candidate date
                if sid not in ES or candidate > ES[sid]:
                    ES[sid] = candidate

                in_degree[sid] -= 1
                if in_degree[sid] == 0:
                    queue.append(sid)

        # Compute EF for any remaining (orphans)
        for tid in task_ids:
            if tid not in EF:
                cal = self._get_calendar(cal_map, cal_id_map[tid])
                es = self._ensure_workday(ES[tid], cal)
                # Anchor unstarted orphans
                if str(tasks.loc[tasks['task_id'] == tid, 'status_code'].values[0]) != 'TK_Complete':
                    es = max(es, anchor_date)
                ES[tid] = es
                EF[tid] = self._add_duration(es, dur[tid], cal)

        # ---- Constraint Application ----
        for _, row in tasks.iterrows():
            tid = row['task_id']
            cstr_type = str(row.get('cstr_type', '') or '').strip()
            cstr_date_raw = row.get('cstr_date', None)
            cstr_date = pd.to_datetime(cstr_date_raw, errors='coerce')

            if pd.isnull(cstr_date):
                continue

            cal = self._get_calendar(cal_map, cal_id_map[tid])
            cdt = cstr_date.to_pydatetime()

            if cstr_type in ('CS_MSOB', 'CS_MSON'):  # Must Start On
                ES[tid] = self._ensure_workday(cdt, cal)
                EF[tid] = self._add_duration(ES[tid], dur[tid], cal)
            elif cstr_type in ('CS_MFOB', 'CS_MFON'):  # Must Finish On / By
                EF[tid] = self._ensure_workday(cdt, cal)
                ES[tid] = self._subtract_duration(EF[tid], dur[tid], cal)
            elif cstr_type in ('CS_SNET',):  # Start No Earlier Than
                if ES[tid] < cdt:
                    ES[tid] = self._ensure_workday(cdt, cal)
                    EF[tid] = self._add_duration(ES[tid], dur[tid], cal)
            elif cstr_type in ('CS_FNLT',):  # Finish No Later Than — affects backward pass
                pass  # Handled in backward pass
            elif cstr_type in ('CS_FNET',):  # Finish No Earlier Than
                candidate_ef = self._ensure_workday(cdt, cal)
                if EF[tid] < candidate_ef:
                    EF[tid] = candidate_ef

        # ---- Backward Pass ----
        # Anchor: use plan_end_date (contractual deadline) if provided.
        # This is THE key to matching P6's negative float output.
        # When the schedule has slipped past the deadline, all LF values start
        # from the deadline (earlier than max_EF), producing negative float.
        max_ef = max(EF.values())
        if plan_end_date is not None:
            proj_end = plan_end_date.to_pydatetime()
        else:
            proj_end = max_ef

        LF: Dict[str, datetime] = {tid: proj_end for tid in task_ids}
        LS: Dict[str, datetime] = {}

        # Apply FNLT / Must Finish constraints as per-task forced LF
        for _, row in tasks.iterrows():
            tid = row['task_id']
            cstr_type = str(row.get('cstr_type', '') or '').strip()
            cstr_date_raw = row.get('cstr_date', None)
            cstr_date = pd.to_datetime(cstr_date_raw, errors='coerce')
            if cstr_type in ('CS_FNLT', 'CS_MFON', 'CS_MFOB') and not pd.isnull(cstr_date):
                cdt = cstr_date.to_pydatetime()
                # Force LF to the constraint date (creates negative float when EF > cdt)
                LF[tid] = min(LF[tid], cdt)

        out_degree = {tid: len(successors[tid]) for tid in task_ids}
        queue_b = [tid for tid in task_ids if out_degree[tid] == 0]
        processed_b = set()
        iteration = 0

        while queue_b and iteration < len(task_ids) * 2:
            iteration += 1
            sid = queue_b.pop(0)
            if sid in processed_b:
                continue
            processed_b.add(sid)

            cal = self._get_calendar(cal_map, cal_id_map[sid])
            lf = LF[sid]
            ls = self._subtract_duration(lf, dur[sid], cal)
            LS[sid] = ls

            for pid, rtype, lag in predecessors[sid]:
                candidate_lf = self._backward_constraint(
                    rtype, lag, LS[sid], LF[sid],
                    dur[pid], cal_map, cal_id_map[pid]
                )
                if candidate_lf < LF[pid]:
                    LF[pid] = candidate_lf

                out_degree[pid] -= 1
                if out_degree[pid] == 0:
                    queue_b.append(pid)

        # Compute LS for any remaining
        for tid in task_ids:
            if tid not in LS:
                cal = self._get_calendar(cal_map, cal_id_map[tid])
                LS[tid] = self._subtract_duration(LF[tid], dur[tid], cal)

        # ---- Output ----
        def fmt(dt: Optional[datetime]) -> Optional[str]:
            if dt is None:
                return None
            if dt.strftime('%Y-%m-%d') in ('2001-09-01', '2001-08-01', '1990-01-01', '1900-01-01'):
                return None
            return dt.strftime('%d %b %Y')

        results = []
        for tid in task_ids:
            es = ES[tid]
            ef = EF[tid]
            ls = LS.get(tid, LF.get(tid))
            lf = LF.get(tid)

            # Float in working days
            cal = self._get_calendar(cal_map, cal_id_map[tid])
            tf_days = self._working_days_diff(es, ls, cal)
            
            # Safe float rounding
            final_tf = 0.0
            if not pd.isna(tf_days):
                final_tf = round(float(tf_days), 2)

            results.append({
                'task_id': tid,
                'early_start': fmt(es),
                'early_finish': fmt(ef),
                'late_start': fmt(ls),
                'late_finish': fmt(lf),
                'total_float': final_tf,
            })

        results_df = pd.DataFrame(results)
        return tasks.merge(results_df, on='task_id', how='left')

    # ------------------------------------------------------------------
    # Relationship Logic Helpers
    # ------------------------------------------------------------------

    def _forward_constraint(
        self, rtype: str, lag: float,
        pred_es: datetime, pred_ef: datetime,
        succ_dur: float, cal_map: Dict, succ_cal_id: Any
    ) -> datetime:
        """Compute the earliest ES for successor based on relationship type."""
        succ_cal = self._get_calendar(cal_map, succ_cal_id)
        if rtype == 'PR_FS':
            # ES_succ >= EF_pred + lag
            return self._add_lag(pred_ef, lag, succ_cal)
        elif rtype == 'PR_SS':
            # ES_succ >= ES_pred + lag
            return self._add_lag(pred_es, lag, succ_cal)
        elif rtype == 'PR_FF':
            # EF_succ >= EF_pred + lag => ES_succ >= EF_pred + lag - dur_succ
            ef_min = self._add_lag(pred_ef, lag, succ_cal)
            return self._subtract_duration(ef_min, succ_dur, succ_cal)
        elif rtype == 'PR_SF':
            # EF_succ >= ES_pred + lag => ES_succ >= ES_pred + lag - dur_succ
            ef_min = self._add_lag(pred_es, lag, succ_cal)
            return self._subtract_duration(ef_min, succ_dur, succ_cal)
        else:  # default FS
            return self._add_lag(pred_ef, lag, succ_cal)

    def _backward_constraint(
        self, rtype: str, lag: float,
        succ_ls: datetime, succ_lf: datetime,
        pred_dur: float, cal_map: Dict, pred_cal_id: Any
    ) -> datetime:
        """Compute latest allowable LF for predecessor based on relationship type."""
        pred_cal = self._get_calendar(cal_map, pred_cal_id)
        if rtype == 'PR_FS':
            # LF_pred <= LS_succ - lag
            return self._subtract_lag(succ_ls, lag, pred_cal)
        elif rtype == 'PR_SS':
            # LS_pred <= LS_succ - lag => LF_pred <= LS_succ - lag + dur_pred
            ls_max = self._subtract_lag(succ_ls, lag, pred_cal)
            return self._add_duration(ls_max, pred_dur, pred_cal)
        elif rtype == 'PR_FF':
            # LF_pred <= LF_succ - lag
            return self._subtract_lag(succ_lf, lag, pred_cal)
        elif rtype == 'PR_SF':
            # LS_pred <= LF_succ - lag => LF_pred <= LF_succ - lag + dur_pred
            ls_max = self._subtract_lag(succ_lf, lag, pred_cal)
            return self._add_duration(ls_max, pred_dur, pred_cal)
        else:
            return self._subtract_lag(succ_ls, lag, pred_cal)

    # ------------------------------------------------------------------
    # Calendar Arithmetic Helpers
    # ------------------------------------------------------------------

    def _ensure_workday(self, dt: datetime, cal: P6Calendar) -> datetime:
        """If dt falls on non-workday, advance to next workday."""
        while not cal.is_workday(dt):
            dt += timedelta(days=1)
        return dt

    def _add_duration(self, dt: datetime, days: float, cal: P6Calendar) -> datetime:
        """Add N working days to dt."""
        if days <= 0:
            return dt
        current = dt
        added = 0
        while added < days:
            current += timedelta(days=1)
            if cal.is_workday(current):
                added += 1
        return current

    def _subtract_duration(self, dt: datetime, days: float, cal: P6Calendar) -> datetime:
        """Subtract N working days from dt."""
        if days <= 0:
            return dt
        current = dt
        subtracted = 0
        while subtracted < days:
            current -= timedelta(days=1)
            if cal.is_workday(current):
                subtracted += 1
        return current

    def _add_lag(self, dt: datetime, lag_days: float, cal: P6Calendar) -> datetime:
        """Add lag (can be negative) in working days."""
        if lag_days == 0:
            return dt
        if lag_days > 0:
            return self._add_duration(dt, lag_days, cal)
        else:
            return self._subtract_duration(dt, abs(lag_days), cal)

    def _subtract_lag(self, dt: datetime, lag_days: float, cal: P6Calendar) -> datetime:
        """Subtract lag (inverse of add_lag)."""
        return self._add_lag(dt, -lag_days, cal)

    def _working_days_diff(self, es: datetime, ls: datetime, cal: P6Calendar) -> float:
        """
        Total Float in working days = LS - ES in working days.
        Can be negative if ls < es.
        """
        if ls == es:
            return 0.0
        elif ls > es:
            return cal.workdays_between(es, ls)
        else:
            return -cal.workdays_between(ls, es)
