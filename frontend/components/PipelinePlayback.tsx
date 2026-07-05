'use client'

import { useMemo, useState, type ReactNode } from 'react'
import { ChevronRight, PlayCircle } from 'lucide-react'

type PlaybackStep = {
  step: number
  title: string
  items: any[]
}

export default function PipelinePlayback({ steps }: { steps: PlaybackStep[] }) {
  const [activeStep, setActiveStep] = useState(0)

  const normalized = useMemo(() => steps || [], [steps])
  if (!normalized.length) return null

  const selected = normalized[activeStep] || normalized[0]

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/50 p-5 space-y-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-white">
        <PlayCircle size={16} className="text-indigo-300" />
        Retrieval Pipeline Playback
      </div>
      <div className="flex flex-wrap gap-2">
        {normalized.map((step, index) => (
          <button
            key={step.step}
            onClick={() => setActiveStep(index)}
            className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs transition-colors ${
              index === activeStep
                ? 'border-indigo-500 bg-indigo-600/20 text-indigo-200'
                : 'border-slate-800 bg-slate-900/60 text-slate-400 hover:text-slate-200'
            }`}
          >
            <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[11px]">{step.step}</span>
            {step.title}
          </button>
        ))}
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-wider text-slate-500">Current step</div>
            <div className="text-sm text-white">{selected.title}</div>
          </div>
          <ChevronRight size={14} className="text-slate-500" />
        </div>
        <div className="mt-3 space-y-2">
          {selected.items.slice(0, 8).map((item, index) => (
            <div key={index} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-300">
              <pre className="whitespace-pre-wrap break-words">
                {JSON.stringify(item, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
