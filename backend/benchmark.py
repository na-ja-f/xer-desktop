#!/usr/bin/env python3
"""
XerAgent Pipeline Benchmark — Real Measurements
Instruments every major pipeline step with actual memory and timing data.
"""

import sys, os, time, gc, tracemalloc, json
import psutil

sys.path.append(os.path.abspath("."))

# ── Helpers ──────────────────────────────────────────────────────────────────

process = psutil.Process(os.getpid())

def get_rss_mb():
    """Resident Set Size — actual physical memory used by this process."""
    return process.memory_info().rss / (1024 * 1024)

def get_obj_size_mb(obj):
    """Deep size estimate using sys.getsizeof (shallow) — for quick reference."""
    return sys.getsizeof(obj) / (1024 * 1024)

def fmt(mb):
    return f"{mb:,.1f} MB"

def fmt_time(s):
    if s < 1:
        return f"{s*1000:,.1f} ms"
    return f"{s:,.2f} s"

class Bench:
    def __init__(self, label):
        self.label = label
        self.results = []
        
    def step(self, name):
        return BenchStep(name, self)

class BenchStep:
    def __init__(self, name, bench):
        self.name = name
        self.bench = bench
    def __enter__(self):
        gc.collect()
        self.rss_before = get_rss_mb()
        tracemalloc.start()
        self.t0 = time.perf_counter()
        return self
    def __exit__(self, *args):
        self.elapsed = time.perf_counter() - self.t0
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.rss_after = get_rss_mb()
        self.rss_delta = self.rss_after - self.rss_before
        self.traced_peak = peak / (1024 * 1024)
        self.traced_current = current / (1024 * 1024)
        
        result = {
            "step": self.name,
            "time": self.elapsed,
            "time_fmt": fmt_time(self.elapsed),
            "rss_before": self.rss_before,
            "rss_after": self.rss_after,
            "rss_delta": self.rss_delta,
            "rss_delta_fmt": fmt(self.rss_delta),
            "traced_peak_mb": self.traced_peak,
            "traced_peak_fmt": fmt(self.traced_peak),
        }
        self.bench.results.append(result)
        print(f"  ✓ {self.name:<50} {result['time_fmt']:>10}  |  RSS Δ {result['rss_delta_fmt']:>10}  |  Peak alloc {result['traced_peak_fmt']:>10}")


# ── XER File ─────────────────────────────────────────────────────────────────

XER_BASELINE = "/Users/shibilmuhammad/Documents/Career/Al Amrah_Infra Package 01_Baseline Program Rev 00.xer"
XER_UPDATE = "/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer"

for f in [XER_BASELINE, XER_UPDATE]:
    if not os.path.exists(f):
        print(f"ERROR: File not found: {f}")
        sys.exit(1)

print(f"XER Baseline: {os.path.basename(XER_BASELINE)} ({os.path.getsize(XER_BASELINE) / (1024*1024):.2f} MB)")
if os.path.exists(XER_UPDATE):
    print(f"XER Update:   {os.path.basename(XER_UPDATE)} ({os.path.getsize(XER_UPDATE) / (1024*1024):.2f} MB)")

print(f"\nProcess baseline RSS: {fmt(get_rss_mb())}")
print("=" * 120)

# ── Import Dependencies ──────────────────────────────────────────────────────

import pandas as pd
from modules.extractor import CompleteXERExtractor
from modules.data_store import XERDataStore
from modules.analyzer import XERAnalyzer

bench = Bench("XerAgent Full Pipeline")

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: XER EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── PHASE 1: XER FILE EXTRACTION ──")

with bench.step("1.1 Read raw file content"):
    extractor = CompleteXERExtractor(XER_BASELINE, "baseline")
    extractor._read_raw_content()
    raw_size = len(extractor.raw_content)
    
with bench.step("1.2 Parse header"):
    extractor._parse_header()

with bench.step("1.3 Parse all tables (TSV → dicts)"):
    extractor._parse_all_tables()
    table_count = len(extractor.tables)
    total_records = sum(len(t) for t in extractor.tables.values())

with bench.step("1.4 Build relationships"):
    extractor._build_relationships()

with bench.step("1.5 Calculate statistics"):
    extractor._calculate_statistics()

with bench.step("1.6 get_complete_data() → final dict"):
    data = extractor.get_complete_data()

print(f"\n  Tables extracted: {table_count}")
print(f"  Total records: {total_records:,}")
print(f"  Raw content size: {raw_size / (1024*1024):.2f} MB")
for tbl in ['TASK', 'TASKPRED', 'PROJWBS', 'RSRC', 'TASKRSRC', 'ACTVCODE', 'ACTVTYPE', 'TASKACTV', 'CALENDAR']:
    if tbl in extractor.tables:
        print(f"    {tbl}: {len(extractor.tables[tbl]):,} rows")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: DATA STORE INGESTION
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── PHASE 2: DATA STORE INGESTION (add_version) ──")

store = XERDataStore()

# Break down add_version into its sub-steps
with bench.step("2.1 _create_dataframes()"):
    dfs = store._create_dataframes(data)

# Measure DataFrame sizes
print("\n  DataFrame memory usage:")
total_df_mem = 0
for name, df in sorted(dfs.items(), key=lambda x: -x[1].memory_usage(deep=True).sum()):
    mem = df.memory_usage(deep=True).sum() / (1024 * 1024)
    total_df_mem += mem
    if mem > 0.1:
        print(f"    {name:<20} {len(df):>6} rows  ×  {len(df.columns):>3} cols  →  {mem:>8.2f} MB")
print(f"    {'TOTAL':<20} {'':>6}       {'':>3}       {total_df_mem:>8.2f} MB")

# Now do the full add_version (includes CPM + dependency graph)
gc.collect()
rss_before_add = get_rss_mb()

with bench.step("2.2 Full add_version() (CPM + dep graph + all)"):
    version_id = store.add_version(
        data,
        data['project']['project_name'],
        data['project']['data_date'],
        type="baseline",
        context="controller"
    )

rss_after_add = get_rss_mb()
print(f"\n  Version ID: {version_id}")
print(f"  Total RSS after baseline ingestion: {fmt(rss_after_add)}")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: CPM SCHEDULING (Isolated)
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── PHASE 3: CPM SCHEDULING (Isolated Re-run) ──")

from modules.scheduler import CPMScheduler, P6Calendar

v = store.contexts["controller"]["versions"][version_id]
tasks_df = v['df']['tasks'].copy()
preds_df = v['df']['taskpred']
calendars_df = v['df'].get('calendar')

with bench.step("3.1 CPMScheduler.calculate() — full CPM pass"):
    sched = CPMScheduler(hours_per_day=v.get('hours_per_day', 8.0))
    result_tasks = sched.calculate(
        tasks_df.copy(),
        preds_df,
        pd.to_datetime("2025-06-09"),
        calendars_df=calendars_df,
    )
    
print(f"  Tasks processed: {len(result_tasks):,}")
print(f"  Tasks with computed float: {result_tasks['total_float'].notna().sum():,}")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: DETERMINISTIC ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── PHASE 4: DETERMINISTIC ANALYSIS ──")

# First, add the update file so we get delay calculations
with bench.step("4.0 Ingest UPDATE file (full add_version)"):
    extractor2 = CompleteXERExtractor(XER_UPDATE, "update")
    extractor2.extract_all()
    data2 = extractor2.get_complete_data()
    update_vid = store.add_version(
        data2,
        data2['project']['project_name'],
        data2['project']['data_date'],
        type="update",
        context="controller"
    )

print(f"  Update version: {update_vid}")

with bench.step("4.1 get_deterministic_analysis() — full pipeline"):
    analysis = store.get_deterministic_analysis(version_id=update_vid, context="controller")

act_analysis = analysis.get("activityAnalysis", {})
proj_summary = analysis.get("projectSummary", {})
print(f"  Activities analyzed: {len(act_analysis):,}")
print(f"  Project delay days: {proj_summary.get('projectDelayDays')}")
print(f"  Health score: {proj_summary.get('healthMetrics', {}).get('projectHealthScore')}")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: COMPUTE BASIC STATS
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── PHASE 5: COMPUTE BASIC STATS ──")

with bench.step("5.1 compute_basic_stats()"):
    stats = store.compute_basic_stats(version_id=update_vid, context="controller")

print(f"  Total activities: {stats.get('total_activities')}")
print(f"  Critical count: {stats.get('critical_count')}")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6: WBS HIERARCHY BUILD
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── PHASE 6: WBS HIERARCHY ──")

with bench.step("6.1 get_table_data(HIERARCHY) — full tree build"):
    hierarchy_data = store.get_table_data(
        "HIERARCHY", "", 100, 0,
        source_id=update_vid,
        filter_type="ALL",
        context="controller"
    )

wbs_tree = hierarchy_data.get("data", [])
print(f"  Top-level WBS nodes: {len(wbs_tree)}")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 7: ACTIVITY CODE RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── PHASE 7: ACTIVITY CODES ──")

with bench.step("7.1 _build_activity_codes_map()"):
    source = store.get_latest(context="controller")
    codes_map = store._build_activity_codes_map(source)

print(f"  Activities with codes: {len(codes_map):,}")

with bench.step("7.2 get_activity_code_types()"):
    code_types = store.get_activity_code_types(context="controller")

print(f"  Code types found: {len(code_types)}")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 8: DEPENDENCY GRAPH
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── PHASE 8: DEPENDENCY GRAPH ──")

with bench.step("8.1 _build_dependency_graph() (isolated)"):
    store._build_dependency_graph(update_vid, context="controller")

dep_graph = store.contexts["controller"]["versions"][update_vid].get("dependency_graph", {})
print(f"  Nodes in graph: {len(dep_graph):,}")
total_edges = sum(len(v['predecessors']) + len(v['successors']) for v in dep_graph.values())
print(f"  Total edges (pred + succ): {total_edges:,}")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 9: AI QUERY PIPELINE (without actual LLM call)
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── PHASE 9: ANALYTICAL TOOL EXECUTION (no LLM) ──")

analyzer = XERAnalyzer()
analyzer.data_store = store

with bench.step("9.1 get_delayed_activities(limit=100)"):
    delayed = analyzer.get_delayed_activities(limit=100, context="controller", version_id=update_vid)
print(f"  Delayed activities found: {delayed.get('total_count', 0)}")

with bench.step("9.2 get_critical_path(limit=100)"):
    critical = analyzer.get_critical_path(limit=100, context="controller", version_id=update_vid)
print(f"  Critical path activities: {critical.get('total_count', 0)}")

with bench.step("9.3 get_negative_float_activities(limit=100)"):
    neg_float = analyzer.get_negative_float_activities(limit=100, context="controller", version_id=update_vid)
print(f"  Negative float activities: {neg_float.get('total_count', 0)}")

with bench.step("9.4 check_open_ends()"):
    open_ends = analyzer.check_open_ends(context="controller", version_id=update_vid)
print(f"  Open ends: {open_ends.get('total_count', 0)}")

with bench.step("9.5 get_project_summary()"):
    summary = analyzer.get_project_summary(context="controller", version_id=update_vid)

with bench.step("9.6 get_wbs_branch_stats()"):
    wbs_stats = analyzer.get_wbs_branch_stats(context="controller", version_id=update_vid)
print(f"  WBS branches: {wbs_stats.get('total_count', 0)}")

with bench.step("9.7 check_integrity()"):
    integrity = analyzer.check_integrity(context="controller", version_id=update_vid)

with bench.step("9.8 get_activities_by_code(code_value='Construction')"):
    by_code = analyzer.get_activities_by_code(code_value="Construction", context="controller", version_id=update_vid)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 10: MEMORY SNAPSHOT
# ═══════════════════════════════════════════════════════════════════════════════

print("\n── PHASE 10: FINAL MEMORY SNAPSHOT ──")

final_rss = get_rss_mb()
print(f"  Final process RSS: {fmt(final_rss)}")
print(f"  Versions loaded: baseline + update = 2")
print(f"  Per-version average: {fmt((final_rss - 50) / 2)}")  # ~50 MB Python baseline

# Count objects
version_count = sum(len(ctx["versions"]) for ctx in store.contexts.values())
print(f"  Total versions in memory: {version_count}")


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY TABLE
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 120)
print("BENCHMARK SUMMARY")
print("=" * 120)
print(f"{'Step':<55} {'Time':>10}  {'RSS Δ':>12}  {'Peak Alloc':>12}")
print("-" * 120)

total_time = 0
for r in bench.results:
    total_time += r["time"]
    print(f"  {r['step']:<53} {r['time_fmt']:>10}  {r['rss_delta_fmt']:>12}  {r['traced_peak_fmt']:>12}")

print("-" * 120)
print(f"  {'TOTAL PIPELINE TIME':<53} {fmt_time(total_time):>10}")
print(f"  {'FINAL PROCESS RSS':<53} {fmt(final_rss):>10}")
print("=" * 120)

# Export results to JSON
output = {
    "benchmark_date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "xer_baseline": os.path.basename(XER_BASELINE),
    "xer_update": os.path.basename(XER_UPDATE),
    "baseline_file_size_mb": round(os.path.getsize(XER_BASELINE) / (1024*1024), 2),
    "total_activities": total_records,
    "total_pipeline_time_s": round(total_time, 3),
    "final_rss_mb": round(final_rss, 1),
    "steps": bench.results
}

json_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
with open(json_path, "w") as f:
    json.dump(output, f, indent=2, default=str)
print(f"\nResults saved to: {json_path}")
