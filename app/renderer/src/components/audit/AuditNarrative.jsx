import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Sparkles } from 'lucide-react';

const AuditNarrative = ({ stats, versionId }) => {
  // Keyed by forVersionId rather than an explicit "loading" flag so loading
  // is derived at render time instead of set synchronously in the effect.
  const [result, setResult] = useState({ forVersionId: null, status: null, narrative: null, message: null });

  useEffect(() => {
    if (!stats?.delay_matrix?.assessment || !versionId) return;
    let ignore = false;

    axios.get(`/api/findings/narrative?context=audit&version_id=${versionId}`)
      .then((res) => {
        if (ignore) return;
        setResult({
          forVersionId: versionId,
          status: res.data.status || 'error',
          narrative: res.data.narrative || null,
          message: res.data.message || null,
        });
      })
      .catch((err) => {
        console.error('Failed to fetch audit narrative', err);
        if (!ignore) setResult({ forVersionId: versionId, status: 'error', narrative: null, message: null });
      });

    return () => { ignore = true; };
  }, [stats, versionId]);

  if (!stats?.delay_matrix?.assessment || !versionId) return null;

  const isLoading = result.forVersionId !== versionId;

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg px-6 py-5 mb-6">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 mb-2.5">
        <Sparkles size={13} className="text-teal-700" />
        AI Summary
      </div>

      {isLoading && (
        <div className="text-sm text-slate-400">Generating narrative summary…</div>
      )}

      {!isLoading && result.status === 'ok' && (
        <div className="space-y-2.5">
          {result.narrative.split(/\n\s*\n/).map((para, i) => (
            <p key={i} className="text-sm text-slate-700 leading-relaxed">{para}</p>
          ))}
        </div>
      )}

      {!isLoading && result.status === 'no_data' && (
        <div className="text-sm text-slate-400">{result.message || 'Narrative summary not available for this snapshot.'}</div>
      )}

      {!isLoading && result.status === 'error' && (
        <div className="text-sm text-slate-400">Narrative unavailable.</div>
      )}
    </div>
  );
};

export default AuditNarrative;
