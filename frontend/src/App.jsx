import React, { useState, useEffect, useRef } from 'react'
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'
import {
  Bot, AlertTriangle, AlertCircle, Info, Send, RefreshCw,
  TrendingUp, Users, DollarSign, Activity, Sparkles,
  ChevronDown, ChevronUp, MessageSquare, BarChart3,
  Upload, FileSpreadsheet, X, CheckCircle
} from 'lucide-react'

const API_BASE_URL = 'http://localhost:8000'

const COLORS = ['#6366f1', '#06b6d4', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#ef4444', '#3b82f6']

// Custom Tooltip for charts
const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-background-card border border-gray-700 rounded-lg px-4 py-2 shadow-lg">
        <p className="text-gray-300 text-sm">{label}</p>
        {payload.map((entry, index) => (
          <p key={index} style={{ color: entry.color }} className="text-sm font-medium">
            {entry.name}: {typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}
          </p>
        ))}
      </div>
    )
  }
  return null
}

// Anomaly Card Component
const AnomalyCard = ({ anomaly, index }) => {
  const [expanded, setExpanded] = useState(false)
  
  const typeStyles = {
    critical: {
      bg: 'bg-red-500/10',
      border: 'border-red-500/30',
      icon: AlertCircle,
      iconColor: 'text-red-500',
      glow: 'glow-critical'
    },
    warning: {
      bg: 'bg-yellow-500/10',
      border: 'border-yellow-500/30',
      icon: AlertTriangle,
      iconColor: 'text-yellow-500',
      glow: 'glow-warning'
    },
    info: {
      bg: 'bg-blue-500/10',
      border: 'border-blue-500/30',
      icon: Info,
      iconColor: 'text-blue-500',
      glow: ''
    }
  }

  const style = typeStyles[anomaly.type] || typeStyles.info
  const Icon = style.icon

  return (
    <div
      className={`${style.bg} ${style.border} border rounded-xl p-4 ${style.glow} transition-all duration-300 animate-slide-up`}
      style={{ animationDelay: `${index * 150}ms` }}
    >
      <div className="flex items-start justify-between cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center gap-3">
          <Icon className={`w-5 h-5 ${style.iconColor}`} />
          <div>
            <h4 className="font-medium text-gray-200 text-sm">{anomaly.title}</h4>
            <p className="text-xs text-gray-400 mt-1">{anomaly.metric}</p>
          </div>
        </div>
        {expanded ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
      </div>
      {expanded && (
        <p className="text-sm text-gray-400 mt-3 pl-8">{anomaly.description}</p>
      )}
    </div>
  )
}

// Chart Component
const ChartRenderer = ({ data, chartType, labels, values }) => {
  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        <p>No data available to display</p>
      </div>
    )
  }

  const chartData = data.map((item, index) => ({
    name: labels ? labels[index] : item[Object.keys(item)[0]],
    value: values ? values[index] : (item[Object.keys(item)[1]] || 0),
    ...item
  }))

  if (chartType === 'line') {
    return (
      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="name" stroke="#9ca3af" fontSize={12} tickLine={false} />
            <YAxis stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Line type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={3} dot={{ r: 4, fill: '#6366f1' }} activeDot={{ r: 6 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    )
  }

  if (chartType === 'pie') {
    return (
      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={2}
              dataKey="value"
              nameKey="name"
              label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
              labelLine={{ stroke: '#4b5563' }}
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    )
  }

  // Default to bar chart
  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="name" stroke="#9ca3af" fontSize={12} tickLine={false} angle={-45} textAnchor="end" height={80} />
          <YAxis stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="value" fill="#6366f1" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// Query Result Card
const QueryResultCard = ({ result, question }) => {
  return (
    <div className="glass rounded-xl p-6 animate-fade-in">
      <div className="flex items-start gap-3 mb-4">
        <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
          <Bot className="w-5 h-5 text-primary" />
        </div>
        <div className="flex-1">
          <p className="text-sm text-gray-400 mb-1">Your question:</p>
          <p className="text-gray-200 font-medium">{question}</p>
        </div>
      </div>

      <div className="bg-background-secondary rounded-lg p-4 mb-4">
        <p className="text-sm text-gray-300 leading-relaxed">{result.insight}</p>
      </div>

      <div className="bg-background/50 rounded-lg p-3 mb-4">
        <p className="text-xs text-gray-500 font-mono mb-2">Generated SQL:</p>
        <code className="text-xs text-accent font-mono bg-background-card px-3 py-2 rounded block overflow-x-auto">
          {result.sql}
        </code>
      </div>

      <ChartRenderer
        data={result.data.raw_data}
        chartType={result.chart_type}
        labels={result.data.labels}
        values={result.data.values}
      />
    </div>
  )
}

// Digest Modal
const DigestModal = ({ digest, onClose }) => {
  if (!digest) return null

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="glass rounded-2xl p-8 max-w-3xl w-full max-h-[80vh] overflow-y-auto animate-slide-up">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-100">Weekly Business Digest</h2>
              <p className="text-xs text-gray-500">Generated {new Date(digest.generated_at).toLocaleString()}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <ChevronUp className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-background-card rounded-lg p-4">
            <p className="text-xs text-gray-500 mb-1">Total Clients</p>
            <p className="text-2xl font-bold text-gray-100">{digest.stats.total_clients}</p>
          </div>
          <div className="bg-background-card rounded-lg p-4">
            <p className="text-xs text-gray-500 mb-1">Total Revenue</p>
            <p className="text-2xl font-bold text-green-400">${digest.stats.total_revenue.toLocaleString()}</p>
          </div>
          <div className="bg-background-card rounded-lg p-4">
            <p className="text-xs text-gray-500 mb-1">Open Tickets</p>
            <p className="text-2xl font-bold text-yellow-400">{digest.stats.open_tickets}</p>
          </div>
        </div>

        <div className="prose prose-invert max-w-none">
          <div className="whitespace-pre-wrap text-gray-300 leading-relaxed">
            {digest.digest}
          </div>
        </div>
      </div>
    </div>
  )
}

// Main App Component
function App() {
  const [anomalies, setAnomalies] = useState([])
  const [aiAnalysis, setAiAnalysis] = useState('')
  const [question, setQuestion] = useState('')
  const [queryResult, setQueryResult] = useState(null)
  const [recentQueries, setRecentQueries] = useState([])
  const [digest, setDigest] = useState(null)
  const [showDigest, setShowDigest] = useState(false)
  const [loading, setLoading] = useState({ anomalies: false, ask: false, digest: false, upload: false, askCsv: false })
  const [error, setError] = useState(null)
  const chatEndRef = useRef(null)
  const fileInputRef = useRef(null)

  // CSV Upload state
  const [csvData, setCsvData] = useState(null)
  const [csvPreview, setCsvPreview] = useState(null)
  const [csvColumns, setCsvColumns] = useState([])
  const [csvQuestion, setCsvQuestion] = useState('')
  const [csvQueryResult, setCsvQueryResult] = useState(null)
  const [csvRecentQueries, setCsvRecentQueries] = useState([])
  const [csvError, setCsvError] = useState(null)
  const [activeTab, setActiveTab] = useState('demo') // 'demo' or 'upload'

  // Quick Stats state
  const [quickStats, setQuickStats] = useState({ total_revenue: 0, active_clients: 0, growth_rate: 'N/A' })
  const [statsLoading, setStatsLoading] = useState(true)

  const fetchQuickStats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/stats`)
      const data = await response.json()
      setQuickStats(data)
    } catch (err) {
      console.error('Error fetching stats:', err)
      setQuickStats({ total_revenue: 0, active_clients: 0, growth_rate: 'N/A' })
    } finally {
      setStatsLoading(false)
    }
  }

  const fetchAnomalies = async () => {
    setLoading(prev => ({ ...prev, anomalies: true }))
    try {
      const response = await fetch(`${API_BASE_URL}/anomalies`)
      const data = await response.json()
      setAnomalies(data.anomalies || [])
      setAiAnalysis(data.aiAnalysis || '')
    } catch (err) {
      console.error('Error fetching anomalies:', err)
      setError('Failed to load anomalies')
    } finally {
      setLoading(prev => ({ ...prev, anomalies: false }))
    }
  }

  const handleAsk = async (e) => {
    e.preventDefault()
    if (!question.trim() || loading.ask) return

    setLoading(prev => ({ ...prev, ask: true }))
    setError(null)

    try {
      const response = await fetch(`${API_BASE_URL}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question })
      })

      const data = await response.json()
      setQueryResult(data)

      // Add to recent queries
      setRecentQueries(prev => [
        { question, result: data, timestamp: new Date().toISOString() },
        ...prev.slice(0, 4)
      ])

      setQuestion('')
    } catch (err) {
      console.error('Error asking question:', err)
      setError('Failed to process your question. Make sure the backend is running.')
    } finally {
      setLoading(prev => ({ ...prev, ask: false }))
    }
  }

  const handleDigest = async () => {
    setLoading(prev => ({ ...prev, digest: true }))
    try {
      const response = await fetch(`${API_BASE_URL}/digest`)
      const data = await response.json()
      setDigest(data)
      setShowDigest(true)
    } catch (err) {
      console.error('Error fetching digest:', err)
      setError('Failed to generate digest')
    } finally {
      setLoading(prev => ({ ...prev, digest: false }))
    }
  }

  const sampleQuestions = [
    "What is the total revenue by plan type?",
    "Show me monthly revenue trends",
    "Which clients have the most support tickets?",
    "What are the most used features?",
    "How many clients do we have by country?"
  ]

  const csvSampleQuestions = [
    "What is the average value by category?",
    "Show me the top 5 items by sales",
    "What is the total count by group?",
    "Show me trends over time"
  ]

  // Fetch quick stats on mount
  useEffect(() => {
    fetchQuickStats()
  }, [])

  // CSV Upload handler
  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    if (!file.name.endsWith('.csv')) {
      setCsvError('Please upload a CSV file')
      return
    }

    setLoading(prev => ({ ...prev, upload: true }))
    setCsvError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(`${API_BASE_URL}/upload-csv`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Upload failed')
      }

      const data = await response.json()
      setCsvData(data)
      setCsvPreview(data.preview)
      setCsvColumns(data.columns)
      setCsvQueryResult(null)
      setCsvRecentQueries([])

      // After successful CSV upload, automatically call fetchAnomalies()
      fetchAnomalies()
    } catch (err) {
      console.error('Error uploading file:', err)
      setCsvError(err.message || 'Failed to upload file')
    } finally {
      setLoading(prev => ({ ...prev, upload: false }))
    }
  }

  // CSV Ask handler
  const handleCsvAsk = async (e) => {
    e.preventDefault()
    if (!csvQuestion.trim() || loading.askCsv) return

    setLoading(prev => ({ ...prev, askCsv: true }))
    setCsvError(null)

    try {
      const response = await fetch(`${API_BASE_URL}/ask-csv`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: csvQuestion })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Query failed')
      }

      const data = await response.json()
      setCsvQueryResult(data)

      setCsvRecentQueries(prev => [
        { question: csvQuestion, result: data, timestamp: new Date().toISOString() },
        ...prev.slice(0, 4)
      ])

      setCsvQuestion('')
    } catch (err) {
      console.error('Error asking question:', err)
      setCsvError(err.message || 'Failed to process your question')
    } finally {
      setLoading(prev => ({ ...prev, askCsv: false }))
    }
  }

  // Clear Data button handler - calls DELETE /clear-data API
  const clearCsvData = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/clear-data`, {
        method: 'DELETE'
      })
      if (response.ok) {
        // Set anomalies to []
        setAnomalies([])
        setAiAnalysis('')
        // Clear csv preview state
        setCsvData(null)
        setCsvPreview(null)
        setCsvColumns([])
        setCsvQueryResult(null)
        setCsvRecentQueries([])
        setCsvError(null)
        if (fileInputRef.current) {
          fileInputRef.current.value = ''
        }
      }
    } catch (err) {
      console.error('Error clearing data:', err)
      // Still reset local state even if backend call fails
      setAnomalies([])
      setAiAnalysis('')
      setCsvData(null)
      setCsvPreview(null)
      setCsvColumns([])
      setCsvQueryResult(null)
      setCsvRecentQueries([])
      setCsvError(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-40 glass border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center glow">
                <Bot className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold gradient-text">AILytics</h1>
                <p className="text-xs text-gray-500">AI-Powered Business Analyst</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={handleDigest}
                disabled={loading.digest}
                className="flex items-center gap-2 px-4 py-2 bg-background-card border border-gray-700 rounded-lg hover:border-primary/50 transition-colors text-sm"
              >
                {loading.digest ? (
                  <div className="spinner w-4 h-4" />
                ) : (
                  <Sparkles className="w-4 h-4 text-accent" />
                )}
                Weekly Digest
              </button>
              <button
                onClick={fetchAnomalies}
                className="flex items-center gap-2 px-4 py-2 bg-background-card border border-gray-700 rounded-lg hover:border-primary/50 transition-colors text-sm"
              >
                <RefreshCw className="w-4 h-4 text-gray-400" />
                Refresh
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Anomaly Banner - Show ONLY when anomalies.length > 0 */}
        {anomalies.length > 0 && (
          <section className="mb-8">
            <div className="flex items-center gap-2 mb-4">
              <AlertTriangle className="w-5 h-5 text-yellow-500" />
              <h2 className="text-lg font-semibold text-gray-200">AI-Detected Anomalies</h2>
              <span className="ml-2 px-2 py-0.5 bg-red-500/20 text-red-400 text-xs rounded-full">
                {anomalies.filter(a => a.type === 'critical').length} Critical
              </span>
            </div>

            {loading.anomalies ? (
              <div className="flex items-center justify-center h-24">
                <div className="spinner" />
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {anomalies.map((anomaly, index) => (
                  <AnomalyCard key={index} anomaly={anomaly} index={index} />
                ))}
              </div>
            )}

            {aiAnalysis && (
              <div className="mt-4 glass rounded-xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Bot className="w-4 h-4 text-primary" />
                  <p className="text-xs text-gray-500 font-medium">AI Analysis</p>
                </div>
                <p className="text-sm text-gray-300">{aiAnalysis}</p>
              </div>
            )}
          </section>
        )}

        {/* Show message when no anomalies */}
        {anomalies.length === 0 && !loading.anomalies && (
          <section className="mb-8">
            <div className="glass rounded-xl p-6 text-center text-gray-500">
              <Info className="w-8 h-8 mx-auto mb-2 text-gray-600" />
              <p>Upload a CSV file to detect anomalies</p>
            </div>
          </section>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content - Chat Section */}
          <div className="lg:col-span-2 space-y-6">
            {/* Chat Input */}
            <section className="glass rounded-xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <MessageSquare className="w-5 h-5 text-primary" />
                <h2 className="text-lg font-semibold text-gray-200">Ask Your Business Questions</h2>
              </div>

              <form onSubmit={handleAsk} className="relative">
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="E.g., What is our total revenue by plan type?"
                  className="w-full bg-background-secondary border border-gray-700 rounded-xl px-5 py-4 pr-14 text-gray-200 placeholder-gray-500 input-glow transition-all"
                />
                <button
                  type="submit"
                  disabled={loading.ask || !question.trim()}
                  className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 bg-primary rounded-lg flex items-center justify-center hover:bg-primary-light transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading.ask ? (
                    <div className="spinner w-4 h-4" />
                  ) : (
                    <Send className="w-4 h-4 text-white" />
                  )}
                </button>
              </form>

              {/* Sample Questions */}
              <div className="mt-4">
                <p className="text-xs text-gray-500 mb-2">Try these examples:</p>
                <div className="flex flex-wrap gap-2">
                  {sampleQuestions.map((q, index) => (
                    <button
                      key={index}
                      onClick={() => setQuestion(q)}
                      className="px-3 py-1.5 bg-background-card border border-gray-700 rounded-lg text-xs text-gray-400 hover:border-primary/50 hover:text-gray-200 transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </section>

            {/* Query Result */}
            {queryResult && (
              <QueryResultCard result={queryResult} question={recentQueries[0]?.question || question} />
            )}

            {error && (
              <div className="glass rounded-xl p-6 border border-red-500/30 bg-red-500/10">
                <div className="flex items-center gap-3">
                  <AlertCircle className="w-5 h-5 text-red-500" />
                  <p className="text-red-400 text-sm">{error}</p>
                </div>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Recent Queries */}
            <section className="glass rounded-xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className="w-5 h-5 text-accent" />
                <h2 className="text-lg font-semibold text-gray-200">Recent Queries</h2>
              </div>

              {recentQueries.length === 0 ? (
                <div className="text-center py-8">
                  <Activity className="w-8 h-8 mx-auto mb-2 text-gray-600" />
                  <p className="text-sm text-gray-500">No queries yet</p>
                  <p className="text-xs text-gray-600 mt-1">Ask a question to get started</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {recentQueries.map((query, index) => (
                    <div
                      key={index}
                      className="p-3 bg-background-secondary rounded-lg border border-gray-800 cursor-pointer hover:border-primary/30 transition-colors"
                      onClick={() => setQueryResult(query.result)}
                    >
                      <p className="text-sm text-gray-300 line-clamp-2">{query.question}</p>
                      <p className="text-xs text-gray-500 mt-1">
                        {new Date(query.timestamp).toLocaleTimeString()}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Quick Stats */}
            <section className="glass rounded-xl p-6">
              <h2 className="text-lg font-semibold text-gray-200 mb-4">Quick Stats</h2>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 bg-background-secondary rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-green-500/20 flex items-center justify-center">
                      <DollarSign className="w-4 h-4 text-green-400" />
                    </div>
                    <span className="text-sm text-gray-400">Total Revenue</span>
                  </div>
                  <span className="text-sm font-medium text-gray-200">
                    {statsLoading ? (
                      <span className="text-gray-500">...</span>
                    ) : quickStats.total_revenue === 0 ? (
                      <span className="text-gray-500 text-xs">Upload data to see stats</span>
                    ) : (
                      `$${quickStats.total_revenue.toLocaleString()}`
                    )}
                  </span>
                </div>
                <div className="flex items-center justify-between p-3 bg-background-secondary rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center">
                      <Users className="w-4 h-4 text-blue-400" />
                    </div>
                    <span className="text-sm text-gray-400">Active Clients</span>
                  </div>
                  <span className="text-sm font-medium text-gray-200">
                    {statsLoading ? (
                      <span className="text-gray-500">...</span>
                    ) : quickStats.active_clients === 0 ? (
                      <span className="text-gray-500 text-xs">Upload data to see stats</span>
                    ) : (
                      quickStats.active_clients
                    )}
                  </span>
                </div>
                <div className="flex items-center justify-between p-3 bg-background-secondary rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
                      <TrendingUp className="w-4 h-4 text-purple-400" />
                    </div>
                    <span className="text-sm text-gray-400">Growth Rate</span>
                  </div>
                  <span className="text-sm font-medium text-gray-200">
                    {statsLoading ? (
                      <span className="text-gray-500">...</span>
                    ) : (
                      quickStats.growth_rate
                    )}
                  </span>
                </div>
              </div>
            </section>
          </div>
        </div>
      </main>

      {/* CSV Upload Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-8">
        <div className="glass rounded-xl p-6 border-t-2 border-primary/30">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-accent to-primary flex items-center justify-center">
                <FileSpreadsheet className="w-5 h-5 text-white" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-gray-200">Upload Your Data</h2>
                <p className="text-xs text-gray-500">Upload a CSV file and ask questions about your data</p>
              </div>
            </div>
            {csvData && (
              <button
                onClick={clearCsvData}
                className="flex items-center gap-2 px-3 py-1.5 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400 hover:bg-red-500/20 transition-colors"
              >
                <X className="w-4 h-4" />
                Clear
              </button>
            )}
          </div>

          {!csvData ? (
            // Upload Area
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-gray-700 rounded-xl p-8 text-center cursor-pointer hover:border-primary/50 hover:bg-primary/5 transition-all group"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileUpload}
                className="hidden"
              />
              {loading.upload ? (
                <div className="flex flex-col items-center gap-3">
                  <div className="spinner" />
                  <p className="text-gray-400 text-sm">Uploading and processing...</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3">
                  <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                    <Upload className="w-8 h-8 text-primary" />
                  </div>
                  <div>
                    <p className="text-gray-300 font-medium">Click to upload CSV file</p>
                    <p className="text-gray-500 text-sm mt-1">or drag and drop your file here</p>
                  </div>
                  <p className="text-xs text-gray-600 mt-2">Only .csv files are supported</p>
                </div>
              )}
            </div>
          ) : (
            // CSV Data Display
            <div className="space-y-6">
              {/* Upload Success & Column Info */}
              <div className="flex items-center gap-2 text-green-400">
                <CheckCircle className="w-5 h-5" />
                <span className="text-sm font-medium">
                  {csvData.message}
                </span>
              </div>

              {/* Column Tags */}
              <div>
                <p className="text-xs text-gray-500 mb-2 font-medium">Detected Columns:</p>
                <div className="flex flex-wrap gap-2">
                  {csvColumns.map((col, index) => (
                    <span
                      key={index}
                      className="px-3 py-1 bg-primary/10 border border-primary/30 rounded-full text-xs text-primary font-mono"
                    >
                      {col}
                    </span>
                  ))}
                </div>
              </div>

              {/* Preview Table */}
              {csvPreview && csvPreview.length > 0 && (
                <div>
                  <p className="text-xs text-gray-500 mb-2 font-medium">Preview (first 5 rows):</p>
                  <div className="overflow-x-auto rounded-lg border border-gray-700">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-background-card">
                          {csvColumns.map((col, index) => (
                            <th key={index} className="px-4 py-3 text-left text-gray-300 font-medium border-b border-gray-700">
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {csvPreview.map((row, rowIndex) => (
                          <tr key={rowIndex} className="hover:bg-background-secondary/50 transition-colors">
                            {csvColumns.map((col, colIndex) => (
                              <td key={colIndex} className="px-4 py-3 text-gray-400 border-b border-gray-800">
                                {row[col] !== null ? String(row[col]) : '-'}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* CSV Chat Input */}
              <div className="border-t border-gray-700 pt-6">
                <div className="flex items-center gap-2 mb-4">
                  <MessageSquare className="w-5 h-5 text-accent" />
                  <h3 className="text-md font-semibold text-gray-200">Ask questions about your uploaded data</h3>
                </div>

                <form onSubmit={handleCsvAsk} className="relative">
                  <input
                    type="text"
                    value={csvQuestion}
                    onChange={(e) => setCsvQuestion(e.target.value)}
                    placeholder="E.g., What is the average sales by region?"
                    className="w-full bg-background-secondary border border-gray-700 rounded-xl px-5 py-4 pr-14 text-gray-200 placeholder-gray-500 input-glow transition-all"
                  />
                  <button
                    type="submit"
                    disabled={loading.askCsv || !csvQuestion.trim()}
                    className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 bg-accent rounded-lg flex items-center justify-center hover:bg-accent/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading.askCsv ? (
                      <div className="spinner w-4 h-4" />
                    ) : (
                      <Send className="w-4 h-4 text-white" />
                    )}
                  </button>
                </form>

                {/* CSV Sample Questions */}
                <div className="mt-4">
                  <p className="text-xs text-gray-500 mb-2">Try these examples:</p>
                  <div className="flex flex-wrap gap-2">
                    {csvSampleQuestions.map((q, index) => (
                      <button
                        key={index}
                        onClick={() => setCsvQuestion(q)}
                        className="px-3 py-1.5 bg-background-card border border-gray-700 rounded-lg text-xs text-gray-400 hover:border-accent/50 hover:text-gray-200 transition-colors"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>

                {/* CSV Query Result */}
                {csvQueryResult && (
                  <div className="mt-6">
                    <QueryResultCard result={csvQueryResult} question={csvRecentQueries[0]?.question || csvQuestion} />
                  </div>
                )}

                {/* CSV Recent Queries */}
                {csvRecentQueries.length > 0 && !csvQueryResult && (
                  <div className="mt-4">
                    <p className="text-xs text-gray-500 mb-2">Recent queries:</p>
                    <div className="space-y-2">
                      {csvRecentQueries.map((query, index) => (
                        <div
                          key={index}
                          className="p-3 bg-background-secondary rounded-lg border border-gray-800 cursor-pointer hover:border-accent/30 transition-colors"
                          onClick={() => setCsvQueryResult(query.result)}
                        >
                          <p className="text-sm text-gray-300">{query.question}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {csvError && (
            <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
              <div className="flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-red-500" />
                <p className="text-red-400 text-sm">{csvError}</p>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Digest Modal */}
      {showDigest && digest && (
        <DigestModal digest={digest} onClose={() => setShowDigest(false)} />
      )}

      {/* Footer */}
      <footer className="border-t border-gray-800 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <p className="text-xs text-gray-500">
              © 2024 AILytics. Powered by Groq AI.
            </p> 
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500 pulse-dot" />
              <p className="text-xs text-gray-500">System Operational</p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default App