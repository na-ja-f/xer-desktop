import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CheckCircle, XCircle, AlertTriangle, Zap, Activity, ChevronRight, ArrowRight } from 'lucide-react';
import ViewAllModal from './ViewAllModal';

// ── Helpers ───────────────────────────────────────────────────────────────────
const safeStr = (v) => {
  if (v === null || v === undefined) return '';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
};

const StatusBadge = ({ status, content }) => {
  if (!status) return null;
  let s = String(status).toUpperCase();
  
  // SPECIAL CASE: If only project boundaries (1 start, 1 finish), force SUCCESS/PASS
  if (content?.stats?.open_start_count === 1 && content?.stats?.open_finish_count === 1) {
    s = 'SUCCESS';
  }

  const cfg = {
    PASS:    { cls: 'bg-green-100 text-green-700 border-green-200',    icon: <CheckCircle size={11} />, label: 'OK' },
    SUCCESS: { cls: 'bg-green-100 text-green-700 border-green-200',    icon: <CheckCircle size={11} />, label: 'OK' },
    WARNING: { cls: 'bg-amber-100 text-amber-700 border-amber-200',    icon: <AlertTriangle size={11} />, label: 'WARNING' },
    FAIL:    { cls: 'bg-red-100 text-red-700 border-red-200',          icon: <XCircle size={11} />, label: 'ERROR' },
    ERROR:   { cls: 'bg-red-100 text-red-700 border-red-200',          icon: <XCircle size={11} />, label: 'ERROR' },
  };
  const badge = cfg[s];
  if (!badge) return null;
  
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border shadow-sm ${badge.cls}`}>
      {badge.icon}{badge.label}
    </span>
  );
};

// ── Template Renderers ────────────────────────────────────────────────────────

const RESPONSE_LABELS = {
  get_project_summary: "Project Summary",
  get_project_metrics: "Project Summary",
  get_critical_path: "Critical Path Analysis",
  get_critical_activities: "Critical Path Analysis",
  get_delayed_activities: "Delayed Activities",
  get_negative_float_activities: "Negative Float Analysis",
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

function ListTemplate({ content }) {
  const [modalOpen, setModalOpen] = useState(false);
  const metrics = content.metrics || {};
  const insights = content.insights || [];
  const recs = content.recommendations || [];

  return (
    <div className="flex flex-col gap-4">
      {/* Truncation Banner */}
      {content.is_truncated && (
        <div className="flex items-center justify-between px-4 py-2.5 bg-blue-50 border border-blue-100 rounded-2xl">
          <div className="flex items-center gap-2">
            <Activity size={12} className="text-blue-500 animate-pulse" />
            <span className="text-xs font-black text-blue-700 uppercase tracking-widest">
              Showing {content.displayed_count} of {content.total_count} activities
            </span>
          </div>
          <button
            onClick={() => setModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1 bg-blue-600 text-white text-[10px] font-black uppercase tracking-widest rounded-xl hover:bg-blue-700 transition-colors shadow-sm">
            View All <ArrowRight size={10} />
          </button>
        </div>
      )}

      {/* Summary (Markdown with tables) */}
      <div className="text-sm text-gray-800 font-medium leading-relaxed markdown-table-content">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content.summary || ''}</ReactMarkdown>
      </div>

      {/* Render Display Items in Chat directly */}
      {content.display_items && content.display_items.length > 0 && (
        <div className="mt-2 space-y-2">
          {content.display_items.map((item, idx) => {
            const itemName = item.name || item.task_name || item.discipline || null;
            const label = content.display_title || itemName || RESPONSE_LABELS[content.type] || null;
            const isWbsPathKey = (key) => {
              const norm = key.toLowerCase().replace(/_/g, '').replace(/\s+/g, '');
              return norm === 'wbspath' || norm === 'wbspath:';
            };
            
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
                    
                    let displayVal = String(v);
                    if (k === 'delay_days' && (v === null || v === undefined)) {
                      displayVal = "N/A (requires update file)";
                    } else if (v === null || v === undefined || typeof v === 'object') {
                      return null;
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

      {/* Metrics Grid - Hidden for activity detail responses to avoid redundant/inconsistent tiles */}
      {Object.keys(metrics).length > 0 && !['get_activity_details', 'analyze_activity_delay', 'get_project_summary', 'get_project_metrics'].includes(content.type) && !(content.display_items && content.display_items.length > 0) && (
        <div className="grid grid-cols-2 gap-2.5">
          {Object.entries(metrics).map(([k, v]) => (
            <div key={k} className="bg-blue-50 border border-blue-100 p-3 rounded-xl">
              <div className="text-[9px] text-blue-500 font-black uppercase tracking-widest mb-1">
                {k.replace(/([A-Z])/g, ' $1').trim()}
              </div>
              <div className="text-lg font-black text-blue-900">{safeStr(v)}</div>
            </div>
          ))}
        </div>
      )}

      {/* Suggestions */}
      {content.suggestions && content.suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-1">
          {content.suggestions.map((s, i) => (
            <span key={i} className="px-3 py-1 bg-gray-100 border border-gray-200 text-xs font-semibold text-gray-700 rounded-full cursor-pointer hover:bg-blue-50 hover:border-blue-200 hover:text-blue-700 transition-colors">
              {s}
            </span>
          ))}
        </div>
      )}

      {/* Insights */}
      {insights.length > 0 && (
        <div className="bg-gray-50 rounded-xl border border-gray-100 p-4">
          <p className="text-[9px] font-black text-gray-400 uppercase tracking-widest mb-3 flex items-center gap-1.5">
            <Activity size={11} /> Key Insights
          </p>
          <div className="space-y-3">
            {insights.map((ins, i) => {
              const str = safeStr(ins);
              const match = str.match(/^\[(.*?)\]\s*(.*)/);
              if (match) {
                const [_, label, text] = match;
                const labelColors = {
                  FINDING: "text-blue-600 bg-blue-50 border-blue-100",
                  INTERPRETATION: "text-purple-600 bg-purple-50 border-purple-100",
                  "PRIMAVERA CONTEXT": "text-green-600 bg-green-50 border-green-100",
                  IMPACT: "text-red-600 bg-red-50 border-red-100",
                  RECOMMENDATION: "text-amber-600 bg-amber-50 border-amber-100"
                };
                const colorClass = labelColors[label] || "text-gray-600 bg-gray-50 border-gray-100";
                
                return (
                  <div key={i} className="flex flex-col gap-1.5 p-3 bg-white border border-gray-100 rounded-xl shadow-sm">
                    <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-md border w-fit ${colorClass}`}>
                      {label}
                    </span>
                    <span className="text-sm text-gray-700 leading-relaxed font-medium">{text}</span>
                  </div>
                );
              }
              return (
                <div key={i} className="flex gap-2.5 text-sm text-gray-700 bg-white border border-gray-100 p-3 rounded-xl shadow-sm">
                  <CheckCircle size={14} className="text-green-500 mt-0.5 flex-shrink-0" />
                  <span className="leading-snug">{str}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {recs.length > 0 && (
        <div className="space-y-2">
          <p className="text-[9px] font-black text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
            <Zap size={11} className="text-amber-500" /> Recommendations
          </p>
          {recs.map((r, i) => (
            <div key={i} className="flex gap-2.5 px-3 py-2.5 bg-amber-50 border border-amber-100 rounded-xl text-xs font-semibold text-amber-800 leading-relaxed">
              <Zap size={10} className="text-amber-500 mt-0.5 flex-shrink-0" />
              {safeStr(r)}
            </div>
          ))}
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

function IntegrityTemplate({ content }) {
  const stats = (content.data || [])[0] || {};
  const summary_stats = content.stats || {};
  const logicStatus = content.status || summary_stats.logic_status || stats.logic_status;
  const openStarts = summary_stats.open_start_names || [];
  const openFinishes = summary_stats.open_finish_names || [];
  const insights = content.insights || [];
  const recs = content.recommendations || [];

  return (
    <div className="flex flex-col gap-4">
      {/* Header with Title and Status */}
      <div className="flex flex-col gap-3 p-5 bg-gray-50 rounded-2xl border border-gray-100">
        <div className="flex justify-between items-center">
          <h4 className="text-xs font-black text-gray-400 uppercase tracking-widest flex items-center gap-2">
            <Activity size={12} className="text-blue-500" />
            {RESPONSE_LABELS[content.type] || "Integrity Analysis"}
          </h4>
          <StatusBadge status={logicStatus} content={content} />
        </div>
        <div className="text-sm font-semibold text-gray-800 leading-relaxed pt-2 border-t border-gray-200/50">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content.summary || ''}</ReactMarkdown>
        </div>
      </div>

      {/* Metrics Grid (Prioritized for Open Ends) */}
      {content.metrics && Object.keys(content.metrics).length > 0 && (
        <div className="grid grid-cols-2 gap-3">
          {Object.entries(content.metrics).map(([k, v]) => (
            <div key={k} className="bg-blue-50 border border-blue-100 p-4 rounded-2xl shadow-sm">
              <div className="text-[10px] font-black text-blue-500 uppercase tracking-widest mb-1">{k.replace(/([A-Z])/g, ' $1').trim()}</div>
              <div className="text-2xl font-black text-blue-900 leading-none">{safeStr(v)}</div>
            </div>
          ))}
        </div>
      )}

      {/* Detailed Activity Lists for Open Ends */}
      {(openStarts.length > 0 || openFinishes.length > 0) && (
        <div className="grid grid-cols-1 gap-3">
          {openStarts.length > 0 && (
            <div className="p-4 bg-white border border-gray-100 rounded-2xl shadow-sm">
              <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                <ChevronRight size={12} className="text-blue-500" /> Open Starts ({openStarts.length})
              </p>
              <div className="space-y-2">
                {openStarts.map((n, i) => (
                  <div key={i} className="px-3 py-2 bg-gray-50 rounded-xl text-xs font-bold text-gray-700 border border-gray-100 flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                    <span className="truncate">{n}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {openFinishes.length > 0 && (
            <div className="p-4 bg-white border border-gray-100 rounded-2xl shadow-sm">
              <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                <ChevronRight size={12} className="text-green-500" /> Open Finishes ({openFinishes.length})
              </p>
              <div className="space-y-2">
                {openFinishes.map((n, i) => (
                  <div key={i} className="px-3 py-2 bg-gray-50 rounded-xl text-xs font-bold text-gray-700 border border-gray-100 flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-400" />
                    <span className="truncate">{n}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Structured Insights (FINDING, INTERPRETATION, etc.) */}
      {insights.length > 0 && (
        <div className="space-y-3 mt-1">
          {insights.map((ins, i) => {
            const str = safeStr(ins);
            const match = str.match(/^\[(.*?)\]\s*(.*)/);
            if (match) {
              const [_, label, text] = match;
              const labelColors = {
                FINDING: "text-blue-600 bg-blue-50 border-blue-100",
                INTERPRETATION: "text-purple-600 bg-purple-50 border-purple-100",
                "PRIMAVERA CONTEXT": "text-green-600 bg-green-50 border-green-100",
                IMPACT: "text-red-600 bg-red-50 border-red-100",
                RECOMMENDATION: "text-amber-600 bg-amber-50 border-amber-100"
              };
              const colorClass = labelColors[label] || "text-gray-600 bg-gray-50 border-gray-100";
              
              return (
                <div key={i} className="flex flex-col gap-2 p-4 bg-white border border-gray-100 rounded-2xl shadow-sm ring-1 ring-black/[0.02]">
                  <span className={`text-[9px] font-black uppercase tracking-widest px-2.5 py-1 rounded-lg border w-fit shadow-xs ${colorClass}`}>
                    {label}
                  </span>
                  <span className="text-[13px] text-gray-700 leading-relaxed font-semibold">{text}</span>
                </div>
              );
            }
            return (
              <div key={i} className="flex gap-3 text-sm text-gray-700 bg-white border border-gray-100 p-4 rounded-2xl shadow-sm">
                <CheckCircle size={16} className="text-green-500 mt-0.5 flex-shrink-0" />
                <span className="font-medium">{str}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Recommendations */}
      {recs.length > 0 && (
        <div className="space-y-2 mt-2">
          {recs.map((r, i) => (
            <div key={i} className="flex gap-3 px-4 py-3 bg-amber-50 border border-amber-100 rounded-2xl text-[13px] font-bold text-amber-800 leading-relaxed shadow-sm">
              <Zap size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
              {safeStr(r)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ClarifyTemplate({ content }) {
  const recs = content.recommendations || [];
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-gray-700 font-medium leading-relaxed">{content.summary}</p>
      {(content.insights || []).map((ins, i) => (
        <p key={i} className="text-sm text-gray-600 italic">{safeStr(ins)}</p>
      ))}
      {recs.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-1">
          {recs.map((r, i) => (
            <span key={i} className="px-3 py-1.5 bg-blue-50 border border-blue-100 text-xs font-bold text-blue-700 rounded-xl cursor-pointer hover:bg-blue-100 transition-colors">
              {safeStr(r)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function KnowledgeTemplate({ content }) {
  const insights = content.insights || [];
  return (
    <div className="flex flex-col gap-4">
      <div className="text-sm text-gray-800 font-medium leading-relaxed markdown-table-content">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content.summary || ''}</ReactMarkdown>
      </div>
      {insights.length > 0 && (
        <div className="space-y-2 mt-2">
          {insights.map((ins, i) => (
            <div key={i} className="flex gap-2.5 text-sm text-gray-600 italic border-l-2 border-blue-100 pl-4">
              <span>{safeStr(ins)}</span>
            </div>
          ))}
        </div>
      )}
      {(content.recommendations || []).length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {content.recommendations.map((r, i) => (
            <div key={i} className="px-3 py-1 bg-gray-50 border border-gray-200 text-[10px] font-black uppercase tracking-widest text-gray-400 rounded-lg">
              {safeStr(r)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DefaultTemplate({ content }) {
  return <ListTemplate content={content} />;
}

// ── Main Export ───────────────────────────────────────────────────────────────
export default function ChatMessage({ content }) {
  if (typeof content === 'string') {
    return (
      <div className="text-sm text-gray-800 leading-relaxed markdown-table-content">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    );
  }
  if (!content || typeof content !== 'object') return null;

  const tmpl = content.template_type || 'list';

  if (tmpl === 'integrity') return <IntegrityTemplate content={content} />;
  if (tmpl === 'clarify')   return <ClarifyTemplate content={content} />;
  if (tmpl === 'knowledge') return <KnowledgeTemplate content={content} />;
  // list, activity, analysis, health all use the rich list template
  return <ListTemplate content={content} />;
}
