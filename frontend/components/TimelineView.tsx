'use client'

import { useState } from 'react'
import { Search, Loader2, GitBranch } from 'lucide-react'
import clsx from 'clsx'

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

interface TimelineResponse {
  concept: string
  events: MemoryEvent[]
  total: number
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  decision: 'border-blue-400 bg-blue-400',
  belief: 'border-purple-400 bg-purple-400',
  opinion: 'border-orange-400 bg-orange-400',
  learning: 'border-green-400 bg-green-400',
  observation: 'border-slate-400 bg-slate-400',
  action: 'border-red-400 bg-red-400',
}

const CONCEPT_EXAMPLES = ['machine learning', 'react', 'career', 'remote work', 'postgresql']

export default function TimelineView() {
  const [concept, setConcept] = useState('')
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<TimelineResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchTimeline = async (c?: string) => {
    const conceptText = c || concept
    if (!conceptText.trim()) return
    setLoading(true)
    setError(null)
    if (c) setConcept(c)

    try {
      const res = await fetch(`/api/timeline?concept=${encodeURIComponent(conceptText)}`)
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      const result = await res.json()
      setData(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load timeline')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex gap-3">
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
            <GitBranch size={16} className="text-slate-400" />
          </div>
          <input
            type="text"
            value={concept}
            onChange={(e) => setConcept(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchTimeline()}
            placeholder="Enter a concept (e.g., machine learning, career, react)"
            className="w-full pl-10 pr-4 py-3 bg-slate-900/80 border border-slate-700 rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 text-sm"
          />
        </div>
        <button
          onClick={() => fetchTimeline()}
          disabled={loading || !concept.trim()}
          className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl font-medium transition-colors flex items-center gap-2 text-sm"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
          View
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {CONCEPT_EXAMPLES.map((c) => (
          <button
            key={c}
            onClick={() => fetchTimeline(c)}
            className="text-xs px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 transition-colors"
          >
            {c}
          </button>
        ))}
      </div>

      {error && (
        <div className="p-4 bg-red-900/20 border border-red-800/50 rounded-xl text-red-300 text-sm">{error}</div>
      )}

      {data && (
        <div>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-white">
              Timeline: <span className="text-indigo-400">{data.concept}</span>
            </h2>
            <span className="text-sm text-slate-400">{data.total} events</span>
          </div>

          {data.events.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <GitBranch size={32} className="mx-auto mb-3 opacity-40" />
              <p>No events found for "{data.concept}"</p>
              <p className="text-xs mt-1">Try ingesting some text first</p>
            </div>
          ) : (
            <div className="relative space-y-0">
              {data.events.map((event, index) => {
                const colorClass = EVENT_TYPE_COLORS[event.event_type] || EVENT_TYPE_COLORS.observation
                const isLast = index === data.events.length - 1
                return (
                  <div key={event.id} className="relative flex gap-6 pb-8">
                    {/* Timeline line */}
                    {!isLast && (
                      <div className="absolute left-[1.1rem] top-8 bottom-0 w-0.5 bg-indigo-900/60" />
                    )}
                    {/* Dot */}
                    <div className={clsx('w-[1.375rem] h-[1.375rem] rounded-full border-2 flex-shrink-0 mt-1', colorClass)} />
                    {/* Content */}
                    <div className="flex-1 bg-slate-900/60 border border-slate-800 rounded-xl p-4 hover:border-indigo-700/40 transition-colors">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-indigo-300 uppercase tracking-wider">
                          {event.event_type}
                        </span>
                        <span className="text-xs text-slate-500">
                          {new Date(event.timestamp).toLocaleDateString('en-US', { year: 'numeric', month: 'long' })}
                        </span>
                      </div>
                      <p className="text-sm text-slate-200 leading-relaxed">{event.text}</p>
                      {(event.importance_score !== undefined || event.memory_strength !== undefined) && (
                        <div className="flex flex-wrap gap-2 mt-2 text-[11px] text-slate-500">
                          {typeof event.importance_score === 'number' && (
                            <span className="px-2 py-0.5 rounded-full border border-slate-700 bg-slate-950/40">
                              importance {event.importance_score.toFixed(2)}
                            </span>
                          )}
                          {typeof event.memory_strength === 'number' && (
                            <span className="px-2 py-0.5 rounded-full border border-slate-700 bg-slate-950/40">
                              strength {event.memory_strength.toFixed(2)}
                            </span>
                          )}
                        </div>
                      )}
                      {event.entities.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {event.entities.slice(0, 4).map((e) => (
                            <span key={e} className="text-xs px-2 py-0.5 bg-slate-800 text-slate-400 rounded-full">{e}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
