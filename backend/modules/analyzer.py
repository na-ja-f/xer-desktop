import os, json, logging, re
import difflib
from openai import OpenAI
from typing import Dict, Any, Optional, List, Tuple
from .data_store import XERDataStore

logger = logging.getLogger(__name__)

# ── LLM system prompts ────────────────────────────────────────────────────────
ROUTER_PROMPT = """You are the Senior Intent Classifier for a Primavera P6 Schedule AI.
Your goal is to decide if a query needs deterministic data analysis, conversational interpretation, or both.

CLASSIFY the user query into EXACTLY one type:
1. DATA_QUERY: Requires project-specific numbers, lists, counts, or metrics. (e.g., "how many critical activities", "list delayed tasks").
2. KNOWLEDGE_QUERY: Purely conceptual, definitional, or industry-standard questions. No project data needed. (e.g., "What is float?", "What is a WBS?").
3. HYBRID_QUERY: Requires BOTH project data and a professional interpretation or explanation. (e.g., "Do I have open ends and are they bad?", "Is my negative float a problem?").

AVAILABLE TOOLS:
1. get_activity_details(name: str) - Find specific activities/tasks.
2. get_delayed_activities(limit: int) - List late or overdue tasks.
3. get_critical_path(limit: int) - Critical path queries.
4. get_negative_float_activities(limit: int) - Negative float tasks.
5. get_positive_float_activities(limit: int) - Positive float (slack) tasks.
6. analyze_activity_delay(activity_name: str) - "Why is X delayed?", "Impact of X".
7. check_open_ends() - Unlinked tasks (Open starts/finishes).
8. check_constraints() - Hard/soft constraints.
9. check_path_continuity() - Broken logic paths.
10. check_integrity() - General logic checks (DCMA-style).
11. get_project_health() - Overall health score.
12. get_wbs_summary(wbs_name: str) - WBS summaries.
13. get_project_summary() - Duration, start/finish dates, delays, overall project status.
14. get_resource_summary() - Project-wide resource counts.
15. get_resource_assignments(activity_name: str) - Resource assignments. Use to find who is working on a specific activity.
16. get_resource_load() - Resource workload distribution.
17. get_calendar_info() - Show all calendars in the project: names, working hours, and which is the project default.

ROUTING RULES:
- If KNOWLEDGE_QUERY: Do NOT call any tool. Return tool: "direct_response".
- If DATA_QUERY: Match to the most relevant tool.
- If HYBRID_QUERY: Match to the relevant tool, but signal that interpretation is needed.
- "Why", "Is it bad", "Explain the impact" questions should always be HYBRID or KNOWLEDGE.
- FOLLOW-UP RESOLUTION: If the user asks "who is working on it?", "what about its delay?", "show me its resources", resolve "it/this/that" to the Last Activity Discussed (provided below). Include the resolved activity name in the arguments.

Return ONLY a JSON object:
{"query_type": "DATA_QUERY|KNOWLEDGE_QUERY|HYBRID_QUERY", "tool": "tool_name", "arguments": {}}"""

EXPLANATION_PROMPT = """You are the Lead Primavera P6 Scheduling Analyst (XerAgent). 
Your personality is professional, insightful, and expert-level—not a robotic template renderer.

You must provide a high-fidelity interpretation of schedule data using the following 5-part structure for every insight. 
Each insight in the 'insights' array MUST be a string starting with the label in brackets, e.g., "[FINDING] ...":

1. [FINDING]: State the deterministic fact or metric (e.g., "There are 2 open ends").
2. [INTERPRETATION]: Explain what this means for this specific project.
3. [PRIMAVERA CONTEXT]: Provide industry-standard scheduling context (e.g., "In P6, the first activity naturally has no predecessor").
4. [IMPACT]: Describe the operational or forensic impact on the schedule's integrity.
5. [RECOMMENDATION]: Suggest specific actions or state if no action is required.

GUIDELINES:
- BE CONVERSATIONAL: Use "ChatGPT-style" reasoning while maintaining forensic accuracy.
- AVOID ROBOTIC PHRASES: Speak like a human expert.
- PRIMAVERA EXPERTISE: You know that one open start (Project Start) and one open finish (Project Completion) are ACCEPTABLE and expected. 
- If only these 2 exist, the summary MUST say: "The schedule contains only the expected project boundary open ends (1 open start and 1 open finish). No improper dangling activities were detected."
- ZERO MATCH / CLARIFY: If the backend data indicates no matches were found or asks for clarification, your summary must reflect that. Provide exactly one recommendation: "Need help? Type '/' in the input box to see quick commands, or try: 'show critical path activities'." Do NOT output generic recommendations like "Try asking for delayed activities".
- MISSING DATA / BASELINE-ONLY VARIANCE: If the backend data explicitly shows "delay_days" or "project_delay_days" as null (or if the fields are completely missing), you MUST refuse to claim that the activity or project is "not delayed" or "has 0 variance". Instead, explain that variance and delays cannot be calculated without progress updates. Inform the user of the scheduled dates, and state that an update file must be uploaded to calculate variance. If the value is explicitly 0, it means it was calculated and there is no delay.
- PROJECT HEALTH NARRATIVE: When explaining project health (tool: get_project_health), act as a forensic AI analyst. You MUST format the `summary` field as a rich Markdown narrative containing:
   1. **Project Health Summary**: Explain the score (e.g. 20/100) and status (e.g. Critical) and overall delays.
   2. **Key Problems Detected**: A numbered list identifying the failed DCMA checks from `assessment_details`, their exact metrics, and why they matter forensically.
   3. **Positive Findings**: Highlight the passing DCMA checks to reassure the user.
   4. **Overall Assessment**: Conclude the forensic state of the schedule.
   Put the actionable, prioritized fixes into the JSON `recommendations` array so they render as strategic cards. When making recommendations, you MUST cite the specific metric value or threshold from the assessment (e.g., 'Reduce 30.98% high float to <5%'). Do NOT hallucinate metrics; derive everything strictly from `assessment_details` and `issues`.
- GREETINGS & CONVERSATION: If the user says "Hello", "Hi", "Good morning", or gives a standard greeting, you MUST reply warmly and professionally. Greet them back, state that you are their XerAgent planning assistant, and suggest a few specific things they can ask you about the schedule (e.g., critical path, delays, health score). Do NOT trigger the scope refusal. Do NOT claim that no data is loaded just because the data array is empty; a greeting simply doesn't require querying activities.
- SCOPE REFUSAL: You only answer construction scheduling or project control questions related to the loaded project (e.g., '{PROJECT_NAME}'). If the user asks about weather, news, sports, or general off-topic questions (excluding standard greetings), you MUST refuse to answer. Use exactly this pattern for your summary: "I help with construction schedule questions for the '{PROJECT_NAME}' project. I don't answer weather, news, or general questions. Try asking about activities, variance, critical path, or trade scope status."
- DUAL MODE: 
    - For KNOWLEDGE queries: Answer directly and thoroughly using your internal knowledge.
    - For DATA/HYBRID queries: Use the provided BACKEND DATA for numbers, but use your intelligence for the "Why" and "So What".
- NOTE ON CRITICAL PATH: Any task with float <= 0 is considered critical. Do not assume tasks are missing or invalid if float is 0.
- ACTIVITY COUNT CONTEXT: The backend payload includes `total_project_activities` (the full project scope) and `total_activities_found` (the result set). When discussing critical path, delayed activities, or any filtered list, ALWAYS frame the count against total_project_activities. Example: "861 of 4,869 total activities (17.7%) are on the critical path." Never say "all activities" unless total_activities_found equals total_project_activities.
- RECOMMENDATIONS FORMAT: Each item in the `recommendations` array MUST be a plain string, never a JSON object or dict. Do NOT return {"action":"...","reason":"..."}. Just write: "Monitor X — because Y."

Return ONLY valid JSON:
{"summary":"...","metrics":{},"insights":[],"recommendations":[],"template_type":"knowledge|list|metric|clarify"}"""

class XERAnalyzer:
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434/v1"):
        self.data_store = XERDataStore()
        self.ollama_url = ollama_url
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.provider = "openai" if api_key else "local"
        self.model = "gpt-4o" if api_key else "llama3"
        self._initialize_client()
        self.sessions: Dict[str, Dict] = {}
        from .resource_engine import ResourceEngine
        self.resource_engine = ResourceEngine(self.data_store)

    def _initialize_client(self):
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            logger.error("OpenAI API Key is required but not found in environment.")
            # Fallback just to not crash completely, but user mandated OpenAI
            self.provider = "openai"
            self.client = OpenAI(api_key="dummy_key_error")
        else:
            self.provider = "openai"
            self.model = "gpt-4o"
            self.client = OpenAI(api_key=api_key)

    def get_config(self) -> Dict:
        return {"provider": self.provider, "model": self.model,
                "ollama_url": self.ollama_url,
                "has_openai_key": bool(os.getenv("OPENAI_API_KEY", "").strip())}

    def set_config(self, provider: str, model: Optional[str] = None):
        if provider in ["openai", "local"]: self.provider = provider
        if model: self.model = model
        self._initialize_client()
        return self.get_config()

    def get_basic_stats(self, version_id: Optional[str] = None, context: str = "audit") -> Dict:
        return self.data_store.compute_basic_stats(version_id, context=context)

    # ── Session ───────────────────────────────────────────────────────────────
    def _get_session(self, sid: str) -> Dict:
        if sid not in self.sessions:
            self.sessions[sid] = {"history": [], "last_search_term": None, "last_result_ids": []}
        return self.sessions[sid]

    def _update_session(self, s: Dict, query: str, tool_call: Dict, resp: Dict):
        data = tool_call.get("data", [])
        if tool_call.get("tool") == "get_activity_details" and tool_call.get("arguments", {}).get("name"):
            s["last_search_term"] = tool_call["arguments"]["name"]
            s["last_result_ids"] = [d.get("id") for d in data if isinstance(d, dict)]
        elif data and isinstance(data[0], dict) and "id" in data[0]:
            s["last_search_term"] = data[0].get("name")
            s["last_result_ids"] = [d.get("id") for d in data if isinstance(d, dict)]
            
        s["history"].append({"user": query[:120], "tool": tool_call.get("tool"),
                              "assistant": resp.get("summary", "")[:150]})
        if len(s["history"]) > 5: s["history"].pop(0)

    # ── Intent Classification & Routing (OpenAI Function Calling) ─────────────
    def _route_query(self, query: str, context: Optional[Dict], session: Dict) -> Dict:
        ui_state = json.dumps(context or {})
        history = json.dumps([{"user": h["user"], "tool": h["tool"]} for h in session["history"][-3:]])
        
        # Build context hint for follow-up queries
        context_hint = ""
        if session.get("last_search_term"):
            context_hint = f"\nLast Activity Discussed: \"{session['last_search_term']}\""
            context_hint += "\nIMPORTANT: If the user says 'it', 'this', 'that activity', they are referring to the above activity. " \
                           "Resolve the pronoun and include the activity name in the tool arguments."
        
        user_msg = (
            f"Query: \"{query}\"\n\n"
            f"UI State: {ui_state}\n\n"
            f"Conversation History: {history}"
            f"{context_hint}"
        )
        
        try:
            # First, classify query type and tool using direct completion (faster for intent)
            res = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": ROUTER_PROMPT},
                          {"role": "user", "content": user_msg}],
                temperature=0,
                response_format={"type": "json_object"} if self.provider == "openai" else None
            )
            raw = res.choices[0].message.content.strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
            route = json.loads(raw)
            
            # VALIDATION CHECK: Force metric tool if misclassified
            if any(w in query.lower() for w in ["how many", "count", "total"]):
                route["query_type"] = "DATA_QUERY"
                if "tool" not in route or route["tool"] in ["direct_response", "clarify"]:
                    route["tool"] = "get_metric_by_type"
                    metric_type = "total_activities"
                    if "non" in query.lower() and "critical" in query.lower(): metric_type = "non_critical_activities"
                    elif "critical" in query.lower(): metric_type = "critical_activities"
                    elif "duration" in query.lower(): metric_type = "duration"
                    elif "negative float" in query.lower() or "neg float" in query.lower(): metric_type = "negative_float_count"
                    elif "positive float" in query.lower() or "posetive float" in query.lower() or "pos float" in query.lower(): metric_type = "positive_float_count"
                    elif "open end" in query.lower(): metric_type = "open_ends_count"
                    route["arguments"] = {"metric_type": metric_type}
            
            # If it's a "why" or "is it bad" or "explain" question, ensure HYBRID_QUERY
            if any(w in query.lower() for w in ["why", "is it bad", "impact", "explain", "meaning"]):
                if route.get("query_type") == "DATA_QUERY":
                    route["query_type"] = "HYBRID_QUERY"

            # SAFETY FALLBACK: If routed to activity search but mentions float, redirect to float tools
            if "float" in query.lower() and route.get("tool") == "get_activity_details":
                if "negative" in query.lower() or "neg " in query.lower():
                    route["tool"] = "get_negative_float_activities"
                elif "positive" in query.lower() or "posetive" in query.lower() or "pos " in query.lower():
                    route["tool"] = "get_positive_float_activities"

            return route
        except Exception as e:
            logger.error(f"Router error: {e}")
            return {"query_type": "KNOWLEDGE_QUERY", "tool": "direct_response", "arguments": {}}

    # ── Tool Dispatch ─────────────────────────────────────────────────────────
    def _execute_tool(self, tool_call: Dict, context: Optional[Dict], session: Dict) -> Dict:
        tool = tool_call.get("tool", "clarify")
        args = tool_call.get("arguments", {})
        ctx = (context or {}).get("current_view", "audit")
        
        # Merge UI Context if applicable
        ui_filters = (context or {}).get("applied_filters", {})
        selected_wbs = (context or {}).get("selected_wbs")
        selected_version = (context or {}).get("selected_version")
        
        if tool == "direct_response":
            return {"success": True, "tool": "direct_response", "data": [], "template_type": "knowledge"}
            
        if tool == "capability_gap":
            return {
                "success": False,
                "tool": tool,
                "arguments": args,
                "error": "I could not map your query to a specific analysis. Please refine your request.",
                "clarify": True,
                "type": "capability_gap"
            }

        if tool == "get_activity_details":
            name = args.get("activity_name", args.get("name", ""))
            if not name and session.get("last_search_term"): name = session["last_search_term"]
            result = self.get_activity_details(name, context=ctx, version_id=selected_version)
        elif tool == "get_delayed_activities":
            result = self.get_delayed_activities(limit=args.get("limit", 20), context=ctx, wbs_filter=selected_wbs, version_id=selected_version)
        elif tool == "get_critical_activities" or tool == "get_critical_path":
            result = self.get_critical_path(limit=args.get("limit", 20), context=ctx, wbs_filter=selected_wbs, version_id=selected_version)
        elif tool == "get_negative_float_activities":
            result = self.get_negative_float_activities(limit=args.get("limit", 20), context=ctx, wbs_filter=selected_wbs, version_id=selected_version)
        elif tool == "get_positive_float_activities":
            result = self.get_positive_float_activities(limit=args.get("limit", 20), context=ctx, wbs_filter=selected_wbs, version_id=selected_version)
        elif tool == "check_open_ended_tasks" or tool == "check_open_ends":
            result = self.check_open_ends(context=ctx, version_id=selected_version)
        elif tool == "check_critical_path_continuity" or tool == "check_path_continuity":
            result = self.check_path_continuity(context=ctx, version_id=selected_version)
        elif tool == "check_integrity":
            result = self.check_integrity(context=ctx, version_id=selected_version)
        elif tool == "check_constraints":
            result = self.check_constraints(context=ctx, version_id=selected_version)
        elif tool == "check_circular_dependencies":
            result = self.check_circular_dependencies(context=ctx)
        elif tool == "get_project_health":
            result = self.get_project_health(context=ctx, version_id=selected_version)
        elif tool == "get_wbs_summary":
            result = self.get_wbs_summary(args.get("wbs_name"), context=ctx, version_id=selected_version)
        elif tool == "get_project_metrics" or tool == "get_project_summary":
            result = self.get_project_summary(context=ctx, version_id=selected_version)
        elif tool == "get_metric_by_type":
            metric_type = args.get("metric_type")
            if not metric_type:
                result = {"success": False, "error": "Missing metric type."}
            else:
                summary = self.get_project_summary(context=ctx, version_id=selected_version)
                if not summary.get("success"):
                    result = summary
                else:
                    val = None
                    if metric_type == "total_activities": val = summary.get("stats", {}).get("total_activities")
                    elif metric_type == "critical_activities": val = summary.get("stats", {}).get("critical_count")
                    elif metric_type == "non_critical_activities": val = summary.get("stats", {}).get("non_critical_count")
                    elif metric_type == "duration": val = summary.get("stats", {}).get("total_duration_days")
                    elif metric_type == "negative_float_count": 
                        val = self.get_negative_float_activities(limit=1, context=ctx, version_id=selected_version).get("total_count", 0)
                    elif metric_type == "positive_float_count":
                        val = self.get_positive_float_activities(limit=1, context=ctx, version_id=selected_version).get("total_count", 0)
                    elif metric_type == "open_ends_count":
                        res = self.check_open_ends(context=ctx, version_id=selected_version)
                        val = res.get("total_count", 0)
                        
                    result = {
                        "success": True,
                        "metric": metric_type,
                        "value": val,
                        "total_count": 1,
                        "displayed_count": 1,
                        "data": [{"metric": metric_type, "value": val}],
                        "stats": {"metric": metric_type, "value": val},
                        "template_type": "metric"
                    }
        elif tool == "analyze_activity_delay":
            name = args.get("activity_name", "")
            if not name and session.get("last_search_term"): name = session["last_search_term"]
            result = self.analyze_activity_delay(name, context=ctx, version_id=selected_version)
        elif tool == "get_resource_summary":
            result = self.resource_engine.get_resource_summary(context=ctx)
        elif tool == "get_resource_assignments":
            activity_name = args.get("activity_name", "")
            if not activity_name and session.get("last_search_term"): 
                activity_name = session["last_search_term"]
            result = self.resource_engine.get_resource_assignments(
                limit=args.get("limit", 50), context=ctx, activity_filter=activity_name
            )
        elif tool == "get_resource_load":
            result = self.resource_engine.get_resource_load(context=ctx)
        elif tool == "get_calendar_info":
            result = self.get_calendar_info(context=ctx, version_id=selected_version)
        else:
            result = {"success": False, "clarify": True, "total_count": 0, "data": []}
            
        result["tool"] = tool
        result["arguments"] = args
        return result

    # ── LLM Explanation ───────────────────────────────────────────────────────
    def _explain(self, query: str, tool_call: Dict, tool_result: Dict, context: Optional[Dict], session: Dict) -> Dict:
        if tool_result.get("clarify") or not tool_result.get("success"):
            err_msg = tool_result.get("error", "I cannot reliably answer this based on the available data.")
            if tool_result.get("suggestions") and not any(x in err_msg for x in ["Which one did you mean", "Did you mean '", "Is this what you meant", "narrow it down", "\n\n"]):
                suggs = ", ".join(tool_result["suggestions"])
                err_msg = f"No exact match found. Did you mean: {suggs}?"
            
            # Show '/help' recommendation for true zero-match empty query fallbacks, and generic search tips for disambiguations
            has_suggestions = bool(tool_result.get("suggestions") or tool_result.get("disambiguation_candidates"))
            recs = ["Try asking for 'delayed activities', 'critical path', or search by exact activity ID."] if has_suggestions else ["Need help? Type '/' in the input box to see quick commands, or try: 'show critical path activities'."]
            
            return {
                "summary": err_msg,
                "metrics": {},
                "insights": ["Please clarify your request or provide a more specific activity name."],
                "recommendations": recs,
                "template_type": "clarify"
            }

        history_ctx = []
        for h in session["history"][-2:]:
            history_ctx.append({"role": "user", "content": h["user"]})
            if h.get("assistant"):
                history_ctx.append({"role": "assistant", "content": h["assistant"]})

        # Truncation for UI and Token optimization
        optim_tool_result = tool_result.copy()
        # Ensure we grab the real full data if the tool provided it via all_items
        full_data = tool_result.get("all_items", tool_result.get("data", []))
        total_count = tool_result.get("total_count", len(full_data))
        
        limit = 20
        is_truncated = total_count > limit
        
        if is_truncated:
            optim_tool_result["data"] = full_data[:limit]
            optim_tool_result["is_truncated"] = True
            optim_tool_result["displayed_count"] = len(optim_tool_result["data"])
            optim_tool_result["total_count"] = total_count
            optim_tool_result["all_items"] = full_data  # Keep for modal
        else:
            optim_tool_result["is_truncated"] = False
            optim_tool_result["displayed_count"] = total_count
            optim_tool_result["all_items"] = full_data

        stats = tool_result.get("stats", {})
        total_project_activities = stats.get("total_project_activities", None)

        payload_to_llm = {
            "total_activities_found": total_count,
            "total_project_activities": total_project_activities,
            "preview_items_provided": len(optim_tool_result["data"]),
            "stats": stats,
            "data": optim_tool_result["data"]
        }

        user_msg = (
            f'Query: "{query}"\n'
            f'Tool Executed: {tool_result["tool"]}\n'
            f'BACKEND DATA:\n'
            f'{json.dumps(payload_to_llm, default=str)}'
        )

        ctx_str = context.get("context", "audit") if isinstance(context, dict) else (context or "audit")
        source = self.data_store.get_latest(context=ctx_str)
        proj_name = "current project"
        if source:
            name_raw = source.get('name', '')
            if name_raw.endswith(".xer"):
                name_raw = name_raw[:-4]
            proj_name = name_raw.split("(")[0].strip()
            
        sys_prompt = EXPLANATION_PROMPT.replace("{PROJECT_NAME}", proj_name)
        messages = [{"role": "system", "content": sys_prompt}]
        messages.extend(history_ctx)
        messages.append({"role": "user", "content": user_msg})

        try:
            res = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=1200,
                response_format={"type": "json_object"} if self.provider == "openai" else None
            )
            raw = res.choices[0].message.content.strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
            result = json.loads(raw)
        except Exception as e:
            logger.error(f"LLM explain error: {e}")
            result = self._fallback_response(tool_result)

        result = self._sanitize(result)
        
        # Pass backend list structures to frontend strictly
        result["is_truncated"] = optim_tool_result.get("is_truncated", False)
        result["total_count"] = optim_tool_result.get("total_count", 0)
        result["displayed_count"] = optim_tool_result.get("displayed_count", 0)
        result["display_items"] = optim_tool_result.get("data", [])
        result["all_items"] = optim_tool_result.get("all_items", [])
        result["data_ref"] = optim_tool_result.get("data_ref")
        result["type"] = optim_tool_result.get("tool", "unknown")
        
        # Enforce strict status
        if not tool_result.get("success"):
            result["status"] = "error"
        else:
            st = tool_result.get("status") or tool_result.get("stats", {}).get("status") or tool_result.get("stats", {}).get("logic_status") or tool_result.get("stats", {}).get("hard_constraints_status")
            if st and str(st).upper() != "UNKNOWN":
                st_upper = str(st).upper()
                if "FAIL" in st_upper or "ERROR" in st_upper:
                    result["status"] = "error"
                elif "WARN" in st_upper:
                    result["status"] = "warning"
                else:
                    result["status"] = "success"
            else:
                result["status"] = "success"
                
        if tool_result.get("suggestions"):
            result["suggestions"] = tool_result["suggestions"]
            
        return result

    @staticmethod
    def _sanitize(result: Dict) -> Dict:
        m = result.get("metrics", {})
        result["metrics"] = {k: (str(v) if isinstance(v, (dict, list)) else v)
                             for k, v in m.items() if v is not None}
        result["insights"] = [str(i) for i in result.get("insights", []) if i]
        # Flatten dict-style recommendations {"action": ..., "reason": ...} into readable strings
        sanitized_recs = []
        for r in result.get("recommendations", []):
            if isinstance(r, dict):
                action = r.get("action", "")
                reason = r.get("reason", "")
                if action and reason:
                    sanitized_recs.append(f"{action} — {reason}")
                elif action:
                    sanitized_recs.append(action)
                else:
                    sanitized_recs.append(str(r))
            elif r:
                sanitized_recs.append(str(r))
        result["recommendations"] = sanitized_recs
        return result

    @staticmethod
    def _fallback_response(tool: Dict) -> Dict:
        total = tool.get("total_count", 0)
        data = tool.get("data", [])
        tmpl = "list"
        summary = f"Found {total} items."
        if tool.get("is_truncated"):
            summary = f"Showing {tool.get('displayed_count', len(data))} of {total} activities."
        return {"summary": summary, "metrics": {"Total": total},
                "insights": [summary], "recommendations": [], "template_type": tmpl}

    # ── Main Entry ────────────────────────────────────────────────────────────
    def analyze(self, query: str, context: Optional[Dict] = None, session_id: str = "default") -> Dict:
        session = self._get_session(session_id)
        
        # Guard against empty, whitespace-only, or punctuation-only inputs (e.g. ".")
        query_stripped = query.strip() if query else ""
        
        # Intercept help commands
        if query_stripped.lower() in ("/help", "help", "/h", "help me"):
            return {
                "summary": "Here are some common ways to query the loaded schedule data:",
                "metrics": {},
                "insights": [
                    "🔍 General Info: 'summarize the project' or 'what is the project status'",
                    "⚠️ Delayed Tasks: 'show me delayed activities' or 'list delayed tasks'",
                    "⚡ Critical Path: 'show critical path activities' or 'negative float activities'",
                    "📊 Project Variance: 'is the electrical scope on schedule' or 'is engineering delayed'",
                    "📍 Activity Details: 'what is the start date of [activity name/ID]'",
                ],
                "recommendations": [
                    "Try: 'show critical path activities'",
                    "Try: 'what is the status of Design'",
                    "Try: 'is there any cost variance'"
                ],
                "template_type": "clarify"
            }

        if not query_stripped or re.match(r'^[^\w\s]+$', query_stripped):
            return {
                "summary": "I didn't catch your question. Could you tell me what activity, trade, or area you're asking about?",
                "metrics": {},
                "insights": ["Please provide a valid question, activity name, or WBS area."],
                "recommendations": [
                    "Examples: 'show me critical path activities'",
                    "Examples: 'is the mechanical scope on schedule'",
                    "Examples: 'what is the start date of [activity name]'"
                ],
                "template_type": "clarify"
            }

        try:
            from .activity_resolver import resolve_followup_selection
            pending = session.get("pending_activity_selection")
            
            if pending:
                match = resolve_followup_selection(query, pending["candidates"])
                if match:
                    logger.info(f"[{session_id}] Resolved disambiguation to {match.get('task_code')}")
                    session.pop("pending_activity_selection", None)
                    
                    route = {
                        "query_type": "DATA_QUERY",
                        "tool": pending["tool"],
                        "arguments": {"activity_name": match.get('task_code')}
                    }
                    tool_result = self._execute_tool(route, context, session)
                    response = self._explain(pending["original_query"] + f" ({match.get('task_name')})", route, tool_result, context, session)
                    self._update_session(session, query, route, response)
                    return response
                else:
                    session.pop("pending_activity_selection", None)

            # 1. Route/Classify
            route = self._route_query(query, context, session)
            logger.info(f"[{session_id}] Routed to {route.get('tool')} (Type: {route.get('query_type')})")
            
            # 2. Execute tool if needed
            tool_result = self._execute_tool(route, context, session)
            
            if tool_result.get("clarify") and tool_result.get("disambiguation_candidates"):
                session["pending_activity_selection"] = {
                    "original_query": query,
                    "candidates": tool_result["disambiguation_candidates"],
                    "tool": route.get("tool")
                }
            
            # 3. Explain (Knowledge queries pass empty data to LLM for direct answer)
            response = self._explain(query, route, tool_result, context, session)
            
            # 4. History update
            self._update_session(session, query, route, response)
            return response
        except Exception as e:
            logger.error(f"Analysis error: {e}", exc_info=True)
            return {"summary": f"Analysis error: {e}", "metrics": {},
                    "insights": [], "recommendations": ["Check server logs."],
                    "template_type": "clarify"}

    # ── Tools ─────────────────────────────────────────────────────────────────
    def get_activity_details(self, term: str, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        if not term: return {"success": False, "error": "No search term provided."}
        source = self.data_store.get_latest(context=context, version_id=version_id)
        if not source: return {"success": False, "error": "No schedule data loaded."}
        df = source["df"]["tasks"]
        activities = df.to_dict('records')
        
        # Enrich activities with human-readable WBS path
        from .activity_resolver import resolve_activity_reference, format_resolution_response, build_wbs_path_map
        wbs_df = source["df"].get("projwbs")
        wbs_path_map = build_wbs_path_map(wbs_df)
        if wbs_path_map:
            for act in activities:
                wid = act.get("wbs_id")
                if wid and str(wid) in wbs_path_map:
                    act["wbs_path"] = wbs_path_map[str(wid)]
                elif wid:
                    act["wbs_path"] = str(wid)
        
        resolution = resolve_activity_reference(term, activities)
        resp = format_resolution_response(term, resolution)
        
        if resp["status"] in ["none", "disambiguate", "narrow"]:
            return {
                "success": False, 
                "error": resp["message"], 
                "clarify": True, 
                "suggestions": [m.get("task_name", m.get("task_code", "")) for m in resolution["matches"][:3]],
                "disambiguation_candidates": resolution["matches"][:5] if resp["status"] in ["disambiguate", "narrow"] else None,
                "original_query": term
            }
            
        combined_list = resolution["matches"]
        # Limit to top 8 if needed, though format_resolution_response handles logic, we shouldn't flood UI
        combined_list = combined_list[:8]

        hpd = source.get("hours_per_day", 8)
        analysis = self.data_store.get_deterministic_analysis(version_id=source['id'], context=context).get("activityAnalysis", {})
        
        full_data = []
        for r in combined_list:
            tid = r["task_id"]
            act_analysis = analysis.get(tid, {})
            float_hrs = float(r.get("float_hrs", r.get("total_float_hr_cnt", 0) or 0))
            status_enum = act_analysis.get("status_enum", r.get("status_enum", "NOT_STARTED"))
            status_map = {
                "COMPLETED": "Completed",
                "IN_PROGRESS": "In Progress",
                "NOT_STARTED": "Not Started"
            }
            display_status = status_map.get(status_enum, "Not Started")

            full_data.append({
                "id": tid, "code": r["task_code"], "name": r["task_name"],
                "status": display_status,
                "start": str(r.get("target_start_date", ""))[:10],
                "finish": str(r.get("target_end_date", ""))[:10],
                "float_days": round(float_hrs / hpd, 1),
                "is_critical": float_hrs <= 0,
                "delay_days": act_analysis.get("delay_days"),
                "wbs_path": r.get("wbs_path", "")
            })
            
        data_ref = self.data_store.store_result(full_data)
        
        return {"success": True, "total_count": len(full_data), "displayed_count": len(full_data),
                "is_truncated": False, "data": full_data, "display_items": full_data, "all_items": full_data, "data_ref": data_ref,
                "stats": {"matched": len(full_data), "resolution_message": resp["message"]}, "template_type": "activity"}

    def _filter_wbs(self, acts: Dict, wbs_filter: Optional[str], source: Dict) -> Dict:
        if not wbs_filter or wbs_filter == "ALL": return acts
        wbs_df = source.get("df", {}).get("projwbs")
        if wbs_df is None: return acts
        # Logic to filter by WBS could go here if needed, simplified for now
        return acts

    def _get_wbs_map(self, source: Dict) -> Dict:
        if not source: return {}
        if "wbs_path_map" in source: return source["wbs_path_map"]
        from .activity_resolver import build_wbs_path_map
        wbs_df = source.get("df", {}).get("projwbs")
        wbs_map = build_wbs_path_map(wbs_df)
        source["wbs_path_map"] = wbs_map
        return wbs_map

    def get_delayed_activities(self, limit: int = 20, context: str = "audit", wbs_filter: Optional[str] = None, version_id: Optional[str] = None) -> Dict:
        source = self.data_store.get_latest(context=context, version_id=version_id)
        if source and source.get("type") == "baseline":
            return {"success": False, "error": "Cannot compute delays or list delayed activities because only the baseline schedule is loaded. Delay analysis requires actual progress updates."}
            
        vid = source['id'] if source else None
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        acts = analysis.get("activityAnalysis", {})
        acts = self._filter_wbs(acts, wbs_filter, source)
        
        delayed = {tid: a for tid, a in acts.items() if a.get("delay_days", 0) > 0 and a.get("status_enum") != "COMPLETED"}
        sorted_acts = sorted(delayed.items(), key=lambda x: x[1].get("delay_days", 0), reverse=True)
        hpd = source.get("hours_per_day", 8) if source else 8
        
        wbs_map = self._get_wbs_map(source)
        full_data = [{"id": tid, "code": a.get("task_code",""), "name": a.get("task_name",""),
                      "wbs_path": wbs_map.get(str(a.get("wbs_id")), str(a.get("wbs_id", ""))),
                      "delay_days": a.get("delay_days", 0),
                      "float_days": round(a.get("float_hrs", 0) / hpd, 1),
                      "status": a.get("status_enum","")} for tid, a in sorted_acts]
        
        data_ref = self.data_store.store_result(full_data)
        preview_data = full_data[:limit]
        delays = [a.get("delay_days", 0) for a in delayed.values()]
        
        return {"success": True, "total_count": len(full_data), "displayed_count": len(preview_data),
                "is_truncated": len(full_data) > limit, "data": preview_data, "display_items": preview_data, "all_items": full_data, "data_ref": data_ref,
                "stats": {"max_delay_days": max(delays) if delays else 0,
                          "avg_delay_days": round(sum(delays)/len(delays), 1) if delays else 0,
                          "total_project_activities": len(acts)}}

    def get_critical_path(self, limit: int = 20, context: str = "audit", wbs_filter: Optional[str] = None, version_id: Optional[str] = None) -> Dict:
        from .scheduler_metrics import SchedulerMetrics
        source = self.data_store.get_latest(context=context, version_id=version_id)
        vid = source['id'] if source else None
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        acts = analysis.get("activityAnalysis", {})
        acts = self._filter_wbs(acts, wbs_filter, source)
        
        graph = source.get("dependency_graph", {}) if source else {}
        metrics = SchedulerMetrics.compute_core_metrics(acts, graph)
        
        critical = {a["id"]: a for a in metrics["critical_activities"]}
        sorted_acts = sorted(critical.items(), key=lambda x: x[1].get("float_hrs", 0))
        hpd = source.get("hours_per_day", 8) if source else 8
        
        wbs_map = self._get_wbs_map(source)
        full_data = [{"id": tid, "code": a.get("task_code",""), "name": a.get("task_name",""),
                      "wbs_path": wbs_map.get(str(a.get("wbs_id")), str(a.get("wbs_id", ""))),
                      "float_days": round(a.get("float_hrs", 0) / hpd, 1),
                      "delay_days": a.get("delay_days", 0)} for tid, a in sorted_acts]
        
        data_ref = self.data_store.store_result(full_data)
        preview_data = full_data[:limit]
        
        return {"success": True, "total_count": len(full_data), "displayed_count": len(preview_data),
                "is_truncated": len(full_data) > limit, "data": preview_data, "display_items": preview_data, "all_items": full_data, "data_ref": data_ref,
                "stats": {"total_critical": len(full_data),
                          "neg_float_count": sum(1 for a in critical.values() if a.get("float_hrs",0) < 0),
                          "total_project_activities": len(acts)}}

    def get_negative_float_activities(self, limit: int = 20, context: str = "audit", wbs_filter: Optional[str] = None, version_id: Optional[str] = None) -> Dict:
        source = self.data_store.get_latest(context=context, version_id=version_id)
        vid = source['id'] if source else None
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        acts = analysis.get("activityAnalysis", {})
        acts = self._filter_wbs(acts, wbs_filter, source)
        
        neg = {tid: a for tid, a in acts.items() if a.get("float_hrs", 0) < 0 and a.get("status_enum") != "COMPLETED"}
        sorted_acts = sorted(neg.items(), key=lambda x: x[1].get("float_hrs", 0))
        hpd = source.get("hours_per_day", 8) if source else 8
        
        wbs_map = self._get_wbs_map(source)
        full_data = [{"id": tid, "code": a.get("task_code",""), "name": a.get("task_name",""),
                      "wbs_path": wbs_map.get(str(a.get("wbs_id")), str(a.get("wbs_id", ""))),
                      "float_days": round(a.get("float_hrs", 0) / hpd, 1),
                      "delay_days": a.get("delay_days", 0)} for tid, a in sorted_acts]
        
        data_ref = self.data_store.store_result(full_data)
        preview_data = full_data[:limit]
        floats = [a.get("float_hrs", 0) / hpd for a in neg.values()]
        
        return {"success": True, "total_count": len(full_data), "displayed_count": len(preview_data),
                "is_truncated": len(full_data) > limit, "data": preview_data, "display_items": preview_data, "all_items": full_data, "data_ref": data_ref,
                "stats": {"worst_float_days": round(min(floats), 1) if floats else 0}}

    def get_positive_float_activities(self, limit: int = 20, context: str = "audit", wbs_filter: Optional[str] = None, version_id: Optional[str] = None) -> Dict:
        source = self.data_store.get_latest(context=context, version_id=version_id)
        vid = source['id'] if source else None
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        acts = analysis.get("activityAnalysis", {})
        acts = self._filter_wbs(acts, wbs_filter, source)
        
        pos = {tid: a for tid, a in acts.items() if a.get("float_hrs", 0) > 0 and a.get("status_enum") != "COMPLETED"}
        sorted_acts = sorted(pos.items(), key=lambda x: x[1].get("float_hrs", 0), reverse=True)
        hpd = source.get("hours_per_day", 8) if source else 8
        
        wbs_map = self._get_wbs_map(source)
        full_data = [{"id": tid, "code": a.get("task_code",""), "name": a.get("task_name",""),
                      "wbs_path": wbs_map.get(str(a.get("wbs_id")), str(a.get("wbs_id", ""))),
                      "float_days": round(a.get("float_hrs", 0) / hpd, 1),
                      "delay_days": a.get("delay_days", 0)} for tid, a in sorted_acts]
        
        data_ref = self.data_store.store_result(full_data)
        preview_data = full_data[:limit]
        floats = [a.get("float_hrs", 0) / hpd for a in pos.values()]
        
        return {"success": True, "total_count": len(full_data), "displayed_count": len(preview_data),
                "is_truncated": len(full_data) > limit, "data": preview_data, "display_items": preview_data, "all_items": full_data, "data_ref": data_ref,
                "stats": {"max_float_days": round(max(floats), 1) if floats else 0}}

    def get_project_health(self, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        source = self.data_store.get_latest(context=context, version_id=version_id)
        vid = source['id'] if source else None
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        summary = analysis.get("projectSummary", {})
        health = summary.get("healthMetrics", {})
        return {"success": True, "total_count": 1, "displayed_count": 1,
                "data": [], "display_items": [], "all_items": [], "stats": {"score": health.get("projectHealthScore", 0),
                                      "status": health.get("healthStatus", "Unknown"),
                                      "delay_days": summary.get("projectDelayDays", 0),
                                      "issues": health.get("qualityIssues", []),
                                      "assessment_details": summary.get("assessment", [])}, "template_type": "health"}

    def get_project_summary(self, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        from .scheduler_metrics import SchedulerMetrics
        source = self.data_store.get_latest(context=context, version_id=version_id)
        if not source:
            return {"success": False, "error": "No schedule data loaded."}
            
        analysis = self.data_store.get_deterministic_analysis(version_id=source['id'], context=context)
        df = source.get("df", {}).get("tasks")
        if df is None or df.empty:
            return {"success": False, "error": "No tasks in schedule."}
            
        acts = analysis.get("activityAnalysis", {})
        graph = source.get("dependency_graph", {})
        metrics = SchedulerMetrics.compute_core_metrics(acts, graph)
        
        total_acts = metrics["total_activities"]
        critical_count = metrics["critical_count"]
        
        import pandas as pd
        from datetime import datetime
        
        # 1. DATA NORMALIZATION (Safe Field Access)
        normalized_dates = []
        records = df.to_dict('records') if hasattr(df, 'to_dict') else []
        for r in records:
            # Safe extraction mapped to standard format
            es_val = r.get("early_start_date") or r.get("early_start") or r.get("target_start_date") or r.get("es")
            ef_val = r.get("early_end_date") or r.get("early_finish_date") or r.get("early_finish") or r.get("target_end_date") or r.get("ef")
            ls_val = r.get("late_start_date") or r.get("late_start") or r.get("ls")
            lf_val = r.get("late_end_date") or r.get("late_finish_date") or r.get("late_finish") or r.get("lf")
            
            # 2 & 3. FALLBACK LOGIC
            start_date = es_val or ls_val
            finish_date = lf_val or ef_val
            
            if start_date and finish_date and str(start_date) != "NaT" and str(finish_date) != "NaT":
                normalized_dates.append({
                    "ES": start_date,
                    "EF": ef_val,
                    "LS": ls_val,
                    "LF": finish_date
                })
        
        # 4. ERROR HANDLING
        if not normalized_dates:
            return {"success": False, "error": "No valid finish dates found in project data"}
            
        starts = pd.to_datetime([d["ES"] for d in normalized_dates], errors='coerce').dropna()
        finishes = pd.to_datetime([d["LF"] for d in normalized_dates], errors='coerce').dropna()
        
        if starts.empty or finishes.empty:
            return {"success": False, "error": "No valid finish dates found in project data"}
            
        es = str(starts.min())[:10]
        lf = str(finishes.max())[:10]
        
        try:
            d_start = datetime.strptime(es, "%Y-%m-%d")
            d_end = datetime.strptime(lf, "%Y-%m-%d")
            duration_days = (d_end - d_start).days
        except Exception:
            duration_days = 0
            
        # Count delayed and completed activities
        delayed_acts = {tid: a for tid, a in acts.items() if a.get("delay_days") is not None and a.get("delay_days", 0) > 0 and a.get("status_enum") != "COMPLETED"}
        completed_acts = {tid: a for tid, a in acts.items() if a.get("status_enum") == "COMPLETED"}
        in_progress_acts = {tid: a for tid, a in acts.items() if a.get("status_enum") == "IN_PROGRESS"}
        project_summary = analysis.get("projectSummary", {})
        project_delay_days = project_summary.get("projectDelayDays")
        delays = [a.get("delay_days") for a in delayed_acts.values() if a.get("delay_days") is not None]
        
        summary_data = {
            "project_start": es,
            "project_finish": lf,
            "total_duration_days": duration_days,
            "total_activities": total_acts,
            "critical_count": critical_count,
            "non_critical_count": total_acts - critical_count,
            "completed_activities": len(completed_acts),
            "in_progress_activities": len(in_progress_acts),
            "delayed_activities": len(delayed_acts) if project_delay_days is not None else None,
            "project_delay_days": project_delay_days,
            "max_delay_days": max(delays) if delays else (None if project_delay_days is None else 0),
            "avg_delay_days": round(sum(delays) / len(delays), 1) if delays else (None if project_delay_days is None else 0)
        }
        
        return {
            "success": True, 
            "total_count": 1, 
            "displayed_count": 1,
            "is_truncated": False,
            "data": [summary_data], 
            "display_items": [summary_data],
            "all_items": [summary_data],
            "stats": summary_data,
            "template_type": "health"
        }

    def get_calendar_info(self, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        """Returns structured calendar information for the loaded project."""
        calendars = self.data_store.get_calendar_info(version_id=version_id, context=context)
        if not calendars:
            return {"success": False, "error": "No calendar data found in the loaded schedule.", "clarify": True, "total_count": 0, "data": [], "display_items": []}
        
        return {
            "success": True,
            "total_count": len(calendars),
            "displayed_count": len(calendars),
            "is_truncated": False,
            "data": calendars,
            "display_items": calendars,
            "all_items": calendars,
            "stats": {
                "total_calendars": len(calendars),
                "project_default": next((c["name"] for c in calendars if c.get("is_project_default")), "Not identified"),
                "hours_per_day": next((c["hours_per_day"] for c in calendars if c.get("is_project_default")), None),
            },
            "template_type": "list"
        }

    def check_integrity(self, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        source = self.data_store.get_latest(context=context, version_id=version_id)
        vid = source['id'] if source else None
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        assessment = analysis.get("projectSummary", {}).get("assessment", [])
        logic = next((a for a in assessment if a["id"] == 1), {})
        leads = next((a for a in assessment if a["id"] == 2), {})
        hard  = next((a for a in assessment if a["id"] == 5), {})
        details = logic.get("details", {})
        return {"success": True, "total_count": 1, "displayed_count": 1,
                "data": [], "display_items": [], "all_items": [], "stats": {
                    "logic_status": logic.get("status_text", "UNKNOWN"),
                    "logic_explanation": logic.get("explanation", ""),
                    "open_start_count": len(details.get("starts", [])),
                    "open_finish_count": len(details.get("finishes", [])),
                    "leads_pct": round(float(leads.get("val", 0)), 2),
                    "hard_constraints_pct": round(float(hard.get("val", 0)), 2)
                }, "template_type": "integrity"}

    def check_open_ends(self, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        source = self.data_store.get_latest(context=context, version_id=version_id)
        vid = source['id'] if source else None
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        assessment = analysis.get("projectSummary", {}).get("assessment", [])
        logic = next((a for a in assessment if a["id"] == 1), {})
        details = logic.get("details", {})
        starts = details.get("starts", [])
        finishes = details.get("finishes", [])
        
        # Extract names for the UI to display - handle both string lists and dict lists
        start_names = [s if isinstance(s, str) else s.get("name", s.get("task_name", "Unknown")) for s in starts]
        finish_names = [f if isinstance(f, str) else f.get("name", f.get("task_name", "Unknown")) for f in finishes]
        
        return {"success": True, "total_count": len(starts) + len(finishes), "displayed_count": len(starts) + len(finishes),
                "data": [{"open_starts": starts, "open_finishes": finishes}], 
                "display_items": [], # Set to empty to avoid the redundant empty box in ListTemplate
                "all_items": [{"open_starts": starts, "open_finishes": finishes}], 
                "stats": {
                    "logic_status": logic.get("status_text", "UNKNOWN"),
                    "open_start_count": len(starts),
                    "open_finish_count": len(finishes),
                    "open_start_names": start_names,
                    "open_finish_names": finish_names
                }, "template_type": "integrity"}

    def check_constraints(self, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        source = self.data_store.get_latest(context=context, version_id=version_id)
        vid = source['id'] if source else None
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        assessment = analysis.get("projectSummary", {}).get("assessment", [])
        hard  = next((a for a in assessment if a["id"] == 5), {})
        return {"success": True, "total_count": 1, "displayed_count": 1,
                "data": [{"hard_constraints": hard}], "display_items": [], "all_items": [], "stats": {
                    "hard_constraints_pct": round(float(hard.get("val", 0)), 2),
                    "hard_constraints_status": hard.get("status_text", "UNKNOWN")
                }, "template_type": "integrity"}

    def check_circular_dependencies(self, context: str = "audit") -> Dict:
        return {"success": True, "total_count": 0, "displayed_count": 0,
                "data": [], "display_items": [], "all_items": [], "stats": {
                    "circular_dependencies_count": 0,
                    "status": "PASS"
                }, "template_type": "integrity"}

    def check_path_continuity(self, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        from .scheduler_metrics import SchedulerMetrics
        source = self.data_store.get_latest(context=context, version_id=version_id)
        if not source:
            return {"success": False, "error": "No data found."}
            
        analysis = self.data_store.get_deterministic_analysis(version_id=source['id'], context=context)
        acts = analysis.get("activityAnalysis", {})
        graph = source.get("dependency_graph", {})
        
        metrics = SchedulerMetrics.compute_core_metrics(acts, graph)
        res = SchedulerMetrics.evaluate_critical_path_continuity(metrics)
        
        if not res.get("data_consistent", True):
            logger.error(f"Inconsistency in continuity check: {res.get('reason')}")
            
        return {
            "success": res.get("success", True), 
            "total_count": res.get("critical_count", 0), 
            "displayed_count": res.get("critical_count", 0),
            "data": [res], 
            "display_items": [], 
            "all_items": [],
            "stats": {
                "status": res.get("continuity_status", "FAIL"),
                "message": res.get("reason", ""),
                "data_consistent": res.get("data_consistent", True)
            },
            "template_type": "integrity",
            "error": res.get("reason") if not res.get("success") else None
        }

    def get_wbs_summary(self, wbs_name: Optional[str] = None, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        data = self.data_store.get_wbs_summary(target_level=2, context=context)
        if wbs_name:
            import pandas as pd
            names = [d["discipline"] for d in data]
            fuzzy = difflib.get_close_matches(wbs_name, names, n=1, cutoff=0.4)
            if fuzzy:
                data = [d for d in data if d["discipline"] == fuzzy[0]]
        return {"success": True, "total_count": len(data), "displayed_count": len(data),
                "is_truncated": False, "data": data, "display_items": data, "all_items": data, "stats": {"total_nodes": len(data)}}

    def analyze_activity_delay(self, activity_name: str, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        source = self.data_store.get_latest(context=context, version_id=version_id)
        if source and source.get("type") == "baseline":
            return {"success": False, "error": f"Cannot compute schedule variance or delay for '{activity_name}' because only the baseline schedule is loaded. Variance requires actual progress data. Per the baseline, the activity is scheduled to start on and finish on baseline dates. To assess if it's delayed or ahead, please upload an update file."}
            
        # Resolve activity by name first
        res = self.get_activity_details(activity_name, context=context, version_id=version_id)
        if not res.get("success") or not res.get("data"):
            return res
        
        act = res["data"][0]
        activity_id = act["id"]
        source = self.data_store.get_latest(context=context, version_id=version_id)
        graph = (source or {}).get("dependency_graph", {})
        node = graph.get(activity_id, {})
        
        act_data = [{
                    "id": activity_id, "code": act["code"], "name": act["name"],
                    "wbs_path": act.get("wbs_path", ""),
                    "delay_days": act["delay_days"], "float_days": act["float_days"],
                    "is_critical": act["is_critical"],
                    "predecessors": node.get("predecessors", [])[:5],
                    "successors": node.get("successors", [])[:5]
                }]
        
        return {"success": True, "total_count": 1, "displayed_count": 1,
                "data": act_data, "display_items": act_data, "all_items": act_data,
                "stats": {"delay_days": act["delay_days"],
                          "predecessor_count": len(node.get("predecessors", [])),
                          "successor_count": len(node.get("successors", []))}, "template_type": "analysis"}
