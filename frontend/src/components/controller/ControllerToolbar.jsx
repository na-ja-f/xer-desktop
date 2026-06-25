import React from 'react';
import { Activity, ListTree, Link as LinkIcon, Info, Search, X, Zap, CheckCircle, Loader2, AlertTriangle, Users, Calendar, BarChart2 } from 'lucide-react';
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
  tableData,
  evmMethodology,
  setEvmMethodology
}) => {
  return (
    <>
      <div className="px-8 py-3 border-b border-gray-200 bg-white flex flex-wrap justify-between items-center gap-y-3 gap-x-4">
        {/* Zone 1: Navigation & Context */}
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex gap-1 p-0.5 bg-gray-100/80 rounded-lg overflow-x-auto min-w-0">
            {[
              { id: 'TASK', label: 'Activities', icon: <Activity size={13} /> },
              { id: 'WBS', label: 'WBS', icon: <ListTree size={13} /> },
              { id: 'RELATIONSHIPS', label: 'Relationships', icon: <LinkIcon size={13} /> },
              { id: 'PROJECT', label: 'Project Info', icon: <Info size={13} /> },
              { id: 'RESOURCES', label: 'Resources', icon: <Users size={13} /> },
              { id: 'CALENDARS', label: 'Calendars', icon: <Calendar size={13} /> },
              { id: 'DASHBOARD', label: 'Dashboard', icon: <BarChart2 size={13} /> }
            ].map(t => (
              <button 
                key={t.id}
                onClick={() => { setViewerTable(t.id); setTablePage(1); }}
                className={`px-3 py-1.5 rounded-md text-[10px] font-bold transition-all whitespace-nowrap flex items-center gap-1.5 ${viewerTable === t.id ? 'bg-white text-blue-700 shadow-sm border border-gray-200/50' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-200/50'}`}
              >
                {t.icon} {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Zone 2: Version Control & Search */}
        <div className="flex items-center flex-wrap justify-end gap-3 flex-1 min-w-[300px]">
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
          <div className="flex items-center gap-2 px-2.5 py-1 bg-gray-50 border border-gray-100 rounded-lg text-[9px] font-black text-gray-600">
            <span className="text-gray-400">VIEW:</span>
            <select 
               value={selectedVersionId ?? ''}
               onChange={(e) => { setSelectedVersionId(e.target.value); setTablePage(1); }}
               className="bg-transparent border-none outline-none cursor-pointer text-gray-900 pr-1 text-[9px] font-black"
            >
               {versions.map(v => (
                  <option key={v.id} value={v.id}>
                     {v.type === 'baseline' ? (v.name || 'Project') : v.data_date}
                  </option>
               ))}
            </select>
          </div>
          <div className="relative w-52">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
            <input 
              type="text"
              placeholder="Search..."
              value={tableSearch}
              onChange={(e) => { setTableSearch(e.target.value); setTablePage(1); }}
              className="w-full pl-8 pr-3 py-1 bg-gray-50 border border-gray-100 rounded-lg text-[10px] font-medium focus:ring-2 focus:ring-blue-500/10 outline-none transition-all focus:bg-white"
            />
          </div>
        </div>

        {/* Zone 3: AI Assistant Toggle */}
        <div className="flex shrink-0">
          <button 
            onClick={() => setIsControllerChatOpen(!isControllerChatOpen)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-xl font-black text-[10px] uppercase tracking-widest transition-all ${isControllerChatOpen ? 'bg-gray-900 text-white shadow-xl translate-y-0.5' : 'bg-blue-600 text-white hover:bg-blue-700 shadow-lg shadow-blue-500/20'}`}
          >
            {isControllerChatOpen ? <X size={14} /> : <Zap size={14} />}
            <span>{isControllerChatOpen ? 'Assistant' : 'Ask AI'}</span>
          </button>
        </div>
      </div>

      {viewerTable === 'TASK' && tableData?.projectAnalysis && (
        <div className="px-8 py-2 border-b border-gray-100 bg-gray-50/50 flex flex-col gap-1.5">
          {/* Sub-row 1: Variance + KPIs + Delay Breakdown */}
          <div className="flex items-center gap-3 flex-wrap">
            {/* Project Variance */}
            <div className="flex items-center gap-2 px-3 py-1 bg-white rounded-lg border border-gray-200 shadow-sm shrink-0">
              <span className="text-[9px] font-black text-gray-400 uppercase tracking-wider">Variance:</span>
              <span className={`text-[12px] font-black ${tableData.projectAnalysis.projectDelayDays > 0 ? 'text-red-600' : 'text-green-600'}`}>
                {tableData.projectAnalysis.projectDelayDays ?? 0} DAYS
              </span>
              {tableData.projectAnalysis.healthMetrics?.isConstrained && (
                <span className="text-[8px] font-black text-red-700 bg-red-50 px-1.5 py-0.5 rounded border border-red-100 animate-pulse">
                  CONSTRAINED
                </span>
              )}
            </div>

            {/* KPI Chips */}
            <div className="flex flex-wrap gap-1.5 items-center text-[9px] font-bold uppercase tracking-wider">
              <span className="flex items-center gap-1 px-2 py-0.5 bg-green-50 border border-green-100 rounded text-green-700"><CheckCircle size={10} /> {tableData.projectAnalysis.healthMetrics?.completedTasks} Completed</span>
              <span className="flex items-center gap-1 px-2 py-0.5 bg-blue-50 border border-blue-100 rounded text-blue-700"><Loader2 size={10} /> {tableData.projectAnalysis.healthMetrics?.inProgressTasks} In Progress</span>
              <span className="flex items-center gap-1 px-2 py-0.5 bg-orange-50 border border-orange-100 rounded text-orange-700"><AlertTriangle size={10} /> {tableData.projectAnalysis.healthMetrics?.executionDelayedCount} Delayed</span>
              <span className="flex items-center gap-1 px-2 py-0.5 bg-red-50 border border-red-100 rounded text-red-700"><AlertTriangle size={10} /> {tableData.projectAnalysis.healthMetrics?.criticalCount} Critical</span>
              <span className="flex items-center gap-1 px-2 py-0.5 bg-amber-50 border border-amber-100 rounded text-amber-700"><AlertTriangle size={10} /> {tableData.projectAnalysis.healthMetrics?.atRiskCount} At Risk</span>
              <span className="flex items-center gap-1 px-2 py-0.5 bg-yellow-50 border border-yellow-100 rounded text-yellow-700"><AlertTriangle size={10} /> {tableData.projectAnalysis.healthMetrics?.watchingCount} Watching</span>
            </div>

            {/* Delay Breakdown */}
            <div className="flex items-center gap-1.5 ml-auto shrink-0">
              <span className="text-[8px] font-black text-gray-400 uppercase mr-1">Delay:</span>
              <div className="flex rounded-md overflow-hidden border border-gray-100 shadow-sm bg-white">
                <div className="px-2 py-1 bg-green-50 text-green-700 flex flex-col items-center min-w-[60px] border-r border-gray-100">
                  <span className="text-[11px] font-black leading-none">{tableData.projectAnalysis.delayFloatMatrix?.delayed_safe}</span>
                  <span className="text-[6px] font-bold uppercase opacity-60 mt-0.5 whitespace-nowrap">Positive Float</span>
                </div>
                <div className="px-2 py-1 bg-red-50 text-red-600 flex flex-col items-center min-w-[60px] border-r border-gray-100">
                  <span className="text-[11px] font-black leading-none">{tableData.projectAnalysis.delayFloatMatrix?.delayed_critical}</span>
                  <span className="text-[6px] font-bold uppercase opacity-60 mt-0.5 whitespace-nowrap">Zero Float</span>
                </div>
                <div className="px-2 py-1 bg-red-900 text-white flex flex-col items-center min-w-[60px]">
                  <span className="text-[11px] font-black leading-none">{tableData.projectAnalysis.delayFloatMatrix?.delayed_negative}</span>
                  <span className="text-[6px] font-bold uppercase opacity-60 mt-0.5 whitespace-nowrap">Negative Float</span>
                </div>
              </div>
            </div>
          </div>

          {/* Sub-row 2: Filters (left) + EVM Toggle (right) */}
          <div className="flex items-center justify-between gap-3">
            <div className="flex gap-1">
              {[
                { id: 'ALL', label: 'All', color: 'border-gray-200 text-gray-600' },
                { id: 'CRITICAL', label: 'Crit', color: 'border-red-200 text-red-600 bg-red-50/30' },
                { id: 'NEG_FLOAT', label: 'Neg', color: 'border-red-400 text-red-800 bg-red-100/50' },
                { id: 'DELAYED', label: 'Del', color: 'border-orange-200 text-orange-700 bg-orange-50/50' },
                { id: 'AT_RISK', label: 'Risk', color: 'border-amber-200 text-amber-700 bg-amber-50/50' },
                { id: 'WATCHING', label: 'Watch', color: 'border-yellow-200 text-yellow-700 bg-yellow-50/50' }
              ].map(f => (
                <button 
                  key={f.id}
                  onClick={() => { setViewerFilter(f.id); setTablePage(1); }}
                  className={`px-2.5 py-1 rounded-md text-[9px] font-black uppercase tracking-tighter border transition-all ${viewerFilter === f.id ? f.color + ' ring-2 ring-offset-1 focus:ring-blue-500' : 'bg-white border-gray-100 text-gray-400 hover:border-gray-300'}`}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <div className="flex bg-gray-100/80 p-0.5 rounded-md border border-gray-200/60 shadow-sm shrink-0">
              <button
                onClick={() => setEvmMethodology('COST')}
                className={`px-3 py-1 text-[9px] font-black tracking-wide uppercase rounded transition-all ${evmMethodology === 'COST' ? 'bg-white shadow-sm text-blue-700 border border-gray-200/50' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200/50'}`}
              >
                Cost EVM
              </button>
              <button
                onClick={() => setEvmMethodology('LABOR')}
                className={`px-3 py-1 text-[9px] font-black tracking-wide uppercase rounded transition-all ${evmMethodology === 'LABOR' ? 'bg-white shadow-sm text-blue-700 border border-gray-200/50' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200/50'}`}
              >
                Labor EVM
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ControllerToolbar;
