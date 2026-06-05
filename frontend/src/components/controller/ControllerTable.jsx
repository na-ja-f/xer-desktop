import React, { useState } from 'react';
import { Search, Circle, CheckCircle, Loader2, AlertTriangle, ChevronLeft, ChevronRight, Folder, FolderOpen, ChevronDown, ChevronRight as ChevronRightIcon } from 'lucide-react';

const formatCurrency = (val) => {
  if (val === null || val === undefined) return '-';
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);
};

const TaskRow = React.memo(({ task, formatP6Date }) => {
  const [showDetails, setShowDetails] = useState(false);
  const analysis = task._analysis || {};
  const status = analysis.status;
  const isDelayed = analysis.delay_days > 0;
  const isCritical = analysis.is_critical;
  const isNegativeFloat = (analysis.total_float || 0) < 0;
  const category = analysis.delay_float_category;
  
  let statusConfig = { label: 'Not Started', color: 'bg-gray-100 text-gray-500', icon: <Circle size={12} /> };
  
  if (status === 'COMPLETED') {
    statusConfig = { label: 'Completed', color: 'bg-green-100 text-green-700', icon: <CheckCircle size={12} /> };
  } else if (status === 'IN_PROGRESS') {
    statusConfig = { label: 'In Progress', color: 'bg-blue-100 text-blue-700 border border-blue-200', icon: <Loader2 size={12} className="animate-spin-slow" /> };
  } else if (isDelayed) {
    statusConfig = { label: 'Delayed', color: 'bg-orange-100 text-orange-700 border border-orange-200', icon: <AlertTriangle size={12} /> };
  }

  const rowClass = `flex items-center hover:bg-blue-50/40 transition-colors group border-b border-gray-50 py-1 px-2 cursor-pointer${
    (category === 'DELAYED_NEGATIVE' || isNegativeFloat) ? ' bg-red-50 border-l-4 border-l-red-900' :
    category === 'DELAYED_CRITICAL' ? ' bg-red-50/50' :
    isDelayed ? ' bg-orange-50/30' : ''
  }`;

  return (
    <div className="flex flex-col">
      <div className={rowClass} onClick={() => setShowDetails(!showDetails)}>
        <div className="w-36 shrink-0 px-1 text-[9px] font-black text-blue-600/70 truncate" title={task.task_code}>{task.task_code}</div>
        
        <div className="flex-1 px-2 text-[10px] font-semibold text-gray-900 truncate">{task.task_name}</div>
        <div className="w-24 shrink-0 px-1 flex justify-start">
          <span title={analysis.delay_days !== null && analysis.delay_days !== undefined ? `Delay: ${analysis.delay_days} days` : 'Delay: N/A (requires update file)'} className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-tight shadow-sm cursor-help ${statusConfig.color}`}>
            {statusConfig.icon}
            {statusConfig.label}
          </span>
        </div>
        <div className="w-14 shrink-0 px-1 text-[9px] font-bold text-gray-500 text-center" title={`${task.target_drtn_hr_cnt || 0} hours`}>
          {Math.round(task.duration_days || 0)}d
        </div>
        <div className="w-20 shrink-0 px-1 text-[9px] font-semibold text-gray-600 text-center">{formatP6Date(analysis.early_start)}</div>
        <div className="w-20 shrink-0 px-1 text-[9px] font-semibold text-gray-600 text-center">{formatP6Date(analysis.early_finish)}</div>
        <div className="w-20 shrink-0 px-1 text-[9px] font-medium text-gray-400 text-center">{formatP6Date(analysis.late_start)}</div>
        <div className="w-20 shrink-0 px-1 text-[9px] font-medium text-gray-400 text-center">{formatP6Date(analysis.late_finish)}</div>
        <div className={`w-16 shrink-0 px-1 text-[10px] text-right font-black ${isNegativeFloat ? 'text-red-700' : isCritical ? 'text-red-600' : 'text-gray-500'}`}>
          {analysis.total_float != null ? Number(analysis.total_float).toFixed(2) : '-'}
        </div>

        {/* Cost Columns - Moved to end */}
        <div className="w-24 shrink-0 px-1 text-[9px] font-semibold text-gray-500 text-right">{formatCurrency(task.bl_project_cost)}</div>
        <div className="w-24 shrink-0 px-1 text-[9px] font-semibold text-gray-700 text-right">{formatCurrency(task.budget_cost)}</div>
        <div className="w-24 shrink-0 px-1 text-[9px] font-semibold text-green-600 text-right">{formatCurrency(task.ev_cost)}</div>
        <div className="w-24 shrink-0 px-1 text-[9px] font-semibold text-blue-600 text-right">{formatCurrency(task.pv_cost)}</div>
      </div>
      
      {showDetails && (
        <div className="bg-gray-50/80 p-4 border-b border-gray-200 flex flex-col gap-4 shadow-inner animate-in fade-in slide-in-from-top-1 duration-200">
          <div className="flex gap-8">
            {/* Predecessors */}
            <div className="flex-1 flex flex-col gap-2">
              <h4 className="text-[10px] font-black text-gray-400 uppercase tracking-widest border-b border-gray-200 pb-1">Predecessors</h4>
              {analysis.predecessors?.length > 0 ? (
                <div className="flex flex-col gap-1.5">
                  {analysis.predecessors.map((p, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-[10px]">
                      <span className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-black">{p.type}</span>
                      <span className="text-gray-600 font-medium truncate flex-1">{p.name}</span>
                      <span className="text-gray-400 font-mono">Lag: {p.lag}h</span>
                      <ChevronRightIcon size={12} className="text-gray-300" />
                    </div>
                  ))}
                </div>
              ) : <p className="text-[10px] text-gray-400 italic">No predecessors</p>}
            </div>
            
            {/* Current Task Node */}
            <div className="w-48 shrink-0 flex items-center justify-center">
              <div className="bg-white border-2 border-blue-500 rounded-xl p-3 shadow-md flex flex-col items-center gap-1 text-center">
                <span className="text-[8px] font-black text-blue-500 uppercase tracking-tighter">Current Activity</span>
                <span className="text-[9px] font-black text-blue-600 font-mono select-all bg-blue-50 px-2.5 py-0.5 rounded border border-blue-100/50" title="Activity ID - Click or drag to copy">{task.task_code}</span>
                <span className="text-[10px] font-bold text-gray-900 leading-tight">{task.task_name}</span>
              </div>
            </div>

            {/* Successors */}
            <div className="flex-1 flex flex-col gap-2">
              <h4 className="text-[10px] font-black text-gray-400 uppercase tracking-widest border-b border-gray-200 pb-1">Successors</h4>
              {analysis.successors?.length > 0 ? (
                <div className="flex flex-col gap-1.5">
                  {analysis.successors.map((s, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-[10px]">
                      <ChevronRightIcon size={12} className="text-gray-300" />
                      <span className="bg-green-100 text-green-700 px-1.5 py-0.5 rounded font-black">{s.type}</span>
                      <span className="text-gray-600 font-medium truncate flex-1">{s.name}</span>
                      <span className="text-gray-400 font-mono">Lag: {s.lag}h</span>
                    </div>
                  ))}
                </div>
              ) : <p className="text-[10px] text-gray-400 italic">No successors</p>}
            </div>
          </div>
          
          {/* Flow Visualization (Simple A -> B -> C) */}
          <div className="flex items-center justify-center gap-2 mt-2 pt-2 border-t border-gray-200">
             <div className="text-[9px] text-gray-400 font-black uppercase tracking-widest mr-4">Local Flow:</div>
             <div className="flex items-center gap-2 max-w-full overflow-x-auto pb-1">
                {analysis.predecessors?.[0] && (
                  <>
                    <div className="bg-gray-100 text-gray-500 px-2 py-1 rounded text-[9px] truncate max-w-[150px]">{analysis.predecessors[0].name}</div>
                    <div className="h-px w-4 bg-gray-300"></div>
                  </>
                )}
                <div className="bg-blue-600 text-white px-3 py-1.5 rounded-lg text-[10px] font-bold shadow-sm whitespace-nowrap">{task.task_name}</div>
                {analysis.successors?.[0] && (
                  <>
                    <div className="h-px w-4 bg-gray-300"></div>
                    <div className="bg-gray-100 text-gray-500 px-2 py-1 rounded text-[9px] truncate max-w-[150px]">{analysis.successors[0].name}</div>
                  </>
                )}
             </div>
          </div>

          {/* Activity Codes */}
          {analysis.activity_codes && Object.keys(analysis.activity_codes).length > 0 && (
            <div className="mt-2 pt-2 border-t border-gray-200">
              <h4 className="text-[10px] font-black text-gray-400 uppercase tracking-widest border-b border-gray-200 pb-1 mb-2">Activity Codes</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {Object.entries(analysis.activity_codes).map(([type, valObj]) => {
                  const val = typeof valObj === 'object' && valObj !== null ? valObj.value : valObj;
                  const scope = typeof valObj === 'object' && valObj !== null ? valObj.scope : '';
                  return (
                  <div key={type} className="bg-white border border-gray-200 rounded-lg px-3 py-2 shadow-sm">
                    <div className="flex justify-between items-center mb-0.5">
                      <div className="text-[8px] font-bold text-gray-400 uppercase tracking-wider truncate" title={type}>{type}</div>
                      {scope && <span className="text-[7px] font-bold text-gray-500 bg-gray-100 px-1 py-0.5 rounded">{scope}</span>}
                    </div>
                    <div className="text-[10px] font-bold text-blue-700 truncate" title={val}>{val}</div>
                  </div>
                )})}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
});
const WBS_STATUS_COLORS = {
  'CRITICAL':  { bg: 'bg-red-100',    text: 'text-red-700',    dot: 'bg-red-500'    },
  'DELAYED':   { bg: 'bg-orange-100', text: 'text-orange-700', dot: 'bg-orange-500' },
  'AT RISK':   { bg: 'bg-yellow-100', text: 'text-yellow-700', dot: 'bg-yellow-500' },
  'ON TRACK':  { bg: 'bg-emerald-100',text: 'text-emerald-700',dot: 'bg-emerald-500'},
  'EMPTY':     { bg: 'bg-gray-100',   text: 'text-gray-400',   dot: 'bg-gray-300'   },
};

const WBS_CRITICALITY_COLORS = {
  'HIGH CRITICALITY':   { bg: 'bg-red-50',     text: 'text-red-600',     border: 'border-red-200' },
  'MEDIUM CRITICALITY': { bg: 'bg-orange-50',  text: 'text-orange-600',  border: 'border-orange-200' },
  'LOW CRITICALITY':    { bg: 'bg-yellow-50',  text: 'text-yellow-600',  border: 'border-yellow-200' },
  'NOT CRITICAL':       { bg: 'bg-slate-50',   text: 'text-slate-500',   border: 'border-slate-200' },
  'EMPTY':              { bg: 'bg-transparent',text: 'text-transparent', border: 'border-transparent' },
};


const WbsStatusBadge = ({ tag }) => {
  if (!tag) return <div className="w-36 shrink-0" />;
  
  let c;
  if (tag.startsWith('COMPLETED LATE')) {
    c = { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500' };
  } else if (tag === 'COMPLETED ON TIME') {
    c = { bg: 'bg-green-100', text: 'text-green-700', dot: 'bg-green-500' };
  } else {
    c = WBS_STATUS_COLORS[tag] || WBS_STATUS_COLORS['EMPTY'];
  }
  
  return (
    <div className={`w-36 shrink-0 flex items-center gap-1 px-2 py-0.5 rounded-full ${c.bg}`}>
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${c.dot}`} />
      <span className={`text-[9px] font-black uppercase tracking-wide ${c.text} truncate`}>{tag}</span>
    </div>
  );
};

const WbsCriticalityBadge = ({ tag }) => {
  if (!tag || tag === 'EMPTY') return <div className="w-24 shrink-0" />;
  const c = WBS_CRITICALITY_COLORS[tag] || WBS_CRITICALITY_COLORS['NOT CRITICAL'];
  return (
    <div className={`w-24 shrink-0 flex items-center justify-center px-1.5 py-0.5 rounded border ${c.bg} ${c.border}`}>
      <span className={`text-[8.5px] font-bold uppercase tracking-wide ${c.text} truncate`}>{tag}</span>
    </div>
  );
};

const WBSTreeNode = React.memo(({ node, level, formatP6Date, defaultExpanded, showActivities, scheduleMode }) => {
  const [isExpanded, setIsExpanded] = useState(level === 0 || defaultExpanded);
  
  const hasChildren = node.children && node.children.length > 0;
  const hasActivities = showActivities && node.activities && node.activities.length > 0;
  
  return (
    <div className="flex flex-col text-sm">
      <div 
        className={`flex items-center py-2 hover:bg-gray-50 border-b border-gray-200 cursor-pointer ${level === 0 ? 'bg-gray-100/80 shadow-sm sticky top-0 z-10' : 'bg-white'}`}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {/* ID Column */}
        <div className="w-36 shrink-0 flex items-center gap-1.5 overflow-hidden pl-3 pr-1">
          <div className="w-4 h-4 shrink-0 flex items-center justify-center text-gray-400">
            {(hasChildren || hasActivities) ? (
              isExpanded ? <ChevronDown size={14} /> : <ChevronRightIcon size={14} />
            ) : <span className="w-3" />}
          </div>
          <span className="font-black text-[9px] text-blue-600/70 truncate" title={node.wbs_short_name}>{node.wbs_short_name}</span>
        </div>

        {/* Name Column */}
        <div className="flex-1 min-w-[300px] flex items-center gap-2 truncate pr-2" style={{ paddingLeft: `${(level * 24) + 8}px` }}>
          <div className="text-blue-600 shrink-0">
             {isExpanded ? <FolderOpen size={16} className="fill-blue-100" /> : <Folder size={16} className="fill-blue-50" />}
          </div>
          <span className="font-bold text-[12px] text-gray-900 truncate tracking-tight" title={node.wbs_name}>{node.wbs_name}</span>
        </div>

        {/* Branch Analytics */}
        <div className="w-16 shrink-0 px-1 text-[10px] font-bold text-gray-700 text-center">
          {node.summary?.activity_count ?? '-'}
        </div>
        
        {scheduleMode === 'WITH_UPDATE' ? (
          <>
            <div className="w-16 shrink-0 px-1 text-[10px] font-bold text-center" style={{ color: (node.summary?.delayed_count || 0) > 0 ? '#c2410c' : '#6b7280' }}>
              {node.summary?.delayed_count ?? '-'}
            </div>
            <div className="w-16 shrink-0 px-1 text-[10px] font-bold text-center" style={{ color: (node.summary?.critical_count || 0) > 0 ? '#b91c1c' : '#6b7280' }}>
              {node.summary?.critical_count ?? '-'}
            </div>
            <div className="w-20 shrink-0 px-1 text-[10px] font-black text-center" style={{ color: (node.summary?.branch_variance_days || 0) > 0 ? '#92400e' : (node.summary?.branch_variance_days || 0) < 0 ? '#15803d' : '#6b7280' }}>
              {(node.summary?.branch_variance_days || 0) > 0 ? `+${node.summary.branch_variance_days}d` : (node.summary?.branch_variance_days || 0) < 0 ? `${node.summary.branch_variance_days}d` : '-'}
            </div>
            <div className="w-20 shrink-0 px-1 text-[10px] font-black text-center" style={{ color: (node.summary?.worst_delay_days || 0) > 0 ? '#b91c1c' : '#6b7280' }}
              title={node.summary?.worst_delayed_activity ? `Worst: ${node.summary.worst_delayed_activity}` : undefined}>
              {(node.summary?.worst_delay_days || 0) > 0 ? `+${node.summary.worst_delay_days}d` : '-'}
            </div>
            <div className="w-16 shrink-0 px-1 text-[10px] font-bold text-center" style={{ color: (node.summary?.avg_delay_days || 0) > 0 ? '#c2410c' : '#6b7280' }}>
              {(node.summary?.avg_delay_days || 0) > 0 ? `+${node.summary.avg_delay_days}d` : '-'}
            </div>
            <div className={`w-16 shrink-0 px-1 text-[10px] text-center font-bold ${(node.summary?.min_float || 0) < 0 ? 'text-red-700' : 'text-gray-500'}`}>
              {node.summary?.min_float != null ? Number(node.summary.min_float).toFixed(1) : '-'}
            </div>
            <WbsStatusBadge tag={node.summary?.status_tag} />
          </>
        ) : (
          <>
            <div className="w-16 shrink-0 px-1 text-[10px] font-bold text-center" style={{ color: (node.summary?.critical_count || 0) > 0 ? '#b91c1c' : '#6b7280' }}>
              {node.summary?.critical_count ?? '-'}
            </div>
            <div className="w-16 shrink-0 px-1 text-[10px] font-bold text-center text-gray-500">
              {node.summary?.critical_pct != null ? `${node.summary.critical_pct}%` : '-'}
            </div>
            <div className="w-20 shrink-0 px-1 text-[10px] font-bold text-center text-gray-500">
              {node.summary?.min_float != null ? Number(node.summary.min_float).toFixed(1) : '-'}
            </div>
            <WbsCriticalityBadge tag={node.summary?.criticality_tag} />
          </>
        )}

        {/* Status Column (empty spacer, replaced by badge) */}
        <div className="w-0 shrink-0" />

        {/* Duration Column */}
        <div className="w-14 shrink-0 px-1 text-[9px] font-black text-gray-700 text-center bg-gray-100/50 rounded-md py-0.5 mx-1">
          {node.summary?.duration_days ?? 0}d
        </div>

        {/* Dates & Float */}
        <div className="w-20 shrink-0 px-1 text-[9px] font-bold text-gray-800 text-center">{formatP6Date(node.summary?.early_start)}</div>
        <div className="w-20 shrink-0 px-1 text-[9px] font-bold text-gray-800 text-center">{formatP6Date(node.summary?.early_finish)}</div>
        <div className="w-20 shrink-0 px-1 text-[9px] font-medium text-gray-400 text-center opacity-60">{formatP6Date(node.summary?.late_start)}</div>
        <div className="w-20 shrink-0 px-1 text-[9px] font-medium text-gray-400 text-center opacity-60">{formatP6Date(node.summary?.late_finish)}</div>

        {/* Summary Cost Columns - Moved to end */}
        <div className="w-24 shrink-0 px-1 text-[9px] font-bold text-gray-500 text-right bg-gray-50/20">{formatCurrency(node.summary?.bl_project_cost)}</div>
        <div className="w-24 shrink-0 px-1 text-[9px] font-bold text-gray-800 text-right bg-gray-50/50">{formatCurrency(node.summary?.budget_cost)}</div>
        <div className="w-24 shrink-0 px-1 text-[9px] font-bold text-green-700 text-right bg-green-50/20">{formatCurrency(node.summary?.ev_cost)}</div>
        <div className="w-24 shrink-0 px-1 text-[9px] font-bold text-blue-700 text-right bg-blue-50/30">{formatCurrency(node.summary?.pv_cost)}</div>
      </div>

      
      {isExpanded && (
        <div className="flex flex-col">
          {hasActivities && (
            <div className="flex flex-col border-b border-gray-200 bg-white" style={{ paddingLeft: `${((level) * 24) + 16 + 28}px` }}>
                <div className="flex items-center py-1.5 px-2 bg-gray-50/80 border-b border-gray-200 text-[8px] font-black text-gray-400 uppercase tracking-widest sticky top-0 z-0 shadow-sm">
                  <div className="w-36 shrink-0 px-1">ID</div>

                  <div className="flex-1 px-2">Activity Name</div>
                  <div className="w-24 shrink-0 px-1">Status</div>
                  <div className="w-14 shrink-0 px-1 text-center">Dur</div>
                  <div className="w-20 shrink-0 px-1 text-center">ES</div>
                  <div className="w-20 shrink-0 px-1 text-center">EF</div>
                  <div className="w-20 shrink-0 px-1 text-center">LS</div>
                  <div className="w-20 shrink-0 px-1 text-center">LF</div>
                  <div className="w-16 shrink-0 px-1 text-right">Float</div>
                  <div className="w-24 shrink-0 px-1 text-right">BL Project Cost</div>
                  <div className="w-24 shrink-0 px-1 text-right">Budgeted Cost</div>
                  <div className="w-24 shrink-0 px-1 text-right">EV Cost</div>
                  <div className="w-24 shrink-0 px-1 text-right">PV Cost</div>
               </div>
               <div className="bg-white">
                 {node.activities.map(task => (
                   <TaskRow key={task.task_id} task={task} formatP6Date={formatP6Date} />
                 ))}
               </div>
            </div>
          )}
          {hasChildren && node.children.map(child => (
            <WBSTreeNode 
              key={child.wbs_id} 
              node={child} 
              level={level + 1} 
              formatP6Date={formatP6Date} 
              defaultExpanded={defaultExpanded}
              showActivities={showActivities}
              scheduleMode={scheduleMode}
            />
          ))}
        </div>
      )}
    </div>
  );
});

const ControllerTable = ({ 
  tableData, 
  viewerTable, 
  viewerFilter, 
  setViewerFilter, 
  tableSearch, 
  setTableSearch, 
  tablePage, 
  setTablePage, 
  formatP6Date, 
  getHeaderLabel,
  hasProject,
  isTableLoading
}) => {
  const isHierarchy = tableData.table === 'HIERARCHY';
  const showActivities = viewerTable === 'TASK';
  const isFiltered = tableSearch !== '' || viewerFilter !== 'ALL';
  const isRelationships = viewerTable === 'RELATIONSHIPS';

  return (
    <>
      <div className="flex-1 overflow-auto px-8 py-4 relative">
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden flex flex-col min-h-full relative">
          {isTableLoading && (
            <div className="absolute inset-0 z-50 bg-white/70 backdrop-blur-[2px] flex flex-col items-center justify-center animate-in fade-in duration-200">
              <Loader2 size={32} className="text-blue-500 animate-spin mb-3" />
              <p className="text-sm font-bold text-gray-700 tracking-tight">Fetching Table Data...</p>
            </div>
          )}
          <div className="flex-1 overflow-y-auto overflow-x-auto scrollbar-thin scrollbar-thumb-gray-200 relative">
            {isHierarchy ? (
               <div className="flex flex-col min-w-[1850px]">
                 {/* Global Sticky Header for Hierarchy */}
                 <div className="flex items-center py-2.5 px-3 bg-gray-50 border-b border-gray-200 text-[10px] font-black text-gray-400 uppercase tracking-widest sticky top-0 z-30 shadow-sm">
                   <div className="w-36 shrink-0 px-1">ID</div>
                   <div className="flex-1 min-w-[300px] px-2">WBS Name / Activity Name</div>
                   <div className="w-16 shrink-0 px-1 text-center">Acts</div>
                   {tableData.schedule_mode === 'WITH_UPDATE' ? (
                     <>
                       <div className="w-16 shrink-0 px-1 text-center">Delayed</div>
                       <div className="w-16 shrink-0 px-1 text-center">Critical</div>
                       <div className="w-20 shrink-0 px-1 text-center">Branch Var</div>
                       <div className="w-20 shrink-0 px-1 text-center">Worst Delay</div>
                       <div className="w-16 shrink-0 px-1 text-center">Avg Delay</div>
                       <div className="w-16 shrink-0 px-1 text-center">Float</div>
                       <div className="w-36 shrink-0 px-1 text-center">Status</div>
                     </>
                   ) : (
                     <>
                       <div className="w-16 shrink-0 px-1 text-center">Critical</div>
                       <div className="w-16 shrink-0 px-1 text-center">Crit %</div>
                       <div className="w-20 shrink-0 px-1 text-center">Float</div>
                       <div className="w-24 shrink-0 px-1 text-center">Criticality</div>
                     </>
                   )}
                   <div className="w-0 shrink-0" />
                   <div className="w-14 shrink-0 px-1 text-center">Dur</div>
                   <div className="w-20 shrink-0 px-1 text-center">ES</div>
                   <div className="w-20 shrink-0 px-1 text-center">EF</div>
                   <div className="w-20 shrink-0 px-1 text-center">LS</div>
                   <div className="w-20 shrink-0 px-1 text-center">LF</div>
                   <div className="w-24 shrink-0 px-1 text-right">BL Project Cost</div>
                   <div className="w-24 shrink-0 px-1 text-right">Budgeted Cost</div>
                   <div className="w-24 shrink-0 px-1 text-right">EV Cost</div>
                   <div className="w-24 shrink-0 px-1 text-right">PV Cost</div>
                 </div>
                 {tableData.records.length > 0 ? (
                   tableData.records.map(rootNode => (
                     <WBSTreeNode 
                       key={rootNode.wbs_id} 
                       node={rootNode} 
                       level={0} 
                       formatP6Date={formatP6Date} 
                       defaultExpanded={isFiltered}
                       showActivities={showActivities}
                       scheduleMode={tableData.schedule_mode || 'BASELINE_ONLY'}
                     />
                   ))
                 ) : (
                   <div className="px-6 py-32 text-center flex flex-col items-center gap-3 text-gray-400">
                     <Search size={48} className="opacity-20 mb-2" />
                     <p className="text-sm font-medium italic">No schedule data found for this specific criteria</p>
                     <button onClick={() => {setTableSearch(''); setViewerFilter('ALL');}} className="text-xs text-blue-600 font-bold hover:underline">Reset filters</button>
                   </div>
                 )}
               </div>
            ) : isRelationships ? (
              <div className="flex flex-col min-w-[1000px]">
                <table className="w-full text-left border-collapse table-fixed">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200 sticky top-0 z-20">
                      <th className="px-6 py-4 text-[10px] font-black text-gray-400 uppercase tracking-widest w-1/3">Activity Name</th>
                      <th className="px-6 py-4 text-[10px] font-black text-gray-400 uppercase tracking-widest w-1/3">Depends On (Predecessor)</th>
                      <th className="px-6 py-4 text-[10px] font-black text-gray-400 uppercase tracking-widest text-center">Type</th>
                      <th className="px-6 py-4 text-[10px] font-black text-gray-400 uppercase tracking-widest text-right">Lag (Hrs)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 bg-white">
                    {tableData.records.length > 0 ? tableData.records.map((row, i) => (
                      <tr key={i} className="hover:bg-blue-50/40 transition-colors group">
                        <td className="px-6 py-3 text-[11px] font-semibold text-gray-900 truncate">{row.activity_name}</td>
                        <td className="px-6 py-3 text-[11px] font-medium text-gray-600 truncate italic">{row.predecessor_name}</td>
                        <td className="px-6 py-3 text-[11px] text-center">
                          <span className="bg-blue-50 text-blue-700 px-2.5 py-1 rounded-md font-black text-[10px] border border-blue-100 uppercase">{row.relationship_type}</span>
                        </td>
                        <td className="px-6 py-3 text-[11px] text-right font-mono text-gray-500 font-bold">{row.lag}</td>
                      </tr>
                    )) : (
                      <tr>
                        <td colSpan="4" className="px-6 py-32 text-center text-gray-400 italic">No relationships found</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            ) : (
              <table className="min-w-[1200px] w-full text-left border-collapse table-fixed">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200 sticky top-0 z-20">
                    {tableData.records.length > 0 && 
                      (viewerTable === 'RELATIONSHIPS'
                        ? ['task_id', 'pred_task_id', 'pred_type', 'lag_hr_cnt']
                        : Object.keys(tableData.records[0]).filter(k => !k.startsWith('_') && k !== 'is_critical')
                      ).map(key => (
                      <th 
                        key={key} 
                        className={`px-6 py-4 text-[10px] font-black text-gray-400 uppercase tracking-widest whitespace-nowrap bg-gray-50 
                          ${key === 'task_name' || key === 'wbs_name' ? 'text-left w-1/3' : 'text-center w-36'}
                          ${['target_start_date', 'act_start_date', 'total_float_hr_cnt'].includes(key) ? 'border-l border-gray-200/60' : ''}`}
                      >
                        {getHeaderLabel(key)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {tableData.records.length > 0 ? tableData.records.map((row, i) => (
                    <tr key={i} className="hover:bg-blue-50/40 transition-colors group">
                      {(viewerTable === 'RELATIONSHIPS'
                        ? ['task_id', 'pred_task_id', 'pred_type', 'lag_hr_cnt']
                        : Object.entries(row).filter(([k]) => !k.startsWith('_') && k !== 'is_critical').map(([k]) => k)
                      ).map((key, j) => (
                        <td key={j} className={`px-6 py-2.5 text-xs whitespace-nowrap text-center 
                          ${key === 'task_name' || key === 'wbs_name' ? 'font-medium text-gray-900 text-left max-w-sm' : 'text-gray-600'}
                          ${['target_start_date', 'act_start_date', 'total_float_hr_cnt'].includes(key) ? 'border-l border-gray-100/50' : ''}`}>
                          {key.includes('cost') ? formatCurrency(row[key]) : String(row[key] || '-')}
                        </td>
                      ))}
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan="100" className="px-6 py-32 text-center">
                        <div className="flex flex-col items-center gap-3 text-gray-400">
                          {hasProject ? (
                            <>
                              <Search size={48} className="opacity-20 mb-2" />
                              <p className="text-sm font-medium italic">No schedule data found for this specific criteria</p>
                              <button onClick={() => {setTableSearch(''); setViewerFilter('ALL');}} className="text-xs text-blue-600 font-bold hover:underline">Reset filters</button>
                            </>
                          ) : (
                            <>
                              <FolderOpen size={48} className="opacity-20 mb-2" />
                              <p className="text-sm font-medium italic text-blue-600/70">Upload a project XER file to view schedule data.</p>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* P6 Style Pagination Footer */}
      <div className="px-8 py-4 bg-white border-t border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <p className="text-[11px] text-gray-400 font-bold uppercase tracking-wider">
            Records: <span className="text-gray-900 font-black">{tableData.total}</span>
          </p>
          <div className="h-4 w-px bg-gray-200"></div>
          {viewerTable === 'TASK' && tableData.projectAnalysis && (
             <div className="flex gap-4">
               <p className="text-[11px] text-gray-400 font-bold uppercase tracking-wider">
                 Critical: <span className="text-red-500 font-black">{tableData.projectAnalysis.healthMetrics?.criticalCount}</span>
               </p>
               <p className="text-[11px] text-gray-400 font-bold uppercase tracking-wider">
                 In Progress: <span className="text-blue-500 font-black">{tableData.projectAnalysis.healthMetrics?.inProgressTasks}</span>
               </p>
             </div>
          )}
        </div>
        
        {!isHierarchy && (
          <div className="flex items-center gap-3">
            <button 
              disabled={tablePage === 1}
              onClick={() => setTablePage(p => p - 1)}
              className="p-2.5 border border-gray-200 rounded-xl hover:bg-gray-50 disabled:opacity-30 transition-all shadow-sm flex items-center justify-center"
            >
              <ChevronLeft size={16} className="text-gray-600" />
            </button>
            <div className="px-5 py-2 bg-gray-50 border border-gray-200 rounded-xl text-[11px] font-black text-gray-900 shadow-inner">
              PAGE {tablePage}
            </div>
            <button 
              disabled={tablePage * 100 >= tableData.total}
              onClick={() => setTablePage(p => p + 1)}
              className="p-2.5 border border-gray-200 rounded-xl hover:bg-gray-50 disabled:opacity-30 transition-all shadow-sm flex items-center justify-center"
            >
              <ChevronRight size={16} className="text-gray-600" />
            </button>
          </div>
        )}
      </div>
    </>
  );
};

export default ControllerTable;
