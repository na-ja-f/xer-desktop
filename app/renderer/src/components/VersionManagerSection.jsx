import React from 'react';
import { Upload, Trash2 } from 'lucide-react';

const VersionManagerSection = ({ versions, selectedVersionId, setSelectedVersionId, handleDeleteVersion, handleUpload, loading, mode = 'full', showUpdates = false }) => {
  const hasBaseline = versions.some(v => v.type === 'baseline');

  if (mode === 'toolbar' || mode === 'compact_row') {
    return (
      <div className={`flex items-center gap-4 py-1 ${mode === 'compact_row' ? 'bg-white rounded-2xl border border-gray-200 px-6 py-3 shadow-sm mx-6 my-4' : ''}`}>
        {/* Compact Project */}
        <div className="flex items-center gap-2 pr-4 border-r border-gray-200 mr-2">
          <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Project:</span>
          {versions.filter(v => v.type === 'baseline').length > 0 ? (
            versions.filter(v => v.type === 'baseline').map((v) => (
              <div 
                key={v.id} 
                onClick={() => setSelectedVersionId(v.id)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border cursor-pointer transition-all ${selectedVersionId === v.id ? 'bg-blue-600 border-blue-600 text-white' : 'bg-white border-gray-200 text-gray-700 hover:border-blue-300'}`}
              >
                <span className="text-[10px] font-bold truncate max-w-[80px]">{v.name}</span>
                <button onClick={(e) => handleDeleteVersion(e, v.id)} className="hover:text-red-400"><Trash2 size={12} /></button>
              </div>
            ))
          ) : (
            <label className="flex items-center gap-1.5 px-3 py-1.5 border border-dashed border-blue-200 rounded-lg text-blue-600 cursor-pointer hover:bg-blue-50 transition-all">
              <Upload size={12} /> <span className="text-[10px] font-black uppercase">Upload</span>
              <input type="file" hidden accept=".xer" onChange={(e) => handleUpload(e, 'baseline')} disabled={loading} />
            </label>
          )}
        </div>

        {/* Compact Updates (Conditional) */}
        {showUpdates && (
          <div className="flex items-center gap-3 overflow-x-auto max-w-[400px] no-scrollbar">
            <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest shrink-0">Updates:</span>
            <div className="flex gap-2">
              {versions.filter(v => v.type === 'update').map((v) => (
                <div 
                  key={v.id} 
                  onClick={() => setSelectedVersionId(v.id)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border cursor-pointer transition-all shrink-0 ${selectedVersionId === v.id ? 'bg-blue-600 border-blue-600 text-white' : 'bg-white border-gray-200 text-gray-700 hover:border-blue-300'}`}
                >
                  <span className="text-[10px] font-bold">{v.data_date}</span>
                  <button onClick={(e) => handleDeleteVersion(e, v.id)} className="hover:text-red-400"><Trash2 size={12} /></button>
                </div>
              ))}
              {hasBaseline ? (
                <label className="flex items-center gap-1.5 px-3 py-1.5 border border-dashed border-gray-200 rounded-lg text-gray-400 cursor-pointer hover:bg-gray-50 transition-all shrink-0">
                  <Upload size={12} />
                  <input type="file" hidden accept=".xer" onChange={(e) => handleUpload(e, 'update')} disabled={loading} />
                </label>
              ) : (
                <div onClick={() => alert("Please upload a Project (Baseline) file first before adding updates.")} className="flex items-center gap-1.5 px-3 py-1.5 border border-dashed border-gray-200 rounded-lg text-gray-300 cursor-pointer hover:bg-gray-50 transition-all shrink-0">
                  <Upload size={12} />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }

  const isCompact = mode === 'compact';
  
  return (
    <div className={`mx-6 my-4 grid grid-cols-1 ${showUpdates ? 'md:grid-cols-2' : ''} gap-4 ${isCompact ? 'max-w-4xl mx-auto' : ''}`}>
      {/* Project Section */}
      <div className={`bg-white rounded-[1.5rem] border border-gray-200 shadow-sm ${isCompact ? 'p-3' : 'p-5'}`}>
        <div className={`flex items-center justify-between px-1 ${isCompact ? 'mb-2' : 'mb-4'}`}>
          <span className={`${isCompact ? 'text-[9px]' : 'text-[11px]'} font-black text-gray-900 uppercase tracking-widest`}>Project Schedule</span>
          {!versions.find(v => v.type === 'baseline') && (
            <span className="text-[9px] font-bold text-orange-500 bg-orange-50 px-2 rounded-lg border border-orange-100 italic">Required</span>
          )}
        </div>
        <div className="grid grid-cols-1 gap-2">
          {versions.filter(v => v.type === 'baseline').length > 0 ? (
            versions.filter(v => v.type === 'baseline').map((v) => (
              <div 
                key={v.id} 
                onClick={() => { setSelectedVersionId(v.id); }}
                className={`${isCompact ? 'p-2' : 'p-4'} rounded-xl border cursor-pointer transition-all relative group shadow-sm ${selectedVersionId === v.id ? 'bg-blue-600 border-blue-600' : 'bg-white border-gray-100 hover:border-blue-200'}`}
              >
                <button 
                  onClick={(e) => handleDeleteVersion(e, v.id)}
                  className={`absolute top-2 right-2 p-1 rounded-lg transition-all z-10 ${selectedVersionId === v.id ? 'bg-white/20 text-white hover:bg-red-500' : 'bg-gray-50 text-gray-400 hover:text-red-600 hover:bg-red-50 border border-gray-100'}`}
                >
                  <Trash2 size={12} />
                </button>
                <div className="flex items-center gap-2 mb-1">
                  <div className={`w-1 h-1 rounded-full ${selectedVersionId === v.id ? 'bg-white animate-pulse' : 'bg-blue-600'}`}></div>
                  <span className={`text-[9px] font-bold font-mono ${selectedVersionId === v.id ? 'text-blue-100' : 'text-gray-400'}`}>{v.data_date}</span>
                </div>
                <div className={`text-[10px] font-black truncate pr-6 ${selectedVersionId === v.id ? 'text-white' : 'text-gray-900'}`}>
                  {v.name}
                </div>
              </div>
            ))
          ) : (
            <label className={`flex flex-col items-center justify-center ${isCompact ? 'p-4' : 'p-8'} border-2 border-dashed border-blue-100 rounded-xl cursor-pointer hover:bg-blue-50/50 transition-all bg-blue-50/20 group`}>
              <Upload size={isCompact ? 18 : 24} className="text-blue-400 mb-1 group-hover:scale-110 transition-transform" />
              <p className="text-[10px] font-black text-blue-700 uppercase tracking-tighter">Upload Project File</p>
              <input type="file" hidden accept=".xer" onChange={(e) => handleUpload(e, 'baseline')} disabled={loading} />
            </label>
          )}
        </div>
      </div>

      {/* Monthly Updates Section (Conditional) */}
      {showUpdates && (
        <div className={`bg-white rounded-[1.5rem] border border-gray-200 shadow-sm ${isCompact ? 'p-3' : 'p-5'}`}>
          <div className={`flex items-center justify-between px-1 ${isCompact ? 'mb-2' : 'mb-4'}`}>
            <span className={`${isCompact ? 'text-[9px]' : 'text-[11px]'} font-black text-gray-950 uppercase tracking-widest`}>Updates</span>
            <span className="text-[9px] font-bold text-gray-400 bg-gray-100 px-2 py-0.5 rounded-lg border border-gray-200/50">{versions.filter(v => v.type === 'update').length}</span>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-2 no-scrollbar">
            {versions.filter(v => v.type === 'update').map((v) => (
              <div 
                key={v.id} 
                onClick={() => { setSelectedVersionId(v.id); }}
                className={`flex-shrink-0 ${isCompact ? 'w-32 p-2' : 'w-56 p-4'} rounded-xl border cursor-pointer transition-all relative group shadow-sm ${selectedVersionId === v.id ? 'bg-blue-600 border-blue-600' : 'bg-white border-gray-100 hover:border-blue-200'}`}
              >
                <button 
                  onClick={(e) => handleDeleteVersion(e, v.id)}
                  className={`absolute top-2 right-2 p-1 rounded-lg transition-all z-10 ${selectedVersionId === v.id ? 'bg-white/20 text-white hover:bg-red-500' : 'bg-gray-50 text-gray-400 hover:text-red-600 hover:bg-red-50 border border-gray-100'}`}
                >
                  <Trash2 size={12} />
                </button>
                <div className="flex items-center gap-2 mb-1">
                  <div className={`w-1 h-1 rounded-full ${selectedVersionId === v.id ? 'bg-white' : 'bg-green-500'}`}></div>
                  <span className={`text-[9px] font-bold font-mono ${selectedVersionId === v.id ? 'text-blue-100' : 'text-gray-400'}`}>{v.data_date}</span>
                </div>
                <div className={`text-[10px] font-black truncate pr-6 ${selectedVersionId === v.id ? 'text-white' : 'text-gray-900'}`}>
                  {v.name}
                </div>
              </div>
            ))}
            {hasBaseline ? (
              <label className={`flex-shrink-0 ${isCompact ? 'w-24' : 'w-48'} flex flex-col items-center justify-center p-2 border-2 border-dashed border-gray-100 rounded-xl cursor-pointer hover:bg-gray-50 transition-all group`}>
                <Upload size={isCompact ? 16 : 20} className="text-gray-400 group-hover:text-blue-500 transition-colors mb-1" />
                <span className="text-[9px] font-black text-gray-500 uppercase group-hover:text-blue-700 transition-colors text-center leading-tight">Add Update</span>
                <input type="file" hidden accept=".xer" onChange={(e) => handleUpload(e, 'update')} disabled={loading} />
              </label>
            ) : (
              <div onClick={() => alert("Please upload a Project (Baseline) file first before adding updates.")} className={`flex-shrink-0 ${isCompact ? 'w-24' : 'w-48'} flex flex-col items-center justify-center p-2 border-2 border-dashed border-gray-100 rounded-xl cursor-pointer hover:bg-gray-50 transition-all group`}>
                <Upload size={isCompact ? 16 : 20} className="text-gray-300 group-hover:text-orange-500 transition-colors mb-1" />
                <span className="text-[9px] font-black text-gray-400 uppercase group-hover:text-orange-600 transition-colors text-center leading-tight">Add Update</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default VersionManagerSection;
