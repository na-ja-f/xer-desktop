"""
B-016: Hero score, grade, and status sentence for the Schedule Audit (M1) page.

Pure functions only — no DB/IO here. compute_hero() derives everything from
the same `assessment` list (data_store.get_deterministic_analysis) that
build_m1_findings (findings.py) writes to DS7, so the numbers always match
what's persisted. compute_trend() takes DS7 history (db.get_score_history)
as an argument rather than querying itself, so it stays testable in isolation.
"""
from typing import Dict, List, Optional

# Mirrors AssessmentTable.jsx's DISPLAY_NAMES — kept in sync by hand since
# each side renders its own copy of the same 13 evaluated DCMA point names.
DISPLAY_NAMES = {
    1: "Missing logic",
    2: "Leads",
    3: "Lags",
    4: "Relationship types",
    5: "Hard constraints",
    6: "High float",
    7: "Negative float",
    8: "High duration",
    9: "Invalid dates",
    10: "Resources",
    11: "Missed tasks",
    12: "Critical path",
    13: "CPLI",
}

# 90+ = A, 80-89 = B+, 70-79 = B-, 55-69 = C, below 55 = D.
GRADE_BANDS = (
    (90, "A"),
    (80, "B+"),
    (70, "B−"),  # B− 
    (55, "C"),
)


def compute_grade(score: float) -> str:
    for cutoff, letter in GRADE_BANDS:
        if score >= cutoff:
            return letter
    return "D"


def compute_hero(assessment: List[Dict]) -> Dict:
    """Excludes point 14 (Baseline/BEI) — not yet evaluated (B-028, not
    started), matching AssessmentTable.jsx's own `id !== 14` filter."""
    points = [p for p in assessment if p.get("id") != 14]
    evaluated = len(points)
    failing_points = [p for p in points if not p.get("status")]
    passing = evaluated - len(failing_points)
    failing = len(failing_points)

    score = round(passing / evaluated * 100) if evaluated else 0
    grade = compute_grade(score)

    failing_checks = [DISPLAY_NAMES.get(p["id"], p.get("name", "")) for p in failing_points]

    if failing == 0:
        sentence = f"All {evaluated} evaluated checks are passing."
    else:
        sentence = (
            f"{failing} of {evaluated} checks failing, {passing} passing. "
            f"Attention needed on {', '.join(failing_checks)}."
        )

    return {
        "score": score,
        "grade": grade,
        "statusSentence": sentence,
        "failingCount": failing,
        "passingCount": passing,
        "evaluatedCount": evaluated,
        "failingChecks": failing_checks,
        "trend": None,
    }


def compute_trend(history: List[Dict], current_snapshot_id: str) -> Optional[Dict]:
    """None unless the snapshot currently being viewed has a predecessor in
    its own DS7 lineage. Deliberately keyed off `current_snapshot_id` rather
    than just "the two latest entries in history" — a user can select an
    older snapshot from the version history, and its trend must be relative
    to what's on screen, not to whatever the newest snapshot happens to be."""
    index = next((i for i, h in enumerate(history) if h["snapshot_id"] == current_snapshot_id), None)
    if index is None or index == 0:
        return None
    current = history[index]["score"]
    previous = history[index - 1]["score"]
    if current is None or previous is None:
        return None
    return {"delta": current - previous, "previousScore": previous}
