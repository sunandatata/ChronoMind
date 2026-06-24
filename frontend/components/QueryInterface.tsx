'use client'

import { useState } from 'react'
import { Search, Loader2, Brain, Sparkles } from 'lucide-react'
import EventCard from './EventCard'
import RetrievalInspector from './RetrievalInspector'

interface MemoryEvent {
  id: string
  text: string
  timestamp: string
  event_type: string
  entities: string[]
  topics: string[]
  sentiment?: number
  importance_score?: number
  memory_strength?: number
}

interface QueryResponse {
  answer: string
  source_events: MemoryEvent[]
  query_type: string
  events_searched: number
  confidence?: number
  debug_trace?: Record<string, any>
}

const EXAMPLE_QUERIES = [
  'What led me to my major decisions?',
  'How has my opinion evolved over time?',
  'When did I first learn about machine learning?',
  'What influenced my technology choices?',
]

export default function QueryInterface() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<QueryResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleQuery = async (q?: string) => {
    const queryText = q || query
    if (!queryText.trim()) return

    setLoading(true)
    setError(null)
    setResponse(null)
    if (q) setQuery(q)

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: queryText, top_k: 8 }),
      })
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      const data = await res.json()
      setResponse(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Query failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="relative">
        <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
          <Search size={18} className="text-slate-400" />
        </div>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
          placeholder="What led me to decide X? How has my view on Y changed over time?"
          className="w-full pl-12 pr-32 py-4 bg-slate-900/80 border border-slate-700 rounded-2xl text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 text-sm"
        />
        <button
          onClick={() => handleQuery()}
          disabled={loading || !query.trim()}
          className="absolute right-2 top-2 bottom-2 px-5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl text-sm font-medium transition-colors flex items-center gap-2"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Brain size={14} />}
          {loading ? 'Thinking...' : 'Query'}
        </button>
      </div>

      {!response && !loading && (
        <div>
          <p className="text-xs text-slate-500 mb-2">Try asking:</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                onClick={() => handleQuery(q)}
                className="text-xs px-3 py-1.5 bg-slate-800/80 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-900/20 border border-red-800/50 rounded-xl text-red-300 text-sm">
          {error}
        </div>
      )}

      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-slate-800/40 rounded-xl animate-pulse" />
          ))}
        </div>
      )}

      {response && (
        <div className="space-y-6">
          <div className="bg-indigo-950/40 border border-indigo-800/50 rounded-2xl p-6">
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <Brain size={16} className="text-indigo-400" />
              <span className="text-xs font-medium text-indigo-400 uppercase tracking-wider">
                ChronoMind Analysis
              </span>
              <span className="ml-auto text-xs text-slate-500">
                {response.events_searched} events · {response.query_type.replace(/_/g, ' ')}
              </span>
            </div>
            <div className="flex flex-wrap gap-2 mb-4 text-xs">
              <span className="px-2 py-1 rounded-full border border-slate-700 bg-slate-950/40 text-slate-300">
                confidence {(response.confidence ?? 0).toFixed(2)}
              </span>
              <span className="px-2 py-1 rounded-full border border-slate-700 bg-slate-950/40 text-slate-300">
                source events {response.source_events.length}
              </span>
            </div>
            <p className="text-slate-200 text-sm leading-relaxed whitespace-pre-wrap">{response.answer}</p>
          </div>

          {response.source_events.length > 0 && (
            <div>
              <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-3">
                Supporting Memory Events ({response.source_events.length})
              </h3>
              <div className="space-y-3">
                {response.source_events.map((event) => (
                  <EventCard key={event.id} event={event} />
                ))}
              </div>
            </div>
          )}

          {response.debug_trace && Object.keys(response.debug_trace).length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-400 uppercase tracking-wider">
                <Sparkles size={14} />
                Retrieval Inspector
              </div>
              <RetrievalInspector debugTrace={response.debug_trace} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
