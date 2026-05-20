import React, { useState, useMemo, useEffect } from 'react';
import { X, Search, AlertTriangle, CheckCircle, Clock, Loader2 } from 'lucide-react';
import axios from 'axios';

const STATUS_COLORS = {
  COMPLETED:    'bg-green-100 text-green-700',
  IN_PROGRESS:  'bg-blue-100 text-blue-700',
  NOT_STARTED:  'bg-gray-100 text-gray-600',
  DELAYED_CRITICAL: 'bg-red-100 text-red-700',
  DELAYED_SAFE: 'bg-orange-100 text-orange-700',
  DELAYED_NEGATIVE: 'bg-red-200 text-red-800',
  DEFAULT:      'bg-gray-100 text-gray-500',
};

const PAGE_SIZE = 30;

export default function ViewAllModal({ isOpen, onClose, title, data = [], dataRef, totalCount, displayedCount }) {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [fullData, setFullData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isOpen && dataRef && !fullData && !isLoading) {
      const fetchFullData = async () => {
        setIsLoading(true);
        setError(null);
        try {
          const res = await axios.get(`/api/full-data?ref=${dataRef}`);
          if (res.data.success) {
            setFullData(res.data.data);
          }
        } catch (err) {
          console.error('Failed to fetch full data', err);
          setError('Failed to retrieve full dataset. It may have expired.');
        } finally {
          setIsLoading(false);
        }
      };
      fetchFullData();
    }
  }, [isOpen, dataRef, fullData]);

  const displayData = fullData || data;

  const filtered = useMemo(() => {
    if (!search.trim()) return displayData;
    const q = search.toLowerCase();
    return displayData.filter(d =>
      (d.name || d.task_name || '').toLowerCase().includes(q) ||
      (d.code || d.task_code || '').toLowerCase().includes(q)
    );
  }, [displayData, search]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col overflow-hidden mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-8 py-5 border-b border-gray-100">
          <div>
            <h2 className="text-lg font-black text-gray-900">{title}</h2>
            <p className="text-xs text-gray-400 mt-0.5 font-medium">
              {search ? `${filtered.length} filtered` : `${fullData ? fullData.length : totalCount} items`}
              {totalCount > displayedCount && !search && !fullData && !isLoading &&
                <span className="ml-2 text-amber-500 font-bold">
                  · Showing preview ({displayedCount})
                </span>}
              {isLoading && <span className="ml-2 text-blue-500 animate-pulse font-bold">· Loading full dataset...</span>}
            </p>
          </div>
          <button onClick={onClose}
            className="p-2 rounded-xl hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* Search */}
        <div className="px-8 py-4 border-b border-gray-50">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
              placeholder="Filter by name or code..."
              className="w-full pl-9 pr-4 py-2.5 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all font-medium"
            />
          </div>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-y-auto min-h-[300px]">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-64 text-blue-500">
              <Loader2 size={32} className="mb-3 animate-spin" />
              <p className="text-sm font-bold uppercase tracking-widest">Retrieving Full Dataset...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-64 text-red-500 p-8 text-center">
              <AlertTriangle size={32} className="mb-3" />
              <p className="text-sm font-bold uppercase tracking-widest mb-2">Error Loading Data</p>
              <p className="text-xs text-red-400 font-medium">{error}</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-gray-400">
              <AlertTriangle size={28} className="mb-3 opacity-40" />
              <p className="text-sm font-medium">No matching activities</p>
            </div>
          ) : (
            <table className="w-full text-left">
              <thead className="sticky top-0 bg-gray-50 border-b border-gray-100">
                <tr>
                  {['Code', 'Activity Name', 'Status', 'Delay', 'Float', 'Finish'].map(h => (
                    <th key={h} className="px-6 py-3 text-[10px] font-black text-gray-400 uppercase tracking-widest">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {paginated.map((row, i) => {
                  const cat = row.category || row.status || 'DEFAULT';
                  const colorClass = STATUS_COLORS[cat] || STATUS_COLORS.DEFAULT;
                  const delayVal = row.delay_days;
                  const float_ = row.float_days ?? '-';
                  return (
                    <tr key={row.id || i} className="hover:bg-blue-50/30 transition-colors">
                      <td className="px-6 py-3 text-xs font-mono text-gray-500">{row.code || '-'}</td>
                      <td className="px-6 py-3 text-sm font-semibold text-gray-800 max-w-[240px] truncate" title={row.name}>{row.name || '-'}</td>
                      <td className="px-6 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wide ${colorClass}`}>
                          {row.status || '-'}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-sm font-bold text-gray-500">
                        {delayVal === null || delayVal === undefined ? 'N/A' : (delayVal > 0 ? `${delayVal}d` : '-')}
                      </td>
                      <td className={`px-6 py-3 text-sm font-bold ${float_ < 0 ? 'text-red-500' : 'text-gray-600'}`}>{float_ !== '-' ? `${float_}d` : '-'}</td>
                      <td className="px-6 py-3 text-xs text-gray-500 font-mono">{row.finish || '-'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-8 py-4 border-t border-gray-100 bg-gray-50/50">
            <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
              className="px-4 py-1.5 text-xs font-bold rounded-lg bg-white border border-gray-200 hover:bg-gray-50 disabled:opacity-30 transition-all">
              Previous
            </button>
            <span className="text-xs text-gray-500 font-medium">Page {page} of {totalPages}</span>
            <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)}
              className="px-4 py-1.5 text-xs font-bold rounded-lg bg-white border border-gray-200 hover:bg-gray-50 disabled:opacity-30 transition-all">
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
