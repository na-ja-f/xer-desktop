import React, { useState } from 'react';

// Safely render any value that might be a non-primitive (object/array) from the LLM
const safeStr = (v) => {
  if (v === null || v === undefined) return '';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
};
import { Zap, Minimize2, Maximize2, X, Cpu, Loader2, ArrowRight, Activity } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import OptimizedChatInput from '../OptimizedChatInput';
import ViewAllModal from '../chat/ViewAllModal';

const RESPONSE_LABELS = {
  get_project_summary: "Project Summary",
  get_project_metrics: "Project Summary",
  get_critical_path: "Critical Path Analysis",
  get_critical_activities: "Critical Path Analysis",
  get_delayed_activities: "Delayed Activities",
  get_negative_float_activities: "Negative Float Analysis",
  get_positive_float_activities: "Positive Float Analysis",
  check_integrity: "Logic Integrity Check",
  check_open_ends: "Open Ends Analysis",
  check_open_ended_tasks: "Open Ends Analysis",
  check_constraints: "Constraints Analysis",
  check_circular_dependencies: "Circular Dependencies",
  check_path_continuity: "Path Continuity",
  check_critical_path_continuity: "Path Continuity",
  get_project_health: "Project Health Assessment",
  get_wbs_summary: "WBS Summary",
  analyze_activity_delay: "Activity Delay Analysis",
  get_activity_details: "Activity Details",
  capability_gap: "Feature Not Available",
  clarify: "System Request"
};

// Sub-component for each assistant message — has its own modal state
function ControllerAssistantMessage({ content }) {
  const [modalOpen, setModalOpen] = useState(false);

  const isWbsPathKey = (key) => {
    const norm = key.toLowerCase().replace(/_/g, '').replace(/\s+/g, '');
    return norm === 'wbspath' || norm === 'wbspath:';
  };

  return (
    <div className="ai-structured-response flex flex-col gap-4 w-full">
      {/* Truncation Banner with View All */}
      {content.is_truncated && (
        <div className="flex items-center justify-between px-3 py-2 bg-blue-50 border border-blue-100 rounded-2xl">
          <div className="flex items-center gap-2">
            <Activity size={12} className="text-blue-500 animate-pulse" />
            <span className="text-[9px] font-black text-blue-700 uppercase tracking-widest">
              Showing {content.displayed_count || content.display_items?.length} of {content.total_count} activities
              {content.stats?.total_project_activities ? ` (${((content.total_count / content.stats.total_project_activities) * 100).toFixed(1)}% of project)` : ''}
            </span>
          </div>
          <button
            onClick={() => setModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1 bg-blue-600 text-white text-[9px] font-black uppercase tracking-widest rounded-xl hover:bg-blue-700 transition-colors shadow-sm">
            View All <ArrowRight size={10} />
          </button>
        </div>
      )}

      <div className="summary text-gray-800 font-medium leading-relaxed markdown-table-content">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content.summary || ''}</ReactMarkdown>
      </div>
      
      {/* Render Display Items directly */}
      {content.display_items && content.display_items.length > 0 && (
        <div className="mt-2 space-y-2">
          {content.display_items.map((item, idx) => {
            const itemName = item.name || item.task_name || item.discipline || null;
            const label = content.display_title || itemName || RESPONSE_LABELS[content.type] || null;
            return (
              <div key={idx} className="p-3 bg-white border border-gray-100 rounded-xl shadow-sm text-xs flex flex-col gap-1">
                {label && (
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-bold text-gray-800 break-words pr-2">{label}</span>
                    {item.id && <span className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded flex-shrink-0 font-mono">{item.code || item.id}</span>}
                  </div>
                )}
                <div className="flex flex-wrap gap-2 text-[10px] mt-1 font-medium text-gray-500">
                  {Object.entries(item).map(([k, v]) => {
                    if (['id', 'code', 'name', 'task_name', 'discipline'].includes(k) || isWbsPathKey(k)) return null;
                    if (v === null || v === undefined || typeof v === 'object') return null;
                    
                    let displayVal = String(v);
                    if (k === 'delay_days' && (v === null || v === undefined)) {
                      displayVal = "N/A (requires update file)";
                    }
                    
                    let labelText = k.replace(/_/g, ' ');
                    const overrides = {
                      'wbs': 'WBS',
                      'wbs_id': 'WBS ID',
                      'wbs_path': 'WBS Path',
                      'float_hrs': 'Float Hrs',
                      'delay_days': 'Delay Days',
                      'is_critical': 'Is Critical'
                    };
                    if (overrides[k]) {
                      labelText = overrides[k];
                    } else {
                      labelText = labelText.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
                    }
                    
                    return (
                      <span key={k} className="bg-gray-50 border border-gray-100 px-2 py-0.5 rounded-md">
                        <span className="text-gray-400 mr-1">{labelText}:</span>
                        <span className="text-gray-700">{displayVal}</span>
                      </span>
                    );
                  })}
                </div>
                {(() => {
                  const wbsEntry = Object.entries(item).find(([k]) => isWbsPathKey(k));
                  if (wbsEntry && wbsEntry[1]) {
                    return (
                      <div className="text-[10px] mt-2 pt-2 border-t border-gray-100/60 text-gray-500 font-medium">
                        <span className="text-gray-400 mr-1.5 font-bold">WBS Path:</span>
                        <span className="text-gray-700 font-semibold break-all bg-gray-50/50 px-2 py-1 rounded border border-gray-100/50 inline-block w-full">{String(wbsEntry[1])}</span>
                      </div>
                    );
                  }
                  return null;
                })()}
              </div>
            )})}
        </div>
      )}
      
      {content.metrics && Object.keys(content.metrics).length > 0 && !['get_activity_details', 'analyze_activity_delay', 'get_project_summary', 'get_project_metrics'].includes(content.type) && !(content.display_items && content.display_items.length > 0) && (
        <div className="grid grid-cols-2 gap-3 mt-1">
          {Object.entries(content.metrics).map(([k, v]) => (
            <div key={k} className="bg-blue-50 border border-blue-100/50 p-3 rounded-xl shadow-sm">
              <div className="text-[10px] text-blue-500 font-black uppercase tracking-widest mb-1">
                {k.replace(/([A-Z])/g, ' $1').trim()}
              </div>
              <div className="text-xl font-black text-blue-900">{safeStr(v)}</div>
            </div>
          ))}
        </div>
      )}

      {(content.recommendations || content.drivers) && (content.recommendations || content.drivers).length > 0 && (
        <div className="recommendations mt-2">
          <div className="text-[10px] text-gray-400 font-black uppercase tracking-widest mb-2 flex items-center gap-1.5">
            <Zap size={12} className="text-amber-500"/> Strategic Recommendations
          </div>
          <div className="space-y-2 mt-2">
            {(content.recommendations || content.drivers).map((rec, idx) => (
              <div key={idx} className="flex gap-2.5 px-3 py-2.5 bg-amber-50/50 text-amber-800 border border-amber-100/50 rounded-xl text-xs font-semibold shadow-sm leading-relaxed">
                <div className="mt-1 shrink-0"><Zap size={10} className="text-amber-500" /></div>
                {safeStr(rec)}
              </div>
            ))}
          </div>
        </div>
      )}

      <ViewAllModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={content.summary?.split('\n')[0]?.replace(/[#*]/g, '').trim() || 'Activities'}
        data={content.all_items || []}
        dataRef={content.data_ref}
        totalCount={content.total_count || 0}
        displayedCount={content.displayed_count || 0}
      />
    </div>
  );
}

const ControllerFloatingChat = ({
  controllerChatPos,
  isDragging,
  isControllerChatExpanded,
  isControllerChatOpen,
  handleDragStart,
  setIsControllerChatExpanded,
  setIsControllerChatOpen,
  controllerMessages,
  isControllerTyping,
  controllerChatEndRef,
  handleControllerAsk,
  chatContainerRef
}) => {
  if (!isControllerChatOpen) return null;

  return (
    <div 
      ref={chatContainerRef}
      style={{ transform: `translate(${controllerChatPos.x}px, ${controllerChatPos.y}px)` }}
      className={`fixed bottom-8 right-8 z-[100] flex flex-col items-end gap-4 ${isDragging ? '' : 'transition-all duration-500 ease-out'} ${isControllerChatExpanded ? 'w-[800px] h-[85vh]' : 'w-[400px] h-[600px]'}`}
    >
      <div className="w-full h-full bg-white rounded-[2rem] shadow-2xl border border-gray-100 flex flex-col overflow-hidden animate-in slide-in-from-bottom-8 fade-in duration-300">
        {/* Header - Drag Handle */}
        <div 
          onMouseDown={handleDragStart}
          className="p-6 bg-gray-900 flex items-center justify-between cursor-move select-none"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500 rounded-xl shadow-lg shadow-blue-500/20">
              <Zap size={18} className="text-white" />
            </div>
            <div>
              <h4 className="text-sm font-black text-white uppercase tracking-widest">Controller Intelligence</h4>
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></div>
                <span className="text-[10px] font-bold text-gray-400">Context: Table Analytics</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button 
              onClick={() => setIsControllerChatExpanded(!isControllerChatExpanded)}
              className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-all"
              title={isControllerChatExpanded ? "Collapse Chat" : "Expand Chat"}
            >
              {isControllerChatExpanded ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
            </button>
            <button 
              onClick={() => setIsControllerChatOpen(false)}
              className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-all"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar bg-gray-50/30">
          {controllerMessages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center px-4 space-y-4">
              <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center">
                <Cpu size={32} className="text-blue-500 opacity-40" />
              </div>
              <p className="text-xs font-bold text-gray-400 uppercase tracking-widest leading-relaxed">
                Ask about planned dates, comparisons,<br/>or negative float drivers in this view.
              </p>
            </div>
          ) : (
            controllerMessages.map((m, i) => (
              <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
                <div className={`max-w-[90%] rounded-[1.5rem] px-5 py-4 text-sm shadow-sm transition-all ${
                  m.role === 'user' 
                    ? 'bg-blue-600 text-white rounded-tr-none' 
                    : 'bg-white text-gray-800 border border-gray-100 rounded-tl-none ring-1 ring-black/5'
                }`}>
                  {m.role === 'assistant' ? (
                      typeof m.content === 'object' && m.content !== null ? (
                        <ControllerAssistantMessage content={m.content} />
                      ) : (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{String(m.content)}</ReactMarkdown>
                      )
                  ) : (
                      <p className="leading-relaxed font-medium">{m.content}</p>
                  )}
                </div>
              </div>
            ))
          )}
          {isControllerTyping && (
            <div className="flex items-start gap-3">
              <div className="p-3 bg-white border border-gray-100 rounded-2xl rounded-tl-none shadow-sm">
                <Loader2 size={16} className="text-blue-500 animate-spin" />
              </div>
            </div>
          )}
          <div ref={controllerChatEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-6 bg-white border-t border-gray-100">
          <OptimizedChatInput 
            placeholder="Ask anything about this project..."
            isTyping={isControllerTyping}
            onSubmit={handleControllerAsk}
            className="w-full pl-6 pr-14 py-4 bg-gray-50 border border-gray-100 rounded-2xl text-sm focus:ring-2 focus:ring-blue-500/20 outline-none transition-all placeholder:text-gray-400 font-medium"
            buttonClassName="absolute right-2 p-2.5 bg-blue-600 text-white rounded-xl shadow-lg shadow-blue-500/20 hover:scale-105 active:scale-95 disabled:opacity-20 disabled:scale-100 transition-all"
          />
        </div>
      </div>
    </div>
  );
};

export default ControllerFloatingChat;
