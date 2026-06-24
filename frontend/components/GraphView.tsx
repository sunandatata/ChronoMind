'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { Loader2, Network, RefreshCw, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react'
import clsx from 'clsx'

interface GraphNode {
  id: string
  label: string
  node_type: string
  properties: Record<string, unknown>
}

interface GraphEdge {
  source: string
  target: string
  relationship: string
}

interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

type Point = { x: number; y: number }

const NODE_COLORS: Record<string, string> = {
  event: '#6366f1',
  concept: '#10b981',
  entity: '#f59e0b',
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  decision: '#3b82f6',
  belief: '#8b5cf6',
  opinion: '#f97316',
  learning: '#10b981',
  observation: '#64748b',
  action: '#ef4444',
}

const REL_COLORS: Record<string, string> = {
  CAUSED_BY: '#ef4444',
  INFLUENCED_BY: '#f59e0b',
  CONTRADICTS: '#a855f7',
  REFINES: '#14b8a6',
  REINFORCES: '#10b981',
  ABOUT: '#6366f1',
  MENTIONS: '#64748b',
  RELATED_TO: '#94a3b8',
}

function buildLayout(nodes: GraphNode[]): Record<string, Point> {
  const centerX = 420
  const centerY = 320
  const radius = Math.max(160, 90 + nodes.length * 8)
  return nodes.reduce<Record<string, Point>>((acc, node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(nodes.length, 1)
    acc[node.id] = {
      x: centerX + Math.cos(angle) * radius + (index % 3) * 10,
      y: centerY + Math.sin(angle) * radius + (index % 4) * 8,
    }
    return acc
  }, {})
}

export default function GraphView() {
  const [data, setData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<GraphNode | null>(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState<Point>({ x: 0, y: 0 })
  const [dragging, setDragging] = useState(false)
  const dragOrigin = useRef<Point>({ x: 0, y: 0 })
  const panOrigin = useRef<Point>({ x: 0, y: 0 })

  const fetchGraph = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/graph')
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      const result = await res.json()
      setData(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load graph')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchGraph()
  }, [])

  const positions = useMemo(() => buildLayout(data?.nodes || []), [data])
  const connections = useMemo(() => {
    if (!data || !selected) return []
    return data.edges.filter((edge) => edge.source === selected.id || edge.target === selected.id)
  }, [data, selected])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={24} className="animate-spin text-indigo-400" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4 bg-red-900/20 border border-red-800/50 rounded-xl text-red-300 text-sm">{error}</div>
    )
  }

  if (!data) return null

  const viewBox = `${-120 + pan.x} ${-40 + pan.y} ${840 / zoom} ${640 / zoom}`

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Memory Graph</h2>
          <p className="text-sm text-slate-400">{data.nodes.length} nodes · {data.edges.length} edges</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setZoom((value) => Math.max(0.6, value - 0.15))}
            className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition-colors"
          >
            <ZoomOut size={14} /> Zoom out
          </button>
          <button
            onClick={() => setZoom(1)}
            className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition-colors"
          >
            <Maximize2 size={14} /> Reset
          </button>
          <button
            onClick={() => setZoom((value) => Math.min(2, value + 0.15))}
            className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition-colors"
          >
            <ZoomIn size={14} /> Zoom in
          </button>
          <button
            onClick={fetchGraph}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition-colors"
          >
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-4 text-xs">
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
            <span className="text-slate-400 capitalize">{type} node</span>
          </div>
        ))}
        {Object.entries(REL_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1.5">
            <div className="w-3 h-0.5" style={{ backgroundColor: color }} />
            <span className="text-slate-500">{type}</span>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_19rem] gap-4">
        <div
          className="bg-slate-950/50 border border-slate-800 rounded-2xl overflow-hidden"
          onMouseDown={(event) => {
            setDragging(true)
            dragOrigin.current = { x: event.clientX, y: event.clientY }
            panOrigin.current = pan
          }}
          onMouseMove={(event) => {
            if (!dragging) return
            const dx = event.clientX - dragOrigin.current.x
            const dy = event.clientY - dragOrigin.current.y
            setPan({ x: panOrigin.current.x - dx / zoom, y: panOrigin.current.y - dy / zoom })
          }}
          onMouseUp={() => setDragging(false)}
          onMouseLeave={() => setDragging(false)}
          onWheel={(event) => {
            event.preventDefault()
            const delta = event.deltaY > 0 ? -0.1 : 0.1
            setZoom((value) => Math.min(2.4, Math.max(0.55, value + delta)))
          }}
        >
          {data.nodes.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-96 text-slate-500">
              <Network size={32} className="mb-3 opacity-40" />
              <p>No nodes yet</p>
              <p className="text-xs mt-1">Ingest some text to build the memory graph</p>
            </div>
          ) : (
            <svg viewBox={viewBox} className="w-full h-[32rem] block cursor-grab active:cursor-grabbing">
              <defs>
                <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
                </marker>
              </defs>
              {data.edges.map((edge, index) => {
                const source = positions[edge.source]
                const target = positions[edge.target]
                if (!source || !target) return null
                const isSelected = selected && (selected.id === edge.source || selected.id === edge.target)
                const color = REL_COLORS[edge.relationship] || '#64748b'
                return (
                  <g key={`${edge.source}-${edge.target}-${index}`}>
                    <line
                      x1={source.x}
                      y1={source.y}
                      x2={target.x}
                      y2={target.y}
                      stroke={color}
                      strokeWidth={isSelected ? 2.4 : 1.2}
                      strokeOpacity={isSelected ? 0.9 : 0.42}
                      markerEnd="url(#arrow)"
                    />
                  </g>
                )
              })}
              {data.nodes.map((node) => {
                const position = positions[node.id]
                if (!position) return null
                const eventType = (node.properties?.event_type as string) || ''
                const fill = node.node_type === 'event'
                  ? (EVENT_TYPE_COLORS[eventType] || NODE_COLORS.event)
                  : NODE_COLORS[node.node_type] || '#6366f1'
                const isSelected = selected?.id === node.id
                return (
                  <g key={node.id} onClick={() => setSelected(isSelected ? null : node)} style={{ cursor: 'pointer' }}>
                    <circle
                      cx={position.x}
                      cy={position.y}
                      r={isSelected ? 18 : 14}
                      fill={fill}
                      stroke={isSelected ? '#e0e7ff' : '#0f172a'}
                      strokeWidth={isSelected ? 3 : 1.5}
                    />
                    <text
                      x={position.x}
                      y={position.y + 30}
                      textAnchor="middle"
                      className="fill-slate-300"
                      style={{ fontSize: 11 }}
                    >
                      {node.label.length > 18 ? `${node.label.slice(0, 18)}…` : node.label}
                    </text>
                  </g>
                )
              })}
            </svg>
          )}
        </div>

        <div className="bg-slate-900/80 border border-slate-700 rounded-2xl p-4 h-fit">
          <h3 className="text-sm font-semibold text-white mb-3">Relationship Inspector</h3>
          {selected ? (
            <div className="space-y-3 text-xs">
              <div>
                <span className="text-slate-500">Type:</span>
                <span className="ml-2 text-slate-300 capitalize">{selected.node_type}</span>
              </div>
              <div>
                <span className="text-slate-500">Label:</span>
                <p className="mt-1 text-slate-300">{selected.label}</p>
              </div>
              {Object.entries(selected.properties).map(([k, v]) => (
                v !== undefined && v !== null && v !== '' ? (
                  <div key={k}>
                    <span className="text-slate-500 capitalize">{k.replace(/_/g, ' ')}:</span>
                    <p className="mt-0.5 text-slate-300">{Array.isArray(v) ? v.join(', ') : String(v)}</p>
                  </div>
                ) : null
              ))}
              <div>
                <span className="text-slate-500">Connections:</span>
                <span className="ml-2 text-slate-300">{connections.length}</span>
              </div>
              <div className="pt-2 border-t border-slate-800 space-y-2">
                {connections.length === 0 ? (
                  <p className="text-slate-500">No relationships connected to this node.</p>
                ) : (
                  connections.map((edge, index) => (
                    <div key={`${edge.source}-${edge.target}-${index}`} className="rounded-lg border border-slate-800 bg-slate-950/40 p-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-slate-300">{edge.relationship}</span>
                        <span className="text-slate-500 truncate">
                          {edge.source === selected.id ? edge.target : edge.source}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : (
            <div className="text-slate-500 text-sm">
              Select a node to inspect relationships, causal links, and concept connections.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
