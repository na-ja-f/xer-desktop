import React from 'react';
import { BarChart2, Activity, TrendingDown, Zap } from 'lucide-react';

const AuditDashboard = ({ stats }) => {
  return (
    <div className="mx-6 my-6 bg-gray-900 rounded-[2.5rem] shadow-2xl relative overflow-hidden flex flex-col border border-white/10 max-h-[500px]">
      <div className="absolute top-0 right-0 p-8 opacity-[0.03] pointer-events-none">
        <BarChart2 size={240} />
      </div>
      
      {/* Sticky Header */}
      <div className="p-8 pb-4 relative z-20 w-full border-b border-white/5 bg-gray-900/50 backdrop-blur-md">
        <div className="flex items-center justify-between">
          <h4 className="text-2xl font-bold flex items-center gap-3 text-white">
            <Activity size={24} className="text-blue-500" />
            Project Audit Summary
          </h4>
        </div>
      </div>

      {/* Scrollable Content Area */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-8 pt-6 relative z-10 w-full">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 pb-4">
          {/* Left Column: Health and Score Metrics */}
          <div className="col-span-1 border-r border-white/10 pr-8">
            <h5 className="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-4">Core Metrics</h5>
            <div className="flex flex-col gap-5">
              <div className="flex justify-between items-center">
                 <span className="text-gray-400 text-xs font-bold uppercase tracking-wider">Project Delay:</span>
                 <span className={`text-xl font-black ${stats?.delay_matrix?.projectDelayDays > 0 ? 'text-red-400' : 'text-green-400'}`}>
                   {stats?.delay_matrix?.projectDelayDays || 0} Days
                 </span>
              </div>
              <div className="flex justify-between items-center">
                 <span className="text-gray-400 text-xs font-bold uppercase tracking-wider">Critical Tasks:</span>
                 <span className="text-xl font-black text-white">{stats?.critical_count || 0}</span>
              </div>
              <div className="flex justify-between items-center">
                 <span className="text-gray-400 text-xs font-bold uppercase tracking-wider">Constraint:</span>
                 <span 
                   className={`text-lg font-black cursor-help ${stats?.delay_matrix?.isConstrained ? 'text-red-400' : 'text-green-400'}`}
                   title={stats?.delay_matrix?.isConstrained ? 'Project has a hard finish constraint (e.g., Must Finish By) which is causing negative float and may be artificially hiding delays.' : 'Project finish date is dynamic and purely logic-driven without hard project-level constraints.'}
                 >
                   {stats?.delay_matrix?.isConstrained ? 'Fixed-Finish' : 'Dynamic'}
                 </span>
              </div>
              <div className="flex justify-between items-center">
                 <span className="text-gray-400 text-xs font-bold uppercase tracking-wider">Negative Float:</span>
                 <span className="text-xl font-black text-orange-400">{stats?.negative_float_count || 0}</span>
              </div>
            </div>

            {stats?.delay_matrix?.qualityIssues?.length > 0 && (
              <div className="mt-6 pt-5 border-t border-white/5">
                <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest mb-3 block">Detected Integrity Issues:</span>
                <div className="space-y-2">
                  {stats.delay_matrix.qualityIssues.map((issue, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-[11px] font-medium text-gray-300">
                      <div className="w-1.5 h-1.5 rounded-full bg-red-400 shrink-0"></div>
                      <span className="leading-tight">{issue}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Middle Column: Top Delay Drivers */}
          <div className="col-span-1 border-r border-white/10 pr-8">
            <h5 className="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-4 flex items-center gap-2">
               <TrendingDown size={14} className="text-red-400" />
               Top Delay Drivers
            </h5>
            <div className="space-y-2">
               {stats?.topDrivers?.length > 0 ? (
                 stats.topDrivers.map((d, i) => (
                   <div key={i} className="flex items-center justify-between p-2.5 bg-red-950/30 rounded border border-red-500/10">
                     <div className="flex flex-col">
                       <span className="text-xs font-black text-blue-300 leading-tight">{d.task_code}</span>
                       <span className="text-[10px] font-medium text-gray-400 w-36 truncate">{d.task_name}</span>
                     </div>
                     <span className="text-sm font-black text-red-500">+{d.delay_days}d</span>
                   </div>
                 ))
               ) : (
                 <div className="text-sm text-gray-500 italic mt-2">No active delay drivers detected.</div>
               )}
            </div>
          </div>

          {/* Right Column: Highest Risk (Negative Float) */}
          <div className="col-span-1">
            <h5 className="text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-4 flex items-center gap-2">
               <Zap size={14} className="text-orange-400" />
               Highest Risk (Negative Float)
            </h5>
            <div className="space-y-2">
               {stats?.topRisks?.length > 0 ? (
                 stats.topRisks.map((r, i) => (
                   <div key={i} className="flex items-center justify-between p-2.5 bg-orange-950/20 rounded border border-orange-500/10">
                     <div className="flex flex-col">
                       <span className="text-xs font-black text-blue-300 leading-tight">{r.task_code}</span>
                       <span className="text-[10px] font-medium text-gray-400 w-36 truncate">{r.task_name}</span>
                     </div>
                     <span className="text-sm font-black text-orange-400">{r.float_hrs}h</span>
                   </div>
                 ))
               ) : (
                 <div className="text-sm text-gray-500 italic mt-2">No negative float detected.</div>
               )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuditDashboard;
