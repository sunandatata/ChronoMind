'use client'

import { useState } from 'react'
import { Upload, CheckCircle, Loader2 } from 'lucide-react'

interface IngestResponse {
  events_extracted: number
  event_ids: string[]
  message: string
}

const SOURCE_TYPES = ['manual', 'note', 'email', 'chat', 'document', 'bookmark']

const DEMO_TEXT = `March 2021: Started learning machine learning from Andrew Ng's Coursera course. Found the math intimidating at first but pushed through. I believe ML will be crucial for my career. Decided to dedicate 2 hours every morning to studying.

September 2021: Completed the ML course. Built my first neural network from scratch in NumPy. The backpropagation implementation finally clicked after reading cs231n notes three times. I now feel confident enough to apply ML to real problems.`

export default function IngestPanel() {
  const [text, setText] = useState('')
  const [timestamp, setTimestamp] = useState('')
  const [source, setSource] = useState('manual')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<IngestResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleIngest = async () => {
    if (!text.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const body: Record<string, string> = { text, source }
      if (timestamp) body.timestamp = new Date(timestamp).toISOString()

      const res = await fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      const data = await res.json()
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ingestion failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wider">
            Text to Ingest
          </label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste your notes, journal entries, emails, or any personal text here..."
            rows={10}
            className="w-full px-4 py-3 bg-slate-900/80 border border-slate-700 rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 text-sm resize-none"
          />
          <button
            onClick={() => setText(DEMO_TEXT)}
            className="mt-1 text-xs text-indigo-400 hover:text-indigo-300"
          >
            Load sample text
          </button>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wider">
              Timestamp (optional)
            </label>
            <input
              type="datetime-local"
              value={timestamp}
              onChange={(e) => setTimestamp(e.target.value)}
              className="w-full px-4 py-2.5 bg-slate-900/80 border border-slate-700 rounded-xl text-slate-100 focus:outline-none focus:border-indigo-500 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1.5 uppercase tracking-wider">
              Source Type
            </label>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="w-full px-4 py-2.5 bg-slate-900/80 border border-slate-700 rounded-xl text-slate-100 focus:outline-none focus:border-indigo-500 text-sm"
            >
              {SOURCE_TYPES.map((s) => (
                <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
              ))}
            </select>
          </div>
        </div>

        <button
          onClick={handleIngest}
          disabled={loading || !text.trim()}
          className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-medium transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <><Loader2 size={16} className="animate-spin" /> Extracting events...</>
          ) : (
            <><Upload size={16} /> Ingest & Extract Events</>
          )}
        </button>
      </div>

      {error && (
        <div className="p-4 bg-red-900/20 border border-red-800/50 rounded-xl text-red-300 text-sm">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="flex items-center gap-3 p-4 bg-green-900/20 border border-green-800/50 rounded-xl">
            <CheckCircle size={18} className="text-green-400" />
            <div>
              <p className="text-green-300 font-medium text-sm">{result.message}</p>
              <p className="text-green-400/70 text-xs mt-0.5">{result.events_extracted} atomic memory events extracted and indexed</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
