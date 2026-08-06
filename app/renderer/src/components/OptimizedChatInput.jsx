import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Search, AlertTriangle, Zap, BarChart3, Activity, FileText, HelpCircle, ArrowUpRight } from 'lucide-react';

const SLASH_COMMANDS = [
  {
    command: '/critical',
    label: 'Critical Path',
    description: 'Show critical path activities',
    icon: Zap,
    color: 'text-red-500',
    bg: 'bg-red-50',
    query: 'show me critical path activities'
  },
  {
    command: '/delayed',
    label: 'Delayed Activities',
    description: 'List all delayed activities',
    icon: AlertTriangle,
    color: 'text-orange-500',
    bg: 'bg-orange-50',
    query: 'show me delayed activities'
  },
  {
    command: '/summary',
    label: 'Project Summary',
    description: 'Project overview: variance, completion, top issues',
    icon: BarChart3,
    color: 'text-blue-500',
    bg: 'bg-blue-50',
    query: 'summarize the project'
  },
  {
    command: '/float',
    label: 'Negative Float',
    description: 'Activities with negative float',
    icon: Activity,
    color: 'text-purple-500',
    bg: 'bg-purple-50',
    query: 'show negative float activities'
  },
  {
    command: '/integrity',
    label: 'Logic Integrity',
    description: 'Check open ends & logic gaps',
    icon: FileText,
    color: 'text-green-500',
    bg: 'bg-green-50',
    query: 'check schedule logic integrity'
  },
  {
    command: '/health',
    label: 'Project Health',
    description: 'DCMA health score & pass/fail rates',
    icon: Activity,
    color: 'text-emerald-500',
    bg: 'bg-emerald-50',
    query: 'what is the project health'
  },
  {
    command: '/help',
    label: 'Help',
    description: 'Show all query examples',
    icon: HelpCircle,
    color: 'text-gray-500',
    bg: 'bg-gray-50',
    query: '/help'
  },
];

const OptimizedChatInput = ({ placeholder, onSubmit, isTyping, className, buttonClassName }) => {
  const [inputValue, setInputValue] = useState('');
  const [showCommands, setShowCommands] = useState(false);
  const [filteredCommands, setFilteredCommands] = useState(SLASH_COMMANDS);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);
  const menuRef = useRef(null);
  
  const handleAsk = useCallback(() => {
    if (inputValue.trim() && !isTyping) {
      onSubmit(inputValue);
      setInputValue('');
      setShowCommands(false);
    }
  }, [inputValue, isTyping, onSubmit]);

  const handleSelectCommand = useCallback((cmd) => {
    onSubmit(cmd.query);
    setInputValue('');
    setShowCommands(false);
    inputRef.current?.focus();
  }, [onSubmit]);

  const handleInputChange = useCallback((e) => {
    const val = e.target.value;
    setInputValue(val);

    if (val.startsWith('/')) {
      const filter = val.toLowerCase();
      const matched = SLASH_COMMANDS.filter(c =>
        c.command.startsWith(filter) || c.label.toLowerCase().includes(filter.slice(1))
      );
      setFilteredCommands(matched.length > 0 ? matched : SLASH_COMMANDS);
      setSelectedIndex(0);
      setShowCommands(true);
    } else {
      setShowCommands(false);
    }
  }, []);

  const handleKeyDown = useCallback((e) => {
    if (showCommands) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(prev => (prev + 1) % filteredCommands.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(prev => (prev - 1 + filteredCommands.length) % filteredCommands.length);
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        handleSelectCommand(filteredCommands[selectedIndex]);
      } else if (e.key === 'Escape') {
        setShowCommands(false);
      }
    } else if (e.key === 'Enter') {
      handleAsk();
    }
  }, [showCommands, filteredCommands, selectedIndex, handleSelectCommand, handleAsk]);

  // Close menu on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target) &&
          inputRef.current && !inputRef.current.contains(e.target)) {
        setShowCommands(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Scroll selected item into view
  useEffect(() => {
    if (showCommands && menuRef.current) {
      const item = menuRef.current.children[selectedIndex];
      if (item) item.scrollIntoView({ block: 'nearest' });
    }
  }, [selectedIndex, showCommands]);

  return (
    <div className="relative flex items-center w-full group pointer-events-auto shadow-2xl rounded-2xl ring-1 ring-black/5">
      {/* Slash Command Palette */}
      {showCommands && (
        <div
          ref={menuRef}
          className="absolute bottom-full left-0 right-0 mb-2 bg-white rounded-2xl border border-gray-200 shadow-2xl shadow-black/10 overflow-hidden z-50 animate-in slide-in-from-bottom-2 fade-in duration-150"
          style={{ maxHeight: '320px', overflowY: 'auto' }}
        >
          <div className="px-4 py-2.5 border-b border-gray-100 bg-gray-50/80">
            <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Quick Commands</span>
          </div>
          {filteredCommands.map((cmd, i) => {
            const Icon = cmd.icon;
            return (
              <div
                key={cmd.command}
                onClick={() => handleSelectCommand(cmd)}
                onMouseEnter={() => setSelectedIndex(i)}
                className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-all duration-75 ${
                  i === selectedIndex
                    ? 'bg-blue-50 border-l-2 border-l-blue-500'
                    : 'border-l-2 border-l-transparent hover:bg-gray-50'
                }`}
              >
                <div className={`p-1.5 rounded-lg ${cmd.bg} flex-shrink-0`}>
                  <Icon size={14} className={cmd.color} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-gray-900">{cmd.label}</span>
                    <span className="text-[10px] font-mono text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">{cmd.command}</span>
                  </div>
                  <p className="text-[10px] text-gray-500 font-medium mt-0.5 truncate">{cmd.description}</p>
                </div>
                {i === selectedIndex && (
                  <ArrowUpRight size={12} className="text-blue-400 flex-shrink-0" />
                )}
              </div>
            );
          })}
          <div className="px-4 py-2 border-t border-gray-100 bg-gray-50/50 flex items-center justify-between">
            <span className="text-[9px] text-gray-400 font-medium">↑↓ Navigate · Enter to select · Esc to close</span>
          </div>
        </div>
      )}

      <input 
        ref={inputRef}
        type="text"
        className={className || "w-full pl-6 pr-14 py-4 bg-gray-50 border border-gray-100 rounded-2xl text-sm focus:ring-2 focus:ring-blue-500/20 outline-none transition-all placeholder:text-gray-400 font-medium"}
        placeholder={placeholder}
        value={inputValue}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
      />
      <button 
        onClick={handleAsk}
        disabled={!inputValue.trim() || isTyping}
        className={buttonClassName || "absolute right-2 p-2.5 bg-blue-600 text-white rounded-xl shadow-lg shadow-blue-500/20 hover:scale-105 active:scale-95 disabled:opacity-20 disabled:scale-100 transition-all"}
      >
        <Send size={18} />
      </button>
    </div>
  );
};

export default OptimizedChatInput;
