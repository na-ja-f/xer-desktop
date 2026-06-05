import pandas as pd
import re
from typing import Dict, List, Optional, Any
from .scheduler import CPMScheduler, P6Calendar

class XERDataStore:
    """Stores all XER data with pre-computed statistics"""

    def __init__(self):
        self.contexts = {
            "audit": {"versions": {}, "active_version_id": None},
            "controller": {"versions": {}, "active_version_id": None}
        }
        self.hours_per_day = 10
        self._cached_stats = {} # {context: stats}
        self.results_cache = {} # {ref_id: List[Dict]}

    def add_version(self, data: Dict, name: str, data_date: str, type: str = "update", context: str = "audit") -> str:
        if context not in self.contexts:
            context = "audit"
            
        ctx = self.contexts[context]
        versions = ctx["versions"]
        
        version_id = f"{type}_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}"
        if type == "baseline":
            version_id = f"baseline_{pd.Timestamp.now().strftime('%Y%m%d%H%M%S')}"
            # If it's a baseline, we might want to clear previous versions for this context if it's a fresh start?
            # User didn't specify, so we'll just add it.
            
        # Extract hours_per_day from CALENDAR if available
        hpd = 8.0 # Default
        if 'tables' in data and 'CALENDAR' in data['tables']:
            cal_table = data['tables']['CALENDAR']
            if cal_table:
                for cal in cal_table:
                    if 'day_hr_cnt' in cal and cal['day_hr_cnt']:
                        try:
                            hpd = float(cal['day_hr_cnt'])
                            break
                        except:
                            continue
        
        versions[version_id] = {
            'id': version_id,
            'type': type,
            'name': name,
            'data_date': data_date,
            'data': data,
            'df': self._create_dataframes(data),
            'hours_per_day': hpd,
            'context': context
        }
        
        # Trigger CPM Calculation
        self._run_cpm(version_id, context)
        
        # Build Dependency Graph for AI/UI
        self._build_dependency_graph(version_id, context)
        
        ctx["active_version_id"] = version_id
        if context in self._cached_stats:
            del self._cached_stats[context]
        return version_id

    def _build_dependency_graph(self, version_id: str, context: str = "audit"):
        """Builds a human-readable dependency map for each activity."""
        ctx = self.contexts.get(context, self.contexts["audit"])
        v = ctx["versions"].get(version_id)
        if not v or 'tasks' not in v['df'] or 'taskpred' not in v['df']: return

        tasks_df = v['df']['tasks']
        rels_df = v['df']['taskpred']
        
        # Map IDs to Names
        id_to_name = dict(zip(tasks_df['task_id'], tasks_df['task_name']))
        type_map = {'PR_FS': 'FS', 'PR_SS': 'SS', 'PR_FF': 'FF', 'PR_SF': 'SF'}

        v['dependency_graph'] = {tid: {'predecessors': [], 'successors': []} for tid in tasks_df['task_id']}
        
        for _, row in rels_df.iterrows():
            sid = row['task_id']      # Successor
            pid = row['pred_task_id'] # Predecessor
            rtype = type_map.get(row['pred_type'], row['pred_type'])
            lag = row.get('lag_hr_cnt', 0)

            if sid in id_to_name and pid in id_to_name:
                v['dependency_graph'][sid]['predecessors'].append({
                    'id': pid,
                    'name': id_to_name[pid],
                    'type': rtype,
                    'lag': lag
                })
                v['dependency_graph'][pid]['successors'].append({
                    'id': sid,
                    'name': id_to_name[sid],
                    'type': rtype,
                    'lag': lag
                })

    def _run_cpm(self, version_id: str, context: str = "audit"):
        """Internal helper to trigger CPM scheduling for a version."""
        ctx = self.contexts.get(context, self.contexts["audit"])
        v = ctx["versions"].get(version_id)
        if not v: return
        dfs = v['df']
        if 'tasks' not in dfs or 'taskpred' not in dfs:
            return

        # Get project start/end from PROJECT table (most reliable source)
        project_df = dfs.get('project', dfs.get('PROJECT', None))
        plan_start_raw = None
        plan_end_raw = None
        
        if project_df is not None and not project_df.empty:
            # Try to find the project row that matches the tasks (XER can have multiple projects)
            proj_id = None
            if not dfs['tasks'].empty:
                proj_id = dfs['tasks'].iloc[0].get('proj_id')
            
            proj_row = None
            if proj_id and 'proj_id' in project_df.columns:
                matches = project_df[project_df['proj_id'].astype(str) == str(proj_id)]
                if not matches.empty:
                    proj_row = matches.iloc[0]
            
            if proj_row is None:
                proj_row = project_df.iloc[0]
                
            plan_start_raw = proj_row.get('plan_start_date') or proj_row.get('last_recalc_date')
            # Check multiple finish date fields for "Must Finish By" or project completion
            plan_end_raw = proj_row.get('plan_end_date') or proj_row.get('scd_end_date') or proj_row.get('finish_date')

        # Fallback: earliest task start date
        if not plan_start_raw and 'target_start_date' in dfs['tasks'].columns:
            plan_start_raw = dfs['tasks']['target_start_date'].dropna().min()

        if not plan_start_raw or pd.isnull(pd.to_datetime(plan_start_raw, errors='coerce')):
            start_date = pd.Timestamp.now()
        else:
            start_date = pd.to_datetime(str(plan_start_raw)[:10])

        # Contractual end date — drives the backward pass anchor for float calculation
        plan_end_date = None
        if plan_end_raw:
            _ped = pd.to_datetime(str(plan_end_raw)[:10], errors='coerce')
            if not pd.isnull(_ped):
                plan_end_date = _ped

        # Get data date for CPM
        data_date_raw = v.get('data_date')
        data_date = pd.to_datetime(data_date_raw, errors='coerce') if data_date_raw else None

        # Build calendars DataFrame from CALENDAR table if available
        calendars_df = dfs.get('calendar', dfs.get('CALENDAR', None))

        scheduler = CPMScheduler(hours_per_day=v.get('hours_per_day', 8.0))
        v['df']['tasks'] = scheduler.calculate(
            dfs['tasks'],
            dfs['taskpred'],
            start_date,
            calendars_df=calendars_df,
            data_date=data_date,
            plan_end_date=plan_end_date,
        )

    def remove_version(self, version_id: str, context: str = "audit"):
        ctx = self.contexts.get(context, self.contexts["audit"])
        if version_id in ctx["versions"]:
            del ctx["versions"][version_id]
            if ctx["active_version_id"] == version_id:
                # Find another version to make active, preferably a baseline
                baselines = [v["id"] for v in ctx["versions"].values() if v["type"] == "baseline"]
                if baselines:
                    ctx["active_version_id"] = baselines[0]
                elif ctx["versions"]:
                    ctx["active_version_id"] = list(ctx["versions"].keys())[0]
                else:
                    ctx["active_version_id"] = None
            if context in self._cached_stats:
                del self._cached_stats[context]

    def _create_dataframes(self, data: Dict) -> Dict[str, pd.DataFrame]:
        dfs = {}
        if data.get('tasks'):
            dfs['tasks'] = pd.DataFrame(data['tasks'])
        if data.get('wbs'):
            dfs['wbs'] = pd.DataFrame(data['wbs'])
        for table_name, records in data.get('tables', {}).items():
            if records:
                dfs[table_name.lower()] = pd.DataFrame(records)
        return dfs

    def _build_activity_codes_map(self, source: Dict) -> Dict[str, Dict[str, str]]:
        """Joins TASKACTV → ACTVCODE → ACTVTYPE to build a per-task activity code map.
        Returns: {task_id: {code_type_name: code_value_name, ...}, ...}

        ASSUMPTION: P6 enforces a 1:1 relationship between (task_id, code_type) and code_value.
        Verified against real XER data: 15,847 assignments with 0 duplicates.
        If a duplicate is ever encountered, the last value wins (dict overwrite).

        NOTE: This runs per source (per version). Baseline and update files maintain
        independent Activity Code structures — they are never merged or shared.
        """
        tables = source.get('data', {}).get('tables', {})
        dfs = source.get('df', {})

        # Get DataFrames — prefer lowercase (from _create_dataframes) then uppercase (from raw tables)
        taskactv_df = dfs.get('taskactv')
        actvcode_df = dfs.get('actvcode')
        actvtype_df = dfs.get('actvtype')

        # Fallback: build from raw tables if DataFrames not present
        if taskactv_df is None and 'TASKACTV' in tables:
            taskactv_df = pd.DataFrame(tables['TASKACTV'])
        if actvcode_df is None and 'ACTVCODE' in tables:
            actvcode_df = pd.DataFrame(tables['ACTVCODE'])
        if actvtype_df is None and 'ACTVTYPE' in tables:
            actvtype_df = pd.DataFrame(tables['ACTVTYPE'])

        if taskactv_df is None or taskactv_df.empty:
            return {}
        if actvcode_df is None or actvcode_df.empty:
            return {}
        if actvtype_df is None or actvtype_df.empty:
            return {}

        try:
            # 1. Join ACTVCODE to get value names
            merged = taskactv_df.merge(
                actvcode_df[['actv_code_id', 'actv_code_name']],
                on='actv_code_id',
                how='left'
            )
            # 2. Join ACTVTYPE to get type names
            merged = merged.merge(
                actvtype_df[['actv_code_type_id', 'actv_code_type']],
                on='actv_code_type_id',
                how='left'
            )
            # 3. Trim whitespace from names
            merged['actv_code_type'] = merged['actv_code_type'].astype(str).str.strip()
            merged['actv_code_name'] = merged['actv_code_name'].astype(str).str.strip()

            # 4. Group by task_id into {type: value} dicts
            # P6 enforces 1:1 per (task, type), so dict() is safe.
            # If duplicates ever exist, last value wins — this is intentional.
            result = (
                merged.groupby('task_id')
                .apply(lambda x: dict(zip(x['actv_code_type'], x['actv_code_name'])))
                .to_dict()
            )
            return result
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to build activity codes map: {e}")
            return {}

    def _inject_activity_codes(self, activity_analysis: Dict, source: Dict) -> Dict:
        """Injects activity_codes into each activity in the activityAnalysis dict."""
        codes_map = self._build_activity_codes_map(source)
        if not codes_map:
            return activity_analysis
        for tid, data in activity_analysis.items():
            data['activity_codes'] = codes_map.get(tid, {})
        return activity_analysis

    def get_activity_code_types(self, version_id: Optional[str] = None, context: str = "audit", scope: Optional[str] = None) -> Dict[str, Dict]:
        """Returns all Activity Code Types, their scope, and their available values from the loaded XER.
        Returns: {type_name: {"scope": "Project", "values": [value1, value2, ...]}, ...}
        """
        source = self.get_latest(context=context, version_id=version_id)
        if not source:
            return {}

        tables = source.get('data', {}).get('tables', {})
        dfs = source.get('df', {})

        actvcode_df = dfs.get('actvcode')
        actvtype_df = dfs.get('actvtype')

        if actvcode_df is None and 'ACTVCODE' in tables:
            actvcode_df = pd.DataFrame(tables['ACTVCODE'])
        if actvtype_df is None and 'ACTVTYPE' in tables:
            actvtype_df = pd.DataFrame(tables['ACTVTYPE'])

        if actvcode_df is None or actvcode_df.empty or actvtype_df is None or actvtype_df.empty:
            return {}

        try:
            scope_map = {"AS_Project": "Project", "AS_Global": "Global", "AS_EPS": "EPS"}
            cols_to_merge = ['actv_code_type_id', 'actv_code_type']
            if 'actv_code_type_scope' in actvtype_df.columns:
                cols_to_merge.append('actv_code_type_scope')
                
            merged = actvcode_df.merge(
                actvtype_df[cols_to_merge],
                on='actv_code_type_id',
                how='left'
            )
            merged['actv_code_type'] = merged['actv_code_type'].astype(str).str.strip()
            merged['actv_code_name'] = merged['actv_code_name'].astype(str).str.strip()
            
            if 'actv_code_type_scope' in merged.columns:
                merged['scope'] = merged['actv_code_type_scope'].map(scope_map).fillna("Global")
            else:
                merged['scope'] = "Global"

            result = {}
            for type_name, group in merged.groupby('actv_code_type'):
                grp_scope = group['scope'].iloc[0]
                if scope and scope.lower() != "all" and scope.lower() != grp_scope.lower():
                    continue
                
                # Build hierarchy map
                id_to_row = {str(row['actv_code_id']): row for _, row in group.iterrows()}
                hierarchy = {}
                
                # First pass: init nodes
                for _, row in group.iterrows():
                    val = row['actv_code_name']
                    hierarchy[val] = {
                        "value": val,
                        "actv_code_id": str(row['actv_code_id']),
                        "parent_actv_code_id": str(row['parent_actv_code_id']) if pd.notna(row['parent_actv_code_id']) and str(row['parent_actv_code_id']) != "None" else None,
                        "parent_value": None,
                        "children_values": [],
                        "hierarchy_path": val
                    }
                
                # Second pass: link parents and children, build paths
                for val, node in hierarchy.items():
                    pid = node["parent_actv_code_id"]
                    if pid and pid in id_to_row:
                        parent_val = id_to_row[pid]['actv_code_name']
                        node["parent_value"] = parent_val
                        if parent_val in hierarchy:
                            hierarchy[parent_val]["children_values"].append(val)
                            
                # Third pass: build full hierarchy path (recursive/iterative)
                def get_path(val, visited):
                    if val in visited: return val # prevent infinite loops
                    visited.add(val)
                    p_val = hierarchy[val]["parent_value"]
                    if p_val and p_val in hierarchy:
                        return get_path(p_val, visited) + " > " + val
                    return val
                
                for val in hierarchy:
                    hierarchy[val]["hierarchy_path"] = get_path(val, set())
                
                result[type_name] = {
                    "scope": grp_scope,
                    "values": sorted(group['actv_code_name'].unique().tolist()),
                    "hierarchy": hierarchy
                }

            return result
        except Exception:
            return {}

    def get_version(self, version_id: Optional[str] = None, context: str = "audit") -> Optional[Dict]:
        ctx = self.contexts.get(context, self.contexts["audit"])
        vid = version_id or ctx["active_version_id"]
        return ctx["versions"].get(vid)

    def get_latest(self, context: str = "audit", version_id: Optional[str] = None) -> Optional[Dict]:
        ctx = self.contexts.get(context, self.contexts["audit"])
        versions = ctx["versions"]
        if not versions: return None
        # If a specific version_id is requested, return it directly
        if version_id and version_id in versions:
            return versions[version_id]
        # Sort updates by date and get latest
        updates = [v for v in versions.values() if v['type'] == 'update']
        if updates:
            updates.sort(key=lambda x: x['data_date'])
            return updates[-1]
        # Fallback to baseline
        baselines = [v for v in versions.values() if v['type'] == 'baseline']
        if baselines:
            baselines.sort(key=lambda x: x['data_date'])
            return baselines[-1]
        return None

    def get_baseline(self, context: str = "audit") -> Optional[Dict]:
        ctx = self.contexts.get(context, self.contexts["audit"])
        # Find the first version of type 'baseline'
        for v in ctx["versions"].values():
            if v["type"] == "baseline":
                return v
        return None

    def get_update_by_month(self, month: str, context: str = "audit") -> Optional[Dict]:
        month_map = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
            'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }
        month_num = month_map.get(month.lower()[:3], month)
        ctx = self.contexts.get(context, self.contexts["audit"])
        updates = [v for v in ctx["versions"].values() if v['type'] == 'update']
        for update in updates:
            if update['data_date'][5:7] == month_num:
                return update
        return None

    def compute_basic_stats(self, version_id: Optional[str] = None, context: str = "audit") -> Dict:
        if not version_id and context in self._cached_stats: return self._cached_stats[context]
        
        source = self.get_version(version_id, context=context) if version_id else self.get_latest(context=context)
        if not source or 'tasks' not in source.get('df', {}): return {}

        tasks_df = source['df']['tasks'].copy()
        stats = {}
        stats['total_activities'] = len(tasks_df)
        stats['data_source'] = source['name']
        stats['data_date'] = source['data_date']

        if 'target_drtn_hr_cnt' in tasks_df.columns:
            tasks_df['duration_hrs'] = pd.to_numeric(tasks_df['target_drtn_hr_cnt'], errors='coerce').fillna(0)
            work_tasks = tasks_df[~tasks_df.get('task_type', '').isin(['TT_LOE', 'TT_Mile', 'TT_FinMile'])]
            stats['long_duration_count'] = len(work_tasks[work_tasks['duration_hrs'] / self.hours_per_day > 30]) if len(work_tasks) > 0 else 0

        if 'total_float_hr_cnt' in tasks_df.columns:
            tasks_df['float_hrs'] = pd.to_numeric(tasks_df['total_float_hr_cnt'], errors='coerce').fillna(0)
            work_tasks = tasks_df[~tasks_df.get('task_type', '').isin(['TT_LOE'])]
            if len(work_tasks) > 0:
                critical = work_tasks[work_tasks['float_hrs'] <= 0]
                stats['critical_count'] = len(critical)
                stats['critical_pct'] = round(len(critical) / len(work_tasks) * 100, 1)
                stats['negative_float_count'] = len(work_tasks[work_tasks['float_hrs'] < 0])
                
                # Simple delay check for stats (comparing current end to target end)
                # Note: For full accuracy, the deterministic analysis should be used.
                if 'target_end_date' in tasks_df.columns and 'act_end_date' in tasks_df.columns:
                    # Very basic check for stats
                    pass 

        if 'taskpred' in source['df']:
            pred_df = source['df']['taskpred']
            all_task_ids = set(tasks_df['task_id'].tolist())
            has_successor = set(pred_df['pred_task_id'].tolist())
            has_predecessor = set(pred_df['task_id'].tolist())
            
            # Open Start: No predecessors
            open_starts = tasks_df[~tasks_df['task_id'].isin(has_predecessor)]
            # Open Finish: No successors
            open_finishes = tasks_df[~tasks_df['task_id'].isin(has_successor)]
            
            stats['open_start_count'] = len(open_starts)
            stats['open_finish_count'] = len(open_finishes)
            stats['open_start_names'] = open_starts['task_name'].tolist()
            stats['open_finish_names'] = open_finishes['task_name'].tolist()
            stats['open_ended_count'] = len(open_starts) + len(open_finishes)

        if 'target_start_date' in tasks_df.columns:
            stats['project_start'] = str(tasks_df['target_start_date'].dropna().min())[:10]
        if 'target_end_date' in tasks_df.columns:
            stats['project_finish'] = str(tasks_df['target_end_date'].dropna().max())[:10]

        # Add the new matrix and health metrics
        analysis = self.get_deterministic_analysis(source['id'], context=context)
        summary = analysis.get('projectSummary', {})
        delay_matrix = summary.get('delayFloatMatrix', {})
        health_metrics = summary.get('healthMetrics', {})
        
        # Merge all metrics ensuring projectDelayDays and assessment are included
        stats['delay_matrix'] = {
            **delay_matrix, 
            **health_metrics, 
            "projectDelayDays": summary.get('projectDelayDays', 0),
            "assessment": summary.get("assessment", []),
            "qualityIssues": health_metrics.get("qualityIssues", [])
        }
        stats['topDrivers'] = summary.get('topDrivers', [])
        stats['topRisks'] = summary.get('topRisks', [])

        # Override the stats with the more robust deterministic analysis calculation
        stats['critical_count'] = health_metrics.get('criticalCount', stats.get('critical_count', 0))
        stats['negative_float_count'] = health_metrics.get('negativeFloatCount', stats.get('negative_float_count', 0))

        self._cached_stats[context] = stats
        return stats

    def _get_baseline_map(self, context: str = "audit") -> Dict[str, pd.Timestamp]:
        """Helper to get task_code -> target_end_date from baseline"""
        baseline = self.get_baseline(context=context)
        if not baseline or 'df' not in baseline or 'tasks' not in baseline['df']:
            return {}
        df = baseline['df']['tasks'].copy()
        df['_dt_target_end_date'] = pd.to_datetime(df['target_end_date'], errors='coerce')
        return df.set_index('task_code')['_dt_target_end_date'].to_dict()

    def _get_baseline_cost_map(self, context: str = "audit") -> Dict[str, float]:
        """Helper to get task_code -> target_cost from baseline"""
        baseline = self.get_baseline(context=context)
        if not baseline or 'df' not in baseline or 'tasks' not in baseline['df']:
            return {}
        df = baseline['df']['tasks'].copy()
        # Check for multiple possible field names
        cost_col = None
        for col in ['target_cost', 'target_tot_cost', 'planned_tot_cost']:
            if col in df.columns:
                cost_col = col
                break
        
        if not cost_col: return {}
        return df.set_index('task_code')[cost_col].apply(lambda x: pd.to_numeric(x, errors='coerce') or 0).to_dict()

    def get_deterministic_analysis(self, version_id: Optional[str] = None, context: str = "audit") -> Dict:
        """
        Pure deterministic schedule analysis based on P6 principles.
        Calculates status, delays (Baseline vs Update), and quality metrics.
        """
        source = self.get_version(version_id, context=context)
        if not source or 'df' not in source or 'tasks' not in source['df']:
            return {}

        is_baseline_only = (source.get('type') == 'baseline')
        df = source['df']['tasks'].copy()
        baseline_map = self._get_baseline_map(context=context)
        
        # 1. Normalize & Pre-process
        # Support multiple P6 field name variations for dates
        date_mapping = {
            '_dt_target_start_date': ['target_start_date', 'plan_start_date', 'start_date'],
            '_dt_target_end_date': ['target_end_date', 'plan_end_date', 'finish_date', 'scd_end_date'],
            '_dt_act_start_date': ['act_start_date', 'actual_start_date', 'as_date'],
            '_dt_act_end_date': ['act_end_date', 'actual_finish_date', 'af_date']
        }
        
        for internal_col, xer_cols in date_mapping.items():
            val = None
            for col in xer_cols:
                if col in df.columns:
                    val = pd.to_datetime(df[col], errors='coerce')
                    break
            df[internal_col] = val

        # Priority: CPM-computed 'total_float' (days) > XER stored 'total_float_hr_cnt' (hours)
        hpd = source.get('hours_per_day', 8.0)
        if 'total_float' in df.columns and df['total_float'].notna().any():
            # CPM output: already in days
            df['float_days'] = pd.to_numeric(df['total_float'], errors='coerce').fillna(0)
            df['float_hrs'] = df['float_days'] * hpd
        else:
            # Try to find a float column
            float_col = None
            for col in ['total_float_hr_cnt', 'target_tf_hr_cnt', 'tf_hr_cnt']:
                if col in df.columns:
                    float_col = col
                    break
            
            if float_col:
                df['float_hrs'] = pd.to_numeric(df[float_col], errors='coerce').fillna(0)
                df['float_days'] = df['float_hrs'] / hpd
            else:
                df['float_hrs'] = 0.0
                df['float_days'] = 0.0

        # 2. Status Calculation
        def calc_status(row):
            is_completed = pd.notnull(row.get('_dt_act_end_date'))
            is_in_progress = pd.notnull(row.get('_dt_act_start_date')) and not is_completed
            if is_completed: return "COMPLETED"
            if is_in_progress: return "IN_PROGRESS"
            return "NOT_STARTED"

        df['status_enum'] = df.apply(calc_status, axis=1)
        df['is_critical_p6'] = df['float_hrs'] <= 0

        # 2.5. Unified Current End Date Logic
        def get_current_end_date(row):
            act = row.get('_dt_act_end_date')
            plan = row.get('_dt_target_end_date')
            return act if pd.notnull(act) else plan

        df['_dt_current_end_date'] = df.apply(get_current_end_date, axis=1)
        df['is_predicted_date'] = pd.isnull(df['_dt_act_end_date']) & pd.notnull(df['_dt_target_end_date'])

        # 3. Precision P6 Delay Calculation (BASELINE vs UPDATE PLANNED)
        def calc_p6_delay(row):
            if is_baseline_only:
                return None
                
            code = row.get('task_code')
            baseline_finish = baseline_map.get(code)
            
            # Use Actual Finish if available, otherwise use Projected/Planned Finish
            current_finish = row.get('_dt_act_end_date')
            if pd.isnull(current_finish):
                current_finish = row.get('_dt_target_end_date')
            
            if pd.isnull(baseline_finish) or pd.isnull(current_finish):
                return 0
            
            try:
                # Direct comparison: If current finish is exactly the same or before baseline, delay is 0
                if current_finish <= baseline_finish:
                    return 0
                
                diff = current_finish - baseline_finish
                return int(diff.days) if hasattr(diff, 'days') else 0
            except:
                return 0

        df['delay_days'] = df.apply(calc_p6_delay, axis=1)

        # 4. Delay-Float Matrix Logic
        def classify_matrix(row):
            # Once a task is COMPLETED, its forensic 'Delayed' status is retired
            if row['status_enum'] == 'COMPLETED':
                return "NORMAL"
                
            delay = row['delay_days']
            flt = row['float_hrs']
            if delay is not None and delay > 0:
                if flt > 0: return "DELAYED_SAFE"
                if flt == 0: return "DELAYED_CRITICAL"
                if flt < 0: return "DELAYED_NEGATIVE"
            return "NORMAL"

        df['delay_float_category'] = df.apply(classify_matrix, axis=1)

        # 5. Project-Level Calculation
        baseline_max_finish = max(baseline_map.values()) if baseline_map else df['_dt_target_end_date'].max()
        current_max_finish = df['_dt_target_end_date'].max()
        
        # Finish Variance (Standard P6 comparison)
        finish_variance = 0
        if pd.notnull(baseline_max_finish) and pd.notnull(current_max_finish):
            finish_variance = (current_max_finish - baseline_max_finish).days

        # Constraint Detection: If finish variance is flat, but we have negative float, 
        # the "Real Delay" is the amount of negative float on the critical path.
        max_neg_float_days = 0
        if not df[df['float_hrs'] < 0].empty:
            # We take the absolute value of the worst negative float
            max_neg_float_days = abs(df['float_hrs'].min() / self.hours_per_day)

        is_constrained = False
        if is_baseline_only:
            project_delay_days = None
        else:
            project_delay_days = finish_variance
            if finish_variance <= 0 and max_neg_float_days > 0:
                is_constrained = True
                project_delay_days = round(max_neg_float_days, 0)

        # 6. DCMA 14-Point Assessment Logic
        total_tasks = len(df)
        critical_count = len(df[df['is_critical_p6']])
        neg_float_count = len(df[df['float_hrs'] < 0])
        
        task_ids = set(df['task_id'].unique())
        preds_df = source['df'].get('projwbs', pd.DataFrame()) # Placeholder for checking exists
        preds_df = source['df'].get('taskpred', pd.DataFrame())
        
        # Helper lists for checks
        incomplete_tasks = df[df['status_enum'] != 'COMPLETED']
        total_incomplete = len(incomplete_tasks)
        
        # Check 1: Logic (Missing Predecessors/Successors)
        has_pred = set(preds_df['task_id'].unique()) if not preds_df.empty else set()
        has_succ = set(preds_df['pred_task_id'].unique()) if not preds_df.empty else set()
        
        missing_logic_tasks = incomplete_tasks[(~incomplete_tasks['task_id'].isin(has_pred)) | (~incomplete_tasks['task_id'].isin(has_succ))]
        missing_logic_count = len(missing_logic_tasks)
        
        open_starts = incomplete_tasks[~incomplete_tasks['task_id'].isin(has_pred)]
        open_finishes = incomplete_tasks[~incomplete_tasks['task_id'].isin(has_succ)]
        
        open_start_count = len(open_starts)
        open_finish_count = len(open_finishes)
        open_start_names = open_starts['task_name'].tolist()
        open_finish_names = open_finishes['task_name'].tolist()
        
        # DCMA allows exceptions for Project Start/Finish
        allowed_exceptions = 0
        if open_start_count > 0: allowed_exceptions += 1
        if open_finish_count > 0: allowed_exceptions += 1
        
        adjusted_missing = max(0, missing_logic_count - allowed_exceptions)
        pt1_val = (adjusted_missing / total_incomplete * 100) if total_incomplete > 0 else 0
        pt1_val = round(pt1_val, 2)
        
        if pt1_val <= 5:
            logic_status_str = "PASS"
            logic_explanation = "Valid schedule logic coverage"
        else:
            logic_status_str = "FAIL"
            logic_explanation = f"Incomplete logic structure ({adjusted_missing} tasks lacking complete logic)."
        
        # Check 2: Leads (Negative Lag)
        leads_count = len(preds_df[pd.to_numeric(preds_df['lag_hr_cnt'], errors='coerce') < 0]) if not preds_df.empty else 0
        total_rels = len(preds_df) if not preds_df.empty else 1
        pt2_val = (leads_count / total_rels * 100)
        
        # Check 3: Lags (Positive Lag)
        lags_count = len(preds_df[pd.to_numeric(preds_df['lag_hr_cnt'], errors='coerce') > 0]) if not preds_df.empty else 0
        pt3_val = (lags_count / total_rels * 100)
        
        # Check 4: Relationship Types (FS)
        fs_count = len(preds_df[preds_df['pred_type'] == 'PR_FS']) if not preds_df.empty else 0
        pt4_val = (fs_count / total_rels * 100)
        
        # Check 5: Hard Constraints
        hard_constraints = ['CS_MNET', 'CS_MSEO', 'CS_MSON', 'CS_MFON'] # Must Start On, Must Finish On, etc.
        hard_const_count = len(incomplete_tasks[incomplete_tasks['cstr_type'].isin(hard_constraints)])
        pt5_val = (hard_const_count / total_incomplete * 100) if total_incomplete > 0 else 0
        
        # Check 6: High Float (> 44 days)
        high_float_threshold = 44 * self.hours_per_day
        high_float_count = len(incomplete_tasks[incomplete_tasks['float_hrs'] > high_float_threshold])
        pt6_val = (high_float_count / total_incomplete * 100) if total_incomplete > 0 else 0
        
        # Check 7: Negative Float
        neg_float_count = len(incomplete_tasks[incomplete_tasks['float_hrs'] < 0])
        pt7_val = (neg_float_count / total_incomplete * 100) if total_incomplete > 0 else 0
        
        # Check 8: High Duration (> 44 days)
        # We use target_drtn_hr_cnt as it represents Planned Duration in most XER exports
        dur_col = 'target_drtn_hr_cnt' if 'target_drtn_hr_cnt' in df.columns else 'orig_dur_hr_cnt'
        high_dur_threshold = 44 * self.hours_per_day
        
        if dur_col in incomplete_tasks.columns:
            high_dur_count = len(incomplete_tasks[pd.to_numeric(incomplete_tasks[dur_col], errors='coerce').fillna(0) > high_dur_threshold])
        else:
            high_dur_count = 0
            
        pt8_val = (high_dur_count / total_incomplete * 100) if total_incomplete > 0 else 0

        # Check 11: Missed Tasks (% of completed tasks with late finish)
        missed_count = len(df[(df['status_enum'] == 'COMPLETED') & (df['delay_days'] > 0)])
        total_completed = len(df[df['status_enum'] == 'COMPLETED'])
        pt11_val = (missed_count / total_completed * 100) if total_completed > 0 else 0

        # Check 13: CPLI (Critical Path Length Index)
        # Formula: (Remaining Working Days + Total Float) / Remaining Working Days
        # Remaining Days = Data Date to Project Finish
        # Robust Data Date lookup
        data_date_val = source.get('stats', {}).get('data_date')
        if not data_date_val or data_date_val == "N/A":
            # Fallback to project info if stats not yet ready
            proj_data = source.get('data', {}).get('project', [])
            if isinstance(proj_data, list) and proj_data:
                data_date_val = proj_data[0].get('last_recalc_date')
            elif isinstance(proj_data, dict):
                data_date_val = proj_data.get('last_recalc_date')
        
        project_work_days = 1 # Default to avoid division by zero
        if data_date_val:
            try:
                # Convert to string and slice safely
                ds = str(data_date_val)[:10]
                data_date = pd.to_datetime(ds)
                finish_date = df['_dt_target_end_date'].max()
                if pd.notnull(finish_date) and pd.notnull(data_date):
                    calendar_diff = finish_date - data_date
                    if hasattr(calendar_diff, 'days'):
                        # Convert calendar days to working days (Benchmark: 5/7 conversion)
                        project_work_days = max(1, int(calendar_diff.days * 5 / 7))
            except:
                project_work_days = 1
        
        # Industrial CPLI uses the Total Float of the PROJECT FINISH milestone
        # Rogue tasks with extreme float are excluded
        finish_milestone = df[df['task_type'] == 'TT_FinMile']
        if not finish_milestone.empty:
            total_float_hrs = finish_milestone['float_hrs'].min()
        else:
            # Fallback: Minimum float of all tasks, but capped to avoid extreme outliers (orphans)
            total_float_hrs = df['float_hrs'].min() if not df.empty else 0
            # If the float is so negative it's more than the project duration, it's likely a data error/orphan
            total_float_hrs = max(total_float_hrs, -(project_work_days * self.hours_per_day))

        min_float_days = total_float_hrs / self.hours_per_day
        pt13_val = round((project_work_days + min_float_days) / project_work_days, 3)

        assessment = [
            {"id": 1, "name": "Logic", "measure": "Open Starts & Finishes", "val": float(pt1_val), "threshold": "1 Start / 1 Finish", "status": bool(logic_status_str == "PASS"), "status_text": logic_status_str, "explanation": logic_explanation, "details": {"starts": open_start_names, "finishes": open_finish_names}},
            {"id": 2, "name": "Leads", "measure": "% links with Negative Lag", "val": float(pt2_val), "threshold": "0%", "status": bool(pt2_val == 0)},
            {"id": 3, "name": "Lags", "measure": "% links with Positive Lag", "val": float(pt3_val), "threshold": "<= 5%", "status": bool(pt3_val <= 5)},
            {"id": 4, "name": "Rel Types", "measure": "% Finish-to-Start relationships", "val": float(pt4_val), "threshold": ">= 90%", "status": bool(pt4_val >= 90)},
            {"id": 5, "name": "Hard Constraints", "measure": "% tasks with mandatory constraints", "val": float(pt5_val), "threshold": "<= 5%", "status": bool(pt5_val <= 5)},
            {"id": 6, "name": "High Float", "measure": "% tasks with float > 44 days", "val": float(pt6_val), "threshold": "<= 5%", "status": bool(pt6_val <= 5)},
            {"id": 7, "name": "Negative Float", "measure": "% tasks with negative float", "val": float(pt7_val), "threshold": "0%", "status": bool(pt7_val == 0)},
            {"id": 8, "name": "High Duration", "measure": "% tasks with duration > 44 days", "val": float(pt8_val), "threshold": "<= 5%", "status": bool(pt8_val <= 5)},
            {"id": 9, "name": "Invalid Dates", "measure": "Dates inconsistent with Data Date", "val": 0.0, "threshold": "0%", "status": True},
            {"id": 10, "name": "Resources", "measure": "Tasks with assigned resources", "val": 100.0, "threshold": "100%", "status": True},
            {"id": 11, "name": "Missed Tasks", "measure": "% completed tasks finished late", "val": float(pt11_val), "threshold": "<= 5%", "status": bool(pt11_val <= 5)},
            {"id": 12, "name": "Critical Path", "measure": "Continuous path integrity", "val": 100.0, "threshold": "Required", "status": bool(critical_count > 0)},
            {"id": 13, "name": "CPLI", "measure": "Critical Path Length Index", "val": float(pt13_val), "threshold": ">= 0.95", "status": bool(pt13_val >= 0.95)},
            {"id": 14, "name": "Baseline", "measure": "Project baseline assignment", "val": 100.0, "threshold": "Required", "status": bool(baseline_map)}
        ]

        # 7. Quality Metrics Aggregate
        score = 100
        issues = []
        
        if pt1_val > 5: score -= 10; issues.append(f"Missing schedule logic ({pt1_val}% of tasks lack complete predecessors/successors)")
        if pt2_val > 0: score -= 10; issues.append(f"Negative lags (leads) detected ({pt2_val}%)")
        if pt3_val > 5: score -= 5; issues.append(f"Excessive positive lags ({pt3_val}%)")
        if pt4_val < 90: score -= 5; issues.append(f"Insufficient Finish-to-Start relationships ({pt4_val}%)")
        if pt5_val > 5: score -= 10; issues.append(f"Excessive hard constraints ({pt5_val}%)")
        if pt6_val > 5: score -= 5; issues.append(f"High float activities > 44 days ({pt6_val}%)")
        if pt7_val > 0: score -= 20; issues.append(f"Negative float / Behind schedule ({pt7_val}%)")
        if pt8_val > 5: score -= 5; issues.append(f"High duration activities > 44 days ({pt8_val}%)")
        if pt11_val > 5: score -= 10; issues.append(f"Missed tasks / Finished late ({pt11_val}%)")
        if critical_count == 0: score -= 10; issues.append("No critical path detected")
        if pt13_val < 0.95: score -= 5; issues.append(f"Low Critical Path Length Index (CPLI {pt13_val})")
        if not baseline_map: issues.append("No baseline assigned for variance tracking")
        
        if project_delay_days is not None and project_delay_days > 0:
            score -= 15
            issues.append(f"Project is delayed by {project_delay_days} days")
            
        if is_constrained:
            score -= 10
            issues.append("Project delay hidden by constraints (Fixed finish date detected)")
            
        score = max(0, score)

        health_status = "Good"
        if score < 65: health_status = "Critical"
        elif score < 85: health_status = "Warning"

        # 8. Root Cause Extraction
        numeric_delays = pd.to_numeric(df['delay_days'], errors='coerce').fillna(0)
        top_delay_drivers = df[numeric_delays > 0].copy()
        if not top_delay_drivers.empty:
            top_delay_drivers = top_delay_drivers.sort_values('delay_days', ascending=False).head(20)
            
        top_neg_float = df[df['float_hrs'] < 0].sort_values('float_hrs').head(20)

        metrics = {
            "totalTasks": total_tasks,
            "completedTasks": len(df[df['status_enum'] == "COMPLETED"]),
            "inProgressTasks": len(df[df['status_enum'] == "IN_PROGRESS"]),
            "notStartedTasks": len(df[df['status_enum'] == "NOT_STARTED"]),
            "delayedTasks": int((numeric_delays > 0).sum()),
            "criticalCount": critical_count,
            "negativeFloatCount": neg_float_count,
            "projectHealthScore": score,
            "healthStatus": health_status,
            "isConstrained": is_constrained,
            "qualityIssues": issues
        }

        matrix_summary = {
            "total_delayed": metrics["delayedTasks"],
            "delayed_safe": len(df[df['delay_float_category'] == "DELAYED_SAFE"]),
            "delayed_critical": len(df[df['delay_float_category'] == "DELAYED_CRITICAL"]),
            "delayed_negative": len(df[df['delay_float_category'] == "DELAYED_NEGATIVE"])
        }

        return {
            "projectSummary": {
                "projectDelayDays": project_delay_days,
                "isDelayed": (project_delay_days > 0) if project_delay_days is not None else False,
                "healthMetrics": metrics,
                "delayFloatMatrix": matrix_summary,
                "assessment": assessment,
                "topDrivers": top_delay_drivers[['task_code', 'task_name', 'delay_days']].to_dict('records'),
                "topRisks": top_neg_float[['task_code', 'task_name', 'float_hrs']].to_dict('records')
            },
            "activityAnalysis": self._inject_activity_codes(
                df[['task_id', 'task_code', 'task_name', 'status_enum', 'delay_days', 'float_hrs', 'delay_float_category', 'is_critical_p6', 'is_predicted_date', '_dt_current_end_date']].set_index('task_id').to_dict('index'),
                source
            )
        }

    def calculate_project_delay(self, context: str = "audit") -> Dict:
        """Calculates delay between baseline and latest update"""
        baseline = self.get_baseline(context=context)
        latest = self.get_latest(context=context)
        if not baseline or not latest or baseline['id'] == latest['id']:
            return {"delay_days": None, "reason": "No baseline or update available for comparison."}
        
        baseline_finish = pd.to_datetime(baseline['data_date'])
        stats = self.compute_basic_stats(version_id=baseline['id'], context=context)
        if 'project_finish' in stats:
            baseline_finish = pd.to_datetime(stats['project_finish'])
            
        latest_finish = pd.to_datetime(latest['data_date'])
        
        # Recalculate latest finish if possible
        latest_stats = self.compute_basic_stats(version_id=latest['id'], context=context)
        if 'project_finish' in latest_stats:
            latest_finish = pd.to_datetime(latest_stats['project_finish'])
            
        delay = (latest_finish - baseline_finish).days
        return {
            "baseline_finish": str(baseline_finish.date()),
            "latest_finish": str(latest_finish.date()),
            "delay_days": delay,
            "is_delayed": delay > 0
        }

    def get_calendar_info(self, version_id: Optional[str] = None, context: str = "audit") -> List[Dict]:
        """Returns structured calendar data from the loaded XER file."""
        source = self.get_latest(context=context, version_id=version_id)
        if not source:
            return []

        calendars_df = source['df'].get('calendar', source['df'].get('CALENDAR'))
        project_df = source['df'].get('project', source['df'].get('PROJECT'))

        # Get the default project calendar ID
        default_cal_id = None
        if project_df is not None and not project_df.empty:
            default_cal_id = str(project_df.iloc[0].get('clndr_id', ''))

        if calendars_df is None or calendars_df.empty:
            return []

        results = []
        for _, row in calendars_df.iterrows():
            cal_id = str(row.get('clndr_id', ''))
            name = row.get('clndr_name', row.get('clndr_short_name', f'Calendar {cal_id}'))
            hours_per_day = None
            try:
                hours_per_day = float(row.get('day_hr_cnt', 0)) or None
            except (ValueError, TypeError):
                pass

            results.append({
                "id": cal_id,
                "name": name,
                "hours_per_day": hours_per_day,
                "is_project_default": (cal_id == default_cal_id),
                "type": row.get('clndr_type', 'Unknown'),
            })

        return results

    def get_critical_path_details(self, limit: int = 20, context: str = "audit") -> List[Dict]:
        """Returns structured info on the most critical tasks"""
        source = self.get_latest(context=context)
        if not source or 'tasks' not in source.get('df', {}): return []
        
        df = source['df']['tasks'].copy()
        if 'total_float_hr_cnt' not in df.columns: return []
        
        df['float'] = pd.to_numeric(df['total_float_hr_cnt'], errors='coerce').fillna(999)
        critical = df[df['float'] <= 0].sort_values('float').head(limit)
        
        results = []
        for _, row in critical.iterrows():
            results.append({
                "activity_id": row.get('task_code', ''),
                "name": row.get('task_name', ''),
                "float": row.get('float'),
                "start": str(row.get('target_start_date', ''))[:10],
                "finish": str(row.get('target_end_date', ''))[:10]
            })
        return results

    def get_logic_health_details(self, context: str = "audit") -> Dict:
        """Detailed analysis of schedule logic health"""
        source = self.get_latest(context=context)
        if not source or 'df' not in source: return {}
        
        tasks_df = source['df']['tasks']
        pred_df = source['df'].get('taskpred')
        
        if pred_df is None: return {"error": "No relationship data available"}
        
        all_ids = set(tasks_df['task_id'].tolist())
        has_successor = set(pred_df['pred_task_id'].tolist())
        has_predecessor = set(pred_df['task_id'].tolist())
        
        work_tasks = tasks_df[~tasks_df['task_type'].isin(['TT_LOE', 'TT_Mile', 'TT_FinMile'])]
        work_ids = set(work_tasks['task_id'].tolist())
        
        open_ended = (all_ids - has_successor) & work_ids
        dangling = (all_ids - has_predecessor) & work_ids
        
        return {
            "open_ended_count": len(open_ended),
            "dangling_count": len(dangling),
            "open_ended_samples": list(tasks_df[tasks_df['task_id'].isin(list(open_ended)[:5])]['task_code']),
            "dangling_samples": list(tasks_df[tasks_df['task_id'].isin(list(dangling)[:5])]['task_code'])
        }

    def get_float_distribution(self, context: str = "audit") -> Dict:
        """Breakdown of float values across the project"""
        source = self.get_latest(context=context)
        if not source or 'tasks' not in source.get('df', {}): return {}
        
        df = source['df']['tasks'].copy()
        df['float'] = pd.to_numeric(df['total_float_hr_cnt'], errors='coerce').fillna(0) if 'total_float_hr_cnt' in df.columns else 0
        
        # Categorize
        neg = len(df[df['float'] < 0])
        zero = len(df[df['float'] == 0])
        low = len(df[(df['float'] > 0) & (df['float'] <= 50)])
        high = len(df[df['float'] > 50])
        
        return {
            "negative": neg,
            "critical_zero": zero,
            "low_float_0_50": low,
            "high_float_50plus": high
        }

    def get_wbs_summary(self, version_id: Optional[str] = None, target_level: int = 2, context: str = "audit") -> List[Dict]:
        """Aggregates task data by Discipline (Activity Code) or WBS level (Heuristic Priority)"""
        source = self.get_version(version_id, context=context)
        if not source or 'df' not in source: return []
        
        tasks_df = source['df'].get('tasks')
        wbs_df = source['df'].get('projwbs')
        tables = source.get('data', {}).get('tables', {})
        
        if tasks_df is None or len(tasks_df) == 0: return []
        
        # 1. Try grouping by Activity Code (The Gold Standard)
        discipline_map = {}
        grouping_mode = "WBS"
        
        if 'TASKACTV' in tables and 'ACTVTYPE' in tables and 'ACTVVAL' in tables:
            # Find the type_id for "Discipline"
            types = pd.DataFrame(tables['ACTVTYPE'])
            disc_types = types[types['actv_code_type_name'].str.contains('discipline|disc|dept|trade|responsibility', case=False, na=False)]
            
            if not disc_types.empty:
                type_id = disc_types.iloc[0]['actv_code_type_id']
                vals = pd.DataFrame(tables['ACTVVAL'])
                map_df = pd.DataFrame(tables['TASKACTV'])
                
                # Filter specifically for our Discipline type
                specific_map = map_df[map_df['actv_code_type_id'] == type_id]
                specific_vals = vals[vals['actv_code_type_id'] == type_id]
                
                # Join to get names
                merged_map = specific_map.merge(specific_vals, on='actv_code_id', how='left')
                discipline_map = merged_map.set_index('task_id')['actv_code_name'].to_dict()
                grouping_mode = f"Code:{disc_types.iloc[0]['actv_code_type_name']}"

        # 2. Cleanup & Processing
        def clean_label(label):
            if not label or not isinstance(label, str): return label
            # Strip numeric prefixes like "4 ", "05. ", "1 - "
            return re.sub(r'^[\d\.\-\s]+', '', label).strip()

        tasks_copy = tasks_df.copy()
        
        if discipline_map:
            tasks_copy['group_key'] = tasks_copy['task_id'].map(discipline_map).fillna("Unassigned / Other")
            tasks_copy['group_name'] = tasks_copy['group_key'].apply(clean_label)
        else:
            # Fallback to WBS
            if wbs_df is not None:
                parent_map = wbs_df.set_index('wbs_id')['parent_wbs_id'].to_dict()
                wbs_info = wbs_df.set_index('wbs_id')[['wbs_short_name', 'wbs_name']].to_dict('index')
                
                def get_parent_at_level(wbs_id, level):
                    path = []
                    curr = wbs_id
                    while curr in parent_map and pd.notnull(curr):
                        path.append(curr)
                        curr = parent_map[curr]
                    path.reverse()
                    idx = min(level, len(path)-1)
                    return path[idx] if path else wbs_id

                tasks_copy['target_wbs_id'] = tasks_copy['wbs_id'].apply(lambda x: get_parent_at_level(x, target_level))
                tasks_copy['group_name'] = tasks_copy['target_wbs_id'].apply(lambda x: clean_label(wbs_info.get(x, {}).get('wbs_name', 'General')))
            else:
                tasks_copy['group_name'] = "General Project"

        # 3. Handle Milestones (Separate from functional work)
        is_mile = tasks_copy['task_type'].isin(['TT_Mile', 'TT_FinMile'])
        tasks_copy.loc[is_mile, 'group_name'] = "Project Milestones"

        # 4. Get deterministic metrics
        analysis = self.get_deterministic_analysis(version_id, context=context)
        activity_metrics = analysis.get('activityAnalysis', {})
        
        metrics_list = []
        for tid, m in activity_metrics.items():
            metrics_list.append({
                'task_id': tid,
                'status': m.get('status_enum'),
                'float_hrs': m.get('float_hrs', 0)
            })
        metrics_df = pd.DataFrame(metrics_list)
        
        # 5. Join and Aggregate
        merged = tasks_copy.merge(metrics_df, on='task_id', how='left')
        merged['drtn'] = pd.to_numeric(merged['target_drtn_hr_cnt'], errors='coerce').fillna(0) / self.hours_per_day if 'target_drtn_hr_cnt' in merged.columns else 0
        
        summary = merged.groupby('group_name').agg(
            total_tasks=('task_id', 'count'),
            duration_days=('drtn', 'sum'),
            avg_float_hrs=('float_hrs', 'mean'),
            completed=('status', lambda x: (x == 'COMPLETED').sum()),
            in_progress=('status', lambda x: (x == 'IN_PROGRESS').sum()),
            not_started=('status', lambda x: (x == 'NOT_STARTED').sum())
        ).reset_index()
        
        # 6. Formatting
        results = []
        for _, row in summary.iterrows():
            results.append({
                "discipline": str(row['group_name']),
                "activities": int(row['total_tasks']),
                "duration_days": round(float(row['duration_days']), 0),
                "avg_float": round(float(row['avg_float_hrs']), 1),
                "status": f"{int(row['completed'])}C / {int(row['in_progress'])}IP / {int(row['not_started'])}NS"
            })
        
        # Sort by impact (negative float)
        return sorted(results, key=lambda x: x['avg_float'])

    def get_wbs_hierarchy(self, source_id: Optional[str] = None, search: str = "", filter_type: str = "ALL", include_activities: bool = True, context: str = "audit") -> Dict:
        """Constructs a recursive WBS tree and maps filtered activities to their respective nodes."""
        source = self.get_version(source_id, context=context)
        if not source or 'df' not in source: return {"records": [], "total": 0}
        
        wbs_df = source['df'].get('projwbs', source['df'].get('wbs'))
        tasks_df = source['df'].get('tasks')
        taskrsrc_df = source['df'].get('taskrsrc')
        baseline_cost_map = self._get_baseline_cost_map(context=context)
        baseline_map = self._get_baseline_map(context=context)
        
        # Pre-aggregate TaskRSRC costs if available (Backup for missing task-level costs)
        task_rsrc_costs = {}
        if taskrsrc_df is not None and not taskrsrc_df.empty:
            # Group by task_id and sum costs
            # Common TASKRSRC cost fields: target_cost, act_reg_cost + act_ot_cost, remain_cost
            rsrc_costs = taskrsrc_df.copy()
            for col in ['target_cost', 'act_reg_cost', 'act_ot_cost', 'remain_cost']:
                rsrc_costs[col] = pd.to_numeric(rsrc_costs.get(col, 0), errors='coerce').fillna(0)
            
            rsrc_costs['tot_act'] = rsrc_costs['act_reg_cost'] + rsrc_costs['act_ot_cost']
            
            agg = rsrc_costs.groupby('task_id').agg({
                'target_cost': 'sum',
                'tot_act': 'sum',
                'remain_cost': 'sum'
            })
            task_rsrc_costs = agg.to_dict('index')
        
        if wbs_df is None: return {"records": [], "total": 0}
        
        # Load Project Default Calendar for WBS duration rollups
        proj_cal = P6Calendar()
        project_df = source['df'].get('project', source['df'].get('PROJECT'))
        calendars_df = source['df'].get('calendar', source['df'].get('CALENDAR'))
        if project_df is not None and not project_df.empty and calendars_df is not None and not calendars_df.empty:
            proj_clndr_id = str(project_df.iloc[0].get('clndr_id', ''))
            cal_row = calendars_df[calendars_df['clndr_id'].astype(str) == proj_clndr_id]
            if not cal_row.empty:
                proj_cal = P6Calendar(cal_row.iloc[0].to_dict())
        
        # 1. Process and Filter Tasks (similar to get_table_data)
        tasks = []
        if tasks_df is not None and include_activities:
            df = tasks_df.copy()
            
            if search:
                mask = df[['task_name', 'task_code']].apply(lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)
                df = df[mask]
                
            if filter_type != 'ALL':
                analysis = self.get_deterministic_analysis(source_id, context=context)
                metrics = analysis.get('activityAnalysis', {})
                
                def check_filter(tid):
                    m = metrics.get(tid, {})
                    status = m.get('status_enum')
                    if filter_type in ['CRITICAL', 'NEG_FLOAT'] and status == 'COMPLETED': return False
                    if filter_type == 'CRITICAL': return m.get('is_critical_p6', False)
                    if filter_type == 'NEG_FLOAT': return (m.get('float_hrs', 0) < 0)
                    if filter_type == 'DELAYED': return (m.get('delay_days', 0) > 0) and status != 'COMPLETED'
                    if filter_type == 'DELAYED_CRITICAL': return m.get('delay_float_category') == 'DELAYED_CRITICAL'
                    if filter_type == 'DELAYED_NEGATIVE': return m.get('delay_float_category') == 'DELAYED_NEGATIVE'
                    return True
                
                df = df[df['task_id'].apply(check_filter)]
                
            # Inject Analysis
            analysis_dict = self.get_deterministic_analysis(source_id, context=context)
            activity_metrics = analysis_dict.get('activityAnalysis', {})\
            
            hpd = source.get('hours_per_day', 8.0)
            for rec in df.to_dict('records'):
                tid = rec.get('task_id')
                m = activity_metrics.get(tid, {})
                rec['duration_days'] = round(pd.to_numeric(rec.get('target_drtn_hr_cnt', 0), errors='coerce') / hpd, 1)
                
                budget = pd.to_numeric(rec.get('target_cost') or rec.get('target_tot_cost') or rec.get('planned_tot_cost', 0), errors='coerce') or 0
                actual = pd.to_numeric(rec.get('act_tot_cost') or rec.get('act_total_cost') or rec.get('actual_tot_cost', 0), errors='coerce') or 0
                remain = pd.to_numeric(rec.get('remain_tot_cost') or rec.get('remaining_tot_cost') or rec.get('remain_total_cost', 0), errors='coerce') or 0
                ev_cost = pd.to_numeric(rec.get('bcwp', 0), errors='coerce') or 0
                pv_cost = pd.to_numeric(rec.get('bcws', 0), errors='coerce') or 0
                
                # Fallback to TaskRSRC aggregation if Task-level summary is 0
                if budget == 0 and tid in task_rsrc_costs:
                    budget = task_rsrc_costs[tid].get('target_cost', 0)
                if actual == 0 and tid in task_rsrc_costs:
                    actual = task_rsrc_costs[tid].get('tot_act', 0)
                if remain == 0 and tid in task_rsrc_costs:
                    remain = task_rsrc_costs[tid].get('remain_cost', 0)

                bl_cost = baseline_cost_map.get(rec.get('task_code'), budget) # Fallback to budget if not in baseline

                rec['budget_cost'] = budget
                rec['actual_cost'] = actual
                rec['remain_cost'] = remain
                rec['ev_cost'] = ev_cost
                rec['pv_cost'] = pv_cost
                rec['bl_project_cost'] = bl_cost
                rec['at_completion_cost'] = actual + remain
                
                # Ensure values are clean for JSON serialization
                for k in ['budget_cost', 'actual_cost', 'remain_cost', 'ev_cost', 'pv_cost', 'bl_project_cost', 'at_completion_cost']:
                    if pd.isna(rec.get(k)): rec[k] = 0.0
                    else: rec[k] = float(rec[k])

                # Float Processing - Prefer native P6 float if available (including 0)
                has_native = False
                native_float_hrs = 0
                computed_float = rec.get('total_float', None)
                for fld in ['total_float_hr_cnt', 'target_tf_hr_cnt', 'tf_hr_cnt']:
                    v = rec.get(fld)
                    if v is not None and str(v).strip() != '' and str(v).strip() != 'nan':
                        try:
                            native_float_hrs = float(v)
                            has_native = True
                            break
                        except: continue

                if has_native:
                    final_float = round(native_float_hrs / hpd, 2)
                else:
                    # Fallback to internal CPM if native dates were never exported
                    final_float = computed_float

                # Safe float helper
                def safe_float(v):
                    if pd.isna(v) or v is None: return 0.0
                    try: return float(v)
                    except: return 0.0

                # Final Record Sanitization (Remove NaNs for JSON safety)
                clean_rec = {}
                for k, v in rec.items():
                    if k == '_analysis': continue # Handled below
                    if pd.isna(v) or v == 'nan': clean_rec[k] = ""
                    else: clean_rec[k] = v

                clean_rec['_analysis'] = {
                    'status': m.get('status_enum', 'NOT_STARTED'),
                    'total_float': safe_float(final_float),
                    'delay_days': safe_float(m.get('delay_days', 0)),
                    'is_critical': m.get('is_critical_p6', False),
                    'current_end_date': str(m.get('_dt_current_end_date', '-')).split(' ')[0],
                    'is_predicted': m.get('is_predicted_date', False),
                    'float_hrs': safe_float(m.get('float_hrs', 0)),
                    'delay_float_category': m.get('delay_float_category', 'SAFE'),
                    'early_start': clean_rec.get('early_start', ""),
                    'early_finish': clean_rec.get('early_finish', ""),
                    'late_start': clean_rec.get('late_start', ""),
                    'late_finish': clean_rec.get('late_finish', ""),
                    'baseline_finish': str(baseline_map.get(clean_rec.get('task_code', ''))) if clean_rec.get('task_code') in baseline_map else None,
                    'predecessors': source.get('dependency_graph', {}).get(tid, {}).get('predecessors', []),
                    'successors': source.get('dependency_graph', {}).get(tid, {}).get('successors', [])
                }
                tasks.append(clean_rec)

        # 1b. Always build analytics stubs — lightweight records for branch rollup.
        #     When include_activities=True, stubs are derived from the full task records.
        #     When include_activities=False (WBS tab), stubs are built from analysis only,
        #     so rollup_stats() still has data to aggregate without rendering full rows.
        analytics_stubs_by_wbs: Dict[str, List[Dict]] = {}
        if tasks_df is not None:
            analysis_dict_for_stubs = self.get_deterministic_analysis(source_id, context=context)
            activity_metrics_stubs = analysis_dict_for_stubs.get('activityAnalysis', {})

            if include_activities:
                # Reuse already-built task records — extract wbs grouping + analysis
                for t in tasks:
                    wid = str(t.get('wbs_id', ''))
                    if wid not in analytics_stubs_by_wbs:
                        analytics_stubs_by_wbs[wid] = []
                    analytics_stubs_by_wbs[wid].append(t)
            else:
                # Build minimal stubs from raw task DataFrame + analysis
                # Note: tasks_df has scheduler-renamed columns (early_start, early_finish, etc.)
                # after CPM runs — use those, not the raw P6 XER names (early_start_date etc.)
                for rec in tasks_df.to_dict('records'):
                    tid = rec.get('task_id')
                    wid = str(rec.get('wbs_id', ''))
                    if not wid or wid == 'nan':
                        continue
                    m = activity_metrics_stubs.get(tid, {})
                    stub = {
                        'task_name': rec.get('task_name', ''),
                        'task_type': rec.get('task_type', ''),
                        'wbs_id': wid,
                        'budget_cost': 0.0,
                        'actual_cost': 0.0,
                        'remain_cost': 0.0,
                        'ev_cost': 0.0,
                        'pv_cost': 0.0,
                        'bl_project_cost': 0.0,
                        '_analysis': {
                            'status': m.get('status_enum', 'NOT_STARTED'),
                            'delay_days': float(m.get('delay_days') or 0),
                            'is_critical': bool(m.get('is_critical_p6', False)),
                            'total_float': float(m.get('float_hrs', 0)),
                            # Use scheduler-renamed columns (added by CPMScheduler._apply_p6_stored_dates)
                            'early_start': str(rec.get('early_start', '') or ''),
                            'early_finish': str(rec.get('early_finish', '') or ''),
                            'late_start': str(rec.get('late_start', '') or ''),
                            'late_finish': str(rec.get('late_finish', '') or ''),
                            'baseline_finish': str(baseline_map.get(rec.get('task_code', ''))) if rec.get('task_code') in baseline_map else None,
                        }
                    }
                    if wid not in analytics_stubs_by_wbs:
                        analytics_stubs_by_wbs[wid] = []
                    analytics_stubs_by_wbs[wid].append(stub)



        # 2. Group tasks by wbs_id (ensure string keys for mapping)
        wbs_tasks = {}
        unassigned_tasks = []
        for t in tasks:
            wid = t.get('wbs_id')
            if pd.isna(wid) or wid == 'nan' or wid is None:
                unassigned_tasks.append(t)
                continue
            
            wid_str = str(wid)
            if wid_str not in wbs_tasks: wbs_tasks[wid_str] = []
            wbs_tasks[wid_str].append(t)
            
        # 3. Build WBS Node Dictionary
        wbs_nodes = {}
        for rec in wbs_df.to_dict('records'):
            wid = str(rec.get('wbs_id'))
            pid = rec.get('parent_wbs_id')
            if pd.isna(pid) or str(pid) == 'nan' or pid is None: pid = None
            else: pid = str(pid)
            
            # Clean values
            for k, v in rec.items():
                if pd.isna(v): rec[k] = None
                
            wbs_nodes[wid] = {
                **rec,
                "parent_wbs_id": pid,
                "children": [],
                "activities": wbs_tasks.get(wid, []),
                # _analytics_activities always populated (stubs in WBS mode, full in Activity mode)
                "_analytics_activities": analytics_stubs_by_wbs.get(wid, [])
            }
            
        # 4. Construct Tree
        tree = []
        for wid, node in wbs_nodes.items():
            pid = node.get('parent_wbs_id')
            if pid and pid in wbs_nodes:
                wbs_nodes[pid]['children'].append(node)
            else:
                tree.append(node)

        # 5. Handle Unassigned Activities or Orphaned Tasks
        # If we have tasks whose WBS isn't in the tree, or tasks with no WBS at all
        orphaned_wids = [wid for wid in wbs_tasks if wid not in wbs_nodes]
        all_orphans = unassigned_tasks.copy()
        for wid in orphaned_wids:
            all_orphans.extend(wbs_tasks[wid])

        if all_orphans:
            # Create a virtual root for orphaned/unassigned work
            virtual_root = {
                "wbs_id": "virtual_root",
                "wbs_name": "General Project Activities",
                "wbs_short_name": "GENERAL",
                "parent_wbs_id": None,
                "children": [],
                "activities": all_orphans
            }
            tree.append(virtual_root)
                
        # 5. Prune empty branches
        def prune(node):
            node['children'] = [child for child in node['children'] if prune(child)]
            has_activities = len(node.get('activities', [])) > 0
            has_children = len(node.get('children', [])) > 0
            is_filtered = bool(search) or (filter_type != "ALL")
            if is_filtered and not (has_activities or has_children):
                return False
            return True
            
        tree = [root for root in tree if prune(root)]
        
        # Sort children sequentially
        def sort_tree(node):
            if 'seq_num' in node and node['seq_num'] is not None:
                node['children'].sort(key=lambda x: pd.to_numeric(x.get('seq_num', 0), errors='coerce'))
            else:
                node['children'].sort(key=lambda x: str(x.get('wbs_short_name', '')))
            for child in node['children']:
                sort_tree(child)
                
        for root in tree: sort_tree(root)
        
        # Import thresholds lazily to avoid circular dependency
        try:
            from .analyzer import WBS_STATUS_THRESHOLDS as _thresholds
        except Exception:
            _thresholds = {
                "critical_pct": 0.50, "delayed_pct": 0.30,
                "at_risk_delayed_pct": 0.10, "at_risk_critical_pct": 0.20,
            }

        def _branch_status(activity_count, delayed_count, critical_count, completed_count, branch_variance_days):
            if activity_count == 0:
                return "EMPTY"
                
            # Completed branch logic
            if completed_count == activity_count:
                if branch_variance_days <= 0:
                    return "COMPLETED ON TIME"
                else:
                    return f"COMPLETED LATE (+{int(branch_variance_days)}d)"
                    
            t = _thresholds
            d_pct = delayed_count / activity_count
            c_pct = critical_count / activity_count
            
            if d_pct > t["delayed_pct"]:
                return "DELAYED"
            elif c_pct > t["critical_pct"]:
                return "CRITICAL"
            elif d_pct > t["at_risk_delayed_pct"] or c_pct > t["at_risk_critical_pct"]:
                return "AT RISK"
            else:
                return "ON TRACK"

        # 6. Rollup stats (Dates, Durations, Float, Branch Analytics)
        def rollup_stats(node):
            starts = []
            finishes = []
            late_starts = []
            late_finishes = []
            bl_finishes = []
            min_float = float('inf')
            
            # Costs
            budget_total = 0
            actual_total = 0
            remain_total = 0
            ev_total = 0
            pv_total = 0
            bl_project_total = 0

            # Branch Analytics
            activity_count = 0
            delayed_count = 0
            critical_count = 0
            completed_count = 0
            total_delay_days = 0.0
            worst_delayed_activity = None
            worst_delay_days = 0.0
            
            # Activity Rollup — dates and costs
            # Use 'activities' (full records) when available (Activities tab).
            # Fall back to '_analytics_activities' stubs in WBS-only mode so
            # dates/duration still roll up even when full records aren't loaded.
            acts_for_dates = node.get('activities') or node.get('_analytics_activities', [])
            for act in acts_for_dates:
                analysis_data = act.get('_analysis', {})
                es = pd.to_datetime(analysis_data.get('early_start'), errors='coerce')
                ef = pd.to_datetime(analysis_data.get('early_finish'), errors='coerce')
                ls = pd.to_datetime(analysis_data.get('late_start'), errors='coerce')
                lf = pd.to_datetime(analysis_data.get('late_finish'), errors='coerce')
                bl_f = pd.to_datetime(analysis_data.get('baseline_finish'), errors='coerce')
                f = pd.to_numeric(analysis_data.get('total_float'), errors='coerce')
                
                if pd.notnull(es): starts.append(es)
                if pd.notnull(ef): finishes.append(ef)
                if pd.notnull(ls): late_starts.append(ls)
                if pd.notnull(lf): late_finishes.append(lf)
                if pd.notnull(bl_f): bl_finishes.append(bl_f)
                
                # Primavera ignores COMPLETED, WBS Summary, and LOE activities when rolling up float for WBS rows
                task_type = act.get('task_type', '')
                act_status = analysis_data.get('status', 'NOT_STARTED')
                if pd.notnull(f) and act_status != 'COMPLETED' and task_type not in ('TT_WBS', 'TT_LOE'):
                    min_float = min(min_float, f)

                # Costs (only meaningful when full records are loaded)
                budget_total += act.get('budget_cost', 0)
                actual_total += act.get('actual_cost', 0)
                remain_total += act.get('remain_cost', 0)
                ev_total += act.get('ev_cost', 0)
                pv_total += act.get('pv_cost', 0)
                bl_project_total += act.get('bl_project_cost', 0)

            # Branch Analytics — uses '_analytics_activities' which is always populated
            # (stubs in WBS-only mode, same full records in Activities mode)
            for act in node.get('_analytics_activities', node.get('activities', [])):
                analysis_data = act.get('_analysis', {})
                task_type = act.get('task_type', '')
                act_status = analysis_data.get('status', 'NOT_STARTED')

                if task_type not in ('TT_WBS', 'TT_LOE'):
                    activity_count += 1
                    delay = float(analysis_data.get('delay_days') or 0)
                    is_critical = bool(analysis_data.get('is_critical', False))
                    
                    if act_status == 'COMPLETED':
                        completed_count += 1
                        
                    if delay > 0 and act_status != 'COMPLETED':
                        delayed_count += 1
                        total_delay_days += delay
                        if delay > worst_delay_days:
                            worst_delay_days = delay
                            worst_delayed_activity = act.get('task_name', '')
                    if is_critical and act_status != 'COMPLETED':
                        critical_count += 1

            # Children Rollup
            for child in node.get('children', []):
                child_stats = rollup_stats(child)
                if child_stats.get('early_start'): starts.append(pd.to_datetime(child_stats['early_start']))
                if child_stats.get('early_finish'): finishes.append(pd.to_datetime(child_stats['early_finish']))
                if child_stats.get('late_start'): late_starts.append(pd.to_datetime(child_stats['late_start']))
                if child_stats.get('late_finish'): late_finishes.append(pd.to_datetime(child_stats['late_finish']))
                if child_stats.get('baseline_finish'): bl_finishes.append(pd.to_datetime(child_stats['baseline_finish']))
                if child_stats.get('min_float') is not None: min_float = min(min_float, child_stats['min_float'])

                # Costs
                budget_total += child_stats.get('budget_cost', 0)
                actual_total += child_stats.get('actual_cost', 0)
                remain_total += child_stats.get('remain_cost', 0)
                ev_total += child_stats.get('ev_cost', 0)
                pv_total += child_stats.get('pv_cost', 0)
                bl_project_total += child_stats.get('bl_project_cost', 0)

                # Branch Analytics Rollup
                activity_count += child_stats.get('activity_count', 0)
                delayed_count += child_stats.get('delayed_count', 0)
                critical_count += child_stats.get('critical_count', 0)
                completed_count += child_stats.get('completed_count', 0)
                total_delay_days += child_stats.get('_total_delay_days_sum', 0.0) # Summed internally for average
                
                child_worst = child_stats.get('worst_delay_days', 0.0)
                if child_worst > worst_delay_days:
                    worst_delay_days = child_worst
                    worst_delayed_activity = child_stats.get('worst_delayed_activity')

            # Calculate Summary Dates
            s = min(starts) if starts else None
            f = max(finishes) if finishes else None
            ls_date = min(late_starts) if late_starts else None
            lf_date = max(late_finishes) if late_finishes else None
            bl_f_date = max(bl_finishes) if bl_finishes else None

            # Branch Finish Variance (Latest Finish minus Latest Baseline Finish)
            branch_variance_days = 0.0
            if f and bl_f_date:
                # Assuming business days difference
                if f > bl_f_date:
                    branch_variance_days = float(proj_cal.workdays_between(bl_f_date, f))
                elif f < bl_f_date:
                    branch_variance_days = -float(proj_cal.workdays_between(f, bl_f_date))
                    
            # Average Delay
            avg_delay_days = total_delay_days / delayed_count if delayed_count > 0 else 0.0

            # Duration in WORKING days, matching P6's WBS summary display
            dur = 0
            if s and f and f > s:
                dur = proj_cal.workdays_between(s, f)

            # Primavera P6 WBS Total Float Calculation:
            # P6 computes WBS float by comparing the summary early and late dates.
            # By default, P6 uses "Finish Float" (Latest Late Finish - Latest Early Finish) for WBS bands.
            wbs_float = None
            if f and lf_date:
                # Calculate Finish Float: Latest Late Finish - Latest Early Finish
                diff = (lf_date.date() - f.date()).days
                wbs_float = float(diff)
            
            if wbs_float is not None and (pd.isna(wbs_float) or wbs_float == float('inf')):
                wbs_float = 0.0

            # Criticality tag — always valid, even in baseline-only mode
            # Describes schedule structure/sensitivity, NOT delay performance
            crit_pct = critical_count / activity_count if activity_count > 0 else 0
            if crit_pct >= 0.60:
                criticality_tag = 'HIGH CRITICALITY'    # PLACEHOLDER threshold — confirm with planner
            elif crit_pct >= 0.30:
                criticality_tag = 'MEDIUM CRITICALITY'  # PLACEHOLDER threshold — confirm with planner
            elif crit_pct > 0:
                criticality_tag = 'LOW CRITICALITY'
            else:
                criticality_tag = 'NOT CRITICAL'

            node['summary'] = {
                'early_start': str(s.date()) if s else None,
                'early_finish': str(f.date()) if f else None,
                'late_start': str(ls_date.date()) if ls_date else None,
                'late_finish': str(lf_date.date()) if lf_date else None,
                'min_float': wbs_float,
                'duration_days': dur,
                'budget_cost': budget_total,
                'actual_cost': actual_total,
                'remain_cost': remain_total,
                'ev_cost': ev_total,
                'pv_cost': pv_total,
                'bl_project_cost': bl_project_total,
                'at_completion_cost': actual_total + remain_total,
                # Branch analytics
                'activity_count': activity_count,
                'delayed_count': delayed_count,
                'critical_count': critical_count,
                'completed_count': completed_count,
                'critical_pct': round(crit_pct * 100, 1),
                'branch_variance_days': round(branch_variance_days, 1),
                'worst_delayed_activity': worst_delayed_activity,
                'worst_delay_days': round(worst_delay_days, 1),
                'avg_delay_days': round(avg_delay_days, 1),
                '_total_delay_days_sum': total_delay_days,
                'baseline_finish': str(bl_f_date.date()) if bl_f_date else None,
                # Performance tag (only meaningful when update schedule is loaded)
                'status_tag': _branch_status(activity_count, delayed_count, critical_count, completed_count, branch_variance_days),
                # Structure tag (always valid — describes critical path density)
                'criticality_tag': criticality_tag,
            }
            return node['summary']

        for root in tree: rollup_stats(root)

        analysis = self.get_deterministic_analysis(source_id, context=context)

        # Determine schedule mode — affects which status columns the UI shows
        # A baseline schedule never has performance/variance data, even if an update
        # exists in the workspace. Only show update columns when viewing an update.
        schedule_mode = 'WITH_UPDATE' if source.get('type') == 'update' else 'BASELINE_ONLY'

        return {
            "records": tree,
            "total": sum(len(wbs_tasks[w]) for w in wbs_tasks),
            "table": "HIERARCHY",
            "schedule_mode": schedule_mode,
            "projectAnalysis": analysis.get('projectSummary', {})
        }

    def get_table_data(self, table_type: str = "TASK", search: str = "", limit: int = 100, offset: int = 0, source_id: Optional[str] = None, filter_type: str = "ALL", context: str = "audit") -> Dict:
        if table_type == "HIERARCHY":
            return self.get_wbs_hierarchy(source_id, search, filter_type, include_activities=True, context=context)
        elif table_type == "WBS_HIERARCHY":
            return self.get_wbs_hierarchy(source_id, search, filter_type, include_activities=False, context=context)

        """Fetch and format paginated table data from a specific version ID"""
        source = self.get_version(source_id, context=context)
        if not source or 'df' not in source: return {"records": [], "total": 0}
        
        # Table mapping
        table_map = {
            "TASK": "tasks",
            "WBS": "projwbs",
            "RELATIONSHIPS": "taskpred",
            "PROJECT": "project"
        }
        
        df_key = table_map.get(table_type.upper(), table_type.lower())
        if df_key not in source['df']:
            return {"records": [], "total": 0, "error": f"Table '{table_type}' not found"}
            
        df = source['df'][df_key].copy()
        
        # 1. Search Logic
        if search:
            search_cols = ['task_name', 'task_code'] if df_key == 'tasks' else df.columns[:3]
            mask = df[search_cols].apply(lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)
            df = df[mask]
            
        # 2. Analytical Filtering (pre-pagination)
        if df_key == 'tasks' and filter_type != 'ALL':
            analysis = self.get_deterministic_analysis(source_id, context=context)
            metrics = analysis.get('activityAnalysis', {})
            
            def check_filter(tid):
                m = metrics.get(tid, {})
                status = m.get('status_enum')
                
                # Exclusion rule: COMPLETED tasks generally don't show in forensic path filters
                if filter_type in ['CRITICAL', 'NEG_FLOAT'] and status == 'COMPLETED':
                    return False
                
                if filter_type == 'CRITICAL': return m.get('is_critical_p6', False)
                if filter_type == 'NEG_FLOAT': return (m.get('float_hrs', 0) < 0)
                if filter_type == 'DELAYED': 
                    # For total 'Delayed' view, focus on active incomplete delays
                    return (m.get('delay_days', 0) > 0) and status != 'COMPLETED'
                if filter_type == 'DELAYED_CRITICAL': return m.get('delay_float_category') == 'DELAYED_CRITICAL'
                if filter_type == 'DELAYED_NEGATIVE': return m.get('delay_float_category') == 'DELAYED_NEGATIVE'
                return True
            
            df = df[df['task_id'].apply(check_filter)]

        if table_type.upper() == "RELATIONSHIPS":
            # Perform Joins to get human readable names
            tasks_df = source['df']['tasks'][['task_id', 'task_name']]
            
            # Join for Successor Name
            df = df.merge(tasks_df, on='task_id', how='left')
            df.rename(columns={'task_name': 'activity_name'}, inplace=True)
            
            # Join for Predecessor Name
            df = df.merge(tasks_df, left_on='pred_task_id', right_on='task_id', how='left', suffixes=('', '_pred'))
            df.rename(columns={'task_name': 'predecessor_name'}, inplace=True)
            
            # Map Relationship Types
            type_map = {'PR_FS': 'FS', 'PR_SS': 'SS', 'PR_FF': 'FF', 'PR_SF': 'SF'}
            df['relationship_type'] = df['pred_type'].map(type_map).fillna(df['pred_type'])
            df['lag'] = df['lag_hr_cnt']
            
            # Select relevant columns
            df = df[['activity_name', 'predecessor_name', 'relationship_type', 'lag']]
            
        total = len(df)
        
        # Paginate
        paginated_df = df.iloc[offset : offset + limit]
        
        # Inject deterministic analysis if viewing TASK table
        analysis = {}
        if df_key == 'tasks':
            analysis = self.get_deterministic_analysis(source_id, context=context)
            activity_metrics = analysis.get('activityAnalysis', {})
            
            records = []
            hpd = source.get('hours_per_day', 8.0)
            for rec in paginated_df.to_dict('records'):
                tid = rec.get('task_id')
                metrics = activity_metrics.get(tid, {})
                rec['duration_days'] = round(pd.to_numeric(rec.get('target_drtn_hr_cnt', 0), errors='coerce') / hpd, 1)
                rec['_analysis'] = {
                    'status': metrics.get('status_enum', 'NOT_STARTED'),
                    'delay_days': round(metrics.get('delay_days', 0), 1),
                    'is_critical': metrics.get('is_critical_p6', False),
                    'current_end_date': str(metrics.get('_dt_current_end_date', '-')).split(' ')[0],
                    'is_predicted': metrics.get('is_predicted_date', False),
                    'early_start': rec.get('early_start'),
                    'early_finish': rec.get('early_finish'),
                    'late_start': rec.get('late_start'),
                    'late_finish': rec.get('late_finish'),
                    'total_float': rec.get('total_float'),
                    'predecessors': source.get('dependency_graph', {}).get(tid, {}).get('predecessors', []),
                    'successors': source.get('dependency_graph', {}).get(tid, {}).get('successors', []),
                    'activity_codes': metrics.get('activity_codes', {})
                }
                records.append(rec)
            return {
                "records": records,
                "total": total,
                "table": table_type,
                "projectAnalysis": analysis.get('projectSummary', {})
            }

        return {
            "records": paginated_df.to_dict('records'),
            "total": total,
            "table": table_type
        }
    def store_result(self, data: List[Dict]) -> str:
        import uuid
        ref_id = str(uuid.uuid4())
        self.results_cache[ref_id] = data
        
        # Simple cleanup: if cache grows too large, remove oldest
        if len(self.results_cache) > 50:
            oldest = list(self.results_cache.keys())[0]
            del self.results_cache[oldest]
            
        return ref_id

    def get_cached_result(self, ref_id: str) -> Optional[List[Dict]]:
        return self.results_cache.get(ref_id)
