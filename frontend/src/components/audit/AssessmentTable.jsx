import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const DISPLAY_NAMES = {
  1: 'Missing logic',
  2: 'Leads',
  3: 'Lags',
  4: 'Relationship types',
  5: 'Hard constraints',
  6: 'High float',
  7: 'Negative float',
  8: 'High duration',
  9: 'Invalid dates',
  10: 'Resources',
  11: 'Missed tasks',
  12: 'Critical path',
  13: 'CPLI',
  14: 'BEI',
};

const BAND_CLASSES = {
  pass: 'bg-[#D1FAE5] text-[#047857]',
  warn: 'bg-[#FEF3C7] text-[#B45309]',
  fail: 'bg-[#FEE2E2] text-[#B91C1C]',
  na: 'bg-[#F1F5F9] text-[#64748B]',
};

const isNA = (point) => point.status === null || point.status === undefined;

const getBand = (point) => {
  if (isNA(point)) return 'na';
  if (point.status_text === 'PASS' || point.status === true) return 'pass';
  if (point.status_text === 'WARNING') return 'warn';
  return 'fail';
};

const formatValue = (point) => {
  if (isNA(point)) return 'N/A';
  if ([13, 14].includes(point.id)) return point.val.toFixed(3);
  if ([1, 9, 10, 12].includes(point.id)) {
    return point.status_text || (point.status ? 'Pass' : 'Fail');
  }
  return typeof point.val === 'number' ? point.val.toFixed(1) + '%' : point.val;
};

const BAND_STROKE = {
  pass: '#047857',
  warn: '#B45309',
  fail: '#B91C1C',
  na: '#64748B',
};

const Sparkline = ({ values, band }) => {
  const w = 56, h = 16, pad = 1;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const points = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - pad * 2);
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} className="shrink-0">
      <polyline
        points={points}
        fill="none"
        stroke={BAND_STROKE[band]}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

const AssessmentTable = ({ stats }) => {
  const [history, setHistory] = useState({});

  const fetchHistory = useCallback(async () => {
    try {
      const res = await axios.get('/api/findings/history?context=audit');
      setHistory(res.data.history || {});
    } catch (err) {
      console.error('Failed to fetch DCMA findings history', err);
      setHistory({});
    }
  }, []);

  useEffect(() => {
    if (stats?.delay_matrix?.assessment) fetchHistory();
  }, [fetchHistory, stats]);

  if (!stats?.delay_matrix?.assessment) return null;

  const points = stats.delay_matrix.assessment;

  return (
    <div className="mb-10">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[13px] font-semibold uppercase tracking-wider text-slate-600">
          DCMA 14-Point Assessment
        </div>
        <div className="text-xs text-teal-700 cursor-default select-none">View detail →</div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
        {points.map((point) => {
          const displayName = DISPLAY_NAMES[point.id] || point.name;
          const band = getBand(point);
          const flaggedCount = point.id === 1 && point.details
            ? (point.details.starts?.length || 0) + (point.details.finishes?.length || 0)
            : null;
          const pointHistory = history[`dcma-${point.id}`] || [];
          const trendValues = pointHistory
            .map(p => p.value_numeric)
            .filter(v => typeof v === 'number');

          return (
            <div
              key={point.id}
              className="bg-white border border-[#E5E7EB] rounded-lg px-3.5 py-3"
            >
              <div className="flex items-center justify-between mb-2 gap-2">
                <span className="text-[12.5px] font-medium text-slate-900 truncate">
                  {displayName}
                </span>
                <span
                  className={`text-xs font-semibold font-mono px-2 py-[3px] rounded-full whitespace-nowrap ${BAND_CLASSES[band]}`}
                  title={band === 'na' ? point.na_reason : undefined}
                >
                  {formatValue(point)}
                </span>
              </div>
              <div className="flex items-center justify-between text-[11px] text-slate-400 gap-2">
                <span className="truncate">Target: {point.threshold}</span>
                {flaggedCount !== null && (
                  <span
                    className="truncate max-w-[110px] italic"
                    title={`Starts: ${point.details.starts?.join(', ') || 'None'} | Finishes: ${point.details.finishes?.join(', ') || 'None'}`}
                  >
                    {flaggedCount} flagged
                  </span>
                )}
                {trendValues.length >= 2 && <Sparkline values={trendValues} band={band} />}
              </div>
              {trendValues.length === 1 && (
                <p className="text-[10px] text-slate-400 italic mt-1">Trend appears after next update</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default AssessmentTable;
