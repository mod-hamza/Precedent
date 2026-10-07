import { useState, useEffect, useCallback, useMemo } from 'react';
import { api, type Graph, type GraphNode, type DecisionStatus } from '../api';
import { LoadingSkeleton, ErrorState, EmptyState } from '../components/States';
import { DecisionDrawer } from '../components/DecisionDrawer';

const STATUS_COLORS: Record<DecisionStatus, string> = {
  active: '#2d8a4e',
  superseded: '#8a8a8a',
  amended: '#c27a1a',
  contested: '#c23a3a',
};

const EDGE_COLORS: Record<string, string> = {
  supersedes: '#8a8a8a',
  amends: '#c27a1a',
  refines: '#3a7ac2',
};

const NODE_W = 200;
const NODE_H = 56;
const LANE_H = 100;
const LANE_PAD = 40;
const LEFT_MARGIN = 220;
const TOP_MARGIN = 40;

export default function TimelinePage() {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<Set<DecisionStatus>>(new Set());
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    try {
      setGraph(await api.graph());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load graph');
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filteredNodes = useMemo(() => {
    if (!graph) return [];
    return graph.nodes.filter(n => {
      if (statusFilter.size > 0 && !statusFilter.has(n.status)) return false;
      if (typeFilter.size > 0 && !typeFilter.has(n.decision_type)) return false;
      return true;
    });
  }, [graph, statusFilter, typeFilter]);

  const filteredNodeIds = useMemo(() => new Set(filteredNodes.map(n => n.decision_id)), [filteredNodes]);

  const filteredEdges = useMemo(() => {
    if (!graph) return [];
    return graph.edges.filter(e => filteredNodeIds.has(e.src) && filteredNodeIds.has(e.dst));
  }, [graph, filteredNodeIds]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!graph) return <LoadingSkeleton lines={6} />;
  if (graph.nodes.length === 0) return <EmptyState title="No decisions yet" description="Ingest emails to build the timeline." />;

  const allDates = filteredNodes.map(n => new Date(n.decided_at).getTime());
  const minDate = Math.min(...allDates);
  const maxDate = Math.max(...allDates);
  const dateSpan = maxDate - minDate || 1;

  const laneMap = new Map<string, number>();
  graph.lanes.forEach((l, i) => laneMap.set(l.cluster_id, i));

  const chartW = Math.max(800, LEFT_MARGIN + 100 + NODE_W);
  const chartH = TOP_MARGIN + graph.lanes.length * (LANE_H + LANE_PAD) + 40;

  function nodePos(n: GraphNode): { x: number; y: number } {
    const t = (new Date(n.decided_at).getTime() - minDate) / dateSpan;
    const laneIdx = laneMap.get(n.cluster_id) ?? 0;
    return {
      x: LEFT_MARGIN + t * (chartW - LEFT_MARGIN - NODE_W - 40),
      y: TOP_MARGIN + laneIdx * (LANE_H + LANE_PAD) + (LANE_H - NODE_H) / 2,
    };
  }

  const nodeById = new Map(filteredNodes.map(n => [n.decision_id, n]));

  function toggleFilter<T>(set: Set<T>, val: T, setter: (s: Set<T>) => void) {
    const next = new Set(set);
    if (next.has(val)) next.delete(val); else next.add(val);
    setter(next);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-serif text-2xl font-bold text-ink">Timeline</h2>
        <div className="flex items-center gap-2">
          {(['active', 'superseded', 'amended', 'contested'] as DecisionStatus[]).map(s => (
            <button
              key={s}
              onClick={() => toggleFilter(statusFilter, s, setStatusFilter)}
              className={`text-xs px-2 py-1 rounded border capitalize transition-colors ${
                statusFilter.has(s) ? 'border-ink bg-ink text-white' : 'border-border text-ink-muted hover:border-ink-muted'
              }`}
            >
              {s}
            </button>
          ))}
          <span className="text-border mx-1">|</span>
          {['explicit', 'implicit'].map(t => (
            <button
              key={t}
              onClick={() => toggleFilter(typeFilter, t, setTypeFilter)}
              className={`text-xs px-2 py-1 rounded border capitalize transition-colors ${
                typeFilter.has(t) ? 'border-ink bg-ink text-white' : 'border-border text-ink-muted hover:border-ink-muted'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-auto bg-white border border-border rounded-lg">
        <svg width={chartW} height={chartH} className="block">
          {/* Lane backgrounds */}
          {graph.lanes.map((lane, i) => (
            <g key={lane.cluster_id}>
              <rect
                x={0}
                y={TOP_MARGIN + i * (LANE_H + LANE_PAD)}
                width={chartW}
                height={LANE_H}
                fill={i % 2 === 0 ? '#faf8f5' : '#f5f2ed'}
                rx={0}
              />
              <text
                x={12}
                y={TOP_MARGIN + i * (LANE_H + LANE_PAD) + LANE_H / 2}
                fontSize={11}
                fill="#8a8a8a"
                dominantBaseline="middle"
                className="font-sans"
              >
                {truncate(lane.topic, 28)}
              </text>
            </g>
          ))}

          {/* Edges */}
          {filteredEdges.map((edge, i) => {
            const src = nodeById.get(edge.src);
            const dst = nodeById.get(edge.dst);
            if (!src || !dst) return null;
            const p1 = nodePos(src);
            const p2 = nodePos(dst);
            const sx = p1.x + NODE_W / 2;
            const sy = p1.y + NODE_H / 2;
            const ex = p2.x + NODE_W / 2;
            const ey = p2.y + NODE_H / 2;
            const mx = (sx + ex) / 2;
            const cpOffset = Math.abs(sy - ey) < 10 ? -30 : 0;
            return (
              <g key={i}>
                <path
                  d={`M${sx},${sy} C${mx},${sy + cpOffset} ${mx},${ey + cpOffset} ${ex},${ey}`}
                  fill="none"
                  stroke={EDGE_COLORS[edge.kind] || '#ccc'}
                  strokeWidth={1.5}
                  strokeDasharray={edge.kind === 'refines' ? '4,3' : undefined}
                  markerEnd="url(#arrowhead)"
                  opacity={0.6}
                />
                <text
                  x={mx}
                  y={Math.min(sy, ey) + cpOffset - 6}
                  fontSize={9}
                  fill={EDGE_COLORS[edge.kind] || '#aaa'}
                  textAnchor="middle"
                  className="font-sans"
                >
                  {edge.kind}
                </text>
              </g>
            );
          })}

          {/* Arrowhead marker */}
          <defs>
            <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
              <polygon points="0 0, 8 3, 0 6" fill="#8a8a8a" />
            </marker>
          </defs>

          {/* Nodes */}
          {filteredNodes.map((node) => {
            const pos = nodePos(node);
            const isSuperseded = node.status === 'superseded';
            return (
              <g
                key={node.decision_id}
                onClick={() => setSelectedId(node.decision_id)}
                className="cursor-pointer"
                opacity={isSuperseded ? 0.5 : 1}
              >
                <rect
                  x={pos.x}
                  y={pos.y}
                  width={NODE_W}
                  height={NODE_H}
                  rx={6}
                  fill="white"
                  stroke={STATUS_COLORS[node.status] || '#ccc'}
                  strokeWidth={selectedId === node.decision_id ? 2.5 : 1.5}
                />
                <rect
                  x={pos.x}
                  y={pos.y}
                  width={4}
                  height={NODE_H}
                  rx={2}
                  fill={STATUS_COLORS[node.status] || '#ccc'}
                />
                <text
                  x={pos.x + 12}
                  y={pos.y + 16}
                  fontSize={10}
                  fill="#1a1a1a"
                  fontWeight={500}
                  className="font-sans"
                >
                  {node.decision_id}
                </text>
                <text
                  x={pos.x + 12}
                  y={pos.y + 32}
                  fontSize={10}
                  fill="#4a4a4a"
                  className="font-sans"
                  textDecoration={isSuperseded ? 'line-through' : undefined}
                >
                  {truncate(node.text, 26)}
                </text>
                <text
                  x={pos.x + 12}
                  y={pos.y + 46}
                  fontSize={9}
                  fill="#8a8a8a"
                  className="font-sans"
                >
                  {node.decided_at} · {node.decided_by[0]}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-ink-muted">
        <span className="font-medium text-ink-light">Edges:</span>
        {Object.entries(EDGE_COLORS).map(([kind, color]) => (
          <span key={kind} className="flex items-center gap-1">
            <span className="w-4 h-0.5 rounded" style={{ backgroundColor: color }} />
            {kind}
          </span>
        ))}
      </div>

      {selectedId && (
        <DecisionDrawer
          decisionId={selectedId}
          onClose={() => setSelectedId(null)}
          onNavigate={setSelectedId}
        />
      )}
    </div>
  );
}

function truncate(s: string, max: number): string {
  return s.length <= max ? s : s.slice(0, max - 1) + '…';
}
