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

const EVENT_TYPE_COLORS: Record<string, string> = {
  decision: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  belief: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
  opinion: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
  learning: 'bg-green-500/20 text-green-300 border-green-500/30',
  observation: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  action: 'bg-red-500/20 text-red-300 border-red-500/30',
}

const EVENT_TYPE_DOT: Record<string, string> = {
  decision: 'bg-blue-400',
  belief: 'bg-purple-400',
  opinion: 'bg-orange-400',
  learning: 'bg-green-400',
  observation: 'bg-slate-400',
  action: 'bg-red-400',
}

function formatDate(ts: string): string {
  try {
    return new Date(ts).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return ts
  }
}

export default function EventCard({ event }: { event: MemoryEvent }) {
  const colorClass = EVENT_TYPE_COLORS[event.event_type] || EVENT_TYPE_COLORS.observation
  const dotColor = EVENT_TYPE_DOT[event.event_type] || EVENT_TYPE_DOT.observation

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 hover:border-indigo-700/50 transition-colors">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <div className={clsx('w-2 h-2 rounded-full flex-shrink-0 mt-1', dotColor)} />
          <span className={clsx('text-xs px-2 py-0.5 rounded-full border font-medium', colorClass)}>
            {event.event_type}
          </span>
        </div>
        <span className="text-xs text-slate-500 flex-shrink-0">{formatDate(event.timestamp)}</span>
      </div>
      <p className="text-sm text-slate-200 leading-relaxed">{event.text}</p>
      {(event.topics.length > 0 || event.entities.length > 0) && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {event.topics.slice(0, 4).map((topic) => (
            <span key={topic} className="text-xs px-2 py-0.5 bg-indigo-900/40 text-indigo-300 rounded-full border border-indigo-800/50">
              {topic}
            </span>
          ))}
          {event.entities.slice(0, 3).map((entity) => (
            <span key={entity} className="text-xs px-2 py-0.5 bg-slate-800 text-slate-300 rounded-full border border-slate-700">
              {entity}
            </span>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2 mt-3 text-[11px] text-slate-500">
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
    </div>
  )
}
