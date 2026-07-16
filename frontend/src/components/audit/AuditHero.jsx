import React from 'react';
import { AlertCircle, CheckCircle, Activity } from 'lucide-react';

const GRADE_COLORS = {
  'A': '#047857',
  'B+': '#047857',
  'B−': '#B45309',
  'C': '#B45309',
  'D': '#B91C1C',
};

const KpiTile = ({ label, value, valueColor, footer, icon: Icon, iconColor }) => (
  <div className="bg-white border border-[#E5E7EB] rounded-lg px-4 py-4">
    <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 mb-2">
      <Icon size={13} style={{ color: iconColor }} />
      {label}
    </div>
    <div className="text-2xl font-semibold tracking-tight" style={{ color: valueColor }}>
      {value}
    </div>
    {footer && <div className="text-[11px] text-slate-400 mt-1.5 truncate">{footer}</div>}
  </div>
);

const AuditHero = ({ stats }) => {
  const hero = stats?.auditHero;
  if (!hero) return null;

  const gradeColor = GRADE_COLORS[hero.grade] || '#475569';
  const trend = hero.trend;
  const trendColor = !trend ? null : trend.delta > 0 ? '#047857' : trend.delta < 0 ? '#B91C1C' : '#64748B';
  const trendArrow = !trend ? '' : trend.delta > 0 ? '▲' : trend.delta < 0 ? '▼' : '–';
  const trendLabel = !trend ? '' : `${trend.delta > 0 ? '+' : ''}${trend.delta} pts`;

  // 3 tiles for v1.0 (M1-016: warning band dropped). Adding a 4th tile back
  // later means pushing one more object here AND bumping the grid's
  // `sm:grid-cols-3` below to `sm:grid-cols-4` — Tailwind needs the class
  // written literally, it can't be derived from tiles.length.
  const tiles = [
    {
      key: 'failing',
      label: 'Failing',
      value: hero.failingCount,
      valueColor: '#B91C1C',
      footer: hero.failingChecks.length ? hero.failingChecks.join(' · ') : 'None',
      icon: AlertCircle,
      iconColor: '#B91C1C',
    },
    {
      key: 'passing',
      label: 'Passing',
      value: hero.passingCount,
      valueColor: '#047857',
      footer: 'Within tolerance',
      icon: CheckCircle,
      iconColor: '#047857',
    },
    {
      key: 'activities',
      label: 'Activities',
      value: stats.total_activities ?? '—',
      valueColor: '#0F172A',
      footer: `${stats.critical_count ?? 0} on critical path · ${stats.critical_pct ?? 0}%`,
      icon: Activity,
      iconColor: '#0F172A',
    },
  ];

  return (
    <div className="max-w-6xl mx-auto px-6 pt-6">
      <div className="mb-5">
        <div className="text-xl font-semibold tracking-tight text-slate-900">Schedule Audit</div>
        <div className="text-sm text-slate-500 mt-0.5">
          DCMA 14-Point Assessment · {hero.evaluatedCount} of 14 checks evaluated
        </div>
      </div>

      <div className="bg-gradient-to-b from-[#fbfcfd] to-[#f4f6f8] border border-[#E5E7EB] rounded-xl px-8 py-7 flex items-center gap-9 mb-3">
        <div className="flex items-baseline gap-3 shrink-0">
          <div className="text-6xl font-semibold tracking-tight text-slate-900 leading-none">{hero.score}</div>
          <div className="text-2xl font-medium" style={{ color: gradeColor }}>{hero.grade}</div>
        </div>

        <div className="flex-1 min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
            Overall Schedule Quality
          </div>
          <div className="text-sm text-slate-600 leading-relaxed max-w-2xl">
            {hero.statusSentence}
          </div>
        </div>

        {trend && (
          <div className="shrink-0 pl-8 border-l border-[#E5E7EB] text-right">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
              vs Previous Snapshot
            </div>
            <div className="text-lg font-medium" style={{ color: trendColor }}>
              {trendArrow} {trendLabel}
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
        {tiles.map((t) => (
          <KpiTile
            key={t.key}
            label={t.label}
            value={t.value}
            valueColor={t.valueColor}
            footer={t.footer}
            icon={t.icon}
            iconColor={t.iconColor}
          />
        ))}
      </div>
    </div>
  );
};

export default AuditHero;
