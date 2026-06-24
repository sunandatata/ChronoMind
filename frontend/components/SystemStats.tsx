'use client'

import { useEffect, useState } from 'react'
import { Database, Layers3, Network, TimerReset, RefreshCw } from 'lucide-react'

interface StatsData {
  total_memories: number
  vector_memories: number
  total_concepts: number
  total_entities: number
  graph_edges: number
  graph_density: number
}

export default function SystemStats() {
  const [data, setData] = useState<StatsData | null>(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/stats', { cache: 'no-store' })
      if (!response.ok) throw new Error(`API error: ${response.status}`)
      const result = await response.json()
      setData(result)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const cards = [
    { label: 'Memories', value: data ? data.vector_memories ?? data.total_memories : 0, icon: <Database size={14} /> },
    { label: 'Concepts', value: data?.total_concepts ?? 0, icon: <Layers3 size={14} /> },
    { label: 'Entities', value: data?.total_entities ?? 0, icon: <Network size={14} /> },
    { label: 'Density', value: data ? data.graph_density.toFixed(4) : '0.0000', icon: <TimerReset size={14} /> },
  ]

  return (
    <section className="border-b border-slate-800 bg-slate-950/60">
      <div className="max-w-6xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between gap-4 mb-3">
          <h2 className="text-sm font-semibold text-white">System Dashboard</h2>
          <button
            onClick={load}
            className="inline-flex items-center gap-2 text-xs px-3 py-2 rounded-lg border border-slate-700 bg-slate-900/70 text-slate-300 hover:bg-slate-800"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            Refresh stats
          </button>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {cards.map((card) => (
            <div key={card.label} className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>{card.label}</span>
                <span>{card.icon}</span>
              </div>
              <div className="mt-2 text-lg font-semibold text-white">{card.value}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
