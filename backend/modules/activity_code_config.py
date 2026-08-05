"""
Activity Code category-name normalization (B-204, Phase 2 of the ticket).

Different projects name the same concept differently (LEVELS vs PROJECT LEVELS
vs AMR-P1-LEVELS). This module auto-suggests a mapping from each project's raw
Activity Code Type names to a small internal canonical vocabulary, persisted
via modules.db's activity_code_config table so the user can review/override
them in Settings — the mapping is never hardcoded per-project.

Called once per upload (see main.py's /upload-xer), best-effort like the DS7/
DS8 writers it sits alongside.
"""
import difflib
from typing import Dict, List

from . import db
from .findings import project_identity

# The canonical side of the mapping — a fixed vocabulary is acceptable here
# since these are internal category concepts, not project-specific data. The
# per-project *mapping* from raw name -> canonical name is what's user-editable.
CANONICAL_NAMES = [
    "Discipline", "Zone", "Sector", "Phase", "Area", "Trade",
    "Responsibility", "Package", "Level", "Utility", "KPI",
]


def _normalize(raw_name: str) -> str:
    """Strips common P6-style project prefixes (e.g. 'AMR-P1- ') and
    punctuation so 'AMR-P1- DISCIPLINE' compares reasonably against 'Discipline'."""
    s = raw_name.strip().lower()
    s = s.replace("-", " ").replace("_", " ")
    # Drop leading short alphanumeric "project code" tokens (e.g. "amr p1"),
    # keeping only the last couple of words, which is usually the real concept.
    words = [w for w in s.split() if w]
    if len(words) > 2:
        words = words[-2:]
    return " ".join(words)


def suggest_synonyms(data_store, version_id: str, context: str) -> List[Dict]:
    """Auto-suggests canonical-name mappings for a version's raw Activity Code
    Type names. Never overwrites a row a user has already manually edited
    (source='user_override'). Returns the list of proposals written/updated."""
    version = data_store.get_version(version_id, context=context)
    if not version:
        return []

    code_types = data_store.get_activity_code_types(version_id=version_id, context=context)
    if not code_types:
        return []

    project_id, _ = project_identity(version, data_store=data_store, context=context)
    existing = {row["raw_name"]: row for row in db.get_activity_code_config(project_id)}

    proposals = []
    for raw_name in code_types.keys():
        existing_row = existing.get(raw_name)
        if existing_row and existing_row.get("source") == "user_override":
            # Never clobber a user's manual edit with a fresh auto-suggestion.
            continue

        normalized = _normalize(raw_name)
        matches = difflib.get_close_matches(normalized, [c.lower() for c in CANONICAL_NAMES], n=1, cutoff=0.4)
        if not matches:
            continue
        canonical = CANONICAL_NAMES[[c.lower() for c in CANONICAL_NAMES].index(matches[0])]

        row = {
            "project_id": project_id,
            "config_type": "synonym",
            "canonical_name": canonical,
            "raw_name": raw_name,
            "source": "auto_suggested",
        }
        db.upsert_activity_code_config(row)
        proposals.append(row)

    return proposals
