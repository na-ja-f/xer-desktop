import sys, os
import pandas as pd

sys.path.append(os.path.abspath('backend'))
from modules.extractor import CompleteXERExtractor

update_path = '/Users/shibilmuhammad/Documents/Career/AMR-UPD-29-Nov 25  AL AMRAH INFRASTRUCTURE PACKAGE -01.xer'
ext = CompleteXERExtractor(update_path, 'update')
ext.extract_all()
data = ext.get_complete_data()

task_rows = data['tables']['TASK']
pred_rows = data['tables']['TASKPRED']

tasks_df = pd.DataFrame(task_rows)
preds_df = pd.DataFrame(pred_rows)

# Filter Path 1
path1 = tasks_df[tasks_df['float_path'] == '1'].copy()
path1['fp_order'] = pd.to_numeric(path1['float_path_order'], errors='coerce').fillna(9999)
path1 = path1.sort_values('fp_order').reset_index(drop=True)

# Build lookup maps
id_to_code = dict(zip(tasks_df['task_id'], tasks_df['task_code']))
id_to_name = dict(zip(tasks_df['task_id'], tasks_df['task_name']))

# Path 1 task_ids (for checking internal connections)
path1_ids = set(path1['task_id'].tolist())

# Build predecessor/successor maps
# predecessors[task_id] = list of (pred_task_id, rel_type, lag)
predecessors = {}
successors = {}
for _, r in preds_df.iterrows():
    tid = r['task_id']
    pid = r['pred_task_id']
    rtype = r.get('pred_type', 'PR_FS')
    lag = float(r.get('lag_hr_cnt', 0) or 0) / 8.0
    if tid not in predecessors: predecessors[tid] = []
    if pid not in successors: successors[pid] = []
    predecessors[tid].append((pid, rtype, lag))
    successors[pid].append((tid, rtype, lag))

print("=" * 120)
print(f"PATH 1 — COMPLETE ACTIVITY LIST ({len(path1)} Activities)")
print("=" * 120)
print(f"{'#':>3}  {'Activity ID':<22}  {'Activity Name':<50}  {'ES':<14}  {'EF':<14}  {'Float':>8}  {'P1-Pred':<20}  {'P1-Succ':<20}")
print("-" * 160)

disconnected = []
for i, row in path1.iterrows():
    tid = row['task_id']
    tc = row['task_code']
    tn = row['task_name']
    es = str(row.get('early_start_date', '') or '')[:16]
    ef = str(row.get('early_end_date', '') or '')[:16]
    tf = float(row.get('total_float_hr_cnt', 0) or 0) / 8.0
    fp_order = int(row['fp_order']) if row['fp_order'] != 9999 else '?'

    # Find predecessors that are also in Path 1
    preds_in_p1 = [(id_to_code.get(p, p), rt, lg) for p, rt, lg in predecessors.get(tid, []) if p in path1_ids]
    succs_in_p1 = [(id_to_code.get(s, s), rt, lg) for s, rt, lg in successors.get(tid, []) if s in path1_ids]

    pred_str = ', '.join([f"{c}({rt[3:]})" for c, rt, _ in preds_in_p1[:2]]) or '—'
    succ_str = ', '.join([f"{c}({rt[3:]})" for c, rt, _ in succs_in_p1[:2]]) or '—'

    # Check for disconnection: if not the first or last, it should have both a p1-pred and p1-succ
    is_first = (int(row['fp_order']) == path1['fp_order'].min())
    is_last  = (int(row['fp_order']) == path1['fp_order'].max())
    if not preds_in_p1 and not is_first:
        disconnected.append((fp_order, tc, 'NO PREDECESSOR IN PATH 1'))
    if not succs_in_p1 and not is_last:
        disconnected.append((fp_order, tc, 'NO SUCCESSOR IN PATH 1'))

    tf_str = f"{tf:+.1f}d"
    tn_short = (tn[:48] + '..') if len(tn) > 50 else tn
    print(f"{fp_order:>3}  {tc:<22}  {tn_short:<50}  {es:<14}  {ef:<14}  {tf_str:>8}  {pred_str:<20}  {succ_str:<20}")

print()
print("=" * 120)
print("CONNECTIVITY VERIFICATION")
print("=" * 120)
if disconnected:
    print(f"\n⚠  DISCONNECTED ACTIVITIES DETECTED ({len(disconnected)}):")
    for seq, code, reason in disconnected:
        print(f"  Order #{seq:3d} | {code:<22} | {reason}")
else:
    print("\n✓  All Path 1 activities are logically connected within the path.")

# Summary chain — show the driving sequence compactly
print()
print("=" * 120)
print("GRAPHICAL CHAIN SUMMARY — PATH 1")
print("=" * 120)
chain_parts = []
for i, row in path1.iterrows():
    tc = row['task_code']
    tf = float(row.get('total_float_hr_cnt', 0) or 0) / 8.0
    tn = row['task_name'][:35]
    chain_parts.append((tc, tn, tf, str(row.get('early_start_date', ''))[:10], str(row.get('early_end_date', ''))[:10]))

# Print in groups of 5 with arrows
for i in range(0, len(chain_parts), 1):
    tc, tn, tf, es, ef = chain_parts[i]
    fp = int(path1.iloc[i]['fp_order'])
    connector = "  ──▶  " if i < len(chain_parts) - 1 else ""
    tf_tag = f"[{tf:+.1f}d]"
    if i % 5 == 0:
        print(f"\n  ┌─── Sequence {fp} to {min(fp+4, len(chain_parts))} ───")
    print(f"  │  {fp:>2}. [{tc}]  {tn:<35}  ES:{es}  EF:{ef}  Float:{tf_tag}")
    if (i + 1) % 5 == 0 and i < len(chain_parts) - 1:
        print(f"  └──────────────────────────────────────── ▼")

print(f"\n  └──── END OF PATH 1 ({len(chain_parts)} activities, total span: {chain_parts[0][3]} → {chain_parts[-1][4]}) ────")
print()
# Show the driving chain as a compact flow
print("=" * 120)
print("COMPACT DRIVING CHAIN (first → last)")
print("=" * 120)
for i, (tc, tn, tf, es, ef) in enumerate(chain_parts):
    connector = " ──▶ " if i < len(chain_parts) - 1 else ""
    print(f"  [{tc}]{connector}", end="")
    if (i + 1) % 4 == 0:
        print()
        print("    ", end="")
print("\n")
