import os
import shutil
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typing import List, Optional

# Load environment variables from the root directory
load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))


from modules.extractor import CompleteXERExtractor
from modules.analyzer import XERAnalyzer
from modules.db import init_db, get_findings_history, get_findings_for_snapshot
from modules.findings import write_findings_for_version, project_identity
from modules.changes import write_changes_for_version
from modules.narrative import generate_audit_narrative

app = FastAPI()

# Enable CORS for React/Electron
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

analyzer = XERAnalyzer()
init_db()

@app.get("/")
def read_root():
    return {"status": "ok"}

@app.post("/upload-xer")
async def upload_xer(
    file: UploadFile = File(...), 
    file_type: str = Form("baseline"), 
    context: str = Form("audit"),
    override_progress: bool = Form(False),
    override_pairing: bool = Form(False)
):
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, file.filename)
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        print(f"--- Processing {file_type} upload: {file.filename} ---")
        extractor = CompleteXERExtractor(temp_path, file_type)
        extractor.extract_all()
        data = extractor.get_complete_data()
        
        ctx = analyzer.data_store.contexts.get(context, analyzer.data_store.contexts["audit"])
        baselines = [v for v in ctx["versions"].values() if v['type'] == 'baseline']
        
        # Case 1: Update uploaded before any Baseline -> Hard block
        if file_type == 'update' and not baselines:
            os.remove(temp_path)
            raise HTTPException(
                status_code=400,
                detail={"type": "error", "error_type": "missing_baseline", "detail": "No baseline schedule has been uploaded yet.\n\nYou may work with a baseline alone, but an update file requires an existing baseline."}
            )

        # Case 2: Progress detected in baseline slot -> Warning with override
        if file_type == 'baseline' and not override_progress:
            tasks = data.get('tasks', [])
            total_tasks = len(tasks)
            
            act_starts = 0
            act_finishes = 0
            in_progress_count = 0
            completed_count = 0
            genuine_progress_count = 0
            
            for t in tasks:
                has_actual_start = bool(str(t.get('act_start_date', '')).strip())
                has_actual_finish = bool(str(t.get('act_end_date', '')).strip())
                status = str(t.get('status_code', ''))
                
                # Genuine progress means it actually started
                is_started = has_actual_start or status in ['TK_Active', 'TK_Complete']
                
                if has_actual_start: act_starts += 1
                if has_actual_finish: act_finishes += 1
                if status == 'TK_Active': in_progress_count += 1
                if status == 'TK_Complete': completed_count += 1
                
                if is_started:
                    genuine_progress_count += 1
                    
            progress_pct = (genuine_progress_count / total_tasks * 100) if total_tasks > 0 else 0
            
            confidence = "Low"
            if progress_pct > 10: confidence = "High"
            elif progress_pct >= 1: confidence = "Medium"
            
            if genuine_progress_count > 0:
                os.remove(temp_path)
                evidence = []
                if act_starts > 0: evidence.append(f"{act_starts} activities have Actual Start")
                if act_finishes > 0: evidence.append(f"{act_finishes} activities have Actual Finish")
                if in_progress_count > 0: evidence.append(f"{in_progress_count} activities are in progress")
                if completed_count > 0: evidence.append(f"{completed_count} activities are completed")
                
                evidence.append(f"{progress_pct:.1f}% of project activities contain progress")
                
                # Only show popup if it's Medium or High confidence, or if there are explicit dates
                if progress_pct >= 1.0 or act_starts > 0:
                    raise HTTPException(
                        status_code=400, 
                        detail={
                            "type": "warning", 
                            "warning_type": "baseline_progress", 
                            "detail": "This file contains progress information and appears to be an update schedule.\n\nBaselines are usually un-progressed schedules.\n\nAre you sure you want to use this as the baseline?",
                            "confidence": confidence,
                            "evidence": evidence
                        }
                    )

        # Case 3: Project mismatch -> Warning with override
        if file_type == 'update' and baselines and not override_pairing:
            pairing_result = analyzer.data_store.check_pairing_heuristics(data, baselines, context=context)
            if not pairing_result["valid"]:
                os.remove(temp_path)
                raise HTTPException(
                    status_code=400,
                    detail={
                        "type": "warning",
                        "warning_type": "project_mismatch",
                        "detail": "The baseline and update schedules do not appear to belong to the same project.",
                        "confidence": "High",
                        "evidence": [
                            f"Baseline Name: {pairing_result['baseline_name']}",
                            f"Update Name: {pairing_result['update_name']}",
                            f"Baseline Proj: {pairing_result['baseline_proj_short_name']}",
                            f"Update Proj: {pairing_result['update_proj_short_name']}",
                            f"Activity overlap: {pairing_result['overlap_pct']}% (Threshold: 80%)"
                        ]
                    }
                )

        
        version_id = analyzer.data_store.add_version(
            data, 
            data['project']['project_name'], 
            data['project']['data_date'],
            type=file_type,
            context=context
        )
        print(f"Version added: {version_id} ({data['project']['project_name']})")

        try:
            written = write_findings_for_version(analyzer.data_store, version_id, context, file_type)
            print(f"DS7 findings written: {written}")
        except Exception as e:
            print(f"WARNING: DS7 findings write failed: {e}")

        try:
            changes_written = write_changes_for_version(analyzer.data_store, version_id, context, file_type)
            print(f"DS8 changes written: {changes_written}")
        except Exception as e:
            print(f"WARNING: DS8 changes write failed: {e}")

        stats = analyzer.get_basic_stats(context=context)
        os.remove(temp_path)
        return {"success": True, "stats": stats, "version_id": version_id}
    except HTTPException as http_exc:
        if os.path.exists(temp_path): os.remove(temp_path)
        raise http_exc
    except Exception as e:
        print(f"ERROR during upload: {str(e)}")
        if os.path.exists(temp_path): os.remove(temp_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def get_health(version_id: Optional[str] = None, context: str = "audit"):
    return analyzer.get_basic_stats(version_id, context=context)

@app.get("/critical-path")
async def get_critical_path(context: str = "audit"):
    # Example logic: filter tasks with float <= 0
    latest = analyzer.data_store.get_latest(context=context)
    if not latest: return []
    tasks = latest['df']['tasks'].copy()
    tasks['float'] = pd.to_numeric(tasks['total_float_hr_cnt'], errors='coerce').fillna(0)
    critical = tasks[tasks['float'] <= 0]
    return critical.head(100).to_dict('records')

@app.post("/ask")
async def ask_question(query: str = Form(...), context: Optional[str] = Form(None), session_id: str = Form("default")):
    ctx_dict = None
    if context:
        try:
            import json
            ctx_dict = json.loads(context)
        except:
            pass
            
    # Use the new modular analytical engine
    response = analyzer.analyze(query, context=ctx_dict, session_id=session_id)
    return {"response": response}

@app.get("/settings")
async def get_settings():
    return analyzer.get_config()

@app.post("/settings/update")
async def update_settings(provider: str = Form(...), model: Optional[str] = Form(None)):
    return analyzer.set_config(provider, model)

@app.get("/versions")
async def get_versions(context: str = "audit"):
    """Returns list of all uploaded schedule versions for a context"""
    versions = []
    ctx = analyzer.data_store.contexts.get(context, analyzer.data_store.contexts["audit"])
    for v in ctx["versions"].values():
        versions.append({
            "id": v["id"],
            "type": v["type"],
            "name": v["name"],
            "data_date": v["data_date"]
        })
    # Sort updates by date, baseline first
    versions.sort(key=lambda x: (0 if x["type"] == "baseline" else 1, x["data_date"]))
    return versions

@app.get("/findings/history")
async def get_findings_history_endpoint(context: str = "audit"):
    """Returns DS7 DCMA finding history grouped by check_id for the active
    version's project, for sparkline rendering (B-015 part 2)."""
    version = analyzer.data_store.get_version(context=context)
    if not version:
        raise HTTPException(status_code=404, detail="No active version for this context")

    project_id, _ = project_identity(version, data_store=analyzer.data_store, context=context)
    history = get_findings_history(project_id)
    return {"project_id": project_id, "history": history}

@app.get("/findings/narrative")
async def get_findings_narrative(version_id: Optional[str] = None, context: str = "audit"):
    """plain-language 2-3 paragraph narrative over the active
    snapshot's DS7 M1 (DCMA) findings. Accepts version_id (unlike
    /findings/history) so it tracks whichever snapshot is on screen, same as
    /health."""
    version = analyzer.data_store.get_version(version_id, context=context)
    if not version:
        raise HTTPException(status_code=404, detail="No active version for this context")

    project_id, snapshot_id = project_identity(version, data_store=analyzer.data_store, context=context)
    findings_rows = get_findings_for_snapshot(project_id, snapshot_id)
    return generate_audit_narrative(findings_rows, analyzer.client, analyzer.model, analyzer.provider)

@app.delete("/versions/{version_id}")
async def delete_version(version_id: str, context: str = "audit"):
    """Deletes a specific schedule version"""
    try:
        analyzer.data_store.remove_version(version_id, context=context)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/xer-data")
async def get_xer_data(table: str = "TASK", search: str = "", page: int = 1, limit: int = 100, version_id: Optional[str] = None, filter: str = "ALL", context: str = "audit"):
    offset = (page - 1) * limit
    try:
        data = analyzer.data_store.get_table_data(table, search, limit, offset, source_id=version_id, filter_type=filter, context=context)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/full-data")
async def get_full_data(ref: str):
    """Retrieves full analytical dataset from results cache"""
    data = analyzer.data_store.get_cached_result(ref)
    if data is None:
        raise HTTPException(status_code=404, detail="Result reference not found or expired")
    return {"success": True, "data": data, "total_count": len(data)}



# ── Calendar Endpoints ────────────────────────────────────────────────────────
@app.get("/calendars")
async def get_calendars(context: str = "audit"):
    """Returns all calendar exceptions and rules."""
    calendars = analyzer.data_store.get_calendar_info(context=context)
    if not calendars:
        raise HTTPException(status_code=404, detail="No calendar data found")
    return {"success": True, "data": calendars}

# ── Resource Endpoints ────────────────────────────────────────────────────────
@app.get("/resources/summary")
async def get_resources_summary(context: str = "audit"):
    """Returns total, assigned, and unassigned resource counts."""
    from modules.resource_engine import ResourceEngine
    engine = ResourceEngine(analyzer.data_store)
    result = engine.get_resource_summary(context=context)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "No data"))
    return result["stats"]

@app.get("/resources/assignments")
async def get_resources_assignments(context: str = "audit", limit: int = 500):
    """Returns resource-to-activity assignments."""
    from modules.resource_engine import ResourceEngine
    engine = ResourceEngine(analyzer.data_store)
    result = engine.get_resource_assignments(limit=limit, context=context)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "No data"))
    return result

@app.get("/resources/load")
async def get_resources_load(context: str = "audit"):
    """Returns time-phased resource load data."""
    from modules.resource_engine import ResourceEngine
    engine = ResourceEngine(analyzer.data_store)
    result = engine.get_resource_load(context=context)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "No data"))
    return result


# ── B-042: Dashboard Endpoint ─────────────────────────────────────────────────
@app.get("/project/dashboard")
async def get_dashboard(context: str = "controller"):
    """B-042: Returns aggregated KPI dashboard data.
    Reuses B-034/B-035/B-036 engines — no duplicate calculations."""
    data = analyzer.data_store.get_dashboard_data(context=context)
    return data


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("API_PORT", 8000))
    uvicorn.run(app, host="127.0.0.1", port=port)
