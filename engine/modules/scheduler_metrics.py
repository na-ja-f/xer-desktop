from typing import Dict, List, Optional, Set
import logging

logger = logging.getLogger(__name__)

class SchedulerMetrics:
    """
    Single Source of Truth (SSOT) for all scheduling metrics.
    All orchestration tools must use this module to prevent contradictory answers.
    """

    @staticmethod
    def compute_core_metrics(acts: Dict[str, Dict], graph: Dict) -> Dict:
        """
        Computes the core metrics from the deterministic activity analysis and relationship graph.
        """
        total_activities = len(acts)
        critical_activities = []
        non_critical_activities = []
        critical_ids = set()

        for tid, a in acts.items():
            if a.get("status_enum") == "COMPLETED":
                # Typically completed activities are not critical moving forward, but let's strictly count
                pass

            # Safe check
            is_crit = a.get("is_critical_p6", False)
            tf = a.get("float_hrs", 0)
            try:
                tf_val = float(tf) if tf is not None else 0.0
            except ValueError:
                tf_val = 0.0

            if (tf_val <= 0) or is_crit:
                if a.get("status_enum") != "COMPLETED":
                    critical_activities.append({"id": tid, **a})
                    critical_ids.add(tid)
            else:
                non_critical_activities.append({"id": tid, **a})

        # Build isolated critical path relationship graph
        crit_graph = {tid: {"preds": set(), "succs": set()} for tid in critical_ids}
        
        for tid in critical_ids:
            node = graph.get(tid, {})
            for p in node.get("predecessors", []):
                pid = p.get("id", p.get("task_id"))
                if pid in critical_ids:
                    crit_graph[tid]["preds"].add(pid)
                    crit_graph[pid]["succs"].add(tid)
            for s in node.get("successors", []):
                sid = s.get("id", s.get("task_id"))
                if sid in critical_ids:
                    crit_graph[tid]["succs"].add(sid)
                    crit_graph[sid]["preds"].add(tid)

        return {
            "total_activities": total_activities,
            "critical_count": len(critical_activities),
            "non_critical_count": len(non_critical_activities),
            "critical_activities": critical_activities,
            "non_critical_activities": non_critical_activities,
            "critical_ids": critical_ids,
            "relationship_graph": graph,
            "critical_relationship_graph": crit_graph
        }

    @staticmethod
    def evaluate_critical_path_continuity(metrics: Dict) -> Dict:
        """
        Evaluates the continuity of the critical path using the SSOT metrics.
        Returns a structured dictionary matching the strict response contract.
        """
        critical_count = metrics["critical_count"]
        total_activities = metrics["total_activities"]
        
        if critical_count == 0 and total_activities > 0:
            logger.error("Data inconsistency detected in scheduling metrics: 0 critical activities but project has activities.")
            # We raise or return an error flag for the UI
            return {
                "success": False,
                "critical_count": 0,
                "continuity_status": "FAIL",
                "reason": "Missing relationships or invalid float calculation caused 0 critical activities.",
                "data_consistent": False
            }

        if critical_count == 0:
            return {
                "success": True,
                "critical_count": 0,
                "continuity_status": "PASS",
                "reason": "No activities in the project.",
                "data_consistent": True
            }

        crit_graph = metrics["critical_relationship_graph"]
        critical_ids = metrics["critical_ids"]

        start_nodes = [tid for tid, links in crit_graph.items() if not links["preds"]]
        
        visited = set()
        queue = list(start_nodes)
        while queue:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                queue.extend(list(crit_graph[curr]["succs"]))
                
        unvisited = critical_ids - visited
        
        if unvisited:
            has_links = any(links["preds"] or links["succs"] for links in crit_graph.values())
            if not has_links and critical_count > 1:
                return {
                    "success": True,
                    "critical_count": critical_count,
                    "continuity_status": "FAIL",
                    "reason": "Some critical activities are not properly linked, which may break continuity.",
                    "data_consistent": True
                }
            else:
                return {
                    "success": True,
                    "critical_count": critical_count,
                    "continuity_status": "FAIL",
                    "reason": "No, the critical path is not continuous. There are breaks in the sequence of critical activities.",
                    "data_consistent": True
                }
        else:
            return {
                "success": True,
                "critical_count": critical_count,
                "continuity_status": "PASS",
                "reason": "Yes, the critical path is continuous from project start to finish.",
                "data_consistent": True
            }
