import React, { useState } from 'react';
import { Search, Circle, CheckCircle, Loader2, AlertTriangle, ChevronLeft, ChevronRight, Folder, FolderOpen, ChevronDown, ChevronRight as ChevronRightIcon } from 'lucide-react';

const formatCurrency = (val) => {
  if (val === null || val === undefined) return '-';
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);
};

const TaskRow = React.memo(({ task, formatP6Date, evmMethodology, level }) => {
  const [showDetails, setShowDetails] = useState(false);
  const [showCalendarDetails, setShowCalendarDetails] = useState(false);
  const analysis = task._analysis || {};
  const status = analysis.status;
  const classification = analysis.classification || 'ON_TRACK';
  const isDelayed = classification === 'DELAYED';
  const isAtRisk = classification === 'AT_RISK';
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
  } else if (isAtRisk) {
    statusConfig = { label: 'At Risk', color: 'bg-amber-100 text-amber-700 border border-amber-200', icon: <AlertTriangle size={12} className="text-amber-500" /> };
  }

  const rowClass = `flex items-center hover:bg-blue-50/40 transition-colors group border-b border-gray-50 py-1 pr-2 cursor-pointer${
    (category === 'DELAYED_NEGATIVE' || isNegativeFloat) ? ' bg-red-50 border-l-4 border-l-red-900' :
    category === 'DELAYED_CRITICAL' ? ' bg-red-50/50' :
    isDelayed ? ' bg-orange-50/30' :
    isAtRisk ? ' bg-amber-50/20' : ' bg-white'
  }`;

  const cellBg = (category === 'DELAYED_NEGATIVE' || isNegativeFloat) ? 'bg-red-50' :
                 category === 'DELAYED_CRITICAL' ? 'bg-[#fff5f5]' :
                 isDelayed ? 'bg-orange-50' : // using Tailwind orange-50
                 isAtRisk ? 'bg-amber-50' : 'bg-white group-hover:bg-blue-50';

  return (
    <div className="flex flex-col">
      <div className={rowClass} onClick={() => setShowDetails(!showDetails)}>
        {/* LEFT PANEL (fixed, sticky) */}
        <div className={`w-[520px] shrink-0 sticky left-0 z-20 border-r border-gray-200 ${cellBg} flex items-center self-stretch pr-2`}>
          <div className="w-36 shrink-0 pl-3 pr-1 text-[9px] font-black text-blue-600/70 truncate border-r border-gray-200/50 h-full flex items-center" title={task.task_code}>
            {task.task_code}
          </div>
          <div className="flex-1 px-3 text-[10px] font-semibold text-gray-900 truncate h-full flex items-center" style={{ paddingLeft: `${((level + 1) * 20) + 8}px` }} title={task.task_name}>
            {task.task_name}
          </div>
        </div>
        <div className="w-24 shrink-0 px-1 flex justify-start">
          <span title={
            isAtRisk 
              ? `At Risk: slip is ${analysis.forecast_slip_days} days (threshold: ${analysis.threshold_days}d)` 
              : (analysis.delay_days !== null && analysis.delay_days !== undefined ? `Delay: ${analysis.delay_days} days` : 'Delay: N/A')
          } className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-tight shadow-sm cursor-help ${statusConfig.color}`}>
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
        
        {/* Baseline Float */}
        <div className="w-20 shrink-0 px-1 text-[10px] text-right font-semibold text-gray-500">
          {analysis.bl_float_days != null ? `${Number(analysis.bl_float_days).toFixed(1)}d` : '-'}
        </div>
        {/* Float Consumed % */}
        <div className={`w-24 shrink-0 px-1 text-[10px] text-right font-semibold ${
          (analysis.float_consumed_pct || 0) > 0.75 ? 'text-red-600' : (analysis.float_consumed_pct || 0) >= 0.50 ? 'text-amber-600' : 'text-emerald-700'
        }`}>
          {analysis.float_consumed_pct != null ? `${(analysis.float_consumed_pct * 100).toFixed(0)}%` : '-'}
        </div>
        {/* Float Risk Badge */}
        <div className="w-24 shrink-0 px-1 flex justify-center">
          {(() => {
            const fRisk = task.float_risk || analysis.float_risk || 'Stable';
            const config = FLOAT_RISK_BADGES[fRisk] || FLOAT_RISK_BADGES['Stable'];
            return (
              <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-tight shadow-sm border ${config.color}`}>
                {config.label}
              </span>
            );
          })()}
        </div>

        {/* Cost Columns - Moved to end */}
        {evmMethodology === 'COST' ? (
          <>
            <div className="w-24 shrink-0 px-1 text-[9px] font-semibold text-gray-500 text-right">{formatCurrency(task.bl_project_cost)}</div>
            <div className="w-24 shrink-0 px-1 text-[9px] font-semibold text-gray-700 text-right">{formatCurrency(task.budget_cost)}</div>
            <div className="w-24 shrink-0 px-1 text-[9px] font-semibold text-green-600 text-right">{formatCurrency(task.ev_cost)}</div>
            <div className="w-24 shrink-0 px-1 text-[9px] font-semibold text-blue-600 text-right">{formatCurrency(task.pv_cost)}</div>
          </>
        ) : (
          <>
            <div className="w-24 shrink-0 px-1 text-[9px] font-semibold text-gray-700 text-right">{task.target_labor != null ? Number(task.target_labor).toLocaleString(undefined, {maximumFractionDigits: 1}) : '-'}</div>
            <div className="w-24 shrink-0 px-1 text-[9px] font-semibold text-blue-600 text-right">{task.pv_labor != null ? Number(task.pv_labor).toLocaleString(undefined, {maximumFractionDigits: 1}) : '-'}</div>
            <div className="w-24 shrink-0 px-1 text-[9px] font-semibold text-green-600 text-right">{task.ev_labor != null ? Number(task.ev_labor).toLocaleString(undefined, {maximumFractionDigits: 1}) : '-'}</div>
            <div className="w-24 shrink-0 px-1 text-[9px] font-semibold text-gray-500 text-right">{task.sv_labor != null ? Number(task.sv_labor).toLocaleString(undefined, {maximumFractionDigits: 1}) : '-'}</div>
          </>
        )}
      </div>
      
      {showDetails && (
        <div className="sticky left-0 max-w-[1000px] z-10 bg-gray-50/90 border-b border-r border-gray-200/50 p-4 flex flex-col gap-4 shadow-inner animate-in fade-in slide-in-from-top-1 duration-200">
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
          
          {/* Float & Risk Diagnostics Card */}
          <div className="bg-white border border-gray-200/80 rounded-xl p-4 shadow-sm flex flex-col gap-2 mt-2">
            <h4 className="text-[10px] font-black text-gray-400 uppercase tracking-widest border-b border-gray-100 pb-1 mb-1">Float & Risk Diagnostics</h4>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <div className="bg-gray-50/50 border border-gray-100 rounded-lg p-2 flex flex-col justify-between">
                <span className="text-[8px] font-bold text-gray-400 uppercase tracking-wider">Baseline Float</span>
                <span className="text-xs font-black text-gray-700 mt-1">
                  {analysis.bl_float_days != null ? `${Number(analysis.bl_float_days).toFixed(1)}d` : '-'}
                </span>
              </div>
              <div className="bg-gray-50/50 border border-gray-100 rounded-lg p-2 flex flex-col justify-between">
                <span className="text-[8px] font-bold text-gray-400 uppercase tracking-wider">Current Float</span>
                <span className={`text-xs font-black mt-1 ${
                  (analysis.total_float || 0) < 0 ? 'text-red-700 font-extrabold' : (analysis.total_float || 0) === 0 ? 'text-red-500 font-extrabold' : 'text-gray-700'
                }`}>
                  {analysis.total_float != null ? `${Number(analysis.total_float).toFixed(1)}d` : '-'}
                </span>
              </div>
              <div className="bg-gray-50/50 border border-gray-100 rounded-lg p-2 flex flex-col justify-between">
                <span className="text-[8px] font-bold text-gray-400 uppercase tracking-wider">Float Consumed %</span>
                <span className={`text-xs font-black mt-1 ${
                  (analysis.float_consumed_pct || 0) > 0.75 ? 'text-red-600' : (analysis.float_consumed_pct || 0) >= 0.50 ? 'text-amber-500' : 'text-emerald-600'
                }`}>
                  {analysis.float_consumed_pct != null ? `${(analysis.float_consumed_pct * 100).toFixed(1)}%` : '-'}
                </span>
              </div>
              <div className="bg-gray-50/50 border border-gray-100 rounded-lg p-2 flex flex-col justify-between">
                <span className="text-[8px] font-bold text-gray-400 uppercase tracking-wider">Float Risk</span>
                <div className="mt-1">
                  {(() => {
                    const fRisk = analysis.float_risk || 'Stable';
                    const config = FLOAT_RISK_BADGES[fRisk] || FLOAT_RISK_BADGES['Stable'];
                    return (
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-tight border ${config.color}`}>
                        {config.label}
                      </span>
                    );
                  })()}
                </div>
              </div>
              <div className="bg-gray-50/50 border border-gray-100 rounded-lg p-2 flex flex-col justify-between">
                <span className="text-[8px] font-bold text-gray-400 uppercase tracking-wider">Forecast Slip</span>
                <span className={`text-xs font-black mt-1 ${
                  (analysis.forecast_slip_days || 0) > 0 ? 'text-red-600 font-extrabold' : 'text-gray-700'
                }`}>
                  {analysis.forecast_slip_days != null ? `${Number(analysis.forecast_slip_days).toFixed(1)}d` : '-'}
                </span>
              </div>
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

          {/* Calendar Details */}
          {analysis.calendar && (
            <div className="mt-2 pt-2 border-t border-gray-200">
              <div className="flex items-center justify-between border-b border-gray-200 pb-1 mb-2">
                <h4 className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Calendar Information</h4>
                <button 
                  onClick={(e) => { e.stopPropagation(); setShowCalendarDetails(!showCalendarDetails); }}
                  className="text-[9px] font-bold text-blue-600 hover:text-blue-800 bg-blue-50 px-2 py-0.5 rounded flex items-center gap-1"
                >
                  {showCalendarDetails ? 'Hide Exceptions' : 'View Exceptions'}
                </button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                <div className="bg-white border border-gray-200 rounded-lg px-3 py-2 shadow-sm">
                  <div className="text-[8px] font-bold text-gray-400 uppercase tracking-wider truncate mb-0.5">Calendar Name</div>
                  <div className="text-[10px] font-bold text-blue-700 truncate" title={analysis.calendar.name}>{analysis.calendar.name}</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg px-3 py-2 shadow-sm">
                  <div className="text-[8px] font-bold text-gray-400 uppercase tracking-wider truncate mb-0.5">Workweek</div>
                  <div className="text-[10px] font-bold text-gray-700 truncate">{analysis.calendar.workweek_type || '-'}</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg px-3 py-2 shadow-sm">
                  <div className="text-[8px] font-bold text-gray-400 uppercase tracking-wider truncate mb-0.5">Hours / Day</div>
                  <div className="text-[10px] font-bold text-gray-700 truncate">{analysis.calendar.hours_per_day ? `${analysis.calendar.hours_per_day}h` : '-'}</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-lg px-3 py-2 shadow-sm">
                  <div className="text-[8px] font-bold text-gray-400 uppercase tracking-wider truncate mb-0.5">Exceptions</div>
                  <div className="text-[10px] font-bold text-gray-700 truncate">
                    {analysis.calendar.non_working_exceptions_count || 0} Holidays
                  </div>
                </div>
              </div>
              
              {showCalendarDetails && (
                <div className="mt-2 bg-gray-50 border border-gray-200 rounded-lg p-3 grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <h5 
                      className="text-[9px] font-black text-amber-600 uppercase tracking-widest mb-2 border-b border-gray-200 pb-1 cursor-help"
                      title="Dates explicitly marked as non-working. These may represent public holidays, company shutdowns, weather delays, Ramadan adjustments, or any manually excluded workdays."
                    >
                      Non-Working Dates ({analysis.calendar.non_working_exceptions_count || 0})
                    </h5>
                    {analysis.calendar.non_working_exceptions?.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                        {analysis.calendar.non_working_exceptions.map((d, i) => {
                          const dateObj = new Date(d.split('-')[0], parseInt(d.split('-')[1]) - 1, d.split('-')[2]);
                          const formatted = isNaN(dateObj.getTime()) ? d : dateObj.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
                          return (
                            <span key={i} className="px-1.5 py-0.5 bg-amber-50 border border-amber-100 rounded text-[9px] font-mono text-amber-800">{formatted}</span>
                          );
                        })}
                      </div>
                    ) : <span className="text-[9px] text-gray-400 italic">No non-working dates defined.</span>}
                  </div>
                  <div>
                    <h5 
                      className="text-[9px] font-black text-emerald-600 uppercase tracking-widest mb-2 border-b border-gray-200 pb-1 cursor-help"
                      title="Dates that would normally be non-working but were intentionally made working to support recovery or acceleration."
                    >
                      Working Overrides ({analysis.calendar.working_exceptions_count || 0})
                    </h5>
                    {analysis.calendar.working_exceptions?.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                        {analysis.calendar.working_exceptions.map((d, i) => {
                          const dateObj = new Date(d.split('-')[0], parseInt(d.split('-')[1]) - 1, d.split('-')[2]);
                          const formatted = isNaN(dateObj.getTime()) ? d : dateObj.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
                          return (
                            <span key={i} className="px-1.5 py-0.5 bg-emerald-50 border border-emerald-100 rounded text-[9px] font-mono text-emerald-800">{formatted}</span>
                          );
                        })}
                      </div>
                    ) : <span className="text-[9px] text-gray-400 italic">No working overrides defined.</span>}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
});
const WBS_STATUS_COLORS = {
  'Critical':   { bg: 'bg-red-100',    text: 'text-red-700',    dot: 'bg-red-500'    },
  'Slipping':   { bg: 'bg-orange-100', text: 'text-orange-700', dot: 'bg-orange-500' },
  'Watch':      { bg: 'bg-yellow-100', text: 'text-yellow-700', dot: 'bg-yellow-500' },
  'Performing': { bg: 'bg-emerald-100',text: 'text-emerald-700',dot: 'bg-emerald-500'},
  'EMPTY':      { bg: 'bg-gray-100',   text: 'text-gray-400',   dot: 'bg-gray-300'   },
};

const WBS_CRITICALITY_COLORS = {
  'HIGH CRITICALITY':   { bg: 'bg-red-50',     text: 'text-red-600',     border: 'border-red-200' },
  'MEDIUM CRITICALITY': { bg: 'bg-orange-50',  text: 'text-orange-600',  border: 'border-orange-200' },
  'LOW CRITICALITY':    { bg: 'bg-yellow-50',  text: 'text-yellow-600',  border: 'border-yellow-200' },
  'NOT CRITICAL':       { bg: 'bg-slate-50',   text: 'text-slate-500',   border: 'border-slate-200' },
  'EMPTY':              { bg: 'bg-transparent',text: 'text-transparent', border: 'border-transparent' },
};

const EVM_STATUS_COLORS = {
  'ON TRACK':    { bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  'NEAR TRACK':  { bg: 'bg-yellow-100',  text: 'text-yellow-700',  dot: 'bg-yellow-500' },
  'BEHIND':      { bg: 'bg-red-100',     text: 'text-red-700',     dot: 'bg-red-500' },
};

const FLOAT_RISK_BADGES = {
  'Critical': { label: 'Critical', color: 'bg-red-100 text-red-700 border border-red-200' },
  'At Risk': { label: 'At Risk', color: 'bg-orange-100 text-orange-700 border border-orange-200' },
  'Watching': { label: 'Watching', color: 'bg-yellow-100 text-yellow-700 border border-yellow-200' },
  'Stable': { label: 'Stable', color: 'bg-green-100 text-green-700 border border-green-200' },
};

const WbsStatusBadge = ({ tag }) => {
  if (!tag) return <div className="w-36 shrink-0" />;
  const c = WBS_STATUS_COLORS[tag] || WBS_STATUS_COLORS['EMPTY'];
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

const WBSTreeNode = React.memo(({ node, level, formatP6Date, defaultExpanded, showActivities, scheduleMode, evmMethodology }) => {
  const [isExpanded, setIsExpanded] = useState(level === 0 || defaultExpanded);
  
  const hasChildren = node.children && node.children.length > 0;
  const hasActivities = showActivities && node.activities && node.activities.length > 0;
  
  const wbsCellBg = level === 0 ? 'bg-gray-100' : 'bg-white group-hover:bg-gray-50';
  return (
    <div className="flex flex-col text-sm">
      <div 
        className={`flex items-center py-2 hover:bg-gray-50 border-b border-gray-200 cursor-pointer group ${level === 0 ? 'bg-gray-100 shadow-sm sticky top-0 z-10' : 'bg-white'}`}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {/* LEFT PANEL (fixed, sticky) */}
        <div className={`w-[520px] shrink-0 sticky left-0 z-20 border-r border-gray-200 ${wbsCellBg} flex items-center self-stretch pr-2`}>
          {/* ID Column part */}
          <div className="w-36 shrink-0 flex items-center gap-1.5 overflow-hidden pl-3 pr-1 border-r border-gray-200/50 h-full">
            <div className="w-4 h-4 shrink-0 flex items-center justify-center text-gray-400">
              {(hasChildren || hasActivities) ? (
                isExpanded ? <ChevronDown size={14} /> : <ChevronRightIcon size={14} />
              ) : <span className="w-3" />}
            </div>
            <span className="font-black text-[9px] text-blue-600/70 truncate" title={node.wbs_short_name}>{node.wbs_short_name}</span>
          </div>

          {/* Name Column part */}
          <div className="flex-1 flex items-center gap-2 truncate px-3 pr-2 h-full" style={{ paddingLeft: `${(level * 20) + 8}px` }}>
            <div className="text-blue-600 shrink-0">
               {isExpanded ? <FolderOpen size={16} className="fill-blue-100" /> : <Folder size={16} className="fill-blue-50" />}
            </div>
            <span className="font-bold text-[12px] text-gray-900 truncate tracking-tight" title={node.wbs_name}>{node.wbs_name}</span>
          </div>
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
            {(() => {
              const floatRiskTooltip = node.summary ? 
                `Float Risk Distribution (Active Tasks):
- Critical: ${node.summary.critical_count ?? 0} (${node.summary.critical_pct ?? 0}%)
- At Risk: ${node.summary.at_risk_count ?? 0} (${node.summary.at_risk_pct ?? 0}%)
- Watching: ${node.summary.watching_count ?? 0} (${node.summary.watching_pct ?? 0}%)
- Stable: ${node.summary.stable_count ?? 0} (${node.summary.stable_pct ?? 0}%)`
                : '';
              return (
                <>
                  <div className="w-16 shrink-0 px-1 text-[10px] font-bold text-center cursor-help" style={{ color: (node.summary?.at_risk_count || 0) > 0 ? '#d97706' : '#6b7280' }} title={floatRiskTooltip}>
                    {node.summary?.at_risk_count ?? '-'}
                  </div>
                  <div className="w-16 shrink-0 px-1 text-[10px] font-bold text-center cursor-help" style={{ color: (node.summary?.critical_count || 0) > 0 ? '#b91c1c' : '#6b7280' }} title={floatRiskTooltip}>
                    {node.summary?.critical_count ?? '-'}
                  </div>
                </>
              );
            })()}
            <div className="w-20 shrink-0 px-1 text-[10px] font-black text-center" style={{ color: (node.summary?.branch_variance_days || 0) > 0 ? '#92400e' : (node.summary?.branch_variance_days || 0) < 0 ? '#15803d' : '#6b7280' }}>
              {(node.summary?.branch_variance_days || 0) > 0 ? `+${node.summary.branch_variance_days}d` : (node.summary?.branch_variance_days || 0) < 0 ? `${node.summary.branch_variance_days}d` : '-'}
            </div>
            <div className="w-20 shrink-0 px-1 text-[10px] font-black text-center" style={{ color: (node.summary?.worst_delay_days || 0) > 0 ? '#b91c1c' : '#6b7280' }}
              title={node.summary?.worst_delayed_activity ? `Worst: ${node.summary.worst_delayed_activity}` : undefined}>
              {(node.summary?.worst_delay_days || 0) > 0 ? `+${node.summary.worst_delay_days}d` : '-'}
            </div>
            {/* SPI Column */}
            <div className={`w-14 shrink-0 px-1 text-[10px] text-center font-black ${
              (evmMethodology === 'COST' ? node.summary?.spi : node.summary?.spi_labor) == null ? 'text-gray-400' :
              (evmMethodology === 'COST' ? node.summary.spi : node.summary.spi_labor) >= 0.95 ? 'text-emerald-700' :
              (evmMethodology === 'COST' ? node.summary.spi : node.summary.spi_labor) >= 0.85 ? 'text-yellow-700' : 'text-red-700'
            }`}
              title={evmMethodology === 'COST' 
                ? (node.summary?.sv_cost != null ? `SV Cost: ${formatCurrency(node.summary.sv_cost)}\n\n${node.summary.spi_coverage_label || ''}` : undefined)
                : (node.summary?.sv_labor != null ? `SV Labor: ${Number(node.summary.sv_labor).toLocaleString(undefined, {maximumFractionDigits: 1})}\n\n${node.summary.spi_labor_coverage_label || ''}` : undefined)
              }>
              {(evmMethodology === 'COST' ? node.summary?.spi : node.summary?.spi_labor) != null ? (evmMethodology === 'COST' ? node.summary.spi : node.summary.spi_labor).toFixed(2) : '-'}
            </div>
            <div className={`w-16 shrink-0 px-1 text-[10px] text-center font-bold ${(node.summary?.min_float || 0) < 0 ? 'text-red-700' : 'text-gray-500'}`}>
              {node.summary?.min_float != null ? Number(node.summary.min_float).toFixed(1) : '-'}
            </div>

            {/* Float Risk Badge */}
            <div className="w-24 shrink-0 px-1 flex justify-center">
              {node.summary?.float_risk ? (() => {
                const config = FLOAT_RISK_BADGES[node.summary.float_risk] || FLOAT_RISK_BADGES['Stable'];
                return (
                  <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-tight shadow-sm border ${config.color}`}>
                    {config.label}
                  </span>
                );
              })() : '-'}
            </div>
            <WbsStatusBadge tag={node.summary?.status_tag} />
            {/* EVM Status Badge */}
            {node.summary?.evm_status ? (() => {
              const ec = EVM_STATUS_COLORS[node.summary.evm_status] || EVM_STATUS_COLORS['BEHIND'];
              return (
                <div className={`w-24 shrink-0 flex items-center gap-1 px-1.5 py-0.5 rounded-full ${ec.bg}`}>
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${ec.dot}`} />
                  <span className={`text-[8px] font-black uppercase tracking-wide ${ec.text} truncate`}>{node.summary.evm_status}</span>
                </div>
              );
            })() : <div className="w-24 shrink-0" />}
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
        {evmMethodology === 'COST' ? (
          <>
            <div className="w-24 shrink-0 px-1 text-[9px] font-bold text-gray-500 text-right bg-gray-50/20">{formatCurrency(node.summary?.bl_project_cost)}</div>
            <div className="w-24 shrink-0 px-1 text-[9px] font-bold text-gray-800 text-right bg-gray-50/50">{formatCurrency(node.summary?.budget_cost)}</div>
            <div className="w-24 shrink-0 px-1 text-[9px] font-bold text-green-700 text-right bg-green-50/20">{formatCurrency(node.summary?.ev_cost)}</div>
            <div className="w-24 shrink-0 px-1 text-[9px] font-bold text-blue-700 text-right bg-blue-50/30">{formatCurrency(node.summary?.pv_cost)}</div>
          </>
        ) : (
          <>
            <div className="w-24 shrink-0 px-1 text-[9px] font-bold text-gray-800 text-right bg-gray-50/50">{node.summary?.target_labor != null ? Number(node.summary.target_labor).toLocaleString(undefined, {maximumFractionDigits: 1}) : '-'}</div>
            <div className="w-24 shrink-0 px-1 text-[9px] font-bold text-blue-700 text-right bg-blue-50/30">{node.summary?.pv_labor != null ? Number(node.summary.pv_labor).toLocaleString(undefined, {maximumFractionDigits: 1}) : '-'}</div>
            <div className="w-24 shrink-0 px-1 text-[9px] font-bold text-green-700 text-right bg-green-50/20">{node.summary?.ev_labor != null ? Number(node.summary.ev_labor).toLocaleString(undefined, {maximumFractionDigits: 1}) : '-'}</div>
            <div className="w-24 shrink-0 px-1 text-[9px] font-bold text-gray-500 text-right bg-gray-50/20">{node.summary?.sv_labor != null ? Number(node.summary.sv_labor).toLocaleString(undefined, {maximumFractionDigits: 1}) : '-'}</div>
          </>
        )}
      </div>

      
      {isExpanded && (
        <div className="flex flex-col">
          {hasActivities && (
            <div className="flex flex-col border-b border-gray-200 bg-white">
                <div className="flex items-center py-1.5 pr-2 bg-gray-50 border-b border-gray-200 text-[8px] font-black text-gray-400 uppercase tracking-widest sticky top-0 z-0 shadow-sm">
                  {/* LEFT PANEL HEADER for Activities */}
                  <div className="w-[520px] shrink-0 flex items-center sticky left-0 z-20 bg-gray-50 border-r border-gray-200 self-stretch pr-2">
                    <div className="w-36 shrink-0 pl-3 pr-1 border-r border-gray-200/50">ID</div>
                    <div className="flex-1 px-3">Activity Name</div>
                  </div>
                  {/* RIGHT PANEL HEADER for Activities */}
                  <div className="w-24 shrink-0 px-1">Status</div>
                  <div className="w-14 shrink-0 px-1 text-center">Dur</div>
                  <div className="w-20 shrink-0 px-1 text-center">ES</div>
                  <div className="w-20 shrink-0 px-1 text-center">EF</div>
                  <div className="w-20 shrink-0 px-1 text-center">LS</div>
                  <div className="w-20 shrink-0 px-1 text-center">LF</div>
                  <div className="w-16 shrink-0 px-1 text-right">Float</div>
                  <div className="w-20 shrink-0 px-1 text-right">Baseline Float</div>
                  <div className="w-24 shrink-0 px-1 text-right">Float Consumed %</div>
                  <div className="w-24 shrink-0 px-1 text-center">Float Risk</div>
                  {evmMethodology === 'COST' ? (
                    <>
                      <div className="w-24 shrink-0 px-1 text-right">BL Project Cost</div>
                      <div className="w-24 shrink-0 px-1 text-right">Budgeted Cost</div>
                      <div className="w-24 shrink-0 px-1 text-right">EV Cost</div>
                      <div className="w-24 shrink-0 px-1 text-right">PV Cost</div>
                    </>
                  ) : (
                    <>
                      <div className="w-24 shrink-0 px-1 text-right">Budget Labor Units</div>
                      <div className="w-24 shrink-0 px-1 text-right">PV Labor Units</div>
                      <div className="w-24 shrink-0 px-1 text-right">EV Labor Units</div>
                      <div className="w-24 shrink-0 px-1 text-right">SV Labor Units</div>
                    </>
                  )}
               </div>
               <div className="bg-white">
                 {node.activities.map(task => (
                   <TaskRow key={task.task_id} task={task} formatP6Date={formatP6Date} evmMethodology={evmMethodology} level={level} />
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
              evmMethodology={evmMethodology}
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
  baselineError,
  getHeaderLabel,
  hasProject,
  isTableLoading,
  evmMethodology
}) => {
  const isHierarchy = tableData.table === 'HIERARCHY';
  const showActivities = viewerTable === 'TASK';
  const isFiltered = tableSearch !== '' || viewerFilter !== 'ALL';
  const isRelationships = viewerTable === 'RELATIONSHIPS';

  return (
    <>
      <div className="flex-1 overflow-hidden px-8 py-4 relative flex flex-col">
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden flex flex-col flex-1 relative">
          {isTableLoading && (
            <div className="absolute inset-0 z-50 bg-white/70 backdrop-blur-[2px] flex flex-col items-center justify-center animate-in fade-in duration-200">
              <Loader2 size={32} className="text-blue-500 animate-spin mb-3" />
              <p className="text-sm font-bold text-gray-700 tracking-tight">Fetching Table Data...</p>
            </div>
          )}
          <div className="flex-1 overflow-y-auto overflow-x-auto scrollbar-thin scrollbar-thumb-gray-200 relative">
            {isHierarchy ? (
               <div className="flex flex-col min-w-[2200px]">
                  {/* Global Sticky Header for Hierarchy */}
                  <div className="flex items-center py-2.5 pr-3 bg-gray-50 border-b border-gray-200 text-[10px] font-black text-gray-400 uppercase tracking-widest sticky top-0 z-30 shadow-sm">
                    {/* LEFT PANEL HEADER (fixed, sticky left-0 top-0, z-40) */}
                    <div className="w-[520px] shrink-0 flex items-center sticky left-0 top-0 z-40 bg-gray-50 border-r border-gray-200 self-stretch pr-2">
                      <div className="w-36 shrink-0 pl-3 pr-1 border-r border-gray-200/50">ID</div>
                      <div className="flex-1 px-3">WBS Name / Activity Name</div>
                    </div>
                   <div className="w-16 shrink-0 px-1 text-center">Acts</div>
                   {tableData.schedule_mode === 'WITH_UPDATE' ? (
                     <>
                       <div className="w-16 shrink-0 px-1 text-center">Delayed</div>
                       <div className="w-16 shrink-0 px-1 text-center">At Risk</div>
                       <div className="w-16 shrink-0 px-1 text-center">Critical</div>
                       <div className="w-20 shrink-0 px-1 text-center">Branch Var</div>
                       <div className="w-20 shrink-0 px-1 text-center">Worst Delay</div>
                       <div className="w-14 shrink-0 px-1 text-center">{evmMethodology === 'COST' ? 'SPI' : 'SPI LBR'}</div>
                       <div className="w-16 shrink-0 px-1 text-center cursor-help" title="Current Total Float in days.">Float</div>

                       <div className="w-24 shrink-0 px-1 text-center cursor-help" title={`Critical:
Current Float <= 0

At Risk:
Float Consumption > 75%

Watching:
Float Consumption 50–75%

Stable:
Float Consumption < 50%`}>Float Risk</div>
                       <div className="w-36 shrink-0 px-1 text-center">Branch Health</div>
                       <div className="w-24 shrink-0 px-1 text-center">EVM</div>
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
                   {evmMethodology === 'COST' ? (
                     <>
                       <div className="w-24 shrink-0 px-1 text-right">BL Project Cost</div>
                       <div className="w-24 shrink-0 px-1 text-right">Budgeted Cost</div>
                       <div className="w-24 shrink-0 px-1 text-right">EV Cost</div>
                       <div className="w-24 shrink-0 px-1 text-right">PV Cost</div>
                     </>
                   ) : (
                     <>
                       <div className="w-24 shrink-0 px-1 text-right">Budget Labor Units</div>
                       <div className="w-24 shrink-0 px-1 text-right">PV Labor Units</div>
                       <div className="w-24 shrink-0 px-1 text-right">EV Labor Units</div>
                       <div className="w-24 shrink-0 px-1 text-right">SV Labor Units</div>
                     </>
                   )}
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
                       evmMethodology={evmMethodology}
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
                          ${['target_start_date', 'act_start_date', 'total_float_hr_cnt'].includes(key) ? 'border-l border-gray-200/60' : ''}
                          ${key === 'task_code' ? 'sticky left-0 z-30 border-r border-gray-200' : ''}
                          ${key === 'task_name' ? 'sticky left-[144px] z-30 border-r border-gray-200' : ''}`}
                      >
                        {getHeaderLabel(key)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {tableData.records.length > 0 ? tableData.records.map((row, i) => (
                    <tr key={i} className="bg-white hover:bg-blue-50/40 transition-colors group">
                      {(viewerTable === 'RELATIONSHIPS'
                        ? ['task_id', 'pred_task_id', 'pred_type', 'lag_hr_cnt']
                        : Object.entries(row).filter(([k]) => !k.startsWith('_') && k !== 'is_critical').map(([k]) => k)
                      ).map((key, j) => (
                        <td key={j} className={`px-6 py-2.5 text-xs whitespace-nowrap text-center 
                          ${key === 'task_name' || key === 'wbs_name' ? 'font-medium text-gray-900 text-left max-w-sm' : 'text-gray-600'}
                          ${['target_start_date', 'act_start_date', 'total_float_hr_cnt'].includes(key) ? 'border-l border-gray-100/50' : ''}
                          ${key === 'task_code' ? 'sticky left-0 z-10 bg-inherit border-r border-gray-200' : ''}
                          ${key === 'task_name' ? 'sticky left-[144px] z-10 bg-inherit border-r border-gray-200' : ''}`}>
                          {key === 'float_risk' ? (
                            (() => {
                              const fRisk = row[key] || 'Stable';
                              const config = FLOAT_RISK_BADGES[fRisk] || FLOAT_RISK_BADGES['Stable'];
                              return (
                                <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-tight shadow-sm border ${config.color}`}>
                                  {config.label}
                                </span>
                              );
                            })()
                          ) : key === 'float_consumed_pct' ? (
                            row[key] != null ? `${(Number(row[key]) * 100).toFixed(0)}%` : '-'
                          ) : key === 'bl_float_days' ? (
                            row[key] != null ? `${Number(row[key]).toFixed(1)}d` : '-'
                          ) : key.includes('cost') ? (
                            formatCurrency(row[key])
                          ) : (
                            String(row[key] || '-')
                          )}
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
