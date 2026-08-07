import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import {
  Users, UserCheck, UserX, Briefcase, BarChart2, Link2,
  ChevronLeft, ChevronRight, Search, RefreshCw, AlertTriangle,
  ChevronDown, ChevronRight as ChevronRightIcon,
  Folder, FolderOpen, Activity, User
} from 'lucide-react';

const BASE = 'http://127.0.0.1:8000';
const PAGE = 30;
const COLORS = ['#3b82f6','#6366f1','#8b5cf6','#06b6d4','#10b981','#f59e0b','#ef4444','#ec4899'];

// ── Summary Card ──────────────────────────────────────────────────────────────
const Card = ({ label, value, icon, border }) => (
  <div className={`flex items-center gap-4 bg-white rounded-2xl border p-5 shadow-sm ${border}`}>
    <div className="p-3 rounded-xl bg-gray-50 flex items-center justify-center shrink-0">{icon}</div>
    <div>
      <p className="text-[10px] font-black uppercase tracking-widest text-gray-400">{label}</p>
      <p className="text-2xl font-black text-gray-900 leading-none mt-1">{value ?? '—'}</p>
    </div>
  </div>
);

// ── Load Chart ────────────────────────────────────────────────────────────────
const LoadChart = ({ data, onResourceClick, activeResource }) => {
  // Sort resources by total units (descending) and take top 10
  const resources = useMemo(() => {
    const totals = {};
    data.forEach(d => {
      totals[d.resource_name] = (totals[d.resource_name] || 0) + (d.units || 0);
    });
    return Object.entries(totals)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(entry => entry[0]);
  }, [data]);

  const periods = useMemo(() => [...new Set(data.map(d => d.date))].sort().slice(-12), [data]);
  const grid      = useMemo(() => {
    const g = {};
    resources.forEach(r => { g[r] = {}; });
    data.forEach(d => { if (g[d.resource_name]) g[d.resource_name][d.date] = d.units; });
    return g;
  }, [data, resources]);
  const maxU = useMemo(() => Math.max(...data.map(d => d.units), 1), [data]);
  if (!data.length) return null;

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
      <div className="flex items-center gap-2 mb-4">
        <BarChart2 size={15} className="text-blue-600" />
        <h3 className="text-xs font-black uppercase tracking-widest text-gray-700">Resource Load — Top 10 Most Loaded</h3>
        <span className="text-[9px] text-gray-400 ml-2">Click to filter tree</span>
      </div>
      <div className="flex flex-wrap gap-2 mb-4">
        {resources.map((r, i) => (
          <button key={r} onClick={() => onResourceClick(r === activeResource ? null : r)}
            className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-[10px] font-semibold border transition-all ${
              r === activeResource ? 'border-blue-400 bg-blue-50 text-blue-700 shadow-sm' : 'border-gray-100 bg-white text-gray-500 hover:border-gray-300'
            }`}>
            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
            <span className="truncate max-w-[100px]">{r}</span>
          </button>
        ))}
      </div>
      <div className="overflow-x-auto">
        <div style={{ minWidth: Math.max(640, periods.length * 52 + 100) }}>
          <div className="grid gap-px" style={{ gridTemplateColumns: `100px repeat(${periods.length}, 1fr)` }}>
            <div />
            {periods.map(p => <div key={p} className="text-[9px] font-bold text-gray-400 text-center pb-1 truncate">{p}</div>)}
            {resources.map((r, ri) => (
              <React.Fragment key={r}>
                <div onClick={() => onResourceClick(r === activeResource ? null : r)}
                  className={`text-[9px] font-semibold pr-2 truncate flex items-center cursor-pointer transition-colors ${r === activeResource ? 'text-blue-700 font-black' : 'text-gray-500 hover:text-gray-800'}`}
                  title={r}>{r}</div>
                {periods.map(p => {
                  const u = grid[r][p] || 0;
                  const pct = Math.min(100, (u / maxU) * 100);
                  const active = !activeResource || r === activeResource;
                  return (
                    <div key={p} onClick={() => onResourceClick(r === activeResource ? null : r)}
                      className="flex flex-col items-center justify-end h-12 gap-0.5 cursor-pointer" title={`${r} | ${p}: ${u}`}>
                      <div className="w-full rounded-sm transition-all"
                        style={{ height: `${pct}%`, minHeight: u > 0 ? 2 : 0, background: COLORS[ri % COLORS.length], opacity: active ? 0.85 : 0.2 }} />
                      {u > 0 && active && <span className="text-[7px] text-gray-400 font-mono leading-none">{u}</span>}
                    </div>
                  );
                })}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

// ── Resource Row (leaf) ───────────────────────────────────────────────────────
const ResourceRow = ({ rsrc, indent }) => (
  <div className="flex items-center py-1.5 border-b border-gray-50 hover:bg-indigo-50/30 transition-colors group"
    style={{ paddingLeft: `${indent}px` }}>
    <div className="w-5 h-5 shrink-0 flex items-center justify-center mr-1">
      <User size={11} className="text-indigo-400" />
    </div>
    {/* Resource name */}
    <div className="w-48 shrink-0 text-[11px] font-semibold text-indigo-700 truncate pr-2">{rsrc.resource_name}</div>
    {/* Role badge */}
    <div className="w-28 shrink-0 pr-2">
      <span className="px-2 py-0.5 rounded-md bg-indigo-50 border border-indigo-100 text-indigo-600 text-[9px] font-black uppercase tracking-wider">{rsrc.role || 'Labor'}</span>
    </div>
    {/* Units */}
    <div className="w-20 shrink-0 text-[11px] font-mono font-bold text-gray-700 text-center">{rsrc.units}</div>
    {/* Start */}
    <div className="w-24 shrink-0 text-[10px] text-gray-500 text-center">{rsrc.start || '—'}</div>
    {/* Finish */}
    <div className="w-24 shrink-0 text-[10px] text-gray-500 text-center">{rsrc.finish || '—'}</div>
  </div>
);

// ── Activity Row (leaf, represents a single assignment under a Resource) ────────
const ActivityNode = React.memo(({ actName, resources, indent }) => {
  const rsrc = resources[0]; // Since we wrapped 1 assignment per activity in buildTree
  
  return (
    <div className="flex items-center py-1.5 border-b border-gray-50 hover:bg-indigo-50/30 transition-colors group"
      style={{ paddingLeft: `${indent}px` }}>
      <div className="w-5 h-5 shrink-0 flex items-center justify-center mr-1">
        <Activity size={11} className="text-blue-400" />
      </div>
      {/* Activity name */}
      <div className="flex-1 text-[11px] font-semibold text-gray-800 truncate pr-3" title={actName}>{actName}</div>
      {/* Role badge */}
      <div className="w-28 shrink-0 pr-2">
        <span className="px-2 py-0.5 rounded-md bg-indigo-50 border border-indigo-100 text-indigo-600 text-[9px] font-black uppercase tracking-wider">{rsrc?.role || 'Labor'}</span>
      </div>
      {/* Units */}
      <div className="w-20 shrink-0 text-[11px] font-mono font-bold text-gray-700 text-center">{rsrc?.units || 0}</div>
      {/* Start */}
      <div className="w-24 shrink-0 text-[10px] text-gray-500 text-center">{rsrc?.start || '—'}</div>
      {/* Finish */}
      <div className="w-24 shrink-0 text-[10px] text-gray-500 text-center">{rsrc?.finish || '—'}</div>
    </div>
  );
});

// ── Tree Node (recursive, handles Categories and Resources) ────────────────
const WBSNode = React.memo(({ node, level, search, activeResource }) => {
  const [isOpen, setIsOpen] = useState(!!search);

  // Auto-expand if search or activeResource changes
  useEffect(() => {
    if (search || activeResource) setIsOpen(true);
  }, [search, activeResource]);

  const indent = (level * 24) + 16;

  const hasChildren  = node.children && node.children.length > 0;
  const hasActivities = node.activities && node.activities.length > 0;
  const totalAssign  = node.totalAssignments || 0;
  const totalRes     = node.totalResources || 0;

  return (
    <div className="flex flex-col text-sm">
      {/* Node row */}
      <div
        className={`flex items-center py-2 px-3 border-b border-gray-200 cursor-pointer hover:bg-gray-50 transition-colors ${
          level === 0 ? 'bg-gray-100/80 shadow-sm sticky top-0 z-10' : 'bg-white'
        }`}
        style={{ paddingLeft: `${indent}px` }}
        onClick={() => setIsOpen(o => !o)}
      >
        {/* Chevron + short code */}
        <div className="w-24 shrink-0 flex items-center gap-1.5 overflow-hidden">
          <div className="w-4 h-4 shrink-0 flex items-center justify-center text-gray-400">
            {(hasChildren || hasActivities)
              ? isOpen ? <ChevronDown size={14} /> : <ChevronRightIcon size={14} />
              : <span className="w-3" />}
          </div>
          <span className="font-black text-[9px] text-blue-600/70 truncate">{node.wbs_short_name || ''}</span>
        </div>
        {/* Icon + name */}
        <div className="flex-1 px-2 flex items-center gap-2 truncate">
          <div className="text-blue-600 shrink-0">
            {node.isResource ? (
              <User size={15} className="text-indigo-500" />
            ) : (
              isOpen ? <FolderOpen size={15} className="fill-blue-100" /> : <Folder size={15} className="fill-blue-50" />
            )}
          </div>
          <span className={`font-bold text-[12px] truncate tracking-tight ${node.isResource ? 'text-indigo-800' : 'text-gray-900'}`}>
            {node.wbs_name}
          </span>
        </div>
        {/* Summary metrics */}
        <div className="shrink-0 flex items-center gap-3 pr-2">
          <span className="text-[9px] font-black text-gray-400 uppercase">
            {totalAssign} assignment{totalAssign !== 1 ? 's' : ''}
          </span>
          {!node.isResource && (
            <span className="text-[9px] font-black text-indigo-500 uppercase">
              {totalRes} resource{totalRes !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>

      {isOpen && (
        <div className="flex flex-col">
          {/* Activities (Assignments) */}
          {hasActivities && (
            <div className="flex flex-col bg-white" style={{ paddingLeft: `${indent + 28}px` }}>
              {/* Sub-header */}
              <div className="flex items-center py-1.5 px-2 bg-gray-50/80 border-b border-gray-200 text-[8px] font-black text-gray-400 uppercase tracking-widest sticky top-0 z-0 shadow-sm">
                <div className="flex-1">Assigned Activity</div>
                <div className="w-28 shrink-0 text-center">Role</div>
                <div className="w-20 shrink-0 text-center">Units</div>
                <div className="w-24 shrink-0 text-center">Start</div>
                <div className="w-24 shrink-0 text-center">Finish</div>
              </div>
              {node.activities.map((act, i) => (
                <ActivityNode
                  key={i}
                  actName={act.activity_name}
                  resources={act.resources}
                  indent={0}
                  search={search}
                />
              ))}
            </div>
          )}
          {/* Child Nodes */}
          {hasChildren && node.children.map(child => (
            <WBSNode
              key={child.wbs_id}
              node={child}
              level={level + 1}
              search={search}
              activeResource={activeResource}
            />
          ))}
        </div>
      )}
    </div>
  );
});

// ── Build Resource Tree ───────────────────────────────────────────────────────
function buildTree(assignments, search, activeResource) {
  // Filter
  const q = search.toLowerCase();
  const filtered = assignments.filter(a => {
    if (activeResource && a.resource_name !== activeResource) return false;
    if (q) {
      const match = a.activity_name?.toLowerCase().includes(q) ||
                    a.activity_id?.toLowerCase().includes(q) ||
                    a.resource_name?.toLowerCase().includes(q) ||
                    a.wbs_name?.toLowerCase().includes(q);
      if (!match) return false;
    }
    return true;
  });

  // Categorize
  const getCategory = (role) => {
    const r = (role || '').toLowerCase();
    if (r.includes('labor') && !r.includes('non')) return 'Labor';
    if (r.includes('material') || r.includes('mat')) return 'Material';
    return 'Non-Labor';
  };

  const getSubCategory = (resName) => {
    const n = (resName || '').toLowerCase();
    if (n.includes('quality') || n.includes('qa') || n.includes('qc') || n.includes('test')) return 'Quality';
    return 'Cost';
  };

  // Group: Category -> [SubCategory] -> Resource -> [Assignments]
  const treeMap = {
    'Labor': { _resources: {} },
    'Non-Labor': { _resources: {} },
    'Material': { 'Cost': { _resources: {} }, 'Quality': { _resources: {} } }
  };

  filtered.forEach(a => {
    const cat = getCategory(a.role);
    const resName = a.resource_name || '(Unknown Resource)';
    let targetMap = treeMap[cat];
    
    if (cat === 'Material') {
      const sub = getSubCategory(resName);
      targetMap = treeMap[cat][sub];
    }

    if (!targetMap._resources[resName]) targetMap._resources[resName] = [];
    targetMap._resources[resName].push(a);
  });

  // Build generic node structure recursively
  let idCounter = 0;
  
  const createResourceNodes = (resMap) => {
    return Object.entries(resMap).map(([resName, acts]) => {
      // For a resource node, the "activities" will be the assignments
      return {
        wbs_id: `res_${idCounter++}`,
        wbs_name: resName,
        wbs_short_name: 'RSRC',
        isResource: true, // Custom flag to change icon in UI
        activities: acts.map(a => ({
           activity_name: `${a.activity_id} - ${a.activity_name}`,
           resources: [a] // wrap assignment to match existing UI structure temporarily
        })),
        children: [],
        totalAssignments: acts.length,
        totalResources: 1,
      };
    }).sort((a, b) => a.wbs_name.localeCompare(b.wbs_name));
  };

  const createCategoryNode = (name, data, isSub = false) => {
    let children = [];
    if (data._resources) {
      children = createResourceNodes(data._resources);
    } else {
      children = Object.entries(data)
        .map(([subName, subData]) => createCategoryNode(subName, subData, true))
        .filter(Boolean);
    }
    
    // Calculate totals from children
    const totalAssign = children.reduce((sum, c) => sum + c.totalAssignments, 0);
    const totalRes = children.reduce((sum, c) => sum + (c.isResource ? 1 : c.totalResources), 0);

    return {
      wbs_id: `cat_${idCounter++}`,
      wbs_name: name,
      wbs_short_name: isSub ? 'TYPE' : 'CAT',
      isCategory: true,
      activities: [],
      children,
      totalAssignments: totalAssign,
      totalResources: totalRes,
    };
  };

  const nodes = [];
  const laborNode = createCategoryNode('Labor', treeMap['Labor']);
  if (laborNode) nodes.push(laborNode);
  
  const nonLaborNode = createCategoryNode('Non-Labor', treeMap['Non-Labor']);
  if (nonLaborNode) nodes.push(nonLaborNode);
  
  const materialNode = createCategoryNode('Material', treeMap['Material']);
  if (materialNode) nodes.push(materialNode);

  return nodes;
}


// ── Main ResourceView ─────────────────────────────────────────────────────────
const ResourceView = ({ context = 'controller' }) => {
  const [summary,        setSummary]        = useState(null);
  const [assignments,    setAssignments]    = useState([]);
  const [load,           setLoad]           = useState([]);
  const [loading,        setLoading]        = useState(false);
  const [error,          setError]          = useState(null);
  const [activeResource, setActiveResource] = useState(null);
  const [search,         setSearch]         = useState('');

  const fetchAll = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [sRes, aRes, lRes] = await Promise.all([
        axios.get(`${BASE}/resources/summary?context=${context}`).catch(() => null),
        axios.get(`${BASE}/resources/assignments?context=${context}&limit=5000`).catch(() => null),
        axios.get(`${BASE}/resources/load?context=${context}`).catch(() => null),
      ]);
      if (sRes?.data) setSummary(sRes.data);
      if (aRes?.data) setAssignments(aRes.data?.all_items ?? aRes.data?.data ?? []);
      if (lRes?.data) setLoad(lRes.data?.all_items ?? lRes.data?.data ?? []);
    } catch {
      setError('Failed to load resource data. Ensure a project XER is loaded.');
    } finally { setLoading(false); }
  }, [context]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const tree = useMemo(() => buildTree(assignments, search, activeResource), [assignments, search, activeResource]);

  const cards = summary ? [
    { label: 'Total Resources',   value: summary.total_resources,     icon: <Users size={17} className="text-blue-600" />,    border: 'border-blue-100' },
    { label: 'Assigned',          value: summary.assigned_resources,   icon: <UserCheck size={17} className="text-green-600" />, border: 'border-green-100' },
    { label: 'Unassigned',        value: summary.unassigned_resources, icon: <UserX size={17} className="text-amber-500" />,  border: 'border-amber-100' },
    { label: 'Total Assignments', value: assignments.length,           icon: <Link2 size={17} className="text-indigo-500" />, border: 'border-indigo-100' },
  ] : [];

  return (
    <div className="flex-1 min-h-0 overflow-y-auto px-8 py-6">
      <div className="flex flex-col gap-6 min-h-full">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Briefcase size={19} className="text-blue-600" />
          <div>
            <h2 className="text-sm font-black text-gray-900 uppercase tracking-widest">Resource Management</h2>
            <p className="text-[10px] text-gray-400 font-medium">Primavera P6 · WBS → Activity → Resource hierarchy</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Search */}
          <div className="relative">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search WBS, activity, resource..."
              className="pl-9 pr-3 py-2 bg-white border border-gray-200 rounded-xl text-[10px] font-medium focus:outline-none focus:ring-2 focus:ring-blue-400/30 w-56" />
          </div>
          {activeResource && (
            <button onClick={() => setActiveResource(null)}
              className="flex items-center gap-1.5 px-3 py-2 bg-blue-50 border border-blue-200 rounded-xl text-[10px] font-black text-blue-700 hover:bg-blue-100 transition-all">
              × {activeResource}
            </button>
          )}
          <button onClick={fetchAll} disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-xs font-black rounded-xl hover:bg-blue-700 transition-all shadow-md shadow-blue-500/20 disabled:opacity-50">
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-3 px-5 py-4 bg-amber-50 border border-amber-200 rounded-2xl text-amber-800 text-xs font-semibold">
          <AlertTriangle size={15} className="shrink-0 text-amber-500" /> {error}
        </div>
      )}

      {loading ? (
        <div className="flex flex-col gap-4 animate-pulse">
          <div className="grid grid-cols-4 gap-4">{[1,2,3,4].map(i => <div key={i} className="h-20 bg-gray-100 rounded-2xl" />)}</div>
          <div className="h-52 bg-gray-100 rounded-2xl" />
          <div className="h-96 bg-gray-100 rounded-2xl" />
        </div>
      ) : !error && (
        <>
          {/* Summary Cards */}
          {cards.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {cards.map(c => <Card key={c.label} {...c} />)}
            </div>
          ) : (
            <div className="flex items-center justify-center py-16 text-gray-400 text-sm italic">
              Upload a project XER file to view resource data.
            </div>
          )}

          {/* Load Chart — Hidden as per user request
          {load.length > 0 && (
            <LoadChart data={load} onResourceClick={setActiveResource} activeResource={activeResource} />
          )}
          */}

          {/* WBS Tree */}
          {tree.length > 0 ? (
            <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
              {/* Tree header */}
              <div className="px-6 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
                <Folder size={13} className="text-blue-500" />
                <span className="text-xs font-black uppercase tracking-widest text-gray-700">
                  Resource Tree — {tree.length} WBS Node{tree.length !== 1 ? 's' : ''}
                </span>
                {activeResource && (
                  <span className="ml-2 text-[10px] font-black text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-full">
                    Filtered: {activeResource}
                  </span>
                )}
              </div>
              <div className="overflow-x-auto">
                <div className="min-w-[900px]">
                  {tree.map(node => (
                    <WBSNode
                      key={node.wbs_id}
                      node={node}
                      level={0}
                      search={search}
                      activeResource={activeResource}
                    />
                  ))}
                </div>
              </div>
              {/* Footer */}
              <div className="px-6 py-3 border-t border-gray-100 bg-gray-50/60">
                <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest">
                  Total: {assignments.length} assignments across {tree.length} WBS nodes
                </p>
              </div>
            </div>
          ) : assignments.length === 0 && cards.length > 0 && (
            <div className="text-center py-16 text-gray-400 text-sm italic">
              No resource assignments found in this schedule.
            </div>
          )}
        </>
      )}
      </div>
    </div>
  );
};

export default ResourceView;
