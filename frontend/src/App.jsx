import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { Upload, X, Send, BarChart2, Activity, Calendar, Clock, User, Table as TableIcon, Search, ChevronLeft, ChevronRight, Filter, Eye, ListTree, Link as LinkIcon, Info, CheckCircle, Circle, Loader2, AlertTriangle, TrendingDown, Zap, Trash2, Globe, Cpu, Maximize2, Minimize2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import logo from './assets/logo.png'

import VersionManagerSection from './components/VersionManagerSection'
import OptimizedChatInput from './components/OptimizedChatInput'
import Sidebar from './components/ui/Sidebar'
import AuditHero from './components/audit/AuditHero'
import AuditNarrative from './components/audit/AuditNarrative'
import AssessmentTable from './components/audit/AssessmentTable'
import AuditAiChat from './components/audit/AuditAiChat'
import ControllerToolbar from './components/controller/ControllerToolbar'
import ControllerTable from './components/controller/ControllerTable'
import ControllerFloatingChat from './components/controller/ControllerFloatingChat'
import ResourceView from './components/controller/ResourceView'
import CalendarSummary from './components/controller/CalendarSummary'
import DashboardView from './components/controller/DashboardView'
import { UploadWarningModal, UploadErrorModal } from './components/UploadModals'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [authError, setAuthError] = useState(null)
  const [userName, setUserName] = useState('')
  
  const [setupStatus, setSetupStatus] = useState('Initializing Application...')
  const [setupError, setSetupError] = useState(null)
  const [isSetupComplete, setIsSetupComplete] = useState(false)

  const [auditBaselineLoaded, setAuditBaselineLoaded] = useState(false)
  const [controllerBaselineLoaded, setControllerBaselineLoaded] = useState(false)
  const [auditStats, setAuditStats] = useState(null)
  const [controllerStats, setControllerStats] = useState(null)
  const [loading, setLoading] = useState(false)
  const [isTableLoading, setIsTableLoading] = useState(false)
  const [isTyping, setIsTyping] = useState(false)
  const [viewMode, setViewMode] = useState('audit') // 'audit' or 'controller'
  const [viewerTable, setViewerTable] = useState('TASK')
  const [tableData, setTableData] = useState({ records: [], total: 0 })
  const [tablePage, setTablePage] = useState(1)
  const [tableSearch, setTableSearch] = useState('')
  const [viewerFilter, setViewerFilter] = useState('ALL') // 'ALL', 'CRITICAL', 'NEG_FLOAT', 'POS_FLOAT', 'DELAYED', 'DELAYED_CRITICAL', 'DELAYED_NEGATIVE'
  const [evmMethodology, setEvmMethodology] = useState('LABOR')
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([])
  const [auditVersions, setAuditVersions] = useState([])
  const [controllerVersions, setControllerVersions] = useState([])
  const [selectedAuditVersionId, setSelectedAuditVersionId] = useState(null)
  const [selectedControllerVersionId, setSelectedControllerVersionId] = useState(null)
  const [aiConfig, setAiConfig] = useState({ provider: 'openai', model: 'gpt-4o', has_openai_key: false })
  const [isUpdatingAI, setIsUpdatingAI] = useState(false)
  
  // Independent Controller Chat State
  const [controllerMessages, setControllerMessages] = useState([])
  const [controllerQuery, setControllerQuery] = useState('')
  const [isControllerChatOpen, setIsControllerChatOpen] = useState(false)
  const [isControllerTyping, setIsControllerTyping] = useState(false)
  const [isControllerChatExpanded, setIsControllerChatExpanded] = useState(false)
  const [controllerChatPos, setControllerChatPos] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const dragStartPos = useRef({ x: 0, y: 0 })
  const chatContainerRef = useRef(null)
  const posRef = useRef({ x: 0, y: 0 })
  
  const chatEndRef = useRef(null)
  const controllerChatEndRef = useRef(null)

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }
  
  const scrollControllerToBottom = () => {
    controllerChatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, isTyping])

  useEffect(() => {
    if (isControllerChatOpen) {
      scrollControllerToBottom()
    }
  }, [controllerMessages, isControllerTyping, isControllerChatOpen])

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging) return
      const newX = e.clientX - dragStartPos.current.x
      const newY = e.clientY - dragStartPos.current.y
      posRef.current = { x: newX, y: newY }
      if (chatContainerRef.current) {
        chatContainerRef.current.style.transform = `translate(${newX}px, ${newY}px)`
      }
    }
    const handleMouseUp = () => {
      setIsDragging(false)
      setControllerChatPos({ ...posRef.current })
    }
    
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging])

  const handleDragStart = (e) => {
    // Only allow drag on the header itself, not children buttons
    if (e.target.closest('button')) return
    setIsDragging(true)
    dragStartPos.current = { 
      x: e.clientX - posRef.current.x, 
      y: e.clientY - posRef.current.y 
    }
  }

  const [uploadWarning, setUploadWarning] = useState(null)
  const [uploadError, setUploadError] = useState(null)

  const handleUpload = async (eOrFile, type = 'baseline', overrideProgress = false, overridePairing = false) => {
    // Determine if we received an event or a direct file object
    const file = eOrFile?.target?.files ? eOrFile.target.files[0] : eOrFile;
    if (!file) return

    setLoading(true)
    const formData = new FormData()
    formData.append('file', file)
    formData.append('file_type', type)
    formData.append('context', viewMode)
    if (overrideProgress) formData.append('override_progress', 'true')
    if (overridePairing) formData.append('override_pairing', 'true')
    
    try {
      const res = await axios.post('/api/upload-xer', formData)
      if (res.data.success) {
        if (viewMode === 'audit') {
          setAuditStats(res.data.stats)
          if (type === 'baseline') setAuditBaselineLoaded(true)
          setSelectedAuditVersionId(res.data.version_id)
        } else {
          setControllerStats(res.data.stats)
          if (type === 'baseline') setControllerBaselineLoaded(true)
          setSelectedControllerVersionId(res.data.version_id)
        }
        fetchVersions(viewMode)
        // Clear modals on success
        setUploadWarning(null)
        setUploadError(null)
      }
    } catch (err) {
      console.error(err)
      const detail = err.response?.data?.detail
      if (detail && typeof detail === 'object') {
        if (detail.type === 'warning') {
          setUploadWarning({ ...detail, originalFile: file, uploadType: type })
          return // do not alert
        } else if (detail.type === 'error') {
          setUploadError(detail)
          return // do not alert
        }
      }
      alert('Upload failed: ' + (typeof detail === 'string' ? detail : err.message))
    } finally {
      setLoading(false)
      if (eOrFile?.target) {
        eOrFile.target.value = ''
      }
    }
  }

  const handleUploadWarningContinue = () => {
    if (!uploadWarning) return;
    const { originalFile, uploadType, warning_type } = uploadWarning;
    const overrideProg = warning_type === 'baseline_progress';
    const overridePair = warning_type === 'project_mismatch';
    
    setUploadWarning(null);
    handleUpload(originalFile, uploadType, overrideProg, overridePair);
  }

  const [baselineError, setBaselineError] = useState(null)

  const fetchTableData = async () => {
    try {
      let reqTable = viewerTable
      if (viewerTable === 'TASK') reqTable = 'HIERARCHY'
      if (viewerTable === 'WBS') reqTable = 'WBS_HIERARCHY'
      
      const selectedId = viewMode === 'audit' ? selectedAuditVersionId : selectedControllerVersionId
      if (!selectedId) return

      setIsTableLoading(true)
      setBaselineError(null)
      const res = await axios.get(`/api/xer-data?table=${reqTable}&page=${tablePage}&search=${tableSearch}&version_id=${selectedId}&filter=${viewerFilter}&context=${viewMode}`)
      
      if (res.data.success === false) {
        setBaselineError(res.data)
        setTableData({ records: [], total: 0 })
      } else {
        setTableData(res.data)
      }
    } catch (err) {
      console.error('Failed to fetch table data', err)
    } finally {
      setIsTableLoading(false)
    }
  }

  const fetchVersions = async (context = viewMode) => {
    try {
      const res = await axios.get(`/api/versions?context=${context}`)
      if (context === 'audit') {
        setAuditVersions(res.data)
      } else {
        setControllerVersions(res.data)
      }
    } catch (err) {
      console.error('Failed to fetch versions', err)
    }
  }

  const fetchAIConfig = async () => {
    try {
      const res = await axios.get('/api/settings')
      setAiConfig(res.data)
    } catch (err) {
      console.error('Failed to fetch AI config', err)
    }
  }

  const handleUpdateAI = async (provider) => {
    setIsUpdatingAI(true)
    try {
      const formData = new FormData()
      formData.append('provider', provider)
      const res = await axios.post('/api/settings/update', formData)
      setAiConfig(res.data)
    } catch (err) {
      console.error('Failed to update AI config', err)
    } finally {
      setIsUpdatingAI(false)
    }
  }

  useEffect(() => {
    const checkExistingData = async (context) => {
      try {
        const res = await axios.get(`/api/versions?context=${context}`)
        if (res.data && res.data.length > 0) {
          if (context === 'audit') {
            setAuditVersions(res.data)
            const bl = res.data.find(v => v.type === 'baseline')
            if (bl) {
              setAuditBaselineLoaded(true)
              setSelectedAuditVersionId(bl.id)
            }
          } else {
            setControllerVersions(res.data)
            const bl = res.data.find(v => v.type === 'baseline')
            if (bl) {
              setControllerBaselineLoaded(true)
              setSelectedControllerVersionId(bl.id)
            }
          }
        }
      } catch (err) {
        console.error(`Initialization check failed for ${context}`, err)
      }
    }
    
    if (isSetupComplete) {
      checkExistingData('audit')
      checkExistingData('controller')
      fetchAIConfig()
    }
  }, [isSetupComplete])

  // Sync stats when version changes
  useEffect(() => {
    const syncStats = async (context) => {
      const selectedId = context === 'audit' ? selectedAuditVersionId : selectedControllerVersionId
      if (!selectedId) return
      try {
        const res = await axios.get(`/api/health?version_id=${selectedId}&context=${context}`)
        if (context === 'audit') setAuditStats(res.data)
        else setControllerStats(res.data)
      } catch (err) {
        console.error(`Failed to sync health stats for ${context}`, err)
      }
    }
    syncStats('audit')
    syncStats('controller')
  }, [selectedAuditVersionId, selectedControllerVersionId])

  // Setup Effect (IPC Listeners)
  useEffect(() => {
    if (typeof window !== 'undefined' && window.require) {
      try {
        const { ipcRenderer } = window.require('electron')
        
        const removeStatus = ipcRenderer.on('setup-status', (e, msg) => setSetupStatus(msg))
        const removeError = ipcRenderer.on('setup-error', (e, err) => setSetupError(err))
        const removeComplete = ipcRenderer.on('setup-complete', (e, data) => {
          if (data && data.apiPort) {
             // Point axios directly at the backend — no /api prefix needed (Vite proxy handles that in browser)
             axios.defaults.baseURL = `http://127.0.0.1:${data.apiPort}`
             // Override all calls to strip /api prefix for direct backend access
             axios.interceptors.request.use((config) => {
               if (config.url && config.url.startsWith('/api/')) {
                 config.url = config.url.replace('/api/', '/')
               }
               return config
             })
          }
          setIsSetupComplete(true)
        })

        return () => {
          if (ipcRenderer.removeAllListeners) {
            ipcRenderer.removeAllListeners('setup-status')
            ipcRenderer.removeAllListeners('setup-error')
            ipcRenderer.removeAllListeners('setup-complete')
          }
        }
      } catch (err) {
         setIsSetupComplete(true)
      }
    } else {
      // Browser fallback (use proxy or default 8000)
      setIsSetupComplete(true)
    }
  }, [])

  // Authentication Effect
  useEffect(() => {
    let domainMatch = false;
    let uName = 'User';
    
    try {
      // Pull allowed domains from env (comma-separated), and add fallbacks dynamically
      const envDomains = import.meta.env.VITE_ALLOWED_DOMAIN 
        ? import.meta.env.VITE_ALLOWED_DOMAIN.split(',').map(d => d.trim().toLowerCase())
        : [];
      
      const allowedDomains = [...envDomains, "ellisdon", "desktop-0qlhho9", "ellisdon.com"];
      
      if (typeof window !== 'undefined' && window.process && window.process.env) {
        const platform = window.process.platform;
        const uDomain = window.process.env.USERDOMAIN || '';
        
        if (window.require) {
           try {
             uName = window.require('os').userInfo().username;
           } catch(e) {}
        }
        
        // Allow bypass on Mac for development, otherwise strict array domain check
        if (platform === 'darwin' || allowedDomains.includes(uDomain.toLowerCase()) || import.meta.env.DEV) {
          domainMatch = true;
        }
      } else {
        // Browser fallback
        domainMatch = import.meta.env.DEV ? true : false;
      }
    } catch (err) {
      console.error('Auth verification error', err);
    }

    if (!domainMatch) {
      setAuthError('Access restricted to EllisDon domain users');
    } else {
      setUserName(uName);
      setIsAuthenticated(true);
    }
  }, []);

  useEffect(() => {
    if (auditBaselineLoaded) {
      fetchVersions('audit')
    }
  }, [auditBaselineLoaded])

  useEffect(() => {
    if (controllerBaselineLoaded) {
      fetchVersions('controller')
    }
  }, [controllerBaselineLoaded])

  useEffect(() => {
    if (viewMode === 'controller' && controllerBaselineLoaded) {
      fetchTableData()
    }
  }, [viewMode, viewerTable, tablePage, tableSearch, selectedControllerVersionId, viewerFilter])

  const handleAsk = async (submittedQuery) => {
    const q = typeof submittedQuery === 'string' ? submittedQuery : query;
    if (!q || isTyping) return

    const isGreeting = /^(hi|hello|hey|good morning|good afternoon|good evening|greetings)\b/i.test(q.trim());

    if (!auditBaselineLoaded) {
      const reply = isGreeting 
        ? "Hello! I am your XerAgent planning assistant. To get started, please upload a project XER file so we can analyze the schedule together."
        : "I'd love to help you with that! Please upload a project XER file first so I can access the schedule data.";
      setMessages(prev => [...prev, 
        { role: 'user', content: q }, 
        { role: 'assistant', content: reply }
      ])
      setQuery('')
      return
    }

    // Collect UI Context
    const context = {
      current_view: 'audit',
      selected_version: selectedAuditVersionId,
      applied_filters: viewerFilter,
      table_search: tableSearch,
      has_baseline: auditBaselineLoaded
    };

    const userMsg = { role: 'user', content: q }
    setMessages(prev => [...prev, userMsg])
    setQuery('')
    setIsTyping(true)
    
    try {
      const params = new URLSearchParams();
      params.append('query', q);
      params.append('context', JSON.stringify(context));
      params.append('session_id', 'audit_chat');
      
      const res = await axios.post('/api/ask', params)
      setMessages(prev => [...prev, { role: 'assistant', content: res.data.response }])
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error connecting to the schedule analyzer.' }])
    } finally {
      setIsTyping(false)
    }
  }

  const handleControllerAsk = async (submittedQuery) => {
    const q = typeof submittedQuery === 'string' ? submittedQuery : controllerQuery;
    if (!q || isControllerTyping) return

    const isGreeting = /^(hi|hello|hey|good morning|good afternoon|good evening|greetings)\b/i.test(q.trim());

    if (!controllerBaselineLoaded) {
      const reply = isGreeting 
        ? "Hello! I am your XerAgent planning assistant. To get started, please upload a project XER file so we can analyze the schedule together."
        : "I'd love to help you with that! Please upload a project XER file first so I can access the schedule data.";
      setControllerMessages(prev => [...prev, 
        { role: 'user', content: q }, 
        { role: 'assistant', content: reply }
      ])
      setControllerQuery('')
      return
    }

    // Collect UI Context
    const context = {
      current_view: 'controller',
      selected_version: selectedControllerVersionId,
      table_mode: viewerTable,
      applied_filters: viewerFilter,
      table_search: tableSearch
    };

    const userMsg = { role: 'user', content: q }
    setControllerMessages(prev => [...prev, userMsg])
    setControllerQuery('')
    setIsControllerTyping(true)
    
    try {
      const params = new URLSearchParams();
      params.append('query', q);
      params.append('context', JSON.stringify(context));
      params.append('session_id', 'controller_chat');

      const res = await axios.post('/api/ask', params)
      setControllerMessages(prev => [...prev, { role: 'assistant', content: res.data.response }])
    } catch (err) {
      setControllerMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error connecting to the controller intelligence engine.' }])
    } finally {
      setIsControllerTyping(false)
    }
  }

  const handleDeleteVersion = async (e, versionId) => {
    e.stopPropagation()
    if (!window.confirm('Are you sure you want to delete this version?')) return
    
    try {
      await axios.delete(`/api/versions/${versionId}?context=${viewMode}`)
      
      // Always refresh the versions list from the backend
      const res = await axios.get(`/api/versions?context=${viewMode}`)
      const updatedVersions = res.data
      
      if (viewMode === 'audit') {
        setAuditVersions(updatedVersions)
        const hasBaseline = updatedVersions.some(v => v.type === 'baseline')
        setAuditBaselineLoaded(hasBaseline)
        
        if (selectedAuditVersionId === versionId) {
          setSelectedAuditVersionId(updatedVersions.find(v => v.type === 'baseline')?.id || updatedVersions[0]?.id || null)
        }
        if (!hasBaseline) {
          setAuditStats(null)
          setMessages([])
          setTableData({ records: [], total: 0 })
        }
      } else {
        setControllerVersions(updatedVersions)
        const hasBaseline = updatedVersions.some(v => v.type === 'baseline')
        setControllerBaselineLoaded(hasBaseline)
        
        if (selectedControllerVersionId === versionId) {
          setSelectedControllerVersionId(updatedVersions.find(v => v.type === 'baseline')?.id || updatedVersions[0]?.id || null)
        }
        if (!hasBaseline) {
          setControllerStats(null)
          setControllerMessages([])
          setTableData({ records: [], total: 0 })
        }
      }
    } catch (err) {
      console.error('Failed to delete version', err)
      alert('Failed to delete version')
    }
  }
  
  if (!isSetupComplete) {
     return (
       <div className="flex flex-col items-center justify-center h-screen bg-white text-center p-4">
         <img src={logo} alt="EllisDon Logo" className="h-12 mb-8 object-contain opacity-50" />
         {!setupError ? (
           <>
             <Loader2 size={40} className="text-blue-500 animate-spin mb-4" />
             <h2 className="text-xl font-bold mb-2 text-gray-900">Preparing Enterprise Environment</h2>
             <p className="text-xs font-bold text-gray-500 uppercase tracking-widest max-w-lg mt-4 px-4 py-2 bg-gray-50 rounded-lg">{setupStatus}</p>
           </>
         ) : (
           <>
             <AlertTriangle size={48} className="text-red-500 mb-4 animate-bounce" />
             <h2 className="text-red-600 text-xl font-bold mb-2">Startup Failed</h2>
             <p className="text-gray-700 mb-8 max-w-md bg-red-50 p-4 rounded-xl border border-red-100">{setupError}</p>
             <button onClick={() => window.location.reload()} className="px-6 py-2 bg-blue-600 text-white rounded-lg shadow font-medium">Retry Verification</button>
           </>
         )}
       </div>
     )
  }

  if (authError) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-50 text-center p-4">
        <AlertTriangle size={64} className="text-red-500 mb-6" />
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Access Denied</h1>
        <p className="text-gray-600 font-medium">{authError}</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-white">
        <Loader2 size={40} className="text-blue-500 animate-spin mb-4" />
        <p className="text-sm font-semibold text-gray-500 uppercase tracking-widest">Verifying Domain Architecture...</p>
      </div>
    )
  }



  // P6 Style Date Formatter
  const formatP6Date = (dateStr) => {
    if (!dateStr || dateStr === 'None' || dateStr === 'nan' || dateStr === '-') return '-'
    try {
      const trimmed = dateStr.trim()
      // If it is already in 'DD MMM YYYY' format (e.g. '09 Jun 2025'), return as-is
      if (/^\d{2}\s[a-zA-Z]{3}\s\d{4}$/.test(trimmed)) {
        return trimmed
      }
      // For ISO dates like '2025-06-09 08:00', take only the date part
      let cleanStr = trimmed
      if (trimmed.includes('-')) {
        cleanStr = trimmed.split(' ')[0]
      }
      const date = new Date(cleanStr)
      if (isNaN(date.getTime())) return dateStr
      return new Intl.DateTimeFormat('en-GB', { 
        day: '2-digit',
        month: 'short', 
        year: 'numeric' 
      }).format(date)
    } catch (e) {
      return dateStr
    }
  }


  // Header Label Mapping
  const getHeaderLabel = (key) => {
    const labels = {
      'task_code': 'Activity ID',
      'task_name': 'Activity Name',
      'status': 'Status',
      'target_start_date': 'Planned Start',
      'target_end_date': 'Planned Finish',
      'act_start_date': 'Actual Start',
      'act_end_date': 'Actual Finish',
      'total_float_hr_cnt': 'Total Float (h)',
      'budget_cost': 'Budgeted Total Cost',
      'ev_cost': 'Earned Value Cost',
      'pv_cost': 'Planned Value Cost',
      'at_completion_cost': 'At Completion Cost',
      'bl_project_cost': 'BL Project Total Cost',
      'float_risk': 'Float Risk',
      'bl_float_days': 'Baseline Float',
      'float_consumed_pct': 'Float Consumed %'
    }
    return labels[key] || key.replace(/_/g, ' ').replace('hr cnt', '(hrs)').replace('pred type', 'Type').toUpperCase()
  }

  return (
    <div className="flex h-screen w-screen bg-gray-50 overflow-hidden font-sans text-gray-950">
      <Sidebar 
        viewMode={viewMode}
        setViewMode={setViewMode}
        userName={userName}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col bg-white overflow-hidden relative">
        {/* Global Loading Overlay */}
        {loading && (
          <div className="absolute inset-0 z-[100] bg-white/80 backdrop-blur-sm flex flex-col items-center justify-center">
            <Loader2 size={48} className="text-blue-600 animate-spin mb-4" />
            <h2 className="text-2xl font-bold text-gray-800 tracking-tight">Processing Schedule File...</h2>
            <p className="text-gray-500 mt-2 font-medium">Parsing data and computing logic networks.</p>
          </div>
        )}

        <div className="h-14 border-b border-gray-100 flex items-center px-6 gap-4 text-sm bg-gray-50/50">
          <div className="h-2 w-2 rounded-full bg-blue-500"></div>
          <span className="font-medium text-gray-600">Project:</span>
          <span className="font-bold text-gray-900">
            {viewMode === 'audit' ? auditStats?.data_source : controllerStats?.data_source}
          </span>
          <span className="text-gray-300">|</span>
          <span className="font-medium text-gray-600">Period:</span>
          <span className="font-bold text-gray-900">
            {viewMode === 'audit' 
              ? (auditStats?.project_start ? `${auditStats.project_start} to ${auditStats.project_finish}` : 'No project loaded') 
              : (controllerStats?.project_start ? `${controllerStats.project_start} to ${controllerStats.project_finish}` : 'No project loaded')
            }
          </span>
        </div>

        {viewMode === 'audit' ? (
          <div className="flex-1 overflow-y-auto bg-gray-50/50 relative pb-48">
            <VersionManagerSection 
              versions={auditVersions}
              selectedVersionId={selectedAuditVersionId}
              setSelectedVersionId={setSelectedAuditVersionId}
              handleDeleteVersion={handleDeleteVersion}
              handleUpload={handleUpload}
              loading={loading}
              mode="compact_row"
              showUpdates={true}
            />

            <AuditHero stats={auditStats} />
            <div className="max-w-6xl mx-auto px-6 pt-6">
              {/* B-019: AI narrative over M1 findings */}
              <AuditNarrative stats={auditStats} versionId={selectedAuditVersionId} />
            </div>
            {/* --- AI CHAT SECTION --- */}
            <div className="max-w-6xl mx-auto px-6 py-6 pb-24">
               {/* 14-Point Assessment Table (DCMA Standard) */}
               <AssessmentTable stats={auditStats} />
               {/* AI Audit Assistant */}
               <AuditAiChat 
                 messages={messages} 
                 isTyping={isTyping} 
                 handleAsk={handleAsk} 
                 chatEndRef={chatEndRef}
                 isUpdatingAI={isUpdatingAI}
                 handleUpdateAI={handleUpdateAI}
                 aiConfig={aiConfig}
                 stats={auditStats}
               />
            </div>
          </div>
        ) : viewMode === 'controller' ? (
          <div className="flex-1 min-h-0 flex flex-col overflow-hidden bg-gray-50/50">
            <ControllerToolbar 
              viewerTable={viewerTable}
              setViewerTable={setViewerTable}
              setTablePage={setTablePage}
              viewerFilter={viewerFilter}
              setViewerFilter={setViewerFilter}
              versions={controllerVersions}
              selectedVersionId={selectedControllerVersionId}
              setSelectedVersionId={setSelectedControllerVersionId}
              handleDeleteVersion={handleDeleteVersion}
              handleUpload={handleUpload}
              loading={loading}
              tableSearch={tableSearch}
              setTableSearch={setTableSearch}
              isControllerChatOpen={isControllerChatOpen}
              setIsControllerChatOpen={setIsControllerChatOpen}
              tableData={tableData}
              evmMethodology={evmMethodology}
              setEvmMethodology={setEvmMethodology}
            />
            {viewerTable === 'RESOURCES' ? (
              <ResourceView context="controller" />
            ) : viewerTable === 'CALENDARS' ? (
              <CalendarSummary context="controller" />
            ) : viewerTable === 'DASHBOARD' ? (
              <DashboardView context="controller" />
            ) : (
              <ControllerTable 
                tableData={tableData}
                viewerTable={viewerTable}
                viewerFilter={viewerFilter}
                setViewerFilter={setViewerFilter}
                tableSearch={tableSearch}
                setTableSearch={setTableSearch}
                tablePage={tablePage}
                setTablePage={setTablePage}
                formatP6Date={formatP6Date}
                baselineError={baselineError}
                getHeaderLabel={getHeaderLabel}
                hasProject={controllerBaselineLoaded}
                isTableLoading={isTableLoading}
                evmMethodology={evmMethodology}
              />
            )}
            
            {/* Controller Intelligence - Independent Floating Chat */}
            <ControllerFloatingChat 
              controllerChatPos={controllerChatPos}
              isDragging={isDragging}
              isControllerChatExpanded={isControllerChatExpanded}
              isControllerChatOpen={isControllerChatOpen}
              handleDragStart={handleDragStart}
              setIsControllerChatExpanded={setIsControllerChatExpanded}
              setIsControllerChatOpen={setIsControllerChatOpen}
              controllerMessages={controllerMessages}
              isControllerTyping={isControllerTyping}
              controllerChatEndRef={controllerChatEndRef}
              handleControllerAsk={handleControllerAsk}
              chatContainerRef={chatContainerRef}
            />
          </div>
        ) : null}
      </div>

      {/* UX validation modals */}
      <UploadWarningModal 
        warning={uploadWarning} 
        onContinue={handleUploadWarningContinue} 
        onCancel={() => setUploadWarning(null)} 
      />
      <UploadErrorModal 
        error={uploadError} 
        onUploadBaseline={(e) => {
          setUploadError(null);
          handleUpload(e, 'baseline');
        }}
        onCancel={() => setUploadError(null)} 
      />

    </div>
  )
}

export default App
