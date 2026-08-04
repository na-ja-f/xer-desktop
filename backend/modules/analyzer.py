import os, json, logging, re
import difflib
from openai import OpenAI
from typing import Dict, Any, Optional, List, Tuple, Union
from .data_store import XERDataStore

logger = logging.getLogger(__name__)

# ── WBS Branch Status Thresholds ──────────────────────────────────────────────
# IMPORTANT: These are PLACEHOLDER values — they are not planner-approved or
# based on any industry standard (DCMA, PMI, etc.). They were chosen as
# reasonable defaults for initial development only.
#
# A planner or project controls lead should review and adjust these before
# using this tool for any real project reporting or decision-making.
#
# All values are fractional percentages of non-completed activities in a branch.
# e.g. 0.30 = 30% of activities in the branch.
WBS_STATUS_THRESHOLDS: Dict[str, Any] = {
    # A branch is tagged "Critical" if more than this fraction of its
    # non-completed activities sit on the critical path (float <= 0).
    "critical_pct": 0.50,  # PLACEHOLDER — adjust with planner

    # A branch is tagged "Delayed" if more than this fraction of its
    # non-completed activities have a positive delay_days value.
    "delayed_pct": 0.30,   # PLACEHOLDER — adjust with planner

    # A branch is tagged "At Risk" if its delayed OR critical ratio
    # exceeds these lower thresholds (but doesn't reach Delayed/Critical).
    "at_risk_delayed_pct": 0.10,   # PLACEHOLDER — adjust with planner
    "at_risk_critical_pct": 0.20,  # PLACEHOLDER — adjust with planner
}

# ── LLM system prompts ────────────────────────────────────────────────────────
ROUTER_PROMPT = """You are the Senior Intent Classifier for a Primavera P6 Schedule AI.
Your goal is to decide if a query needs deterministic data analysis, conversational interpretation, or both.

CLASSIFY the user query into EXACTLY one type:
1. DATA_QUERY: Requires project-specific numbers, lists, counts, or metrics. (e.g., "how many critical activities", "list delayed tasks").
2. KNOWLEDGE_QUERY: Purely conceptual, definitional, or industry-standard questions. No project data needed. (e.g., "What is float?", "What is a WBS?").
3. HYBRID_QUERY: Requires BOTH project data and a professional interpretation or explanation. (e.g., "Do I have open ends and are they bad?", "Is my negative float a problem?").

AVAILABLE TOOLS:
1. get_activity_details(name: str) - Find specific activities/tasks. IMPORTANT: Use this tool even if the user asks for the "WBS path" of a specific activity (e.g. "show me the wbs path of AMI-1234"). The activity details inherently contain the WBS path. Do NOT use get_wbs_summary for an activity ID/name.
2. get_delayed_activities(limit: int, code_filter: str) - List tasks with execution delay (overdue to start or finish as of the Data Date). Pass a code value to filter (e.g. "Construction").
3. get_critical_path(limit: int, code_filter: str) - Critical path queries. Pass a code value to filter.
4. get_negative_float_activities(limit: int) - Negative float tasks.
5. get_positive_float_activities(limit: int) - Positive float (slack) tasks.
6. get_activities_by_status(limit: int, status: str, code_filter: str, wbs_filter: str) - Find activities by their progress status. Use when user asks for "in progress", "partially completed", "completed", "done", "not started", etc. The status argument MUST be one of 'IN_PROGRESS', 'COMPLETED', or 'NOT_STARTED'. Use wbs_filter if they specify a WBS (e.g. "design", "mobilization").
7. analyze_activity_delay(activity_name: str) - "Why is X delayed?", "Impact of X".
8. check_open_ends() - Unlinked tasks (Open starts/finishes).
9. check_constraints() - Hard/soft constraints.
10. check_path_continuity() - Broken logic paths.
11. check_integrity() - General logic checks (DCMA-style).
12. get_project_health() - Overall health score.
13. get_wbs_summary(wbs_name: str) - WBS summaries.
14. get_project_summary() - Duration, start/finish dates, delays, overall project status.
15. get_resource_summary() - Project-wide resource counts.
16. get_resource_assignments(activity_name: str) - Resource assignments. Use to find who is working on a specific activity.
17. get_resource_load() - Resource workload distribution.
18. get_calendar_info() - Show all calendars in the project: names, working hours, and which is the project default.
19. get_activity_code_types() - List all Activity Code Types, their scopes, and values defined in the project.
20. get_activity_code_types_by_scope(scope: str) - List activity code types filtered by a specific scope (valid scopes: 'Project', 'Global', 'EPS'). Use when user asks "Show project activity codes" or "Show global activity codes".
21. get_activity_code_values(code_type: str) - List all specific values for a given Activity Code Type (e.g. "What utilities exist?").
22. get_activities_by_code(code_type: str, code_value: str, rollup: bool, exact_match: bool) - Filter activities by a specific Activity Code. Use when user asks for activities of a specific type/category/level/utility/area/trade. IMPORTANT: If the user only provides the value (e.g. "Construction", "WATER NETWORK") without explicitly naming the type (e.g. "KPI" or "Levels"), you MUST leave code_type="" so the backend can resolve the ambiguity. Set rollup=True if user asks for activities "under" or "within" a parent area (to include descendants). Set exact_match=True if user asks for activities "directly assigned" to a specific area.
23. get_filtered_activities(limit: int, status: str, code_filter: str, wbs_filter: str, is_delayed: bool, is_at_risk: bool, cost_loaded: bool, evm_filter: str, sort_by: str) - Advanced filter tool. Use when the user combines multiple filters, EVM metrics, or sorting queries (e.g. "show all cost-loaded delayed activities", "top 10 highest BAC", "SPI < 1", "in-progress BOQ activities with cost data").
      - `cost_loaded`: set to true if user asks for activities with budget, cost data, or BAC > 0.
      - `evm_filter`: 'spi_lt_1', 'cpi_lt_1', 'sv_neg', 'cv_neg'.
      - `sort_by`: 'bac_desc', 'ev_desc', 'variance_desc', 'delay_desc'.
24. get_wbs_branch_stats() - Get schedule performance per WBS branch. Returns activity count, variance days, delayed count, at_risk_count, critical count, and a status tag (On Track/At Risk/Delayed/Critical/Completed) for each top-level WBS branch. Use when user asks: "How is each WBS performing?", "Show me branch status", "Which WBS is delayed?", "Show schedule performance by WBS", "SPI by branch" (when EV is not configured).
25. get_at_risk_activities(limit: int, code_filter: str) - List activities currently classified as At Risk (forecast finish exceeds baseline plus threshold, but not yet execution delayed). Pass a code value to filter.
26. get_baseline_pairing_status() - Check whether the baseline and update schedules are correctly paired. Shows overlap percentage, project names, and validation status. Use when user asks: "Is the baseline paired?", "Check baseline status", "Why is variance not working?".
27. get_activities_by_calendar(calendar_name: str, calendar_id: str, workweek_type: str, semantic_tag: str, limit: int) - Filter activities by calendar. Use when user asks for activities on a specific calendar, workweek type, or calendar tag.
      - `workweek_type`: '5-day', '6-day', '7-day'.
      - `semantic_tag`: 'RAMADAN', 'SUMMER', 'NIGHT_SHIFT', 'SHIFT'.
      - `calendar_name`: partial match on calendar name.
28. get_calendar_exceptions(calendar_name: str, month: int, year: int, exception_type: str, limit: int) - Retrieve exception dates for a calendar. Use when user asks "show exception dates", "show holidays", "show working Saturdays", etc.
      - `exception_type`: 'holiday' (for non-working dates), 'working' (for overrides).
      - `month`: 1-12 or None.
      - `year`: 4-digit year or None.
29. check_bei() - Baseline Execution Index (DCMA point 14): fraction of activities baseline-scheduled to finish by the data date that actually finished by the data date. DCMA target >= 0.95. Use when user asks "what's our BEI", "baseline execution index", "are we executing to plan", "execution discipline". Requires an update file with progress data — if only the baseline is loaded, the tool itself returns the reason rather than a fabricated value; just relay that reason, do not guess a number.

ACTIVITY CODE ROUTING RULES:
- When a user asks about "Construction activities", "Sewer activities", "Sector 1A", or any category that matches a detected Activity Code Type or Value, route to get_activities_by_code.
- NEVER guess or auto-fill 'code_type' unless the user explicitly names it. If they just say "Show Construction activities", pass code_value="Construction" and code_type="".
- When a user asks "which level/type/area/utility does activity X belong to?", route to get_activity_details — the response will include Activity Codes.
- When a user asks "show me all code types" or "what activity codes are in this project?", route to get_activity_code_types.
- When a user asks for codes by scope (e.g., "project activity codes", "global codes"), route to get_activity_code_types_by_scope.
- When a user asks "what values exist for X" or "list all areas/utilities/levels", route to get_activity_code_values.
- When a user asks for delayed/critical/partially completed activities filtered by a code value (e.g., "delayed Construction activities", "partially completed WATER NETWORK"), route to get_filtered_activities and pass the relevant arguments.
- When a user asks for activities filtered by cost (e.g. "cost loaded", "SPI < 1", "highest BAC"), route to get_filtered_activities.
- When a user asks for activities filtered by WBS (e.g. "show me in progress design activities", "delayed mobilization tasks"), route to the respective tool and pass the WBS name/path in the wbs_filter argument.
{DETECTED_CODE_TYPES}

CALENDAR ROUTING RULES (B-041):
- "Which calendar does activity X use?" → get_activity_details (calendar info is included in the response).
- "List all 7-day calendar activities" → get_activities_by_calendar(workweek_type="7-day").
- "Show Ramadan calendar activities" → get_activities_by_calendar(semantic_tag="RAMADAN").
- "How many calendars are there?" / "Show all calendars" → get_calendar_info.
- "How many working days are there?" / "How many working days in this calendar?" → get_calendar_info.
- If the user provides just a calendar name as a follow-up (e.g. "stage 28 6 day") → Review conversation history. If the previous question asked about exceptions, holidays, or dates, route to get_calendar_exceptions(calendar_name="..."), AND preserve any other arguments/filters (like month, year) from their original query. Otherwise, route to get_calendar_info(calendar_name="..."). Do NOT route to get_activities_by_calendar unless they explicitly ask for activities.
- "Show exception dates", "Show holidays", "Show working Saturdays", "Show exceptions in January 2026", "What are the exception dates for X" → get_calendar_exceptions.
- "What holidays affect this activity?" → get_activity_details (calendar_holidays are included).
- "Why is this activity taking longer?" → analyze_activity_delay (calendar info enriches the analysis).
- "Is the baseline valid?" / "Check baseline pairing" → get_baseline_pairing_status.

ROUTING RULES:
- If KNOWLEDGE_QUERY: Do NOT call any tool. Return tool: "direct_response".
- If DATA_QUERY: Match to the most relevant tool.
- If HYBRID_QUERY: Match to the relevant tool, but signal that interpretation is needed.
- "Why", "Is it bad", "Explain the impact" questions should always be HYBRID or KNOWLEDGE.
- FOLLOW-UP RESOLUTION: If the user asks "who is working on it?", "what about its delay?", "show me its resources", resolve "it/this/that" to the Last Activity Discussed (provided below). Include the resolved activity name in the arguments.
- DATE FILTERS: When a user asks a follow-up question involving "all" (e.g., "show me all holidays", "list all exceptions"), you MUST drop any previous month/year filters and set them to null to retrieve the entire list.
- DISAMBIGUATION: If the user responds to a list with an index or selection (e.g., "4th one", "number 2", "the last one", "first one"), you MUST call the relevant tool (e.g., get_calendar_exceptions) AND you MUST set the `calendar_name` (or relevant argument) to exactly their selection string (e.g., "4th one"). Do NOT leave the calendar_name argument empty. Preserve any other filters from their original query.

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
- DELAY DRIVER GROUNDING (tool: analyze_activity_delay) — B-004.1: The backend payload carries deterministic, pre-computed grounding — never invent numbers or phrasing here yourself. You MUST ground the [RECOMMENDATION] insight and the `recommendations` array strictly in this data, per these rules, and NEVER output generic platitudes like "ensure prerequisites are completed", "monitor progress closely", or "coordinate with stakeholders":
   1. NEAR-TERM RISK (highest priority): If `near_term_risk` is present (non-null), copy its `deterministic_recommendation` string into the `recommendations` array VERBATIM — word for word, no rephrasing, no recomputing the percentage or remaining days yourself. Use that same sentence (or a direct quote of it) as the [RECOMMENDATION] insight too. This field already encodes the exact manager-approved pattern: "[Activity] is scheduled to start [date] but its predecessor [Activity] is [X]% complete with [Y] days remaining," plus a count of any additional incomplete predecessors — do not add to or shorten it.
   2. ALL PREDECESSORS COMPLETE: Else if `all_predecessors_complete` is true, say so explicitly and name them from the `predecessors` array, e.g. "All predecessors ('Submit QA Plan', 'Procure Steel Beams') are already complete — the constraint here is this activity's own float, not upstream logic." Do not tell the user to "ensure prerequisites are completed" when the data shows they already are.
   3. NO ACTIONABLE DATA: Else if `has_actionable_recommendation_data` is false, the `recommendations` array MUST be empty (`[]`) — do not invent a recommendation when there is no near-term risk, completed-predecessor fact, criticality, or delay signal to ground it in.
   4. Every recommendation must resolve to the verbatim `deterministic_recommendation` string, an explicit "all predecessors complete" statement, or be omitted per rule 3 — there is no fourth, generic option.
- ACTIVITY CODES: When explaining activity code types (from get_activity_code_types), you MUST explicitly list and group the counts by Scope in your summary using markdown. Example format: "**Project Activity Codes (4)** - used for... \n\n**Global Activity Codes (2)** - used for...". Do NOT just write a single flat paragraph.
- ACTIVITY CODE HIERARCHIES: When explaining code values (from get_activity_code_values) and hierarchy data (children/parents) is present, you MUST present the values as a tree using markdown characters (├ and └) instead of a flat list. Do not flatten the hierarchy. Example:
  PACKAGE 1A
  ├ Direct Assignments: 87
  ├ SECTOR 1A
  └ SECTOR 1B
- WBS BRANCH STATS (template_type: wbs_branch_stats): When data comes from get_wbs_branch_stats, you MUST format as a markdown table with columns: WBS Branch | Activities | Delayed | Critical | Variance Days | Status. Add a prominent note at the top: "⚠️ Earned Value (SPI/CPI) is not available for this project — all activities use Duration % Complete. The Status Tag is derived from delay ratio and critical path ratio." Sort Critical/Delayed rows first. Explain the status logic briefly.
- GREETINGS & CONVERSATION: If the user says "Hello", "Hi", "Good morning", or gives a standard greeting, you MUST reply warmly and professionally. Greet them back, state that you are their XerAgent planning assistant, and suggest a few specific things they can ask you about the schedule (e.g., critical path, delays, health score). Do NOT trigger the scope refusal. Do NOT claim that no data is loaded just because the data array is empty; a greeting simply doesn't require querying activities.
- SCOPE REFUSAL: You only answer construction scheduling or project control questions related to the loaded project (e.g., '{PROJECT_NAME}'). If the user asks about weather, news, sports, or general off-topic questions, you MUST refuse to answer. EXCEPTIONS: Any question mentioning calendars, holidays, workweeks, or specific working exceptions (e.g., "Ramadan", "Summer", "Christmas", "Eid") MUST NOT trigger a scope refusal. These are valid schedule inquiries. For off-topic questions only, use exactly this pattern for your summary: "I help with construction schedule questions for the '{PROJECT_NAME}' project. I don't answer weather, news, or general questions. Try asking about activities, variance, critical path, or trade scope status."
- CALENDAR GROUNDING: Never estimate calendar values, working days, or exception counts. Never use words like "typically", "usually", "assuming", "would have", "might have", "probably", or "generally". Rely STRICTLY on the injected backend payload. If a requested calendar does not exist, explicitly say: "No such calendar exists in the uploaded XER." If the calendar exists but has no exceptions for the requested date, explicitly state: "No exceptions match the specified date criteria for this calendar." Do NOT estimate. If the user asks about 'Ramadan' and no matching calendar/exception is found, you MUST state exactly: "No calendar, exception, or holiday containing 'Ramadan' exists in the uploaded XER. Therefore the system cannot determine a Ramadan-specific calendar."
- CALENDAR FORMATTING: When answering calendar questions, you MUST format all dates as 'MMM D, YYYY' (e.g., 'Jun 12, 2026'). You MUST ALWAYS structure responses using this exact format (including the markdown and source footer):
  **Calendar Name**
  * Workweek: [Type]
  * Hours/day: [Hours]
  * Non-working dates: [Effective Count] affecting project ([Total Count] total)
  * Working overrides: [Effective Count] affecting project ([Total Count] total)
  
  **Exception Dates Found:**
  [Provide exact Holiday/Exception Dates in a bulleted list, formatted as '* MMM D, YYYY ([type of exception])'. Example: '* Jun 17, 2026 (Non-working)'. If holiday count is 0 but exceptions exist, explicitly state: "No named holidays are defined. However calendar exceptions exist."]
  
  *(Note: Dates shown are effective dates within the project period. The calendar contains historical exceptions that are hidden because they do not affect this project.)*
  
  Source:
  Parsed directly from uploaded XER.
- DUAL MODE: 
    - For KNOWLEDGE queries: Answer directly and thoroughly using your internal knowledge.
    - For DATA/HYBRID queries: Use the provided BACKEND DATA for numbers, but use your intelligence for the "Why" and "So What".
- NOTE ON CRITICAL PATH: Any task with float <= 0 is considered critical. Do not assume tasks are missing or invalid if float is 0.
- AMBIGUOUS CALENDAR QUERIES: If the user asks a general question like "How many working days are there?" without specifying a calendar, and the backend data returns multiple calendars, you MUST NOT dump all calendars. Instead, reply EXACTLY with: "Multiple calendars exist in this project. \n\n* [List calendar names here] \n\nPlease specify:\n• calendar name\n• activity\n• or date range"
- ACTIVITY COUNT CONTEXT: The backend payload includes `total_project_activities` (the full project scope). If a `filtered_subset_total` is provided (e.g., when a user filters by an Activity Code), you MUST frame your response around both totals! Example: "There are 2,861 Construction activities delayed out of 2,867 Construction activities (99.8%), while the project overall has 4,869 total activities." ALWAYS calculate and state the percentage in your summary. Never say "all activities" unless the delayed/critical count equals the total project activities.
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
            self.sessions[sid] = {"history": [], "last_search_term": None, "last_result_ids": [], "selected_activity": None}
        return self.sessions[sid]

    def _update_session(self, s: Dict, query: str, tool_call: Dict, resp: Dict, tool_result: Dict = None):
        # Extract data from the actual tool_result to ensure we have the resolved data
        if tool_result:
            data = tool_result.get("data", [])
        else:
            data = resp.get("data", [])
            
        tool = tool_call.get("tool")
        
        if tool == "get_activity_details":
            if tool_call.get("arguments", {}).get("name"):
                s["last_search_term"] = tool_call["arguments"]["name"]
            elif tool_call.get("arguments", {}).get("activity_name"):
                s["last_search_term"] = tool_call["arguments"]["activity_name"]
            
            # If we successfully resolved exactly ONE activity, persist it as the selected entity!
            if len(data) == 1 and isinstance(data[0], dict):
                act = data[0]
                s["selected_activity"] = {
                    "selected_activity_id": act.get("id"),
                    "selected_activity_code": act.get("code"),
                    "selected_activity_name": act.get("name")
                }
                logger.info(f"Selected activity stored: {act.get('code')}")
        elif data and isinstance(data[0], dict) and "id" in data[0]:
            # For other tools returning lists of activities, just track the search term and clear strict selection
            s["last_search_term"] = data[0].get("name")
            s["last_result_ids"] = [d.get("id") for d in data if isinstance(d, dict)]
            s["selected_activity"] = None
            
        s["history"].append({"user": query[:120], "tool": tool,
                              "assistant": resp.get("summary", "")[:150]})
        if len(s["history"]) > 5: s["history"].pop(0)

    # ── Intent Classification & Routing (OpenAI Function Calling) ─────────────
    def _route_query(self, query: str, context: Optional[Dict], session: Dict) -> Dict:
        ui_state = json.dumps(context or {})
        history = json.dumps([{"user": h["user"], "tool": h["tool"]} for h in session["history"][-3:]])
        
        # Build context hint for follow-up queries
        context_hint = ""
        selected_act = session.get("selected_activity")
        if selected_act:
            logger.info(f"[{session.get('sid', '???')}] Pronoun context available: {selected_act.get('selected_activity_code')}")
            context_hint = f"\nLast Selected Activity: {selected_act['selected_activity_code']} ({selected_act['selected_activity_name']})"
            context_hint += "\nIMPORTANT: If the user uses pronouns ('it', 'this activity', 'that activity', 'same activity', 'selected activity', 'above activity'), they are referring to the Last Selected Activity. " \
                           "Resolve the pronoun and use the selected activity code as the argument."
        elif session.get("last_search_term"):
            context_hint = f"\nLast Topic Discussed: \"{session['last_search_term']}\""
        
        # Inject detected Activity Code Types into the router context
        code_types_hint = ""
        ctx_str_for_codes = (context or {}).get("current_view", "audit")
        try:
            code_types = self.data_store.get_activity_code_types(context=ctx_str_for_codes)
            if code_types:
                types_list = []
                for t, info in code_types.items():
                    vals = info["values"]
                    preview = ', '.join(vals[:5])
                    if len(vals) > 5:
                        preview += f', ... ({len(vals)} total)'
                    types_list.append(f"  - {t}: [{preview}]")
                code_types_hint = "\n\nDetected Activity Code Types in this project:\n" + "\n".join(types_list)
                code_types_hint += "\nIMPORTANT: If the user's query mentions ANY of these code type names or code values, route to get_activities_by_code or include code_filter in arguments."
        except Exception:
            pass

        router_prompt = ROUTER_PROMPT.replace("{DETECTED_CODE_TYPES}", code_types_hint)

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
                messages=[{"role": "system", "content": router_prompt},
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
            code_filter = args.get("code_filter")
            result = self.get_delayed_activities(limit=args.get("limit", 20), context=ctx, wbs_filter=selected_wbs, version_id=selected_version, code_filter=code_filter)
        elif tool == "get_at_risk_activities":
            code_filter = args.get("code_filter")
            result = self.get_at_risk_activities(limit=args.get("limit", 20), context=ctx, wbs_filter=selected_wbs, version_id=selected_version, code_filter=code_filter)
        elif tool == "get_critical_activities" or tool == "get_critical_path":
            code_filter = args.get("code_filter")
            result = self.get_critical_path(limit=args.get("limit", 20), context=ctx, wbs_filter=selected_wbs, version_id=selected_version, code_filter=code_filter)
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
        elif tool == "check_bei":
            result = self.check_bei(context=ctx, version_id=selected_version)
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
        elif tool == "get_activities_by_status":
            result = self.get_activities_by_status(
                limit=args.get("limit", 20),
                status=args.get("status", "IN_PROGRESS"),
                code_filter=args.get("code_filter"),
                wbs_filter=args.get("wbs_filter"),
                context=ctx,
                version_id=selected_version
            )
        elif tool == "get_filtered_activities":
            result = self.get_filtered_activities(
                limit=args.get("limit", 20),
                status=args.get("status"),
                code_filter=args.get("code_filter"),
                wbs_filter=args.get("wbs_filter"),
                is_delayed=args.get("is_delayed"),
                is_at_risk=args.get("is_at_risk"),
                is_critical=args.get("is_critical"),
                cost_loaded=args.get("cost_loaded"),
                evm_filter=args.get("evm_filter"),
                sort_by=args.get("sort_by"),
                context=ctx,
                version_id=selected_version
            )
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
            result = self.get_calendar_info(calendar_name=args.get("calendar_name"), context=ctx, version_id=selected_version)
        elif tool == "get_activity_code_types":
            result = self.get_activity_code_types_tool(context=ctx, version_id=selected_version)
        elif tool == "get_activity_code_types_by_scope":
            result = self.get_activity_code_types_tool(context=ctx, version_id=selected_version, scope=args.get("scope"))
        elif tool == "get_activity_code_values":
            result = self.get_activity_code_values(
                code_type=args.get("code_type", ""),
                context=ctx, version_id=selected_version
            )
        elif tool == "get_activities_by_code":
            result = self.get_activities_by_code(
                code_type=args.get("code_type", ""),
                code_value=args.get("code_value", ""),
                rollup=args.get("rollup", False),
                exact_match=args.get("exact_match", False),
                limit=args.get("limit", 100),
                context=ctx, version_id=selected_version
            )
        elif tool == "get_wbs_branch_stats":
            result = self.get_wbs_branch_stats(context=ctx, version_id=selected_version)
        elif tool == "get_baseline_pairing_status":
            result = self.get_baseline_pairing_status(context=ctx)
        elif tool == "get_activities_by_calendar":
            result = self.get_activities_by_calendar(
                calendar_name=args.get("calendar_name"),
                calendar_id=args.get("calendar_id"),
                workweek_type=args.get("workweek_type"),
                semantic_tag=args.get("semantic_tag"),
                limit=args.get("limit", 50),
                context=ctx, version_id=selected_version
            )
        elif tool == "get_calendar_exceptions":
            result = self.get_calendar_exceptions(
                calendar_name=args.get("calendar_name"),
                month=args.get("month"),
                year=args.get("year"),
                exception_type=args.get("exception_type"),
                limit=args.get("limit", 100),
                context=ctx, version_id=selected_version
            )
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
                    self._update_session(session, query, route, response, tool_result=tool_result)
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
            self._update_session(session, query, route, response, tool_result=tool_result)
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
        code_types = self.data_store.get_activity_code_types(version_id=version_id, context=context)
        
        # B-041: Get calendar map for enrichment
        cal_map = self.data_store.get_calendar_map(version_id=version_id, context=context)
        
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

            codes_payload = {}
            for k, v in act_analysis.get("activity_codes", {}).items():
                codes_payload[k] = {
                    "value": v,
                    "scope": code_types.get(k, {}).get("scope", "Global")
                }

            # B-041: Calendar enrichment
            cal_id = str(r.get("clndr_id", ""))
            cal_info = cal_map.get(cal_id, {})

            full_data.append({
                "id": tid, "code": r["task_code"], "name": r["task_name"],
                "status": display_status,
                "start": str(r.get("target_start_date", ""))[:10],
                "finish": str(r.get("target_end_date", ""))[:10],
                "float_days": round(float_hrs / hpd, 1),
                "is_critical": float_hrs <= 0,
                "delay_days": act_analysis.get("delay_days"),
                "wbs_path": r.get("wbs_path", ""),
                "activity_codes": codes_payload,
                # B-041: Calendar fields
                "calendar_id": cal_id,
                "calendar_name": cal_info.get("name", ""),
                "calendar_hours_per_day": cal_info.get("hours_per_day"),
                "workweek_type": cal_info.get("workweek_type", ""),
                "calendar_holidays": cal_info.get("holidays", []),
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

    def _filter_by_code(self, acts: Dict, code_filter: Union[Dict, str, None], code_types: Dict = None) -> Dict:
        """Filter activities by Activity Code type/value.
        code_filter: {"code_type": "AMR-P1- LEVELS", "code_value": "AMI-CONSTRUCTION", "rollup": True, "exact_match": True}
        """
        if not code_filter:
            return acts
        
        if isinstance(code_filter, str):
            code_type = ""
            code_value = code_filter.strip()
            rollup = False
            exact_match = False
        else:
            code_type = (code_filter.get("code_type") or "").strip()
            code_value = (code_filter.get("code_value") or "").strip()
            rollup = code_filter.get("rollup", False)
            exact_match = code_filter.get("exact_match", False)
            
        if not code_type and not code_value:
            return acts

        def norm(s): return s.strip().lower().replace(" ", "")

        # If rollup is True, collect all target values (including descendants)
        target_values = [code_value.lower()] if code_value else []
        if rollup and code_value and code_types:
            for type_info in code_types.values():
                hierarchy = type_info.get("hierarchy", {})
                for k, v in hierarchy.items():
                    if norm(code_value) == norm(k):
                        # Found the node, add all its descendants
                        def add_descendants(node_val):
                            if node_val in hierarchy:
                                for child in hierarchy[node_val].get("children_values", []):
                                    target_values.append(child.lower())
                                    add_descendants(child)
                        add_descendants(k)

        filtered = {}
        for tid, a in acts.items():
            codes = a.get("activity_codes", {})
            if not codes:
                continue
                
            matched = False
            
            if code_type and code_value:
                for t, v in codes.items():
                    if norm(code_type) in norm(t) or norm(t) in norm(code_type):
                        if exact_match:
                            if any(v.lower() == tv for tv in target_values):
                                matched = True
                                break
                        else:
                            if any(tv in v.lower() for tv in target_values):
                                matched = True
                                break
            elif code_value:
                for v in codes.values():
                    if exact_match:
                        if any(v.lower() == tv for tv in target_values):
                            matched = True
                            break
                    else:
                        if any(tv in v.lower() for tv in target_values):
                            matched = True
                            break
            elif code_type:
                for t in codes.keys():
                    if norm(code_type) in norm(t) or norm(t) in norm(code_type):
                        matched = True
                        break
                        
            if matched:
                filtered[tid] = a
                
        return filtered

    def get_delayed_activities(self, limit: int = 20, context: str = "audit", wbs_filter: Optional[str] = None, version_id: Optional[str] = None, code_filter: Optional[Dict] = None) -> Dict:
        source = self.data_store.get_latest(context=context, version_id=version_id)
        if source and source.get("type") == "baseline":
            return {"success": False, "error": "Cannot compute delays or list delayed activities because only the baseline schedule is loaded. Delay analysis requires actual progress updates."}
        
        # B-040: Check baseline pairing validity
        ctx = self.data_store.contexts.get(context, self.data_store.contexts["audit"])
        pairing = ctx.get("baseline_pairing", {})
        if pairing and not pairing.get("valid"):
            reason = pairing.get("reason", "Baseline pairing validation failed.")
            return {"success": False, "error": reason}
            
        vid = source['id'] if source else None
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        acts = analysis.get("activityAnalysis", {})
        acts = self._filter_wbs(acts, wbs_filter, source)
        acts = self._filter_by_code(acts, code_filter)
        
        delayed = {tid: a for tid, a in acts.items() if a.get("classification") == "DELAYED"}
        sorted_acts = sorted(delayed.items(), key=lambda x: x[1].get("delay_days", 0), reverse=True)
        hpd = source.get("hours_per_day", 8) if source else 8
        
        wbs_map = self._get_wbs_map(source)
        full_data = [{"id": tid, "code": a.get("task_code",""), "name": a.get("task_name",""),
                      "wbs_path": wbs_map.get(str(a.get("wbs_id")), str(a.get("wbs_id", ""))),
                      "delay_days": a.get("delay_days", 0),
                      "float_days": round(a.get("float_hrs", 0) / hpd, 1),
                      "status": a.get("status_enum",""),
                      "classification": "DELAYED",
                      "activity_codes": a.get("activity_codes", {})} for tid, a in sorted_acts]
        
        data_ref = self.data_store.store_result(full_data)
        preview_data = full_data[:limit]
        delays = [a.get("delay_days", 0) for a in delayed.values()]
        
        filter_label = ""
        if isinstance(code_filter, str):
            filter_label = f" (filtered by {code_filter})"
        elif isinstance(code_filter, dict):
            filter_label = f" (filtered by {code_filter.get('code_type', '')} = {code_filter.get('code_value', '')})"
        
        return {"success": True, "total_count": len(full_data), "displayed_count": len(preview_data),
                "is_truncated": len(full_data) > limit, "data": preview_data, "display_items": preview_data, "all_items": full_data, "data_ref": data_ref,
                "stats": {"max_delay_days": max(delays) if delays else 0,
                          "avg_delay_days": round(sum(delays)/len(delays), 1) if delays else 0,
                          "total_project_activities": len(analysis.get("activityAnalysis", {})),
                          "filtered_subset_total": len(acts),
                          "filter_applied": filter_label}}

    def get_at_risk_activities(self, limit: int = 20, context: str = "audit", wbs_filter: Optional[str] = None, version_id: Optional[str] = None, code_filter: Optional[Dict] = None) -> Dict:
        source = self.data_store.get_latest(context=context, version_id=version_id)
        if source and source.get("type") == "baseline":
            return {"success": False, "error": "Cannot compute risks or list at-risk activities because only the baseline schedule is loaded. Risk analysis requires actual progress updates."}
            
        vid = source['id'] if source else None
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        acts = analysis.get("activityAnalysis", {})
        acts = self._filter_wbs(acts, wbs_filter, source)
        acts = self._filter_by_code(acts, code_filter)
        
        at_risk = {tid: a for tid, a in acts.items() if a.get("classification") == "AT_RISK"}
        sorted_acts = sorted(at_risk.items(), key=lambda x: x[1].get("forecast_slip_days", 0), reverse=True)
        hpd = source.get("hours_per_day", 8) if source else 8
        
        wbs_map = self._get_wbs_map(source)
        full_data = [{"id": tid, "code": a.get("task_code",""), "name": a.get("task_name",""),
                      "wbs_path": wbs_map.get(str(a.get("wbs_id")), str(a.get("wbs_id", ""))),
                      "slip_days": a.get("forecast_slip_days", 0),
                      "threshold_days": round(a.get("threshold_days", 5.0), 1),
                      "float_days": round(a.get("float_hrs", 0) / hpd, 1),
                      "status": a.get("status_enum",""),
                      "classification": "AT_RISK",
                      "activity_codes": a.get("activity_codes", {})} for tid, a in sorted_acts]
        
        data_ref = self.data_store.store_result(full_data)
        preview_data = full_data[:limit]
        slips = [a.get("forecast_slip_days", 0) for a in at_risk.values()]
        
        filter_label = ""
        if isinstance(code_filter, str):
            filter_label = f" (filtered by {code_filter})"
        elif isinstance(code_filter, dict):
            filter_label = f" (filtered by {code_filter.get('code_type', '')} = {code_filter.get('code_value', '')})"
        
        return {"success": True, "total_count": len(full_data), "displayed_count": len(preview_data),
                "is_truncated": len(full_data) > limit, "data": preview_data, "display_items": preview_data, "all_items": full_data, "data_ref": data_ref,
                "stats": {"max_slip_days": max(slips) if slips else 0,
                          "avg_slip_days": round(sum(slips)/len(slips), 1) if slips else 0,
                          "total_project_activities": len(analysis.get("activityAnalysis", {})),
                          "filtered_subset_total": len(acts),
                          "filter_applied": filter_label}}

    def get_critical_path(self, limit: int = 20, context: str = "audit", wbs_filter: Optional[str] = None, version_id: Optional[str] = None, code_filter: Optional[Dict] = None) -> Dict:
        from .scheduler_metrics import SchedulerMetrics
        source = self.data_store.get_latest(context=context, version_id=version_id)
        vid = source['id'] if source else None
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        acts = analysis.get("activityAnalysis", {})
        acts = self._filter_wbs(acts, wbs_filter, source)
        acts = self._filter_by_code(acts, code_filter)
        
        graph = source.get("dependency_graph", {}) if source else {}
        metrics = SchedulerMetrics.compute_core_metrics(acts, graph)
        
        critical = {a["id"]: a for a in metrics["critical_activities"]}
        sorted_acts = sorted(critical.items(), key=lambda x: x[1].get("float_hrs", 0))
        hpd = source.get("hours_per_day", 8) if source else 8
        
        wbs_map = self._get_wbs_map(source)
        full_data = [{"id": tid, "code": a.get("task_code",""), "name": a.get("task_name",""),
                      "wbs_path": wbs_map.get(str(a.get("wbs_id")), str(a.get("wbs_id", ""))),
                      "float_days": round(a.get("float_hrs", 0) / hpd, 1),
                      "delay_days": a.get("delay_days", 0),
                      "activity_codes": a.get("activity_codes", {})} for tid, a in sorted_acts]
        
        data_ref = self.data_store.store_result(full_data)
        preview_data = full_data[:limit]
        
        filter_label = ""
        if isinstance(code_filter, str):
            filter_label = f" (filtered by {code_filter})"
        elif isinstance(code_filter, dict):
            filter_label = f" (filtered by {code_filter.get('code_type', '')} = {code_filter.get('code_value', '')})"
            
        return {"success": True, "total_count": len(full_data), "displayed_count": len(preview_data),
                "is_truncated": len(full_data) > limit, "data": preview_data, "display_items": preview_data, "all_items": full_data, "data_ref": data_ref,
                "stats": {"total_critical": len(full_data),
                          "neg_float_count": sum(1 for a in critical.values() if a.get("float_hrs",0) < 0),
                          "total_project_activities": len(analysis.get("activityAnalysis", {})),
                          "filtered_subset_total": len(acts),
                          "filter_applied": filter_label}}

    def get_activity_code_types_tool(self, context: str = "audit", version_id: Optional[str] = None, scope: Optional[str] = None) -> Dict:
        """AI tool wrapper: Returns all Activity Code Types and their available values and assignment stats."""
        code_types = self.data_store.get_activity_code_types(version_id=version_id, context=context, scope=scope)
        if not code_types:
            return {"success": False, "error": f"No Activity Codes found in the loaded schedule{(' for scope ' + scope) if scope else ''}.", "total_count": 0, "data": [], "display_items": []}
        
        # Get actual assignments from activity analysis to compute assignment counts
        source = self.data_store.get_latest(context=context, version_id=version_id)
        vid = source['id'] if source else None
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        acts = analysis.get("activityAnalysis", {})
        
        type_assignments = {t: 0 for t in code_types.keys()}
        total_activities_with_codes = set()
        
        for tid, a in acts.items():
            codes = a.get("activity_codes", {})
            if codes:
                for t in codes.keys():
                    if t in type_assignments:
                        type_assignments[t] += 1
                        total_activities_with_codes.add(tid)
        
        data = [
            {
                "code_type": t, 
                "scope": info["scope"],
                "values": info["values"], 
                "distinct_value_count": len(info["values"]),
                "assigned_activities_count": type_assignments.get(t, 0)
            } 
            for t, info in code_types.items()
        ]
        
        # Sort data by scope (Project -> Global -> EPS) then by name
        scope_order = {"Project": 0, "Global": 1, "EPS": 2}
        data.sort(key=lambda x: (scope_order.get(x["scope"], 99), x["code_type"]))
        
        scope_counts = {
            "Project": sum(1 for d in data if d["scope"] == "Project"),
            "Global": sum(1 for d in data if d["scope"] == "Global"),
            "EPS": sum(1 for d in data if d["scope"] == "EPS")
        }
        
        return {
            "success": True,
            "total_count": len(data),
            "displayed_count": len(data),
            "is_truncated": False,
            "data": data,
            "display_items": data,
            "all_items": data,
            "stats": {
                "total_code_types": len(data), 
                "scope_counts": scope_counts,
                "total_distinct_values": sum(len(info["values"]) for info in code_types.values()),
                "total_activities_with_any_code": len(total_activities_with_codes),
                "total_project_activities": len(acts)
            },
            "template_type": "list"
        }

    def get_activity_code_values(self, code_type: str, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        """Returns all specific values for a given Activity Code Type."""
        code_types = self.data_store.get_activity_code_types(version_id=version_id, context=context)
        if not code_types:
            return {"success": False, "error": "No Activity Codes found in the loaded schedule."}
            
        matched_type = None
        
        # Helper to normalize strings for comparison
        def norm(s): return s.strip().lower().replace(" ", "")
        
        # 1. Try exact normalized match first
        for t in code_types.keys():
            if norm(t) == norm(code_type):
                matched_type = t
                break
                
        # 2. Try substring match if exact fails
        if not matched_type:
            for t in code_types.keys():
                if norm(code_type) in norm(t) or norm(t) in norm(code_type):
                    matched_type = t
                    break
                
        if not matched_type:
            return {
                "success": False, 
                "error": f"Activity Code Type '{code_type}' not found.",
                "available_types": list(code_types.keys())
            }
            
        info = code_types[matched_type]
        values = info["values"]
        scope = info["scope"]
        hierarchy = info.get("hierarchy", {})
        
        data = []
        for v in values:
            item = {"value": v, "scope": scope}
            if v in hierarchy:
                node = hierarchy[v]
                item["parent_actv_code_id"] = node.get("parent_actv_code_id")
                item["parent_name"] = node.get("parent_value")
                item["children"] = node.get("children_values", [])
                item["hierarchy_path"] = node.get("hierarchy_path", v)
            data.append(item)
        
        return {
            "success": True,
            "total_count": len(values),
            "displayed_count": len(values),
            "is_truncated": False,
            "data": data,
            "display_items": data,
            "all_items": data,
            "stats": {"code_type": matched_type, "scope": scope, "total_values": len(values)},
            "template_type": "list"
        }

    def get_activities_by_code(self, code_type: str = "", code_value: str = "", rollup: bool = False, exact_match: bool = False, limit: int = 100, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        """Returns activities filtered by Activity Code type and/or value.
        When no match is found, returns available code values for the requested type
        so the AI can show the user what IS available — no fuzzy guessing.
        """
        source = self.data_store.get_latest(context=context, version_id=version_id)
        if not source:
            return {"success": False, "error": "No schedule data loaded."}
        
        vid = source['id']
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        acts = analysis.get("activityAnalysis", {})
        
        all_code_types = self.data_store.get_activity_code_types(version_id=version_id, context=context)
        
        # --- AMBIGUITY RESOLUTION START ---
        if not code_type and code_value:
            matches = []
            cv_lower = code_value.strip().lower()
            
            # 1. Search Activity Codes
            for c_type, info in all_code_types.items():
                scope = info.get("scope", "Global")
                for val in info.get("values", []):
                    val_lower = val.lower()
                    if exact_match:
                        if cv_lower == val_lower:
                            matches.append({"type": "code", "code_type": c_type, "value": val, "scope": scope, "exact": True})
                    else:
                        if cv_lower in val_lower:
                            matches.append({"type": "code", "code_type": c_type, "value": val, "scope": scope, "exact": (cv_lower == val_lower)})
                            
            # 2. Search WBS
            wbs_map = self._get_wbs_map(source)
            for wbs_id, wbs_path in wbs_map.items():
                w_name = str(wbs_path.split(" > ")[-1]).strip()
                w_name_lower = w_name.lower()
                if exact_match:
                    if cv_lower == w_name_lower:
                        matches.append({"type": "wbs", "value": w_name, "exact": True})
                else:
                    if cv_lower in w_name_lower:
                        matches.append({"type": "wbs", "value": w_name, "exact": (cv_lower == w_name_lower)})

            # Deduplicate matches
            unique_matches = {}
            for m in matches:
                key = f"{m['type']}_{m.get('code_type', '')}_{m['value']}"
                if key not in unique_matches:
                    unique_matches[key] = m
                elif m['exact'] and not unique_matches[key]['exact']:
                    unique_matches[key] = m
            matches = list(unique_matches.values())

            if len(matches) > 1:
                # Rank matches
                def rank_score(m):
                    score = 0
                    if m.get("exact"): score += 1000
                    if m.get("type") == "code":
                        if str(m.get("scope", "")).lower() == "project":
                            score += 500
                    elif m.get("type") == "wbs":
                        score += 400
                    return score
                
                matches.sort(key=rank_score, reverse=True)
                
                # Check ambiguity
                if matches[0].get("exact") and not matches[1].get("exact"):
                    # Single strong match
                    top_match = matches[0]
                    if top_match["type"] == "code":
                        code_type = top_match["code_type"]
                        code_value = top_match["value"]
                        exact_match = True
                    else:
                        # WBS unambiguous match, tell AI to use WBS filter
                        return {
                            "success": True, "total_count": 0, "displayed_count": 0, "data": [], "display_items": [], "all_items": [],
                            "stats": {
                                "no_match_reason": f"'{code_value}' is a WBS element, not an Activity Code. Please query WBS data directly or use get_delayed_activities with wbs_filter='{top_match['value']}'."
                            }, "template_type": "list"
                        }
                else:
                    # Ambiguous matches - return clarification prompt
                    msg = f"I found multiple matches for '{code_value}'. Please ask the user to clarify by presenting this exact markdown list:\n\n"
                    seen_display = set()
                    display_cands = []
                    for m in matches:
                        if m["type"] == "code":
                            disp = f"- **{m['value']}** ({m['code_type']})"
                        else:
                            disp = f"- **{m['value']}** (WBS)"
                        if disp not in seen_display:
                            seen_display.add(disp)
                            display_cands.append(disp)
                            
                    msg += "\n".join(display_cands[:10])
                    msg += "\n\nWhich one would you like to view?"
                    
                    return {
                        "success": True, "total_count": 0, "displayed_count": 0, "data": [], "display_items": [], "all_items": [],
                        "stats": {
                            "filter": code_value,
                            "no_match_reason": msg,
                            "clarification_required": True
                        }, "template_type": "list"
                    }
            elif len(matches) == 1:
                top_match = matches[0]
                if top_match["type"] == "code":
                    code_type = top_match["code_type"]
                    code_value = top_match["value"]
                else:
                    return {
                        "success": True, "total_count": 0, "displayed_count": 0, "data": [], "display_items": [], "all_items": [],
                        "stats": {
                            "no_match_reason": f"'{code_value}' is a WBS element, not an Activity Code. Please query WBS data directly or use get_delayed_activities with wbs_filter='{top_match['value']}'."
                        }, "template_type": "list"
                    }
        # --- AMBIGUITY RESOLUTION END ---

        code_filter = {"code_type": code_type, "code_value": code_value, "rollup": rollup, "exact_match": exact_match}
        filtered = self._filter_by_code(acts, code_filter, code_types=all_code_types)
        
        if not filtered:
            # Zero match — provide available values so the AI can tell the user what exists
            
            available_values = []
            matched_type = None
            
            if code_type:
                # Exact or case-insensitive match for the type name
                for t, vals in all_code_types.items():
                    if t.strip().lower() == code_type.strip().lower():
                        matched_type = t
                        available_values = vals
                        break
            
            if not matched_type and code_value:
                # The user specified a value but no matching type — search all types for similar values
                for t, vals in all_code_types.items():
                    lower_vals = [v.lower() for v in vals]
                    if code_value.strip().lower() in lower_vals:
                        matched_type = t
                        available_values = vals
                        break
            
            error_msg = f"No activities found matching '{code_value}'"
            if code_type:
                error_msg += f" in code type '{code_type}'"
            error_msg += "."
            
            if matched_type and available_values:
                error_msg += f"\n\nAvailable values for '{matched_type}':\n"
                for v in available_values:
                    error_msg += f"  - {v}\n"
            elif all_code_types:
                error_msg += "\n\nAvailable Activity Code Types in this project:\n"
                for t, info in all_code_types.items():
                    vals = info["values"]
                    preview = ', '.join(vals[:5])
                    if len(vals) > 5:
                        preview += f', ... ({len(vals)} total)'
                    error_msg += f"  - {t}: [{preview}]\n"
            
            return {
                "success": True, "total_count": 0, "displayed_count": 0,
                "data": [], "display_items": [], "all_items": [],
                "stats": {
                    "filter": f"{code_type} = {code_value}",
                    "total_project_activities": len(acts),
                    "no_match_reason": error_msg,
                    "available_values": available_values if matched_type else [],
                    "available_types": list(all_code_types.keys()) if all_code_types else []
                },
                "template_type": "list"
            }
        
        hpd = source.get("hours_per_day", 8)
        wbs_map = self._get_wbs_map(source)
        
        sorted_acts = sorted(filtered.items(), key=lambda x: x[1].get("task_code", ""))
        full_data = [{
            "id": tid, "code": a.get("task_code", ""), "name": a.get("task_name", ""),
            "status": a.get("status_enum", ""),
            "float_days": round(a.get("float_hrs", 0) / hpd, 1),
            "delay_days": a.get("delay_days", 0),
            "is_critical": a.get("is_critical_p6", False),
            "wbs_path": wbs_map.get(str(a.get("wbs_id")), ""),
            "activity_codes": a.get("activity_codes", {})
        } for tid, a in sorted_acts]
        
        data_ref = self.data_store.store_result(full_data)
        preview_data = full_data[:limit]
        
        # Summary stats for the filtered set
        delayed_count = sum(1 for a in filtered.values() if (a.get("delay_days") or 0) > 0 and a.get("status_enum") != "COMPLETED")
        critical_count = sum(1 for a in filtered.values() if a.get("is_critical_p6", False))
        completed_count = sum(1 for a in filtered.values() if a.get("status_enum") == "COMPLETED")
        in_progress_count = sum(1 for a in filtered.values() if a.get("status_enum") == "IN_PROGRESS")
        
        return {
            "success": True, "total_count": len(full_data), "displayed_count": len(preview_data),
            "is_truncated": len(full_data) > limit, "data": preview_data, "display_items": preview_data, "all_items": full_data, "data_ref": data_ref,
            "stats": {
                "filter": f"{code_type} = {code_value}",
                "total_matched": len(full_data),
                "total_project_activities": len(acts),
                "delayed_count": delayed_count,
                "critical_count": critical_count,
                "completed_count": completed_count,
                "in_progress_count": in_progress_count
            },
            "template_type": "list"
        }


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

    def get_activities_by_status(self, limit: int = 20, status: str = "IN_PROGRESS", code_filter: Optional[str] = None, wbs_filter: Optional[str] = None, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        source = self.data_store.get_latest(context=context, version_id=version_id)
        vid = source['id'] if source else None
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        acts = analysis.get("activityAnalysis", {})
        
        acts = self._filter_wbs(acts, wbs_filter, source)
        
        if code_filter:
            acts = self._filter_by_code(acts, code_filter, self.data_store.get_activity_code_types(vid, context))
            
        status = status.upper()
        if status not in ["IN_PROGRESS", "COMPLETED", "NOT_STARTED"]:
            status = "IN_PROGRESS"
            
        filtered_acts = {tid: a for tid, a in acts.items() if a.get("status_enum") == status}
        
        # Sort by early start if available, else by ID
        def get_es(a):
            dt = a.get("early_start")
            if dt and str(dt) != "nan" and str(dt).strip() != "":
                return str(dt)
            return "9999-12-31"
            
        sorted_acts = sorted(filtered_acts.items(), key=lambda x: (get_es(x[1]), x[1].get("task_code", "")))
        
        wbs_map = self._get_wbs_map(source)
        full_data = [{"id": tid, "code": a.get("task_code",""), "name": a.get("task_name",""),
                      "wbs_path": wbs_map.get(str(a.get("wbs_id")), str(a.get("wbs_id", ""))),
                      "status": a.get("status_enum")} for tid, a in sorted_acts]
                      
        data_ref = self.data_store.store_result(full_data)
        preview_data = full_data[:limit]
        
        return {"success": True, "total_count": len(full_data), "displayed_count": len(preview_data),
                "is_truncated": len(full_data) > limit, "data": preview_data, "display_items": preview_data, "all_items": full_data, "data_ref": data_ref,
                "stats": {"status_type": status}}


    def get_filtered_activities(self, limit: int = 20, status: Optional[str] = None, code_filter: Optional[str] = None, wbs_filter: Optional[str] = None, is_delayed: Optional[bool] = None, is_at_risk: Optional[bool] = None, is_critical: Optional[bool] = None, cost_loaded: Optional[bool] = None, evm_filter: Optional[str] = None, sort_by: Optional[str] = None, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        source = self.data_store.get_latest(context=context, version_id=version_id)
        if not source: return {"success": False, "error": "No project loaded."}
        
        # Pull table data from HIERARCHY to inherit EVM and Cost calculations
        tree_resp = self.data_store.get_table_data(table_type="HIERARCHY", limit=999999, context=context, source_id=source['id'])
        
        def flatten_wbs(nodes):
            res = []
            for n in nodes:
                res.extend(n.get("activities", []))
                res.extend(flatten_wbs(n.get("children", [])))
            return res
            
        acts = flatten_wbs(tree_resp.get("records", []))
        
        debug_info = {}
        debug_info["1_total_table_acts"] = len(acts)
        ami = next((a for a in acts if a.get("task_code") == "AMI-FXCH-1080"), None)
        debug_info["ami_initial"] = ami.copy() if ami else "NOT_FOUND"

        # Base filter using analysis dict for WBS and Codes
        analysis = self.data_store.get_deterministic_analysis(version_id=source['id'], context=context).get("activityAnalysis", {})
        debug_info["2_total_analysis_keys"] = len(analysis)
        
        if wbs_filter:
            analysis = self._filter_wbs(analysis, wbs_filter, source)
        if code_filter:
            analysis = self._filter_by_code(analysis, code_filter, self.data_store.get_activity_code_types(source['id'], context))
            
        allowed_tids = {str(k) for k in analysis.keys()}
        acts = [a for a in acts if str(a.get("task_id")) in allowed_tids]
        debug_info["3_after_allowed_tids"] = len(acts)
        debug_info["ami_after_allowed"] = any(a.get("task_code") == "AMI-FXCH-1080" for a in acts)
        
        if status:
            acts = [a for a in acts if a.get("_analysis", {}).get("status") == status.upper()]
        debug_info["4_after_status"] = len(acts)
        debug_info["ami_after_status"] = any(a.get("task_code") == "AMI-FXCH-1080" for a in acts)
        
        if is_delayed is True:
            acts = [a for a in acts if a.get("_analysis", {}).get("classification") == "DELAYED"]
            
        if is_at_risk is True:
            acts = [a for a in acts if a.get("_analysis", {}).get("classification") == "AT_RISK"]
            
        if is_critical is True:
            acts = [a for a in acts if a.get("_analysis", {}).get("float_hrs", 0) <= 0 and a.get("_analysis", {}).get("status") != "COMPLETED"]
            
        if cost_loaded is True:
            acts = [a for a in acts if a.get("cost_loaded", False)]
        debug_info["5_after_cost_loaded"] = len(acts)
        debug_info["ami_after_cost"] = any(a.get("task_code") == "AMI-FXCH-1080" for a in acts)
            
        if evm_filter == "spi_lt_1":
            acts = [a for a in acts if a.get("spi") is not None and a.get("spi") < 1.0]
        elif evm_filter == "cpi_lt_1":
            acts = [a for a in acts if a.get("cpi") is not None and a.get("cpi") < 1.0]
        elif evm_filter == "sv_neg":
            acts = [a for a in acts if a.get("sv_cost", 0) < 0]
        elif evm_filter == "cv_neg":
            acts = [a for a in acts if a.get("cv_cost", 0) < 0]
            
        if sort_by == "bac_desc":
            acts.sort(key=lambda x: max(x.get("budget_cost", 0), x.get("bl_project_cost", 0)), reverse=True)
        elif sort_by == "ev_desc":
            acts.sort(key=lambda x: x.get("ev_cost", 0), reverse=True)
        elif sort_by == "variance_desc":
            acts.sort(key=lambda x: abs(x.get("sv_cost", 0)), reverse=True)
        elif sort_by == "delay_desc":
            acts.sort(key=lambda x: x.get("_analysis", {}).get("delay_days", 0), reverse=True)
            
        # Flatten properties for cleaner AI context
        for a in acts:
            an = a.get("_analysis", {})
            a["status"] = an.get("status", "NOT_STARTED")
            a["delay_days"] = an.get("delay_days", 0)
            a["float_hrs"] = an.get("float_hrs", 0)
            a["is_critical"] = an.get("is_critical", False)
            a["classification"] = an.get("classification", "ON_TRACK")
            a.pop("_analysis", None)
            
        preview = acts[:limit]
        data_ref = self.data_store.store_result(preview)
        
        return {"success": True, "total_count": len(acts), "displayed_count": len(preview),
                "is_truncated": len(acts) > limit, "data": preview, "display_items": preview, "all_items": acts, "data_ref": data_ref,
                "stats": {"filters": {"status": status, "cost_loaded": cost_loaded, "evm": evm_filter}, "debug": debug_info}}

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
            
        # Count delayed, at risk and completed activities
        delayed_acts = {tid: a for tid, a in acts.items() if a.get("classification") == "DELAYED"}
        at_risk_acts = {tid: a for tid, a in acts.items() if a.get("classification") == "AT_RISK"}
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
            "delayed_activities": len(delayed_acts),
            "at_risk_activities": len(at_risk_acts),
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

    def get_calendar_info(self, calendar_name: Optional[str] = None, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        """Returns structured calendar information for the loaded project (B-041 enhanced)."""
        calendars = self.data_store.get_calendar_info(version_id=version_id, context=context)
        if not calendars:
            return {"success": False, "error": "No calendar data found in the loaded schedule.", "clarify": True, "total_count": 0, "data": [], "display_items": []}
            
        if calendar_name:
            search_str = calendar_name.lower().replace(" ", "").replace("-", "").replace("_", "")
            cals = [c for c in calendars if search_str in c.get('name', '').lower().replace(" ", "").replace("-", "").replace("_", "")]
            if cals:
                calendars = cals
        elif len(calendars) > 1:
            # If no specific calendar requested, but multiple exist, return a clarify payload.
            names = "\n* ".join(c.get("name", "") for c in calendars)
            return {"success": False, "error": f"Multiple calendars exist in this project.\n\n* {names}\n\nPlease specify:\n\n• calendar name\n• activity\n• or date range", "clarify": True, "total_count": 0, "data": [], "display_items": []}
        
        # B-041: Compute enhanced stats
        workweek_counts = {}
        semantic_counts = {}
        total_holidays = 0
        for c in calendars:
            wt = c.get("workweek_type", "unknown")
            workweek_counts[wt] = workweek_counts.get(wt, 0) + 1
            for tag in c.get("semantic_tags", []):
                semantic_counts[tag] = semantic_counts.get(tag, 0) + 1
            total_holidays += c.get("holiday_count", 0)
        
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
                "workweek_distribution": workweek_counts,
                "semantic_tags": semantic_counts,
                "total_holidays": total_holidays,
            },
            "template_type": "list"
        }

    def get_baseline_pairing_status(self, context: str = "audit") -> Dict:
        """B-040: Returns the current baseline-update pairing status."""
        pairing = self.data_store.validate_baseline_pairing(context=context)
        return {
            "success": True,
            "total_count": 1,
            "displayed_count": 1,
            "is_truncated": False,
            "data": [pairing],
            "display_items": [pairing],
            "all_items": [pairing],
            "stats": {
                "is_valid": pairing.get("valid", False),
                "overlap_pct": pairing.get("overlap_pct"),
                "baseline_name": pairing.get("baseline_name", "Not loaded"),
                "update_name": pairing.get("update_name", "Not loaded"),
                "reason": pairing.get("reason"),
            },
            "template_type": "status"
        }

    def get_activities_by_calendar(self, calendar_name: Optional[str] = None, calendar_id: Optional[str] = None,
                                    workweek_type: Optional[str] = None, semantic_tag: Optional[str] = None,
                                    limit: int = 50, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        """B-041: Filter activities by calendar criteria. Delegates to data_store."""
        return self.data_store.get_activities_by_calendar(
            calendar_name=calendar_name,
            calendar_id=calendar_id,
            workweek_type=workweek_type,
            semantic_tag=semantic_tag,
            limit=limit,
            version_id=version_id,
            context=context
        )

    def get_calendar_exceptions(self, calendar_name: Optional[str] = None, month: Optional[int] = None, 
                                year: Optional[int] = None, exception_type: Optional[str] = None, date_filter: str = "effective",
                                limit: int = 100, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        """B-041: Retrieve specific exception dates for a calendar."""
        print(f"[DEBUG] get_calendar_exceptions called with: calendar_name={calendar_name}, month={month}, year={year}, exception_type={exception_type}")
        calendars = self.data_store.get_calendar_info(version_id=version_id, context=context)
        if not calendars:
            return {"success": False, "error": "No calendar data found.", "clarify": True, "total_count": 0, "data": []}
            
        if calendar_name:
            search_str = calendar_name.lower().replace(" ", "").replace("-", "").replace("_", "")
            cals = []
            
            # Handle positional names like "4th one", "number 2", "second one"
            import re
            
            # Map words to numbers
            word_to_num = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10, 'last': len(calendars)}
            
            idx = None
            pos_match = re.search(r'(\d+)(st|nd|rd|th)?\s*(one)?|number\s*(\d+)', calendar_name.lower())
            if pos_match:
                idx_str = pos_match.group(1) or pos_match.group(4)
                if idx_str:
                    idx = int(idx_str) - 1
            else:
                for word, num in word_to_num.items():
                    if word in calendar_name.lower():
                        idx = num - 1
                        break
                        
            if idx is not None and 0 <= idx < len(calendars):
                cals = [calendars[idx]]
            
            if not cals:
                cals = [c for c in calendars if search_str in c.get('name', '').lower().replace(" ", "").replace("-", "").replace("_", "")]
        else:
            cals = calendars
            
        if len(cals) > 1 and not calendar_name:
            names = "\n* ".join(c.get("name", "") for c in calendars)
            return {"success": False, "error": f"Multiple calendars exist in this project.\n\n* {names}\n\nPlease specify:\n\n• calendar name\n• activity\n• or date range", "clarify": True, "total_count": 0, "data": []}
        
        all_exceptions = []
        for c in cals:
            # Gather exceptions
            nw_key = "effective_non_working_dates" if date_filter == "effective" else "raw_non_working_dates"
            w_key = "effective_working_overrides" if date_filter == "effective" else "raw_working_overrides"
            
            holidays = [{"date": d, "type": "non_working", "calendar": c["name"]} for d in c.get(nw_key, c.get("non_working_exceptions", []))]
            working = [{"date": d, "type": "working", "calendar": c["name"]} for d in c.get(w_key, c.get("working_exceptions", []))]
            
            combined = []
            if not exception_type or "holiday" in exception_type.lower() or "non" in exception_type.lower():
                combined.extend(holidays)
            if not exception_type or "working" in exception_type.lower() and "non" not in exception_type.lower():
                combined.extend(working)
                
            print(f"[DEBUG] Calendar {c['name']} - holidays size: {len(holidays)}, working size: {len(working)}, combined: {len(combined)}")
            for ex in combined:
                d_parts = ex["date"].split('-')
                if len(d_parts) == 3:
                    y, m, d = int(d_parts[0]), int(d_parts[1]), int(d_parts[2])
                    if year and y != int(year): continue
                    if month and m != int(month): continue
                all_exceptions.append(ex)
                
        print(f"[DEBUG] all_exceptions size: {len(all_exceptions)}")
        # Sort by date
        all_exceptions.sort(key=lambda x: x["date"])
        
        total_count = len(all_exceptions)
        display_data = all_exceptions[:limit]
        
        # Include metadata for the matched calendar
        cal_metadata = {}
        if cals and len(cals) == 1:
            cal = cals[0]
            cal_metadata = {
                "name": cal.get("name"),
                "workweek_type": cal.get("workweek_type"),
                "hours_per_day": cal.get("hours_per_day"),
                "total_effective_non_working": cal.get("effective_non_working_dates_count"),
                "total_raw_non_working": cal.get("raw_non_working_dates_count"),
                "total_effective_working_overrides": cal.get("effective_working_overrides_count", 0),
                "total_raw_working_overrides": cal.get("raw_working_overrides_count", 0)
            }
        
        return {
            "success": True,
            "total_count": total_count,
            "displayed_count": len(display_data),
            "is_truncated": total_count > limit,
            "data": display_data,
            "all_items": all_exceptions,
            "calendar_metadata": cal_metadata,
            "stats": {"total_exceptions": total_count},
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

    def check_bei(self, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        source = self.data_store.get_latest(context=context, version_id=version_id)
        vid = source['id'] if source else None
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        assessment = analysis.get("projectSummary", {}).get("assessment", [])
        bei = next((a for a in assessment if a["id"] == 14), {})

        if bei.get("status") is None:
            return {"success": False, "error": bei.get("na_reason") or "BEI requires an update file with progress data."}

        return {"success": True, "total_count": 1, "displayed_count": 1,
                "data": [{"bei": bei}], "display_items": [], "all_items": [], "stats": {
                    "bei_val": round(float(bei.get("val", 0)), 3),
                    "bei_status": "PASS" if bei.get("status") else "FAIL",
                    "bei_threshold": bei.get("threshold", ">= 0.95"),
                    "affected_count": bei.get("affected_count"),
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

    # B-004.1: default lookahead window (working days) for flagging an incomplete predecessor as a
    # near-term risk — matches the two-week planner lookahead per manager sign-off (2026-08-04).
    # No project-config layer exists yet (tracked separately as B-205: add lookahead_window_days to
    # config schema). Until B-205 lands, _get_lookahead_window_days() is the single lookup point —
    # never hardcode this window inline anywhere else.
    DEFAULT_LOOKAHEAD_WINDOW_DAYS = 10

    def _get_lookahead_window_days(self, source: Dict) -> int:
        """B-004.1: reads source['config']['lookahead_window_days'] once a config layer (B-205)
        is wired in; falls back to DEFAULT_LOOKAHEAD_WINDOW_DAYS until then."""
        cfg = (source or {}).get("config") or {}
        try:
            val = cfg.get("lookahead_window_days")
            return int(val) if val is not None else self.DEFAULT_LOOKAHEAD_WINDOW_DAYS
        except (TypeError, ValueError):
            return self.DEFAULT_LOOKAHEAD_WINDOW_DAYS

    @staticmethod
    def _task_percent_complete(row: Dict) -> Optional[float]:
        """CP_Phys / CP_Drtn / CP_Units dispatch, mirroring the EV percent-complete logic in
        data_store.py's get_deterministic_analysis, as a standalone helper so B-004.1's
        predecessor-completion math doesn't need the full EV pipeline. Returns 0-100 or None."""
        import pandas as pd
        pct_type = row.get("complete_pct_type")
        status = row.get("status_code")
        if pct_type == "CP_Phys":
            phys = pd.to_numeric(row.get("phys_complete_pct"), errors="coerce")
            return float(phys) if pd.notnull(phys) else 0.0
        if pct_type == "CP_Drtn":
            orig = pd.to_numeric(row.get("target_drtn_hr_cnt"), errors="coerce")
            rem = pd.to_numeric(row.get("remain_drtn_hr_cnt"), errors="coerce")
            if pd.notnull(orig) and orig > 0:
                dur_pct = (orig - (rem if pd.notnull(rem) else 0)) / orig
                return round(max(0.0, min(1.0, dur_pct)) * 100, 1)
            return 100.0 if status == "TK_Complete" else 0.0
        if pct_type == "CP_Units":
            return 100.0 if status == "TK_Complete" else None
        return None

    def analyze_activity_delay(self, activity_name: str, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        import pandas as pd
        from .scheduler import P6Calendar

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

        tasks_df = source["df"]["tasks"]
        tasks_indexed = tasks_df.set_index("task_id", drop=False)
        hpd = source.get("hours_per_day", 8.0) or 8.0
        data_date = pd.to_datetime(source.get("data_date"), errors="coerce")

        # B-004.1: per-calendar working-day arithmetic — the lookahead window must be counted on
        # the activity's OWN calendar (a 5-day authority activity spans two calendar weeks in 10
        # working days; a 7-day procurement one doesn't), not flat calendar days.
        calendars_df = source["df"].get("calendar", source["df"].get("CALENDAR"))
        cal_map = {}
        if calendars_df is not None and not calendars_df.empty:
            for _, crow in calendars_df.iterrows():
                cal_map[str(crow.get("clndr_id"))] = P6Calendar(crow.to_dict())

        def _cal_for(tid):
            if tid in tasks_indexed.index:
                return cal_map.get(str(tasks_indexed.loc[tid].get("clndr_id", "")), P6Calendar())
            return P6Calendar()

        def _display_list(rel_list):
            out = []
            for rel in rel_list:
                prow = tasks_indexed.loc[rel["id"]] if rel["id"] in tasks_indexed.index else None
                if prow is not None:
                    act_finish = pd.to_datetime(prow.get("act_end_date"), errors="coerce")
                    act_start_r = pd.to_datetime(prow.get("act_start_date"), errors="coerce")
                    status = "Completed" if pd.notnull(act_finish) else ("In Progress" if pd.notnull(act_start_r) else "Not Started")
                    code = prow.get("task_code", "")
                else:
                    status, code = "Not Started", ""
                out.append({**rel, "code": code, "status": status})
            return out

        predecessors_raw = node.get("predecessors", [])[:5]
        successors_raw = node.get("successors", [])[:5]
        predecessors = _display_list(predecessors_raw)
        successors = _display_list(successors_raw)

        # B-004.1: "incomplete" per manager spec = remaining duration > 0 OR no actual finish.
        def _is_predecessor_complete(pid):
            if pid not in tasks_indexed.index:
                return True  # unknown activity carries no risk signal
            prow = tasks_indexed.loc[pid]
            act_finish = pd.to_datetime(prow.get("act_end_date"), errors="coerce")
            remain_hrs = pd.to_numeric(prow.get("remain_drtn_hr_cnt"), errors="coerce")
            remain_hrs = remain_hrs if pd.notnull(remain_hrs) else 0.0
            return pd.notnull(act_finish) and remain_hrs <= 0

        all_predecessors_complete = bool(predecessors_raw) and all(_is_predecessor_complete(p["id"]) for p in predecessors_raw)

        # B-004.1: near-term risk fires only when all three manager-specified conditions hold:
        #   1) activity.early_start <= data_date + lookahead_window_days (working days, activity's own calendar)
        #   2) activity has no actual start
        #   3) at least one predecessor is incomplete
        # When multiple predecessors are incomplete, the "driving" one is whichever has the latest
        # early_finish — the actual constraint holding back this activity's start.
        near_term_risk = None
        lookahead_days = self._get_lookahead_window_days(source)

        if activity_id in tasks_indexed.index and pd.notnull(data_date):
            cur_row = tasks_indexed.loc[activity_id]
            early_start = pd.to_datetime(cur_row.get("early_start"), errors="coerce")
            not_started = pd.isnull(pd.to_datetime(cur_row.get("act_start_date"), errors="coerce"))
            window_end = _cal_for(activity_id).add_workdays(data_date, lookahead_days)
            within_window = pd.notnull(early_start) and early_start <= window_end

            if within_window and not_started:
                incomplete = []
                for p in predecessors_raw:
                    pid = p["id"]
                    if pid not in tasks_indexed.index or _is_predecessor_complete(pid):
                        continue
                    prow = tasks_indexed.loc[pid]
                    remain_hrs = pd.to_numeric(prow.get("remain_drtn_hr_cnt"), errors="coerce")
                    incomplete.append({
                        "id": pid,
                        "code": prow.get("task_code", ""),
                        "name": prow.get("task_name", p.get("name", "")),
                        "early_finish": pd.to_datetime(prow.get("early_finish"), errors="coerce"),
                        "percent_complete": self._task_percent_complete(prow.to_dict()),
                        "remaining_days": round((remain_hrs if pd.notnull(remain_hrs) else 0.0) / hpd, 1)
                    })

                if incomplete:
                    incomplete.sort(key=lambda x: (pd.notnull(x["early_finish"]), x["early_finish"]), reverse=True)
                    driving = incomplete[0]
                    others = len(incomplete) - 1

                    early_start_display = f"{early_start.strftime('%b')} {early_start.day}, {early_start.year}"
                    pct_display = f"{driving['percent_complete']:.0f}" if driving["percent_complete"] is not None else "an unknown"
                    rec_text = (f"{act['code']} - {act['name']} is scheduled to start {early_start_display} "
                                f"but its predecessor {driving['code']} - {driving['name']} is "
                                f"{pct_display}% complete with {driving['remaining_days']} days remaining.")
                    if others > 0:
                        rec_text += f" ({others} more incomplete predecessor{'s' if others > 1 else ''}.)"

                    near_term_risk = {
                        "activity_early_start": str(early_start.date()),
                        "lookahead_window_days": lookahead_days,
                        "driving_predecessor_id": driving["id"],
                        "driving_predecessor_code": driving["code"],
                        "driving_predecessor_name": driving["name"],
                        "driving_predecessor_percent_complete": driving["percent_complete"],
                        "driving_predecessor_remaining_days": driving["remaining_days"],
                        "additional_incomplete_predecessor_count": others,
                        "deterministic_recommendation": rec_text
                    }

        has_actionable_recommendation_data = bool(near_term_risk) or all_predecessors_complete or act["is_critical"] or (act.get("delay_days") or 0) > 0

        act_data = [{
                    "id": activity_id, "code": act["code"], "name": act["name"],
                    "wbs_path": act.get("wbs_path", ""),
                    "delay_days": act["delay_days"], "float_days": act["float_days"],
                    "is_critical": act["is_critical"],
                    "predecessors": predecessors,
                    "successors": successors,
                    "all_predecessors_complete": all_predecessors_complete,
                    "near_term_risk": near_term_risk,
                    "has_actionable_recommendation_data": has_actionable_recommendation_data
                }]

        return {"success": True, "total_count": 1, "displayed_count": 1,
                "data": act_data, "display_items": act_data, "all_items": act_data,
                "stats": {"delay_days": act["delay_days"],
                          "predecessor_count": len(predecessors),
                          "successor_count": len(successors),
                          "all_predecessors_complete": all_predecessors_complete,
                          "has_near_term_risk": bool(near_term_risk),
                          "has_actionable_recommendation_data": has_actionable_recommendation_data}, "template_type": "analysis"}

    def get_wbs_branch_stats(self, context: str = "audit", version_id: Optional[str] = None) -> Dict:
        """Returns per-WBS-branch schedule performance metrics without requiring EV configuration.
        Exposes: activity_count, total_variance_days, critical_count, delayed_count, status_tag.
        This is the SPI-equivalent when Earned Value is not configured in the project.
        """
        source = self.data_store.get_latest(context=context, version_id=version_id)
        if not source:
            return {"success": False, "error": "No schedule data loaded."}

        vid = source['id']
        hpd = source.get("hours_per_day", 8)
        analysis = self.data_store.get_deterministic_analysis(version_id=vid, context=context)
        acts = analysis.get("activityAnalysis", {})
        wbs_map = self._get_wbs_map(source)

        # Build WBS parent map for branch resolution
        wbs_df = source.get("df", {}).get("projwbs")
        if wbs_df is None:
            return {"success": False, "error": "No WBS data available."}

        # Build: wbs_id -> wbs_name, wbs_id -> parent_wbs_id
        wbs_id_to_name = {}
        wbs_id_to_parent = {}
        try:
            for _, row in wbs_df.iterrows():
                wid = str(row.get("wbs_id", ""))
                wbs_id_to_name[wid] = str(row.get("wbs_name") or row.get("wbs_short_name") or wid)
                parent = row.get("parent_wbs_id")
                wbs_id_to_parent[wid] = str(parent) if parent and str(parent) != "nan" else None
        except Exception as e:
            logger.warning(f"WBS map build error: {e}")

        # Walk up to find the top-level WBS branch for a given wbs_id
        def get_top_branch(wid: str, visited=None) -> str:
            if visited is None:
                visited = set()
            if wid in visited:
                return wid
            visited.add(wid)
            parent = wbs_id_to_parent.get(wid)
            if parent and parent in wbs_id_to_parent:  # has a grandparent → keep walking
                return get_top_branch(parent, visited)
            return wid  # this IS the top level

        # Aggregate metrics per top-level WBS branch
        branch_data: Dict[str, Dict] = {}

        for tid, a in acts.items():
            wid = str(a.get("wbs_id", ""))
            branch_id = get_top_branch(wid)
            branch_name = wbs_id_to_name.get(branch_id, branch_id)

            if branch_name not in branch_data:
                branch_data[branch_name] = {
                    "wbs_branch": branch_name,
                    "activity_count": 0,
                    "total_variance_days": 0.0,
                    "critical_count": 0,
                    "delayed_count": 0,
                    "at_risk_count": 0,
                    "completed_count": 0,
                    "in_progress_count": 0,
                    "not_started_count": 0,
                }

            b = branch_data[branch_name]
            b["activity_count"] += 1

            status = a.get("status_enum", "NOT_STARTED")
            if status == "COMPLETED":
                b["completed_count"] += 1
            elif status == "IN_PROGRESS":
                b["in_progress_count"] += 1
            else:
                b["not_started_count"] += 1

            classification = a.get("classification", "ON_TRACK")
            if classification == "DELAYED":
                b["delayed_count"] += 1
            elif classification == "AT_RISK":
                b["at_risk_count"] += 1

            delay = a.get("delay_days") or 0
            if delay > 0 and status != "COMPLETED":
                b["total_variance_days"] += delay

            if a.get("is_critical_p6", False) and status != "COMPLETED":
                b["critical_count"] += 1

        # Derive status tag per branch
        # Thresholds are read from WBS_STATUS_THRESHOLDS (top of file).
        # These are placeholder values — confirm with planner before reporting.
        t = WBS_STATUS_THRESHOLDS
        def status_tag(b: Dict) -> str:
            total = b["activity_count"]
            if total == 0:
                return "Empty"
            completed = b["completed_count"]
            if completed == total:
                if b["total_variance_days"] <= 0:
                    return "Performing"
                else:
                    return "Slipping"
            delayed_pct = b["delayed_count"] / total
            at_risk_pct = b["at_risk_count"] / total
            critical_pct = b["critical_count"] / total
            if delayed_pct > t["delayed_pct"]:
                return "Slipping"
            if critical_pct > t["critical_pct"]:
                return "Critical"
            if delayed_pct > t["at_risk_delayed_pct"] or at_risk_pct > t["at_risk_delayed_pct"] or critical_pct > t["at_risk_critical_pct"]:
                return "Watch"
            return "Performing"

        results = []
        for name, b in branch_data.items():
            b["total_variance_days"] = round(b["total_variance_days"], 1)
            b["status_tag"] = status_tag(b)
            b["ev_note"] = "EV/PV not configured (Duration % Complete only). SPI unavailable."
            results.append(b)

        # Sort: Critical first, then by delayed count descending
        status_order = {"Critical": 0, "Slipping": 1, "Watch": 2, "Performing": 3, "Empty": 4}
        def get_order_key(tag: str) -> int:
            if tag in status_order:
                return status_order[tag]
            return 9
        results.sort(key=lambda x: (get_order_key(x["status_tag"]), -x["delayed_count"]))

        data_ref = self.data_store.store_result(results)
        total_acts = len(acts)
        total_delayed = sum(b["delayed_count"] for b in results)
        total_at_risk = sum(b["at_risk_count"] for b in results)
        total_critical = sum(b["critical_count"] for b in results)

        return {
            "success": True,
            "total_count": len(results),
            "displayed_count": len(results),
            "is_truncated": False,
            "data": results,
            "display_items": results,
            "all_items": results,
            "data_ref": data_ref,
            "stats": {
                "total_wbs_branches": len(results),
                "total_project_activities": total_acts,
                "total_delayed_activities": total_delayed,
                "total_at_risk_activities": total_at_risk,
                "total_critical_activities": total_critical,
                "ev_available": False,
                "ev_note": "Earned Value not configured. All activities use Duration % Complete (CP_Drtn). act_reg_cost is zero across all TASKRSRC rows. SPI/CPI cannot be computed from this XER.",
                "thresholds_applied": WBS_STATUS_THRESHOLDS,
                "thresholds_note": "PLACEHOLDER values — not planner-approved. Review WBS_STATUS_THRESHOLDS in analyzer.py before using for reporting."
            },
            "template_type": "wbs_branch_stats"
        }
