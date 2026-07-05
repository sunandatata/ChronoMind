'use client'

import { useState } from 'react'
import QueryInterface from '@/components/QueryInterface'
import IngestPanel from '@/components/IngestPanel'
import TimelineView from '@/components/TimelineView'
import GraphView from '@/components/GraphView'
import SystemStats from '@/components/SystemStats'
import BeliefEvolutionView from '@/components/BeliefEvolutionView'
import EvaluationDashboard from '@/components/EvaluationDashboard'
import ArchitectureView from '@/components/ArchitectureView'
import { Brain, Search, Upload, GitBranch, Network } from 'lucide-react'
import clsx from 'clsx'

type Tab = 'query' | 'belief' | 'evaluation' | 'architecture' | 'ingest' | 'timeline' | 'graph'

const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'query', label: 'Query Memory', icon: <Search size={16} /> },
  { id: 'belief', label: 'Belief Evolution', icon: <GitBranch size={16} /> },
  { id: 'evaluation', label: 'Evaluation', icon: <Network size={16} /> },
  { id: 'architecture', label: 'Architecture', icon: <Brain size={16} /> },
  { id: 'ingest', label: 'Ingest', icon: <Upload size={16} /> },
  { id: 'timeline', label: 'Timeline', icon: <GitBranch size={16} /> },
  { id: 'graph', label: 'Graph', icon: <Network size={16} /> },
]

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<Tab>('query')

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-950 text-slate-100">
      <header className="border-b border-indigo-900/50 bg-slate-950/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-600 rounded-lg">
              <Brain size={20} className="text-white" />
            </div>
            <div>
              <h1 className="font-bold text-lg text-white tracking-tight">ChronoMind</h1>
              <p className="text-xs text-indigo-400">Temporal RAG Memory Engine</p>
            </div>
          </div>
          <div className="text-xs text-slate-500">v1.0.0</div>
        </div>
      </header>

      <SystemStats />

      <div className="max-w-6xl mx-auto px-6 pt-6">
        <div className="flex gap-1 bg-slate-900/60 rounded-xl p-1 w-fit border border-slate-800">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200',
                activeTab === tab.id
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/50'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              )}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <main className="max-w-6xl mx-auto px-6 py-8">
        {activeTab === 'query' && <QueryInterface />}
        {activeTab === 'belief' && <BeliefEvolutionView />}
        {activeTab === 'evaluation' && <EvaluationDashboard />}
        {activeTab === 'architecture' && <ArchitectureView />}
        {activeTab === 'ingest' && <IngestPanel />}
        {activeTab === 'timeline' && <TimelineView />}
        {activeTab === 'graph' && <GraphView />}
      </main>
    </div>
  )
}
