import React from 'react';
import { Activity, Table as TableIcon } from 'lucide-react';
import logo from '../../assets/logo.png';

const Sidebar = ({ viewMode, setViewMode, userName }) => {
  return (
    <div className="w-[300px] bg-[#f8f9fa] border-r border-gray-200 p-6 flex flex-col overflow-y-auto">
      <div className="mb-8">
        <img src={logo} alt="EllisDon Logo" className="h-8 object-contain" />
      </div>

      <div className="space-y-2 mb-8">
        <button 
          onClick={() => setViewMode('audit')}
          className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${viewMode === 'audit' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-gray-600 hover:bg-gray-100'}`}
        >
          <Activity size={18} /> Project Audit
        </button>
        <button 
          onClick={() => setViewMode('controller')}
          className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${viewMode === 'controller' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-gray-600 hover:bg-gray-100'}`}
        >
          <TableIcon size={18} /> Project Controller
        </button>
      </div>
      
      <div className="flex-1">
        {/* Version management removed from sidebar */}
      </div>

      <div className="mt-auto pt-6 border-t border-gray-200">
        <div className="flex items-center gap-3 px-2">
          <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold text-xs uppercase shadow-sm">
            {userName ? userName.substring(0, 2) : 'U'}
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-bold text-gray-900 truncate w-32">{userName || 'User'}</span>
            <span className="text-[10px] font-medium text-gray-400 uppercase tracking-tight">Standard User</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;
