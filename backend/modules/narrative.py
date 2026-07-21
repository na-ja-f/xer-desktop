"""
M4 narrative generation on M1 audit findings (B-019).

Turns the DS7 `findings` rows for one snapshot into a short plain-language
narrative a planner could paste into a report. Standalone by design — not
wired into analyzer.py's router/dispatch/explain pipeline, since this isn't
an /ask chat tool.

generate_audit_narrative always returns a dict, never raises, mirroring the
fail-safe pattern of XERAnalyzer._explain/_fallback_response.
"""
import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

NARRATIVE_PROMPT = """You are a project controls analyst writing a plain-language
summary of a DCMA 14-point schedule audit for a program manager.

STRICT RULES:
- Narrate ONLY the findings provided below. Never invent, estimate, or infer a
  number, percentage, count, or fact that is not explicitly present in the data.
- If a check's narrative_hint or severity is missing/null, say plainly that
  check could not be evaluated - do not guess at its outcome.
- Do not speculate about root causes or recommendations beyond what the
  provided narrative_hint text already states.
- Plain, non-technical language. Exactly 2 to 3 paragraphs of prose. No
  headers, no bullet points, no markdown.

Respond as JSON:
{"status": "ok" | "no_data", "narrative": "<2-3 paragraphs>" | null, "message": "<short reason>" | null}
"""


def generate_audit_narrative(
    findings_rows: List[Dict[str, Any]],
    client,
    model: str,
    provider: str,
) -> Dict[str, Any]:
    if not findings_rows:
        return {
            "status": "no_data",
            "narrative": None,
            "message": "No DCMA audit findings are available yet for this snapshot.",
        }

    passing = sum(1 for f in findings_rows if f.get("severity") == "pass")
    failing = sum(1 for f in findings_rows if f.get("severity") == "fail")
    payload = {
        "summary": {"evaluatedCount": len(findings_rows), "passingCount": passing, "failingCount": failing},
        "findings": findings_rows,
    }

    try:
        res = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": NARRATIVE_PROMPT},
                {"role": "user", "content": json.dumps(payload, default=str)},
            ],
            temperature=0.1,
            max_tokens=600,
            response_format={"type": "json_object"} if provider == "openai" else None,
        )
        raw = res.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        parsed = json.loads(raw)

        narrative = parsed.get("narrative")
        if parsed.get("status") == "ok" and isinstance(narrative, str) and narrative.strip():
            return {"status": "ok", "narrative": narrative.strip(), "message": None}

        return {
            "status": "no_data",
            "narrative": None,
            "message": parsed.get("message") or "Narrative could not be generated for this snapshot.",
        }
    except Exception as e:
        logger.error(f"Audit narrative generation failed: {e}")
        return {
            "status": "error",
            "narrative": None,
            "message": "Narrative generation is unavailable right now.",
        }
