import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  Calendar, TrendingUp, TrendingDown, AlertTriangle, Activity, Target,
  Clock, DollarSign, BarChart2, ArrowUpRight, ArrowDownRight, Loader2,
  ChevronRight, Shield, Zap, AlertCircle, RefreshCw
} from 'lucide-react';

const formatCurrency = (val) => {
  if (val === null || val === undefined) return 'Not Available';
  const abs = Math.abs(val);
  if (abs >= 1e9) return `${(val / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(val / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${(val / 1e3).toFixed(1)}K`;
  return val.toFixed(2);
};

const formatDate = (dateStr) => {
  if (!dateStr) return 'Not Available';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
};

// ── KPI Tile Component ──────────────────────────────────────────────────────
const KPITile = ({ title, value, subtitle, icon: Icon, color = 'blue', badge, badgeColor, size = 'normal' }) => {
  const colorMap = {
    blue: 'from-blue-500/10 to-blue-600/5 border-blue-200/60',
    green: 'from-emerald-500/10 to-emerald-600/5 border-emerald-200/60',
    red: 'from-red-500/10 to-red-600/5 border-red-200/60',
    amber: 'from-amber-500/10 to-amber-600/5 border-amber-200/60',
    purple: 'from-violet-500/10 to-violet-600/5 border-violet-200/60',
    slate: 'from-slate-500/10 to-slate-600/5 border-slate-200/60',
  };

  const iconColorMap = {
    blue: 'text-blue-600 bg-blue-100',
    green: 'text-emerald-600 bg-emerald-100',
    red: 'text-red-600 bg-red-100',
    amber: 'text-amber-600 bg-amber-100',
    purple: 'text-violet-600 bg-violet-100',
    slate: 'text-slate-600 bg-slate-100',
  };

  const valColorMap = {
    blue: 'text-blue-900',
    green: 'text-emerald-900',
    red: 'text-red-900',
    amber: 'text-amber-900',
    purple: 'text-violet-900',
    slate: 'text-slate-900',
  };

  return (
    <div className={`relative bg-gradient-to-br ${colorMap[color]} border rounded-xl p-4 transition-all hover:shadow-md hover:scale-[1.01] group`}>
      <div className="flex items-start justify-between mb-2">
        <div className={`p-2 rounded-lg ${iconColorMap[color]} transition-transform group-hover:scale-110`}>
          <Icon size={16} />
        </div>
        {badge && (
          <span className={`text-[8px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full border ${
            badgeColor === 'amber' ? 'bg-amber-100 text-amber-700 border-amber-200' :
            badgeColor === 'red' ? 'bg-red-100 text-red-700 border-red-200' :
            'bg-gray-100 text-gray-600 border-gray-200'
          }`}>
            {badge}
          </span>
        )}
      </div>
      <p className="text-[9px] font-black uppercase tracking-widest text-gray-400 mb-1">{title}</p>
      <p className={`text-xl font-black ${valColorMap[color]} tracking-tight leading-none mb-1`}>
        {value ?? 'Not Available'}
      </p>
      {subtitle && (
        <p className="text-[10px] font-semibold text-gray-500 mt-1.5">{subtitle}</p>
      )}
    </div>
  );
};

// ── Critical Path Card ──────────────────────────────────────────────────────
const CriticalPathCard = ({ title, icon: Icon, data, color = 'red' }) => {
  const [showPath, setShowPath] = useState(false);
  const borderColor = color === 'red' ? 'border-red-200' : 'border-amber-200';
  const headerBg = color === 'red' ? 'bg-red-50' : 'bg-amber-50';
  const headerText = color === 'red' ? 'text-red-800' : 'text-amber-800';
  const iconColor = color === 'red' ? 'text-red-600' : 'text-amber-600';
  const accentColor = color === 'red' ? 'text-red-600 bg-red-50 border-red-100' : 'text-amber-600 bg-amber-50 border-amber-100';

  const floatColor = (f) => {
    if (f < 0) return 'text-red-700 bg-red-50 border-red-200';
    if (f === 0) return 'text-amber-700 bg-amber-50 border-amber-200';
    return 'text-emerald-700 bg-emerald-50 border-emerald-200';
  };

  return (
    <div className={`bg-white border ${borderColor} rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-all`}>
      <div className={`${headerBg} px-5 py-3 border-b ${borderColor} flex items-center justify-between`}>
        <div className="flex items-center gap-2.5">
          <Icon size={16} className={iconColor} />
          <h3 className={`text-[11px] font-black uppercase tracking-widest ${headerText}`}>{title}</h3>
        </div>
        {data && data.path_sequence && data.path_sequence.length > 0 && (
          <button
            onClick={() => setShowPath(!showPath)}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[9px] font-black uppercase tracking-widest border transition-all ${
              showPath
                ? `${accentColor} opacity-80`
                : 'text-gray-500 bg-white border-gray-200 hover:border-gray-300'
            }`}
          >
            <ChevronRight size={10} className={`transition-transform ${showPath ? 'rotate-90' : ''}`} />
            {showPath ? 'Hide Path' : `View Path (${data.path_sequence.length})`}
          </button>
        )}
      </div>
      <div className="p-5">
        {data ? (
          <>
            <div className="grid grid-cols-3 gap-3">
              {data.count !== undefined && (
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <p className="text-[8px] font-black uppercase tracking-widest text-gray-400 mb-1">Activities</p>
                  <p className="text-lg font-black text-gray-900">{data.count}</p>
                </div>
              )}
              {data.duration !== undefined && data.duration !== null && (
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <p className="text-[8px] font-black uppercase tracking-widest text-gray-400 mb-1">Path Duration</p>
                  <p className="text-lg font-black text-gray-900">{data.duration}d</p>
                </div>
              )}
              {data.worst_float !== undefined && data.worst_float !== null && (
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <p className="text-[8px] font-black uppercase tracking-widest text-gray-400 mb-1">Worst Float</p>
                  <p className={`text-lg font-black ${data.worst_float < 0 ? 'text-red-700' : 'text-gray-900'}`}>
                    {data.worst_float > 0 ? '+' : ''}{data.worst_float}d
                  </p>
                </div>
              )}
              {data.min_float !== undefined && data.min_float !== null && (
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <p className="text-[8px] font-black uppercase tracking-widest text-gray-400 mb-1">Min Float</p>
                  <p className="text-lg font-black text-amber-700">{data.min_float > 0 ? '+' : ''}{data.min_float}d</p>
                </div>
              )}
              {data.first_activity && (
                <div className="col-span-3 bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <p className="text-[8px] font-black uppercase tracking-widest text-gray-400 mb-1">First Activity</p>
                  <p className="text-[11px] font-bold text-gray-800 truncate" title={data.first_activity}>
                    <span className="text-blue-600 font-mono mr-1">{data.first_activity_id}</span>
                    {data.first_activity}
                  </p>
                </div>
              )}
              {data.last_activity && (
                <div className="col-span-3 bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <p className="text-[8px] font-black uppercase tracking-widest text-gray-400 mb-1">Last Activity</p>
                  <p className="text-[11px] font-bold text-gray-800 truncate" title={data.last_activity}>
                    <span className="text-blue-600 font-mono mr-1">{data.last_activity_id}</span>
                    {data.last_activity}
                  </p>
                </div>
              )}
            </div>

            {/* ── Expandable Path Sequence ── */}
            {showPath && data.path_sequence && data.path_sequence.length > 0 && (
              <div className="mt-4 border-t border-gray-100 pt-4">
                <p className="text-[9px] font-black uppercase tracking-widest text-gray-400 mb-3">
                  Full Path Sequence — {data.path_sequence.length} Activities
                </p>
                <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
                  {data.path_sequence.map((act, i) => (
                    <div key={i} className="flex items-center gap-2 py-1.5 px-2.5 rounded-lg hover:bg-gray-50 transition-colors group">
                      <span className="text-[9px] font-black text-gray-300 w-5 shrink-0 text-right">{i + 1}</span>
                      <span className="text-[9px] font-mono font-bold text-blue-600 shrink-0 w-28 truncate">{act.id}</span>
                      <span className="text-[10px] font-semibold text-gray-700 flex-1 truncate" title={act.name}>{act.name}</span>
                      <span className="text-[9px] text-gray-400 shrink-0 hidden group-hover:block">{act.es} → {act.ef}</span>
                      <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border shrink-0 ${floatColor(act.float)}`}>
                        {act.float > 0 ? '+' : ''}{act.float}d
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <p className="text-sm text-gray-400 font-medium italic">No data available</p>
        )}
      </div>
    </div>
  );
};

// ── Main Dashboard View ─────────────────────────────────────────────────────

const DashboardView = ({ context = 'controller' }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`/api/project/dashboard?context=${context}`);
      setData(res.data);
    } catch (err) {
      console.error('Dashboard fetch error:', err);
      setError(err.message || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }, [context]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  // ── Loading State ──
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50/50">
        <div className="text-center">
          <Loader2 size={40} className="text-blue-500 animate-spin mx-auto mb-4" />
          <p className="text-sm font-bold text-gray-500 uppercase tracking-widest">Loading Dashboard...</p>
        </div>
      </div>
    );
  }

  // ── Error State ──
  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50/50">
        <div className="text-center max-w-md">
          <AlertTriangle size={48} className="text-red-400 mx-auto mb-4" />
          <h2 className="text-lg font-bold text-gray-800 mb-2">Dashboard Error</h2>
          <p className="text-sm text-gray-500 mb-4">{error}</p>
          <button onClick={fetchDashboard} className="px-4 py-2 bg-blue-600 text-white text-xs font-bold rounded-lg hover:bg-blue-700">
            Retry
          </button>
        </div>
      </div>
    );
  }

  // ── Baseline-Only / No Data ──
  if (!data || data.mode === 'BASELINE_ONLY' || data.mode === 'NO_DATA') {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50/50">
        <div className="text-center max-w-lg bg-white border border-amber-200 rounded-2xl p-10 shadow-sm">
          <div className="w-16 h-16 bg-amber-100 rounded-2xl flex items-center justify-center mx-auto mb-5">
            <AlertCircle size={32} className="text-amber-600" />
          </div>
          <h2 className="text-xl font-black text-gray-900 mb-2 tracking-tight">Dashboard Unavailable</h2>
          <p className="text-sm font-medium text-gray-500 mb-6 leading-relaxed">
            This dashboard requires an update file to compute KPIs.<br />
            <span className="text-amber-700 font-bold">Current mode: {data?.mode === 'NO_DATA' ? 'No data loaded' : 'Baseline only'}.</span>
          </p>
          <div className="flex items-center justify-center gap-2 text-[10px] font-black text-gray-400 uppercase tracking-widest">
            <Shield size={14} /> Upload a schedule update to activate the dashboard
          </div>
        </div>
      </div>
    );
  }

  // ── Error from backend ──
  if (data.mode === 'ERROR') {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50/50">
        <div className="text-center max-w-md">
          <AlertTriangle size={48} className="text-red-400 mx-auto mb-4" />
          <h2 className="text-lg font-bold text-gray-800 mb-2">Calculation Error</h2>
          <p className="text-sm text-gray-500 mb-4">{data.error}</p>
          <button onClick={fetchDashboard} className="px-4 py-2 bg-blue-600 text-white text-xs font-bold rounded-lg hover:bg-blue-700">
            <RefreshCw size={14} className="inline mr-1" /> Retry
          </button>
        </div>
      </div>
    );
  }

  // ── WITH_UPDATE: Full Dashboard ──
  const delayColor = data.delay_days > 0 ? 'red' : data.delay_days === 0 ? 'slate' : 'green';
  const delayDisplay = data.delay_days !== null && data.delay_days !== undefined
    ? `${data.delay_days > 0 ? '+' : ''}${data.delay_days} Days`
    : 'Not Available';

  const svColor = (data.cost_sv ?? 0) >= 0 ? 'green' : 'red';
  const svDisplay = data.cost_sv !== null && data.cost_sv !== undefined
    ? `${data.cost_sv >= 0 ? '+' : ''}$${formatCurrency(data.cost_sv)}`
    : 'Not Available';

  const physSvColor = (data.schedule_performance_pct ?? 0) >= 0 ? 'green' : 'red';
  const physSvDisplay = data.schedule_performance_pct !== null && data.schedule_performance_pct !== undefined
    ? `${data.schedule_performance_pct >= 0 ? '+' : ''}${data.schedule_performance_pct}%`
    : 'Not Available';

  const spiColor = data.spi >= 0.95 ? 'green' : data.spi >= 0.85 ? 'amber' : data.spi !== null ? 'red' : 'slate';
  const cpiColor = data.cpi >= 0.95 ? 'green' : data.cpi >= 0.85 ? 'amber' : data.cpi !== null ? 'red' : 'slate';

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50/50 p-6">
      {/* Dashboard Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-100 rounded-xl">
            <BarChart2 size={20} className="text-blue-600" />
          </div>
          <div>
            <h1 className="text-lg font-black text-gray-900 tracking-tight">Project Dashboard</h1>
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Layer 2 Analytics</p>
          </div>
        </div>
        <button
          onClick={fetchDashboard}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-[10px] font-bold text-gray-600 hover:bg-gray-50 hover:border-gray-300 transition-all shadow-sm"
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {/* ── Row 1: KPI Tiles ── */}
      <div className="grid grid-cols-3 lg:grid-cols-5 xl:grid-cols-9 gap-3 mb-6">
        <KPITile
          title="Forecast Finish"
          value={formatDate(data.forecast_finish)}
          icon={Calendar}
          color="blue"
        />
        <KPITile
          title="Baseline Finish"
          value={formatDate(data.baseline_finish)}
          icon={Target}
          color="slate"
        />
        <KPITile
          title="Delay Days"
          value={delayDisplay}
          icon={data.delay_days > 0 ? TrendingDown : TrendingUp}
          color={delayColor}
        />
        <KPITile
          title="Cost SV"
          value={svDisplay}
          icon={DollarSign}
          color={svColor}
        />
        <KPITile
          title="Schedule Performance %"
          value={physSvDisplay}
          icon={data.schedule_performance_pct >= 0 ? ArrowUpRight : ArrowDownRight}
          color={physSvColor}
        />
        <KPITile
          title="PV Cost"
          value={data.pv_cost !== null && data.pv_cost !== undefined ? `$${formatCurrency(data.pv_cost)}` : 'Not Available'}
          icon={DollarSign}
          color="blue"
        />
        <KPITile
          title="EV Cost"
          value={data.ev_cost !== null && data.ev_cost !== undefined ? `$${formatCurrency(data.ev_cost)}` : 'Not Available'}
          icon={DollarSign}
          color="purple"
        />
        <KPITile
          title="SPI"
          value={data.spi !== null && data.spi !== undefined ? data.spi.toFixed(2) : 'Not Available'}
          subtitle={data.spi_coverage !== null && data.spi_coverage !== undefined ? `Coverage: ${data.spi_coverage}%` : null}
          icon={Activity}
          color={spiColor}
          badge={data.spi_coverage !== null && data.spi_coverage < 20 ? 'Low Coverage' : null}
          badgeColor="amber"
        />
        <KPITile
          title="CPI"
          value={data.cpi !== null && data.cpi !== undefined ? data.cpi.toFixed(2) : 'Not Available'}
          subtitle={data.cpi_coverage !== null && data.cpi_coverage !== undefined ? `Coverage: ${data.cpi_coverage}%` : null}
          icon={DollarSign}
          color={cpiColor}
          badge={data.cpi_coverage !== null && data.cpi_coverage < 20 ? 'Low Coverage' : null}
          badgeColor="amber"
        />
      </div>

      {/* ── Row 2: Critical Path Cards ── */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-black text-gray-800 tracking-tight">Driving Paths</h2>
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 border border-red-100 rounded-lg shadow-sm">
          <AlertCircle size={14} className="text-red-500" />
          <span className="text-[10px] font-black uppercase tracking-widest text-red-800">
            Total Critical Activities (Float ≤ 0): {data.critical_count ?? 0}
          </span>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <CriticalPathCard
          title="Current Critical Path"
          icon={Zap}
          data={data.current_critical_path}
          color="red"
        />
        <CriticalPathCard
          title="Next Critical Path"
          icon={AlertTriangle}
          data={data.next_critical_path}
          color="amber"
        />
      </div>

      {/* ── Row 3: WBS Delay Table ── */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
        <div className="bg-gray-50 px-5 py-3 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <BarChart2 size={16} className="text-blue-600" />
            <h3 className="text-[11px] font-black uppercase tracking-widest text-gray-700">Per-WBS Delay Table</h3>
          </div>
          <span className="text-[9px] font-bold text-gray-400 uppercase">
            {data.wbs_delay?.length || 0} WBS Branches
          </span>
        </div>

        {data.wbs_delay && data.wbs_delay.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50/80 border-b border-gray-100">
                  <th className="text-left px-5 py-2.5 text-[9px] font-black text-gray-400 uppercase tracking-widest">WBS Branch</th>
                  <th className="text-right px-5 py-2.5 text-[9px] font-black text-gray-400 uppercase tracking-widest">Baseline Finish</th>
                  <th className="text-right px-5 py-2.5 text-[9px] font-black text-gray-400 uppercase tracking-widest">Forecast Finish</th>
                  <th className="text-right px-5 py-2.5 text-[9px] font-black text-gray-400 uppercase tracking-widest">Delay (Working Days)</th>
                  <th className="text-center px-5 py-2.5 text-[9px] font-black text-gray-400 uppercase tracking-widest">Status</th>
                  <th className="text-right px-5 py-2.5 text-[9px] font-black text-gray-400 uppercase tracking-widest">% Complete</th>
                  <th className="text-right px-5 py-2.5 text-[9px] font-black text-gray-400 uppercase tracking-widest">Activities</th>
                </tr>
              </thead>
              <tbody>
                {data.wbs_delay.map((row, idx) => (
                  <tr key={idx} className="border-b border-gray-50 hover:bg-blue-50/20 transition-colors">
                    <td className="px-5 py-3">
                      <div className="flex flex-col">
                        <span className="text-[10px] font-mono text-gray-400 mb-0.5">{row.wbs_id}</span>
                        <span className="text-[12px] font-bold text-gray-900">{row.wbs}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-right text-[11px] font-mono text-gray-500">{formatDate(row.bl_finish)}</td>
                    <td className="px-5 py-3 text-right text-[11px] font-mono text-gray-500">{formatDate(row.up_finish)}</td>
                    <td className="px-5 py-3 text-right">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-black ${
                        row.delay_working_days > 0
                          ? 'bg-red-50 text-red-700 border border-red-200'
                          : row.delay_working_days < 0
                          ? 'bg-green-50 text-green-700 border border-green-200'
                          : 'bg-gray-50 text-gray-600 border border-gray-200'
                      }`}>
                        {row.delay_working_days > 0 ? <ArrowUpRight size={12} /> : row.delay_working_days < 0 ? <ArrowDownRight size={12} /> : null}
                        {row.delay_working_days > 0 ? '+' : ''}{row.delay_working_days}d
                      </span>
                    </td>
                    <td className="px-5 py-3 text-center">
                      <span className={`text-[10px] font-bold uppercase tracking-widest ${
                        row.status === 'Behind Schedule' ? 'text-red-600' :
                        row.status === 'Ahead of Schedule' ? 'text-green-600' : 'text-gray-500'
                      }`}>
                        {row.status}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right text-[11px] font-bold text-blue-700">{row.pct_complete}%</td>
                    <td className="px-5 py-3 text-right text-[11px] font-semibold text-gray-600">{row.activity_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center">
            <p className="text-sm font-medium text-gray-400 italic">No WBS delay data available</p>
          </div>
        )}
      </div>

      {/* Footer spacer */}
      <div className="h-20" />
    </div>
  );
};

export default DashboardView;
