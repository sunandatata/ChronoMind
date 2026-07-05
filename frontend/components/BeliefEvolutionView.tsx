'use client'

import { useState } from 'react'
import { Loader2, Search, Sparkles } from 'lucide-react'

interface BeliefEvent {
  id: string
  text: string
  timestamp: string
  event_type: string
  relationship: string
  role: string
  sentiment?: number | null
  importance_score?: number | null
  memory_strength?: number | null
}

interface BeliefResponse {
  concept: string
  timeline: BeliefEvent[]
  links: Array<{ source: string; target: string; relationship: string }>
  belief_edges: Record<string, number>
}

const EXAMPLES = ['react', 'remote work', 'postgresql', 'machine learning', 'career']

export default function BeliefEvolutionView() {
  const [concept, setConcept] = useState('react')
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<BeliefResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = async (value?: string) => {
    const term = value || concept
    if (!term.trim()) return
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/beliefs/${encodeURIComponent(term)}`, { cache: 'no-store' })
      if (!response.ok) throw new Error(`API error: ${response.status}`)
      setData(await response.json())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load belief evolution')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex gap-3">
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
            <Sparkles size={16} className="text-slate-400" />
          </div>
          <input
            value={concept}
            onChange={(e) => setConcept(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && load()}
            placeholder="Concept or opinion topic"
            className="w-full rounded-xl border border-slate-700 bg-slate-900/80 py-3 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
          />
        </div>
        <button
          onClick={() => load()}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-50"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
          View
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((item) => (
          <button
            key={item}
            onClick={() => {
              setConcept(item)
              load(item)
            }}
            className="rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700"
          >
            {item}
          </button>
        ))}
      </div>

      {error && <div className="rounded-xl border border-red-800/50 bg-red-900/20 p-4 text-sm text-red-300">{error}</div>}

      {data && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-950/50 p-5">
            <div className="text-xs uppercase tracking-wider text-slate-500">Concept</div>
            <h2 className="mt-1 text-lg font-semibold text-white">{data.concept}</h2>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
              <span className="rounded-full border border-slate-700 bg-slate-900/60 px-3 py-1">Contradictions: {data.belief_edges.CONTRADICTS ?? 0}</span>
              <span className="rounded-full border border-slate-700 bg-slate-900/60 px-3 py-1">Refinements: {data.belief_edges.REFINES ?? 0}</span>
              <span className="rounded-full border border-slate-700 bg-slate-900/60 px-3 py-1">Reinforcements: {data.belief_edges.REINFORCES ?? 0}</span>
            </div>
          </div>

          <div className="space-y-3">
            {data.timeline.map((event, index) => (
              <div key={event.id} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                <div className="flex items-center justify-between gap-3 text-xs text-slate-500">
                  <span>{new Date(event.timestamp).getFullYear()}</span>
                  <span>{event.relationship || event.role || event.event_type}</span>
                </div>
                <p className="mt-2 text-sm text-slate-200">{event.text}</p>
                <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-500">
                  {typeof event.importance_score === 'number' && <span className="rounded-full border border-slate-700 bg-slate-950/40 px-2 py-0.5">importance {event.importance_score.toFixed(2)}</span>}
                  {typeof event.memory_strength === 'number' && <span className="rounded-full border border-slate-700 bg-slate-950/40 px-2 py-0.5">strength {event.memory_strength.toFixed(2)}</span>}
                </div>
                {index < data.timeline.length - 1 && (
                  <div className="mt-4 border-l border-slate-800 pl-4 text-xs text-slate-500">
                    ↓
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
