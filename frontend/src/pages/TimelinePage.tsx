import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
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

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const CARD_W = 220;
const CARD_H = 74;
const LABEL_W = 200;
const LABEL_PAD = 12;
const CHART_LEFT = LABEL_W + 16;
const RIGHT_PAD = 16;
const AXIS_H = 36;
const GAP_X = 10;
const GAP_Y = 8;
const LANE_PAD_Y = 10;
const LANE_GAP = 14;
const MIN_CHART_W = 720;

interface CardBox {
  node: GraphNode;
  x: number;
  y: number;
  row: number;
}

interface LaneLayout {
  clusterId: string;
  topic: string;
  y: number;
  h: number;
  rows: number;
  boxes: CardBox[];
  firstMs: number;
  interesting: boolean;
}

interface EdgeGeom {
  key: string;
  kind: string;
  sx: number;
  sy: number;
  c1x: number;
  c2x: number;
  ex: number;
  ey: number;
  midX: number;
  midY: number;
}

interface Layout {
  chartW: number;
  chartH: number;
  ticks: { x: number; label: string }[];
  yearLabel: string;
  lanes: LaneLayout[];
  boxById: Map<string, { x: number; y: number }>;
  edges: EdgeGeom[];
}

export default function TimelinePage() {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<Set<DecisionStatus>>(new Set());
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set());
  const [width, setWidth] = useState(0);

  // Callback ref: the wrap div only mounts once the graph has loaded, so a
  // plain useEffect([]) would miss it.
  const roRef = useRef<ResizeObserver | null>(null);
  const attachWrap = useCallback((el: HTMLDivElement | null) => {
    roRef.current?.disconnect();
    roRef.current = null;
    if (el) {
      setWidth(el.clientWidth);
      const ro = new ResizeObserver((entries) => {
        for (const entry of entries) setWidth(entry.contentRect.width);
      });
      ro.observe(el);
      roRef.current = ro;
    }
  }, []);

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

  const layout = useMemo<Layout | null>(() => {
    if (!graph || filteredNodes.length === 0 || width < 100) return null;

    const chartW = Math.max(Math.floor(width), MIN_CHART_W);
    const chartRight = chartW - RIGHT_PAD;
    const plotW = Math.max(chartRight - CHART_LEFT, 1);

    const times = filteredNodes.map(n => new Date(n.decided_at).getTime());
    const minT = Math.min(...times);
    const maxT = Math.max(...times);

    const dMin = new Date(minT);
    const domainStart = new Date(dMin.getFullYear(), dMin.getMonth(), 1);
    const dMax = new Date(maxT);
    const domainEnd = new Date(dMax.getFullYear(), dMax.getMonth() + 1, 1);
    const span = Math.max(domainEnd.getTime() - domainStart.getTime(), 1);

    const xOf = (t: number) => CHART_LEFT + ((t - domainStart.getTime()) / span) * plotW;
    const clampX = (x: number) => Math.min(Math.max(x, CHART_LEFT), Math.max(chartRight - CARD_W, CHART_LEFT));

    const ticks: { x: number; label: string }[] = [];
    const cursor = new Date(domainStart);
    while (cursor <= domainEnd) {
      ticks.push({ x: xOf(cursor.getTime()), label: MONTHS[cursor.getMonth()] });
      cursor.setMonth(cursor.getMonth() + 1);
    }
    const yearStart = domainStart.getFullYear();
    const yearEnd = new Date(domainEnd.getTime() - 1).getFullYear();
    const yearLabel = yearStart === yearEnd ? String(yearStart) : `${yearStart}–${yearEnd}`;

    const topicByCluster = new Map(graph.lanes.map(l => [l.cluster_id, l.topic]));

    const groups = new Map<string, GraphNode[]>();
    for (const n of filteredNodes) {
      const arr = groups.get(n.cluster_id);
      if (arr) arr.push(n);
      else groups.set(n.cluster_id, [n]);
    }

    const lanes: LaneLayout[] = [];
    for (const [clusterId, nodes] of groups) {
      const sorted = [...nodes].sort((a, b) => {
        if (a.decided_at !== b.decided_at) return a.decided_at < b.decided_at ? -1 : 1;
        return a.decision_id.localeCompare(b.decision_id);
      });

      // Collision-free row packing: each row tracks the right edge of its last card.
      const rowEnds: number[] = [];
      const boxes: CardBox[] = [];
      for (const n of sorted) {
        const x = clampX(xOf(new Date(n.decided_at).getTime()) - CARD_W / 2);
        let row = rowEnds.findIndex(end => x >= end + GAP_X);
        if (row === -1) {
          rowEnds.push(x + CARD_W);
          row = rowEnds.length - 1;
        } else {
          rowEnds[row] = x + CARD_W;
        }
        boxes.push({ node: n, x, y: 0, row });
      }

      const rows = rowEnds.length;
      lanes.push({
        clusterId,
        topic: topicByCluster.get(clusterId) ?? clusterId,
        y: 0,
        h: rows * CARD_H + (rows - 1) * GAP_Y + 2 * LANE_PAD_Y,
        rows,
        boxes,
        firstMs: new Date(sorted[0].decided_at).getTime(),
        interesting: boxes.some(b => b.node.status === 'contested') || boxes.length > 2,
      });
    }

    lanes.sort((a, b) => {
      if (a.interesting !== b.interesting) return a.interesting ? -1 : 1;
      if (a.firstMs !== b.firstMs) return a.firstMs - b.firstMs;
      return a.clusterId.localeCompare(b.clusterId);
    });

    let yCursor = AXIS_H;
    const boxById = new Map<string, { x: number; y: number }>();
    for (const lane of lanes) {
      lane.y = yCursor;
      for (const box of lane.boxes) {
        box.y = lane.y + LANE_PAD_Y + box.row * (CARD_H + GAP_Y);
        boxById.set(box.node.decision_id, { x: box.x, y: box.y });
      }
      yCursor += lane.h + LANE_GAP;
    }
    const chartH = yCursor - LANE_GAP + 8;

    // Edges run from the right edge of the older card (dst) to the left edge of
    // the newer card (src); the API's src is always the newer decision.
    const edges: EdgeGeom[] = [];
    for (const e of filteredEdges) {
      const srcBox = boxById.get(e.src);
      const dstBox = boxById.get(e.dst);
      if (!srcBox || !dstBox) continue;
      const sx = dstBox.x + CARD_W;
      const sy = dstBox.y + CARD_H / 2;
      const ex = srcBox.x;
      const ey = srcBox.y + CARD_H / 2;
      const dx = Math.min(Math.max(Math.abs(ex - sx) * 0.4, 24), 90) * (ex >= sx ? 1 : -1);
      const c1x = sx + dx;
      const c2x = ex - dx;
      edges.push({
        key: `${e.src}-${e.dst}`,
        kind: e.kind,
        sx, sy, c1x, c2x, ex, ey,
        midX: (sx + 3 * c1x + 3 * c2x + ex) / 8,
        midY: (sy + ey) / 2,
      });
    }

    return { chartW, chartH, ticks, yearLabel, lanes, boxById, edges };
  }, [graph, filteredNodes, filteredEdges, width]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!graph) return <LoadingSkeleton lines={6} />;
  if (graph.nodes.length === 0) return <EmptyState title="No decisions yet" description="Ingest emails to build the timeline." />;

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

      <div ref={attachWrap} className="bg-white border border-border rounded-lg overflow-x-auto">
        {!layout ? (
          <div className="text-sm text-ink-muted px-4 py-8 text-center">
            {filteredNodes.length === 0 ? 'No decisions match the current filters.' : 'Measuring…'}
          </div>
        ) : (
          <svg width={layout.chartW} height={layout.chartH} className="block">
            <defs>
              {Object.entries(EDGE_COLORS).map(([kind, color]) => (
                <marker
                  key={kind}
                  id={`arrow-${kind}`}
                  viewBox="0 0 9 7"
                  refX="9"
                  refY="3.5"
                  markerWidth="9"
                  markerHeight="7"
                  orient="auto"
                  markerUnits="userSpaceOnUse"
                >
                  <path d="M0,0 L9,3.5 L0,7 Z" fill={color} />
                </marker>
              ))}
            </defs>

            {/* Lane backgrounds and labels */}
            {layout.lanes.map((lane, i) => (
              <g key={lane.clusterId}>
                <rect
                  x={0}
                  y={lane.y}
                  width={layout.chartW}
                  height={lane.h}
                  fill={i % 2 === 0 ? '#faf8f5' : '#f5f2ed'}
                />
                <foreignObject x={LABEL_PAD} y={lane.y} width={LABEL_W - LABEL_PAD - 6} height={lane.h}>
                  <div className="flex h-full items-center" style={{ pointerEvents: 'none' }}>
                    <div className="font-sans text-[12px] leading-snug text-ink line-clamp-2">
                      {lane.topic}
                    </div>
                  </div>
                </foreignObject>
              </g>
            ))}

            {/* Month axis with gridlines */}
            <g>
              {layout.ticks.map(t => (
                <line
                  key={`grid-${t.label}-${t.x.toFixed(0)}`}
                  x1={t.x}
                  y1={AXIS_H - 4}
                  x2={t.x}
                  y2={layout.chartH}
                  stroke="#e5e0d8"
                  strokeWidth={1}
                />
              ))}
              <line
                x1={CHART_LEFT}
                y1={AXIS_H - 4}
                x2={layout.chartW - RIGHT_PAD}
                y2={AXIS_H - 4}
                stroke="#e5e0d8"
                strokeWidth={1}
              />
              {layout.ticks.map(t => (
                <text
                  key={`tick-${t.label}-${t.x.toFixed(0)}`}
                  x={t.x}
                  y={AXIS_H - 10}
                  fontSize={10}
                  fill="#8a8a8a"
                  textAnchor="middle"
                  className="font-sans"
                >
                  {t.label}
                </text>
              ))}
              <text
                x={layout.chartW - RIGHT_PAD}
                y={13}
                fontSize={10}
                fill="#4a4a4a"
                textAnchor="end"
                className="font-sans"
              >
                {layout.yearLabel}
              </text>
            </g>

            {/* Edges: older (dst) right edge → newer (src) left edge */}
            {layout.edges.map(e => (
              <path
                key={e.key}
                d={`M${e.sx},${e.sy} C${e.c1x},${e.sy} ${e.c2x},${e.ey} ${e.ex},${e.ey}`}
                fill="none"
                stroke={EDGE_COLORS[e.kind] || '#8a8a8a'}
                strokeWidth={1.5}
                strokeDasharray={e.kind === 'refines' ? '5,3' : undefined}
                markerEnd={`url(#arrow-${e.kind})`}
                opacity={0.65}
              />
            ))}

            {/* Decision cards */}
            {layout.lanes.flatMap(lane =>
              lane.boxes.map(box => {
                const node = box.node;
                const color = STATUS_COLORS[node.status] || '#8a8a8a';
                const isSuperseded = node.status === 'superseded';
                const isSelected = selectedId === node.decision_id;
                const first = node.decided_by[0] ?? 'Unknown';
                const extra = node.decided_by.length > 1 ? ` +${node.decided_by.length - 1}` : '';
                const chips: { label: string; fg: string; bg: string }[] = [];
                if (node.decision_type === 'implicit') chips.push({ label: 'Implicit', fg: '#7c6fb0', bg: '#f0edf8' });
                if (node.authority_flag) chips.push({ label: 'Authority?', fg: '#c27a1a', bg: '#fef3e2' });
                if (node.cross_thread) chips.push({ label: 'Cross-thread', fg: '#3a7ac2', bg: '#e8f0fa' });
                return (
                  <g
                    key={node.decision_id}
                    data-decision-id={node.decision_id}
                    onClick={() => setSelectedId(node.decision_id)}
                    className="cursor-pointer"
                    opacity={isSuperseded ? 0.5 : 1}
                  >
                    <rect
                      x={box.x}
                      y={box.y}
                      width={CARD_W}
                      height={CARD_H}
                      rx={6}
                      fill="white"
                      stroke={color}
                      strokeWidth={isSelected ? 2.5 : 1.5}
                    />
                    <rect x={box.x} y={box.y} width={4} height={CARD_H} rx={2} fill={color} />
                    <foreignObject x={box.x + 10} y={box.y + 7} width={CARD_W - 18} height={30}>
                      <div
                        className={`font-serif text-[11px] leading-[1.35] text-ink line-clamp-2 ${isSuperseded ? 'line-through' : ''}`}
                        style={{ pointerEvents: 'none' }}
                      >
                        {node.text}
                      </div>
                    </foreignObject>
                    <text x={box.x + 10} y={box.y + 49} fontSize={8.5} fill="#8a8a8a" className="font-sans">
                      {node.decision_id} · {node.decided_at} · {first}{extra}
                    </text>
                    {(() => {
                      let cx = box.x + 10;
                      return chips.map(chip => {
                        const w = chip.label.length * 4.8 + 9;
                        const el = (
                          <g key={chip.label}>
                            <rect x={cx} y={box.y + 56} width={w} height={15} rx={3} fill={chip.bg} />
                            <text
                              x={cx + w / 2}
                              y={box.y + 63.5 + 3}
                              fontSize={8.5}
                              fill={chip.fg}
                              textAnchor="middle"
                              className="font-sans"
                              style={{ pointerEvents: 'none' }}
                            >
                              {chip.label}
                            </text>
                          </g>
                        );
                        cx += w + 4;
                        return el;
                      });
                    })()}
                  </g>
                );
              }),
            )}

            {/* Edge labels on white pills, drawn above cards so they stay readable */}
            {layout.edges.map(e => {
              const w = e.kind.length * 5.4 + 10;
              const color = EDGE_COLORS[e.kind] || '#8a8a8a';
              return (
                <g key={`pill-${e.key}`} style={{ pointerEvents: 'none' }}>
                  <rect
                    x={e.midX - w / 2}
                    y={e.midY - 7}
                    width={w}
                    height={14}
                    rx={7}
                    fill="white"
                    stroke={color}
                    strokeWidth={0.75}
                  />
                  <text
                    x={e.midX}
                    y={e.midY + 3.2}
                    fontSize={9}
                    fill={color}
                    textAnchor="middle"
                    className="font-sans"
                  >
                    {e.kind}
                  </text>
                </g>
              );
            })}
          </svg>
        )}
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
