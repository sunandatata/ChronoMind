'use client'

import { useMemo, useState } from 'react'
import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react'

const STAGES = [
  { title: 'Data Sources', text: 'Notes, journals, chats, documents, bookmarks' },
  { title: 'Ingestion Pipeline', text: 'Atomic event extraction, entity/topic detection, timestamping' },
  { title: 'Event Extraction', text: 'Beliefs, decisions, actions, observations, learning moments' },
  { title: 'Storage Layer', text: 'Qdrant vector store, Neo4j graph store, BM25 index' },
  { title: 'Candidate Generation', text: 'Vector, graph, temporal, and lexical retrieval channels' },
  { title: 'Ranking Pipeline', text: 'Fusion, temporal weighting, centrality, importance, diversity' },
  { title: 'Timeline Reconstruction', text: 'Chronological compression and causal ordering' },
  { title: 'Reasoning Layer', text: 'LLM answer generation grounded in retrieved memory events' },
]

export default function ArchitectureView() {
  const [zoom, setZoom] = useState(1)

  const scale = useMemo(() => `scale(${zoom})`, [zoom])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">ChronoMind Architecture</h2>
          <p className="text-sm text-slate-400">A temporal memory search engine from data source to grounded answer.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setZoom((v) => Math.max(0.7, v - 0.1))} className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-300">
            <ZoomOut size={14} />
          </button>
          <button onClick={() => setZoom(1)} className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-300">
            <Maximize2 size={14} />
          </button>
          <button onClick={() => setZoom((v) => Math.min(1.5, v + 0.1))} className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-300">
            <ZoomIn size={14} />
          </button>
        </div>
      </div>

      <div className="overflow-auto rounded-2xl border border-slate-800 bg-slate-950/50 p-6">
        <div className="min-w-[980px] space-y-5" style={{ transform: scale, transformOrigin: 'top left' }}>
          {STAGES.map((stage, index) => (
            <div key={stage.title} className="relative">
              <div className="flex items-center gap-5">
                <div className="w-56 rounded-xl border border-slate-700 bg-slate-900/80 p-4">
                  <div className="text-xs uppercase tracking-wider text-indigo-300">{String(index + 1).padStart(2, '0')}</div>
                  <div className="mt-1 text-sm font-semibold text-white">{stage.title}</div>
                  <p className="mt-2 text-xs leading-relaxed text-slate-400">{stage.text}</p>
                </div>
                {index < STAGES.length - 1 && (
                  <div className="flex-1">
                    <div className="h-px bg-slate-800" />
                    <div className="mt-1 text-[11px] uppercase tracking-wider text-slate-500">Flows into next stage</div>
                  </div>
                )}
              </div>
              {index < STAGES.length - 1 && <div className="ml-28 mt-4 h-8 border-l border-slate-800" />}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
