'use client'

import { useEffect, useMemo, useState } from 'react'
import { RefreshCw, BarChart3 } from 'lucide-react'

interface EvaluationRun {
  run_id: string
  created_at: string
  dataset_size: number
  metrics: Record<string, number>
  queries: Array<Record<string, unknown>>
}

interface HistoryResponse {
  runs: EvaluationRun[]
}

const metricOrder = [
  'recall@k',
  'precision@k',
  'mrr',
  'ndcg@10',
  'temporal_ordering_accuracy',
  'redundancy_score',
]

export default function EvaluationDashboard() {
  const [history, setHistory] = useState<HistoryResponse>({ runs: [] })
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/evaluations', { cache: 'no-store' })
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      setHistory(await res.json())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const latest = history.runs[0]
  const metricHistory = useMemo(() => {
    const result: Record<string, number[]> = {}
    for (const key of metricOrder) {
      result[key] = history.runs.map((run) => run.metrics?.[key] ?? 0)
    }
    return result
  }, [history])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Evaluation Dashboard</h2>
          <p className="text-sm text-slate-400">Metric history and comparison runs from the live retrieval stack.</p>
        </div>
        <button
          onClick={load}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-300"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
        {metricOrder.map((key) => (
          <div key={key} className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
            <div className="text-xs uppercase tracking-wider text-slate-500">{key.replace(/_/g, ' ')}</div>
            <div className="mt-2 text-xl font-semibold text-white">
              {latest ? (latest.metrics?.[key] ?? 0).toFixed(3) : '0.000'}
            </div>
            <div className="mt-2 h-1.5 rounded-full bg-slate-800">
              <div
                className="h-1.5 rounded-full bg-indigo-500"
                style={{ width: `${Math.min((latest?.metrics?.[key] ?? 0) * 100, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-950/50 p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <BarChart3 size={16} className="text-indigo-300" />
          Metric history
        </div>
        <div className="mt-4 space-y-3">
          {metricOrder.map((key) => (
            <div key={key} className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
              <div className="text-xs uppercase tracking-wider text-slate-500">{key.replace(/_/g, ' ')}</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {metricHistory[key].map((value, index) => (
                  <span key={index} className="rounded-full border border-slate-700 bg-slate-950/40 px-2 py-0.5 text-[11px] text-slate-300">
                    {value.toFixed(3)}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-950/50 p-5">
        <div className="text-sm font-semibold text-white">Comparison runs</div>
        <div className="mt-4 space-y-3">
          {history.runs.map((run) => (
            <div key={run.run_id} className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="text-sm text-white">{run.run_id}</div>
                  <div className="text-xs text-slate-500">{new Date(run.created_at).toLocaleString()}</div>
                </div>
                <div className="text-xs text-slate-400">Dataset size {run.dataset_size}</div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
                {metricOrder.map((key) => (
                  <div key={key} className="rounded-lg border border-slate-800 bg-slate-950/50 p-2 text-xs">
                    <div className="text-slate-500">{key.replace(/_/g, ' ')}</div>
                    <div className="mt-1 text-slate-200">{(run.metrics?.[key] ?? 0).toFixed(3)}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {history.runs.length === 0 && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-sm text-slate-500">
              No evaluation history found yet. Run the evaluation harness to populate this dashboard.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
