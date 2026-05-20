import React from 'react';
import { Activity, ListTree, Link as LinkIcon, Info, Search, X, Zap, CheckCircle, Loader2, AlertTriangle, Users } from 'lucide-react';
import VersionManagerSection from '../VersionManagerSection';

const ControllerToolbar = ({
  viewerTable,
  setViewerTable,
  setTablePage,
  viewerFilter,
  setViewerFilter,
  versions,
  selectedVersionId,
  setSelectedVersionId,
  handleDeleteVersion,
  handleUpload,
  loading,
  tableSearch,
  setTableSearch,
  isControllerChatOpen,
  setIsControllerChatOpen,
  tableData
}) => {
  return (
    <>
      <div className="px-8 py-4 border-b border-gray-200 bg-white flex justify-between items-start gap-4">
        {/* Zone 1: Navigation & Context */}
        <div className="flex flex-col gap-3">
          <div className="flex gap-1.5 p-1 bg-gray-100/80 rounded-xl overflow-x-auto shrink-0">
            {[
              { id: 'TASK', label: 'Activities', icon: <Activity size={14} /> },
              { id: 'WBS', label: 'WBS', icon: <ListTree size={14} /> },
              { id: 'RELATIONSHIPS', label: 'Relationships', icon: <LinkIcon size={14} /> },
              { id: 'PROJECT', label: 'Project Info', icon: <Info size={14} /> },
              { id: 'RESOURCES', label: 'Resources', icon: <Users size={14} /> }
            ].map(t => (
              <button 
                key={t.id}
                onClick={() => { setViewerTable(t.id); setTablePage(1); }}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all whitespace-nowrap flex items-center gap-2 ${viewerTable === t.id ? 'bg-white text-blue-700 shadow-sm border border-gray-200/50' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-200/50'}`}
              >
                {t.icon} {t.label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap gap-1.5">
            {viewerTable === 'TASK' && [
              { id: 'ALL', label: 'All', color: 'border-gray-200 text-gray-600' },
              { id: 'CRITICAL', label: 'Crit', color: 'border-red-200 text-red-600 bg-red-50/30' },
              { id: 'NEG_FLOAT', label: 'Neg', color: 'border-red-400 text-red-800 bg-red-100/50' },
              { id: 'DELAYED', label: 'Del', color: 'border-orange-200 text-orange-700 bg-orange-50/50' },
              { id: 'DELAYED_CRITICAL', label: 'D+C', color: 'border-red-600 text-red-900 bg-red-100' },
              { id: 'DELAYED_NEGATIVE', label: 'D+N', color: 'border-red-800 text-white bg-red-900' }
            ].map(f => (
              <button 
                key={f.id}
                onClick={() => { setViewerFilter(f.id); setTablePage(1); }}
                className={`px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-tighter border transition-all ${viewerFilter === f.id ? f.color + ' ring-2 ring-offset-1 focus:ring-blue-500' : 'bg-white border-gray-100 text-gray-400 hover:border-gray-300'}`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Zone 2: Version Control & Search (Middle) */}
        <div className="flex flex-col gap-3 items-center">
           <div className="flex shrink-0">
             <VersionManagerSection 
                versions={versions}
                selectedVersionId={selectedVersionId}
                setSelectedVersionId={setSelectedVersionId}
                handleDeleteVersion={handleDeleteVersion}
                handleUpload={handleUpload}
                loading={loading}
                mode="toolbar"
                showUpdates={true}
             />
          </div>

          <div className="flex items-center gap-3">
             <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 border border-gray-100 rounded-xl text-[10px] font-black text-gray-600">
               <span className="text-gray-400">VIEW:</span>
               <select 
                  value={selectedVersionId ?? ''}
                  onChange={(e) => { setSelectedVersionId(e.target.value); setTablePage(1); }}
                  className="bg-transparent border-none outline-none cursor-pointer text-gray-900 pr-1 text-[10px] font-black"
               >
                   {versions.map(v => (
                      <option key={v.id} value={v.id}>
                         {v.type === 'baseline' ? (v.name || 'Project') : v.data_date}
                      </option>
                   ))}
               </select>
             </div>

             <div className="relative w-64">
               <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
               <input 
                 type="text"
                 placeholder="Search..."
                 value={tableSearch}
                 onChange={(e) => { setTableSearch(e.target.value); setTablePage(1); }}
                 className="w-full pl-9 pr-4 py-1.5 bg-gray-50 border border-gray-100 rounded-xl text-[10px] font-medium focus:ring-2 focus:ring-blue-500/10 outline-none transition-all focus:bg-white"
               />
             </div>
          </div>
        </div>

        {/* Zone 3: AI Assistant Toggle */}
        <div className="flex shrink-0">
          <button 
            onClick={() => setIsControllerChatOpen(!isControllerChatOpen)}
            className={`flex items-center gap-2 px-6 py-3 rounded-2xl font-black text-xs uppercase tracking-widest transition-all ${isControllerChatOpen ? 'bg-gray-900 text-white shadow-xl translate-y-0.5' : 'bg-blue-600 text-white hover:bg-blue-700 shadow-lg shadow-blue-500/20'}`}
          >
            {isControllerChatOpen ? <X size={16} /> : <Zap size={16} />}
            <span>{isControllerChatOpen ? 'Assistant' : 'Ask AI'}</span>
          </button>
        </div>
      </div>

      {/* P6 Legend & Health Dashboard */}
      {viewerTable === 'TASK' && tableData?.projectAnalysis && (
        <div className="px-8 mt-4 flex flex-col gap-4">
          <div className="flex flex-wrap gap-4 items-center">
            <div className="px-4 py-2 bg-white rounded-xl border border-gray-200 shadow-sm flex items-center gap-3">
              <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Project Variance:</span>
              <span className={`text-sm font-black ${tableData.projectAnalysis.projectDelayDays > 0 ? 'text-red-600' : 'text-green-600'}`}>
                {tableData.projectAnalysis.projectDelayDays ?? 0} DAYS
              </span>
              {tableData.projectAnalysis.healthMetrics?.isConstrained && (
                <span className="text-[10px] font-black text-red-700 bg-red-50 px-2 py-0.5 rounded border border-red-100 animate-pulse">
                  CONSTRAINED
                </span>
              )}
            </div>
            <div className="flex gap-6 items-center text-[10px] font-bold uppercase tracking-wider text-gray-400">
              <span className="flex items-center gap-1.5"><CheckCircle size={12} className="text-green-500" /> {tableData.projectAnalysis.healthMetrics?.completedTasks} Completed</span>
              <span className="flex items-center gap-1.5"><Loader2 size={12} className="text-blue-500" /> {tableData.projectAnalysis.healthMetrics?.inProgressTasks} In Progress</span>
              <span className="flex items-center gap-1.5 text-red-500/80"><AlertTriangle size={12} className="text-red-500" /> {tableData.projectAnalysis.healthMetrics?.delayedTasks} Delayed</span>
            </div>
            
            {/* Delay-Float Matrix Summary */}
            <div className="flex items-center gap-2 ml-auto">
              <span className="text-[9px] font-black text-gray-400 uppercase mr-2 mt-0.5">Delay Breakdown:</span>
              <div className="flex rounded-lg overflow-hidden border border-gray-100 shadow-sm">
                <div className="px-3 py-1.5 bg-green-50 text-green-700 flex flex-col items-center min-w-[60px] border-r border-gray-100">
                  <span className="text-[12px] font-black leading-none">{tableData.projectAnalysis.delayFloatMatrix?.delayed_safe}</span>
                  <span className="text-[7px] font-bold uppercase opacity-60">Safe</span>
                </div>
                <div className="px-3 py-1.5 bg-red-50 text-red-600 flex flex-col items-center min-w-[60px] border-r border-gray-100">
                  <span className="text-[12px] font-black leading-none">{tableData.projectAnalysis.delayFloatMatrix?.delayed_critical}</span>
                  <span className="text-[7px] font-bold uppercase opacity-60">Critical</span>
                </div>
                <div className="px-3 py-1.5 bg-red-900 text-white flex flex-col items-center min-w-[60px]">
                  <span className="text-[12px] font-black leading-none">{tableData.projectAnalysis.delayFloatMatrix?.delayed_negative}</span>
                  <span className="text-[7px] font-bold uppercase opacity-60">Negative</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ControllerToolbar;
