import React, { useRef } from 'react';
import { AlertTriangle, AlertCircle, FileUp, X, Check } from 'lucide-react';

export const UploadWarningModal = ({ warning, onContinue, onCancel }) => {
  if (!warning) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="bg-amber-50 px-6 py-4 flex items-center gap-3 border-b border-amber-100">
          <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center shrink-0">
            <AlertTriangle className="text-amber-600" size={20} />
          </div>
          <div>
            <h3 className="font-bold text-amber-900">Schedule Warning</h3>
            <div className="text-xs font-semibold text-amber-700 bg-amber-100/50 inline-block px-2 py-0.5 rounded mt-1">
              Confidence: {warning.confidence || 'Medium'}
            </div>
          </div>
        </div>
        
        <div className="p-6">
          <p className="text-sm text-gray-700 font-medium whitespace-pre-wrap mb-4">
            {warning.detail}
          </p>
          
          {warning.evidence && warning.evidence.length > 0 && (
            <div className="bg-gray-50 border border-gray-100 rounded-lg p-4 mb-6">
              <h4 className="text-xs font-black text-gray-400 uppercase tracking-widest mb-2">Evidence</h4>
              <ul className="space-y-1.5">
                {warning.evidence.map((item, idx) => (
                  <li key={idx} className="text-sm text-gray-600 flex items-start gap-2">
                    <span className="text-amber-500 mt-1">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          
          <div className="flex gap-3 pt-2 border-t border-gray-100">
            <button 
              onClick={onCancel}
              className="flex-1 px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-xl hover:bg-gray-50 hover:border-gray-300 font-semibold transition-all"
            >
              Upload Different File
            </button>
            <button 
              onClick={onContinue}
              className="flex-1 px-4 py-2 bg-amber-600 text-white rounded-xl hover:bg-amber-700 font-semibold transition-all flex items-center justify-center gap-2"
            >
              <Check size={16} /> Continue Anyway
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export const UploadErrorModal = ({ error, onUploadBaseline, onCancel }) => {
  if (!error) return null;
  const fileInputRef = useRef(null);

  const handleBaselineSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      onUploadBaseline(e);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="bg-red-50 px-6 py-4 flex items-center gap-3 border-b border-red-100">
          <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center shrink-0">
            <AlertCircle className="text-red-600" size={20} />
          </div>
          <div>
            <h3 className="font-bold text-red-900">Missing Baseline</h3>
          </div>
        </div>
        
        <div className="p-6">
          <p className="text-sm text-gray-700 font-medium whitespace-pre-wrap mb-6">
            {error.detail}
          </p>
          
          <div className="flex gap-3 pt-2 border-t border-gray-100">
            <button 
              onClick={onCancel}
              className="flex-1 px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-xl hover:bg-gray-50 hover:border-gray-300 font-semibold transition-all"
            >
              Cancel
            </button>
            <button 
              onClick={() => fileInputRef.current?.click()}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 font-semibold transition-all flex items-center justify-center gap-2 shadow-sm"
            >
              <FileUp size={16} /> Upload Baseline
            </button>
            <input 
              type="file" 
              className="hidden" 
              accept=".xer" 
              ref={fileInputRef} 
              onChange={handleBaselineSelect} 
            />
          </div>
        </div>
      </div>
    </div>
  );
};
