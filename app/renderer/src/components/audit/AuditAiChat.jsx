import React from 'react';
import { Send, Globe, Cpu, Activity, Loader2 } from 'lucide-react';
import logo from '../../assets/logo.png';
import OptimizedChatInput from '../OptimizedChatInput';
import ChatMessage from '../chat/ChatMessage';

const safeStr = (v) => {
  if (v === null || v === undefined) return '';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
};

const AuditAiChat = ({
  messages,
  isTyping,
  handleAsk,
  chatEndRef,
  isUpdatingAI,
  handleUpdateAI,
  aiConfig,
  stats
}) => {
  return (
    <div className="bg-white rounded-[2.5rem] border border-gray-200 shadow-sm p-10 relative flex flex-col min-h-[500px]">
      {/* Header */}
      <div className="flex items-center gap-3 mb-10 border-b border-gray-100 pb-5">
        <div className="w-10 h-10 rounded-2xl bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-200">
          <Send size={18} className="text-white" />
        </div>
        <div>
          <h3 className="text-xl font-black text-gray-900 tracking-tight">AI Audit Assistant</h3>
          <p className="text-xs text-gray-400 font-medium tracking-tight">Forensic P6 analysis — intent-driven</p>
        </div>

        {/* Model Switcher */}
        <div className="ml-auto flex items-center gap-1.5 p-1 bg-gray-50 border border-gray-200 rounded-2xl">
          <button
            disabled={isUpdatingAI}
            onClick={() => handleUpdateAI('openai')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-[10px] font-black transition-all ${
              aiConfig.provider === 'openai'
                ? 'bg-red-600 text-white shadow-sm'
                : 'text-gray-400 hover:text-gray-600'
            } ${!aiConfig.has_openai_key && 'opacity-30 cursor-not-allowed'}`}
            title={!aiConfig.has_openai_key ? 'OpenAI API Key missing' : 'GPT-4o Cloud'}>
            <Globe size={12} /> Cloud
            {aiConfig.provider === 'openai' && <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />}
          </button>
          <button
            disabled={isUpdatingAI}
            onClick={() => handleUpdateAI('local')}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-[10px] font-black transition-all ${
              aiConfig.provider === 'local'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-gray-400 hover:text-gray-600'
            }`}>
            <Cpu size={12} /> Local
            {aiConfig.provider === 'local' && <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />}
          </button>
        </div>

        <span className="text-[10px] font-black uppercase tracking-widest bg-gray-100 text-gray-500 px-3 py-1.5 rounded-xl border border-gray-200/50">
          {stats?.data_source}
        </span>
      </div>

      {/* Messages */}
      <div className="space-y-6">
        {messages.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-3xl border border-gray-100 shadow-sm">
            <p className="text-gray-500 font-medium max-w-md mx-auto text-sm leading-relaxed">
              Ask me anything about your project's delays, critical path, or schedule logic.
              I'll analyze the data and give you a forensic expert response.
            </p>
            <div className="flex flex-wrap justify-center gap-2 mt-6">
              {['Show delayed activities', 'Critical path tasks', 'Is schedule logic valid?', 'Negative float activities'].map(s => (
                <button key={s} onClick={() => handleAsk(s)}
                  className="px-3 py-1.5 bg-blue-50 border border-blue-100 text-xs font-semibold text-blue-700 rounded-xl hover:bg-blue-100 transition-colors">
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          Array.isArray(messages) && messages.map((m, i) => {
            if (!m) return null;
            return (
              <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {m.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-full bg-blue-100 flex flex-shrink-0 items-center justify-center mt-1 outline outline-2 outline-white shadow-sm">
                    <Activity size={14} className="text-blue-600" />
                  </div>
                )}
                <div className={`
                  max-w-[88%] px-5 py-4 rounded-2xl text-sm leading-relaxed shadow-sm transition-all
                  ${m.role === 'user'
                    ? 'bg-blue-600 text-white rounded-tr-none shadow-md'
                    : 'bg-white border border-gray-100 text-gray-800 rounded-tl-none ring-1 ring-black/5'}
                `}>
                  {m.role === 'assistant'
                    ? <ChatMessage content={m.content} />
                    : <span>{safeStr(m.content)}</span>
                  }
                </div>
              </div>
            );
          })
        )}

        {/* Typing indicator */}
        {isTyping && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0 mt-1">
              <Loader2 size={16} className="text-blue-400 animate-spin" />
            </div>
            <div className="bg-white border border-gray-100 text-gray-500 px-5 py-3.5 rounded-2xl rounded-tl-none text-sm flex items-center gap-3 shadow-sm italic">
              <div className="flex gap-1">
                {[0, 200, 400].map(d => (
                  <div key={d} className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce"
                    style={{ animationDelay: `${d}ms`, animationDuration: '0.8s' }} />
                ))}
              </div>
              Analyzing schedule data...
            </div>
          </div>
        )}
        <div ref={chatEndRef} className="h-4" />
      </div>

      {/* Input */}
      <div className="absolute bottom-10 left-1/2 -translate-x-1/2 w-full max-w-2xl px-8 pointer-events-none">
        <OptimizedChatInput
          placeholder="Ask about delays, critical path, float, or search an activity..."
          isTyping={isTyping}
          onSubmit={handleAsk}
          className="w-full pl-6 pr-14 py-4.5 bg-white/95 backdrop-blur-md border border-gray-200 shadow-xl rounded-2xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-400 transition-all outline-none text-sm placeholder:text-gray-400 font-medium"
          buttonClassName="absolute right-2.5 top-1/2 -translate-y-1/2 p-2.5 bg-blue-600 hover:bg-blue-700 rounded-xl transition-all shadow-lg shadow-blue-200 text-white"
        />
      </div>
    </div>
  );
};

export default AuditAiChat;
