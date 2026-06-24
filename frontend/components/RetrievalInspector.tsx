'use client'

import { useMemo, type ReactNode } from 'react'
import { ChevronDown, ChevronRight, Gauge, GitBranch, Search, Sparkles } from 'lucide-react'

interface InspectorProps {
  debugTrace: Record<string, any>
}

function Section({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
      <div className="flex items-center gap-2 mb-3 text-sm font-medium text-white">
        {icon}
        {title}
      </div>
      {children}
    </div>
  )
}

function RankedList({ items }: { items: any[] }) {
  return (
    <div className="space-y-2">
      {items.map((item, index) => (
        <div key={`${item.id}-${index}`} className="rounded-lg border border-slate-800 bg-slate-900/50 p-3">
          <div className="flex items-center justify-between gap-2 text-xs">
            <span className="text-slate-400">#{index + 1}</span>
            <span className="text-indigo-300">{typeof item.score === 'number' ? item.score.toFixed(4) : 'n/a'}</span>
          </div>
          <p className="mt-2 text-sm text-slate-200 line-clamp-2">{item.text}</p>
          <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-500">
            {item.event_type && <span className="px-2 py-0.5 rounded-full border border-slate-700">{item.event_type}</span>}
            {item.source && <span className="px-2 py-0.5 rounded-full border border-slate-700">{item.source}</span>}
            {item.timestamp && <span className="px-2 py-0.5 rounded-full border border-slate-700">{String(item.timestamp).slice(0, 10)}</span>}
            {item.cluster && <span className="px-2 py-0.5 rounded-full border border-slate-700">{item.cluster}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function RetrievalInspector({ debugTrace }: InspectorProps) {
  const queryProfile = debugTrace?.query_profile || {}
  const candidateCounts = debugTrace?.candidate_counts || {}
  const expandedCounts = debugTrace?.candidate_counts_with_expansion || {}
  const beforeFusion = debugTrace?.top_20_before_fusion || {}
  const afterFusion = debugTrace?.top_10_after_fusion || []
  const reranked = debugTrace?.reranked_top_10 || []
  const finalEvents = debugTrace?.final_context_events || []

  const traceSections = useMemo(() => [
    { key: 'vector', label: 'Vector', icon: <Search size={14} />, items: beforeFusion.vector || [] },
    { key: 'graph', label: 'Graph', icon: <GitBranch size={14} />, items: beforeFusion.graph || [] },
    { key: 'bm25', label: 'BM25', icon: <Gauge size={14} />, items: beforeFusion.bm25 || [] },
  ], [beforeFusion])

  return (
    <div className="space-y-4">
      <Section title="Query Classification" icon={<Sparkles size={14} className="text-indigo-300" />}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <div className="text-slate-500 text-xs uppercase tracking-wider">Query Type</div>
            <div className="mt-1 text-slate-100">{queryProfile.query_type || 'unknown'}</div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <div className="text-slate-500 text-xs uppercase tracking-wider">Temporal Intent</div>
            <div className="mt-1 text-slate-100">{queryProfile.temporal_intent || 'unknown'}</div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <div className="text-slate-500 text-xs uppercase tracking-wider">Causal Intent</div>
            <div className="mt-1 text-slate-100">{String(queryProfile.causal_intent ?? false)}</div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
            <div className="text-slate-500 text-xs uppercase tracking-wider">Graph Hops</div>
            <div className="mt-1 text-slate-100">{queryProfile.graph_hops ?? 0}</div>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs text-slate-400">
          <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-2">Vector: {candidateCounts.vector ?? 0}</div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-2">Graph: {candidateCounts.graph ?? 0}</div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-2">BM25: {candidateCounts.bm25 ?? 0}</div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-2">Belief: {expandedCounts.belief ?? 0}</div>
        </div>
      </Section>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {traceSections.map((section) => (
          <Section key={section.key} title={`${section.label} candidates`} icon={section.icon}>
            <RankedList items={section.items.slice(0, 5)} />
          </Section>
        ))}
      </div>

      <Section title="Fusion + Reranking" icon={<ChevronRight size={14} className="text-indigo-300" />}>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div>
            <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">Post-fusion top 10</div>
            <RankedList items={afterFusion} />
          </div>
          <div>
            <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">Final reranked top 10</div>
            <RankedList items={reranked} />
          </div>
        </div>
      </Section>

      <Section title="Final Timeline" icon={<ChevronDown size={14} className="text-indigo-300" />}>
        <div className="space-y-2">
          {finalEvents.map((event: any, index: number) => (
            <div key={`${event.id}-${index}`} className="rounded-lg border border-slate-800 bg-slate-900/50 p-3">
              <div className="flex items-center justify-between gap-2 text-xs text-slate-400">
                <span>{index + 1}. {String(event.timestamp).slice(0, 10)}</span>
                <span>{event.event_type}</span>
              </div>
              <p className="mt-2 text-sm text-slate-200">{event.text}</p>
            </div>
          ))}
        </div>
      </Section>

      {debugTrace?.context_text && (
        <Section title="LLM Input Context" icon={<Gauge size={14} className="text-indigo-300" />}>
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-300">
            {debugTrace.context_text}
          </pre>
        </Section>
      )}
    </div>
  )
}
