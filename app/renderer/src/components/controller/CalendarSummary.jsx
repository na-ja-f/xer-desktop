import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { Calendar, ChevronDown, ChevronRight, Search, RefreshCw, AlertTriangle, List, CheckCircle, XCircle } from 'lucide-react';

const BASE = 'http://127.0.0.1:8000';

const CalendarRow = ({ cal }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [showHistorical, setShowHistorical] = useState(false);

  return (
    <div className="flex flex-col bg-white border-b border-gray-100 last:border-b-0">
      <div 
        className="flex items-center py-3 px-4 cursor-pointer hover:bg-gray-50 transition-colors group"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="w-8 shrink-0 text-gray-400 group-hover:text-blue-500">
          {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </div>
        <div className="w-1/3 shrink-0 pr-4">
          <div className="flex items-center gap-2">
            <span className="font-bold text-gray-900 text-[12px]">{cal.name}</span>
            {cal.is_project_default && (
              <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-700 text-[8px] font-black uppercase tracking-wider border border-blue-200">
                Default
              </span>
            )}
          </div>
        </div>
        <div className="w-32 shrink-0 text-[11px] font-semibold text-gray-600">
          {cal.workweek_type || 'Unknown'}
        </div>
        <div className="w-32 shrink-0 text-[11px] font-mono font-medium text-gray-700">
          {cal.hours_per_day ? `${cal.hours_per_day} hrs/day` : '-'}
        </div>
        <div className="w-40 shrink-0 flex items-center gap-2">
          <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 text-[10px] font-bold">
            {cal.effective_non_working_dates_count !== undefined ? cal.effective_non_working_dates_count : cal.non_working_exceptions_count} Non-Working
          </span>
        </div>
        <div className="w-40 shrink-0 flex items-center gap-2">
          <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-bold">
            {cal.effective_working_overrides_count !== undefined ? cal.effective_working_overrides_count : cal.working_exceptions_count} Overrides
          </span>
        </div>
      </div>

      {isOpen && (
        <div className="bg-gray-50 p-4 border-t border-gray-100 shadow-inner grid grid-cols-3 gap-4">
          
          {/* Workweek Pattern */}
          <div className="bg-white p-3 rounded-xl border border-gray-200 shadow-sm">
            <div className="mb-3 border-b border-gray-100 pb-2">
              <h4 
                className="flex items-center gap-2 text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1 cursor-help"
                title="The standard 7-day weekly work pattern defined in Primavera P6 for this calendar."
              >
                <Calendar size={14} className="text-blue-500" />
                Workweek Pattern
              </h4>
              <p className="text-[9px] text-gray-400 italic">Standard working days per week.</p>
            </div>
            {cal.workweek_pattern ? (
              <div className="flex flex-col gap-1">
                {Object.entries(cal.workweek_pattern).map(([day, isWorking]) => (
                  <div key={day} className="flex items-center justify-between py-1 px-2 rounded hover:bg-gray-50 transition-colors">
                    <span className="text-[10px] font-semibold text-gray-700">{day}</span>
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${isWorking ? 'bg-blue-50 text-blue-700 border border-blue-100' : 'bg-gray-100 text-gray-500 border border-gray-200'}`}>
                      {isWorking ? 'Working' : 'Non-working'}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <span className="text-[10px] italic text-gray-400">Standard pattern not available</span>
            )}
          </div>

          {/* Non-working Exceptions / Holidays */}
          <div className="bg-white p-3 rounded-xl border border-gray-200 shadow-sm">
            <div className="mb-3 border-b border-gray-100 pb-2 flex justify-between items-start">
              <div>
                <h4 
                  className="flex items-center gap-2 text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1 cursor-help"
                  title="Dates explicitly marked as non-working."
                >
                  <XCircle size={14} className="text-amber-500" />
                  Non-Working Dates
                </h4>
                <p className="text-[9px] text-gray-400 italic">
                  {showHistorical ? 'Showing all historical dates.' : `Showing dates within project period (${cal.project_start || '?' } to ${cal.project_finish || '?'}).`}
                </p>
              </div>
              <button 
                onClick={() => setShowHistorical(!showHistorical)}
                className="text-[9px] text-blue-500 hover:underline"
              >
                {showHistorical ? 'Hide historical' : 'Show historical'}
              </button>
            </div>
            {(() => {
              const dates = showHistorical ? cal.raw_non_working_dates : cal.effective_non_working_dates;
              const displayDates = dates || cal.non_working_exceptions;
              if (displayDates && displayDates.length > 0) {
                return (
                  <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto pr-2 custom-scrollbar">
                    {displayDates.map((date, idx) => {
                      const d = new Date(date.split('-')[0], parseInt(date.split('-')[1]) - 1, date.split('-')[2]);
                      const formatted = isNaN(d.getTime()) ? date : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
                      return (
                        <span key={idx} className="px-2 py-1 bg-amber-50/50 border border-amber-100 rounded text-[10px] font-mono text-amber-800">
                          {formatted}
                        </span>
                      );
                    })}
                  </div>
                );
              }
              return <span className="text-[10px] italic text-gray-400">No non-working dates defined</span>;
            })()}
          </div>

          {/* Working Exceptions */}
          <div className="bg-white p-3 rounded-xl border border-gray-200 shadow-sm">
            <div className="mb-3 border-b border-gray-100 pb-2 flex justify-between items-start">
              <div>
                <h4 
                  className="flex items-center gap-2 text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1 cursor-help"
                  title="Dates that would normally be non-working but were intentionally made working."
                >
                  <CheckCircle size={14} className="text-emerald-500" />
                  Working Overrides
                </h4>
                <p className="text-[9px] text-gray-400 italic">
                  {showHistorical ? 'Showing all historical dates.' : `Showing dates within project period (${cal.project_start || '?' } to ${cal.project_finish || '?'}).`}
                </p>
              </div>
              <button 
                onClick={() => setShowHistorical(!showHistorical)}
                className="text-[9px] text-blue-500 hover:underline"
              >
                {showHistorical ? 'Hide historical' : 'Show historical'}
              </button>
            </div>
            {(() => {
              const dates = showHistorical ? cal.raw_working_overrides : cal.effective_working_overrides;
              const displayDates = dates || cal.working_exceptions;
              if (displayDates && displayDates.length > 0) {
                return (
                  <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto pr-2 custom-scrollbar">
                    {displayDates.map((date, idx) => {
                      const d = new Date(date.split('-')[0], parseInt(date.split('-')[1]) - 1, date.split('-')[2]);
                      const formatted = isNaN(d.getTime()) ? date : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
                      return (
                        <span key={idx} className="px-2 py-1 bg-emerald-50/50 border border-emerald-100 rounded text-[10px] font-mono text-emerald-800">
                          {formatted}
                        </span>
                      );
                    })}
                  </div>
                );
              }
              return <span className="text-[10px] italic text-gray-400">No working overrides defined</span>;
            })()}
          </div>
        </div>
      )}
    </div>
  );
};

const CalendarSummary = ({ context = 'controller' }) => {
  const [calendars, setCalendars] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');

  const fetchCalendars = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`${BASE}/calendars?context=${context}`);
      if (res.data?.success) {
        setCalendars(res.data.data || []);
      }
    } catch (err) {
      setError('Failed to load calendars. Ensure a project XER is loaded.');
    } finally {
      setLoading(false);
    }
  }, [context]);

  useEffect(() => {
    fetchCalendars();
  }, [fetchCalendars]);

  const filtered = useMemo(() => {
    if (!search) return calendars;
    return calendars.filter(c => c.name.toLowerCase().includes(search.toLowerCase()));
  }, [calendars, search]);

  return (
    <div className="flex-1 min-h-0 overflow-y-auto px-8 py-6">
      <div className="flex flex-col gap-6 min-h-full">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Calendar size={19} className="text-blue-600" />
            <div>
              <h2 className="text-sm font-black text-gray-900 uppercase tracking-widest">Calendar Intelligence</h2>
              <p className="text-[10px] text-gray-400 font-medium">Verify P6 working days and exceptions mapped to activities.</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input 
                value={search} 
                onChange={e => setSearch(e.target.value)}
                placeholder="Search calendars..."
                className="pl-9 pr-3 py-2 bg-white border border-gray-200 rounded-xl text-[10px] font-medium focus:outline-none focus:ring-2 focus:ring-blue-400/30 w-56 shadow-sm" 
              />
            </div>
            <button onClick={fetchCalendars} disabled={loading}
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
          <div className="flex flex-col gap-2 animate-pulse mt-4">
            {[1, 2, 3, 4].map(i => <div key={i} className="h-14 bg-gray-100 rounded-xl" />)}
          </div>
        ) : !error && (
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden flex flex-col">
            <div className="flex items-center py-3 px-4 bg-gray-50 border-b border-gray-200 sticky top-0 z-10 text-[10px] font-black text-gray-400 uppercase tracking-widest">
              <div className="w-8 shrink-0"></div>
              <div className="w-1/3 shrink-0">Calendar Name</div>
              <div className="w-32 shrink-0">Workweek</div>
              <div className="w-32 shrink-0">Hours / Day</div>
              <div className="w-40 shrink-0">Non-Working Dates</div>
              <div className="w-40 shrink-0">Working Overrides</div>
            </div>
            <div className="flex flex-col">
              {filtered.length > 0 ? (
                filtered.map(cal => <CalendarRow key={cal.id} cal={cal} />)
              ) : (
                <div className="py-12 text-center text-gray-400 italic text-sm">
                  {search ? 'No calendars match your search.' : 'No calendars found in this project.'}
                </div>
              )}
            </div>
            <div className="px-6 py-3 border-t border-gray-100 bg-gray-50/60">
              <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest">
                Total: {filtered.length} calendars
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CalendarSummary;
