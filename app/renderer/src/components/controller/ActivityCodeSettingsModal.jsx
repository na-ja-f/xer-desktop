import React, { useEffect, useState } from 'react';
import { X, Loader2, AlertTriangle, Check } from 'lucide-react';
import axios from 'axios';

// B-204 Phase 2: lets a planner review/override the auto-suggested canonical
// name for each raw Activity Code category detected in the loaded project.
// Deliberately minimal — one modal, one list, one save action per row.
export default function ActivityCodeSettingsModal({ isOpen, onClose, versionId, context }) {
  const [categories, setCategories] = useState(null);
  const [config, setConfig] = useState({});
  const [drafts, setDrafts] = useState({});
  const [savingRaw, setSavingRaw] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen) return;
    const load = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [typesRes, configRes] = await Promise.all([
          axios.get(`/api/activity-codes/types?context=${context}`),
          axios.get(`/api/activity-codes/config?context=${context}&version_id=${versionId || ''}`),
        ]);
        const types = typesRes.data?.data || [];
        setCategories(types);

        const byRaw = {};
        for (const row of configRes.data?.config || []) {
          byRaw[row.raw_name] = row;
        }
        setConfig(byRaw);
        const initialDrafts = {};
        for (const t of types) {
          initialDrafts[t.code_type] = byRaw[t.code_type]?.canonical_name || '';
        }
        setDrafts(initialDrafts);
      } catch (err) {
        console.error('Failed to load activity code config', err);
        setError('Failed to load Activity Code categories.');
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [isOpen, versionId, context]);

  const handleSave = async (rawName) => {
    const canonicalName = (drafts[rawName] || '').trim();
    if (!canonicalName) return;
    setSavingRaw(rawName);
    try {
      const form = new FormData();
      form.append('canonical_name', canonicalName);
      form.append('raw_name', rawName);
      form.append('context', context);
      if (versionId) form.append('version_id', versionId);
      await axios.post('/api/activity-codes/config', form);
      setConfig(prev => ({ ...prev, [rawName]: { canonical_name: canonicalName, raw_name: rawName, source: 'user_override' } }));
    } catch (err) {
      console.error('Failed to save activity code config', err);
    } finally {
      setSavingRaw(null);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-8 py-5 border-b border-gray-100">
          <div>
            <h2 className="text-lg font-black text-gray-900">Activity Code Categories</h2>
            <p className="text-xs text-gray-400 mt-0.5 font-medium">
              Map each raw category name to an internal canonical name. Auto-suggested on upload — override anytime.
            </p>
          </div>
          <button onClick={onClose}
            className="p-2 rounded-xl hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto min-h-[200px] px-8 py-5">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-48 text-blue-500">
              <Loader2 size={28} className="mb-3 animate-spin" />
              <p className="text-sm font-bold uppercase tracking-widest">Loading categories...</p>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-48 text-red-500 text-center">
              <AlertTriangle size={28} className="mb-3" />
              <p className="text-xs text-red-400 font-medium">{error}</p>
            </div>
          ) : !categories || categories.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-gray-400">
              <AlertTriangle size={24} className="mb-3 opacity-40" />
              <p className="text-sm font-medium">No Activity Code categories detected in this project.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {categories.map(cat => {
                const source = config[cat.code_type]?.source;
                return (
                  <div key={cat.code_type} className="flex items-center gap-3 bg-gray-50 border border-gray-100 rounded-xl px-4 py-3">
                    <div className="flex-1 min-w-0">
                      <div className="text-[9px] font-black text-gray-400 uppercase tracking-wider">Raw category ({cat.scope})</div>
                      <div className="text-sm font-bold text-gray-800 truncate" title={cat.code_type}>{cat.code_type}</div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-[9px] font-black text-gray-400 uppercase tracking-wider">Canonical name</div>
                      <input
                        value={drafts[cat.code_type] || ''}
                        onChange={e => setDrafts(prev => ({ ...prev, [cat.code_type]: e.target.value }))}
                        placeholder="e.g. Discipline, Zone, Sector..."
                        className="w-full px-2 py-1 text-sm font-semibold bg-white border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
                      />
                    </div>
                    <button
                      onClick={() => handleSave(cat.code_type)}
                      disabled={savingRaw === cat.code_type || !(drafts[cat.code_type] || '').trim()}
                      className="shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-wide bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 transition-all"
                    >
                      {savingRaw === cat.code_type ? <Loader2 size={12} className="animate-spin" /> : (source === 'user_override' ? <Check size={12} /> : null)}
                      Save
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
