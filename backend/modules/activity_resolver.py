import difflib
import re
from typing import List, Dict, Any, Optional
import pandas as pd

AUTO_ANSWER_THRESHOLD = 0.85

def normalize_activity_text(text: str) -> str:
    """Normalizes activity strings for consistent matching."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = text.replace("-", " ").replace("_", " ")
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def rank_by_criticality(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ranks activities: critical first, then near-critical, then alphabetical tiebreaker."""
    def sort_key(act):
        try:
            tf = float(act.get("total_float", act.get("total_float_hr_cnt", 9999)))
        except (ValueError, TypeError):
            tf = 9999
        name = str(act.get("task_name", "")).lower()
        return (tf, name)
    return sorted(matches, key=sort_key)

def build_wbs_path_map(wbs_df) -> Dict[str, str]:
    """Builds a map of wbs_id -> human-readable WBS path like 'PROCUREMENT > SUB-CONTRACTOR > APPROVALS-PREQUALIFICATION'."""
    if wbs_df is None or wbs_df.empty:
        return {}
    try:
        parent_map = wbs_df.set_index('wbs_id')['parent_wbs_id'].to_dict()
        # Prefer wbs_name (full descriptive) over wbs_short_name (often just a number)
        if 'wbs_name' in wbs_df.columns:
            name_map = wbs_df.set_index('wbs_id')['wbs_name'].to_dict()
        else:
            name_map = wbs_df.set_index('wbs_id')['wbs_short_name'].to_dict()
    except Exception:
        return {}
    
    path_cache = {}
    
    def _get_path(wbs_id):
        if wbs_id in path_cache:
            return path_cache[wbs_id]
        parts = []
        curr = wbs_id
        seen = set()
        while curr and curr in name_map and curr not in seen:
            seen.add(curr)
            label = str(name_map.get(curr, "")).strip()
            # Only include meaningful labels (skip pure numbers and empty strings)
            if label and not label.replace("-", "").replace(".", "").isdigit():
                parts.append(label)
            curr = parent_map.get(curr)
        parts.reverse()
        # Skip the root project node (first element) if path has depth
        if len(parts) > 1:
            parts = parts[1:]
        path = " > ".join(parts) if parts else "N/A"
        path_cache[wbs_id] = path
        return path
    
    return {wid: _get_path(wid) for wid in name_map}

def format_activity_candidates(matches: List[Dict[str, Any]], limit: int = 5) -> str:
    """Formats a list of activity candidates into a readable string."""
    if not matches:
        return ""
    lines = []
    for idx, act in enumerate(matches[:limit], start=1):
        act_name = act.get("task_name", act.get("name", "Unknown Name"))
        act_code = act.get("task_code", act.get("id", "UNKNOWN"))
        wbs_path = act.get("wbs_path", act.get("wbs_id", "N/A"))
        
        lines.append(
            f"{idx}. **{act_name}**  \n"
            f"   Activity ID: `{act_code}`  \n"
            f"   WBS: {wbs_path}"
        )
    return "\n\n".join(lines)

def resolve_followup_selection(query: str, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Resolves a follow-up disambiguation selection against a list of candidates."""
    query_lower = query.lower().strip()
    
    # 1. Check strict numeric index ("1", "2")
    if query_lower.isdigit():
        idx = int(query_lower) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]
            
    # 2. Textual ordinals
    ordinal_map = {
        "first": 0, "1st": 0, "1": 0,
        "second": 1, "2nd": 1, "2": 1,
        "third": 2, "3rd": 2, "3": 2,
        "fourth": 3, "4th": 3, "4": 3,
        "fifth": 4, "5th": 4, "5": 4,
    }
    
    # Strip filler words safely (e.g. "second one" -> "second")
    cleaned_query = re.sub(r'\b(the|one|activity|option)\b', '', query_lower).strip()
    
    # 2.5 Positive affirmation for single-candidate fuzzy matches ("Did you mean X?" -> "yes")
    affirmations = ["yes", "y", "yeah", "yep", "correct", "right", "sure"]
    if len(candidates) == 1 and cleaned_query in affirmations:
        return candidates[0]
    
    # Exact token match
    tokens = cleaned_query.split()
    for key, idx in ordinal_map.items():
        if key == cleaned_query or key in tokens:
            if 0 <= idx < len(candidates):
                return candidates[idx]
            
    # 3. Keyword match against candidate names
    for act in candidates:
        name = normalize_activity_text(str(act.get("task_name", act.get("name", ""))))
        code = str(act.get("task_code", act.get("id", ""))).lower()
        if cleaned_query and (cleaned_query in name or cleaned_query in code):
            return act
            
    return None

def resolve_activity_reference(query: str, activities: List[Dict[str, Any]], threshold: float = 0.7) -> Dict[str, Any]:
    """
    Universal activity reference resolver.
    Matches across exact ID, exact name, startswith, substring, and fuzzy matching.
    """
    norm_query = normalize_activity_text(query)
    raw_query_lower = query.strip().lower()
    
    exact_id_matches = []
    exact_name_matches = []
    startswith_matches = []
    contains_matches = []
    
    for act in activities:
        act_id = str(act.get("task_code", act.get("id", ""))).strip()
        act_name = str(act.get("task_name", act.get("name", "")))
        norm_name = normalize_activity_text(act_name)
        
        # 1. Exact ID
        if act_id.lower() == raw_query_lower or normalize_activity_text(act_id) == norm_query:
            exact_id_matches.append(act)
            continue
            
        # 2. Exact Name
        if norm_name == norm_query:
            exact_name_matches.append(act)
            continue
            
        # 3. Startswith
        if norm_name.startswith(norm_query):
            startswith_matches.append(act)
            continue
            
        # 4. Partial substring — ALL query words must appear in the activity name
        query_tokens = norm_query.split()
        if len(query_tokens) > 1:
            if all(token in norm_name for token in query_tokens):
                contains_matches.append(act)
        else:
            if norm_query in norm_name:
                contains_matches.append(act)
            
    if exact_id_matches:
        return {
            "matches": exact_id_matches,
            "confidence_score": 1.00,
            "match_type": "exact_id"
        }
    elif exact_name_matches:
        return {
            "matches": rank_by_criticality(exact_name_matches),
            "confidence_score": 0.98,
            "match_type": "exact_name"
        }
    elif startswith_matches:
        return {
            "matches": rank_by_criticality(startswith_matches),
            "confidence_score": 0.90,
            "match_type": "startswith"
        }
    elif contains_matches:
        return {
            "matches": rank_by_criticality(contains_matches),
            "confidence_score": 0.75,
            "match_type": "contains"
        }
        
    # 5. Fuzzy match fallback
    act_names_map = {}
    for act in activities:
        name = normalize_activity_text(str(act.get("task_name", act.get("name", ""))))
        if name:
            if name not in act_names_map:
                act_names_map[name] = []
            act_names_map[name].append(act)
            
    fuzzy_candidates = difflib.get_close_matches(norm_query, act_names_map.keys(), n=5, cutoff=threshold)
    
    if fuzzy_candidates:
        best_match = fuzzy_candidates[0]
        score = difflib.SequenceMatcher(None, norm_query, best_match).ratio()
        fuzzy_matches = []
        
        # If we have a very strong top match, ONLY return activities for that specific name
        if score >= AUTO_ANSWER_THRESHOLD:
            fuzzy_matches.extend(act_names_map[best_match])
        else:
            # Otherwise, return all close candidates for disambiguation
            for cand in fuzzy_candidates:
                fuzzy_matches.extend(act_names_map[cand])
            
        return {
            "matches": rank_by_criticality(fuzzy_matches),
            "confidence_score": round(score, 2),
            "match_type": "fuzzy"
        }
        
    return {
        "matches": [],
        "confidence_score": 0.0,
        "match_type": "none"
    }

def format_resolution_response(query: str, resolution: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translates resolution results into standard conversational templates based on UX requirements.
    """
    matches = resolution["matches"]
    conf = resolution["confidence_score"]
    mtype = resolution["match_type"]
    
    if not matches:
        return {
            "status": "none",
            "message": f"No activities found matching '{query}'. Try searching by trade, zone, or activity ID."
        }
        
    if conf >= AUTO_ANSWER_THRESHOLD:
        if len(matches) == 1:
            name = matches[0].get("task_name", matches[0].get("name", ""))
            return {
                "status": "ready",
                "message": f"I found '{name}'. Here are the details..."
            }
        elif 2 <= len(matches) <= 5:
            cands = format_activity_candidates(matches, limit=5)
            return {
                "status": "disambiguate",
                "message": f'I found {len(matches)} matching activities for "{query}". Which one did you mean?\n\n{cands}'
            }
        else:
            cands = format_activity_candidates(matches, limit=5)
            return {
                "status": "narrow",
                "message": f"I found {len(matches)} activities containing '{query}'. Could you narrow it down with a trade, zone, or activity ID? Here are 5 critical matches to help you start:\n\n{cands}"
            }
    elif 0.70 <= conf < AUTO_ANSWER_THRESHOLD:
        if mtype == "fuzzy":
            cand = format_activity_candidates(matches, limit=1)
            return {
                "status": "disambiguate",
                "message": f"No exact matches found for '{query}'. Did you mean:\n\n{cand}"
            }
        else:
            if len(matches) == 1:
                cand = format_activity_candidates(matches, limit=1)
                return {
                    "status": "disambiguate",
                    "message": f"I found a partial match. Is this what you meant?\n\n{cand}"
                }
            elif 2 <= len(matches) <= 5:
                cands = format_activity_candidates(matches, limit=5)
                return {
                    "status": "disambiguate",
                    "message": f'I found {len(matches)} matching activities for "{query}". Which one did you mean?\n\n{cands}'
                }
            else:
                cands = format_activity_candidates(matches, limit=5)
                return {
                    "status": "narrow",
                    "message": f"I found {len(matches)} activities loosely matching '{query}'. Could you narrow it down? Here are top candidates:\n\n{cands}"
                }
    else:
        return {
            "status": "none",
            "message": f"No confident matches found for '{query}'. Try searching by trade, zone, or activity ID."
        }
