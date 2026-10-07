import { useState, useEffect, useCallback } from 'react';
import { api, type EvalResult } from '../api';
import { LoadingSkeleton, ErrorState, EmptyState } from '../components/States';

interface MetricDef {
  key: string;
  label: string;
  targetKey: string;
  format: (v: unknown) => string;
  compare: (v: unknown, t: unknown) => boolean;
}

const METRICS: MetricDef[] = [
  { key: 'decision_recall', label: 'Decision Recall', targetKey: 'decision_recall', format: pct, compare: gte },
  { key: 'decision_precision', label: 'Decision Precision', targetKey: 'decision_precision', format: pct, compare: gte },
  { key: 'near_decision_fp', label: 'Near-Decision FPs', targetKey: 'near_decision_fp_max', format: num, compare: lte },
  { key: 'supersession_accuracy', label: 'Supersession Accuracy', targetKey: 'supersession_accuracy', format: pct, compare: gte },
  { key: 'conflicts_detected', label: 'Conflicts Detected', targetKey: 'conflicts_min', format: num, compare: gte },
  { key: 'evidence_support', label: 'Evidence Support', targetKey: 'evidence_support', format: pct, compare: gte },
  { key: 'qa_accuracy', label: 'Q&A Accuracy', targetKey: 'qa_accuracy', format: pct, compare: gte },
  { key: 'no_decision_correct', label: 'No-Decision Correct', targetKey: 'no_decision_correct', format: frac, compare: gte },
  { key: 'latency_p50_ms', label: 'Latency p50', targetKey: 'latency_p50_ms', format: ms, compare: lte },
];

const GLOBAL_METRICS: MetricDef[] = [
  { key: 'quote_validity', label: 'Quote Validity', targetKey: 'quote_validity', format: pct, compare: gte },
  { key: 'pipeline_minutes', label: 'Pipeline Minutes', targetKey: 'pipeline_minutes', format: (v) => `${Number(v).toFixed(1)} min`, compare: lte },
];

export default function ScorecardPage() {
  const [evalData, setEvalData] = useState<EvalResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeSplit, setActiveSplit] = useState<'dev' | 'holdout'>('dev');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setEvalData(await api.evalLatest());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load evaluation');
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!evalData) return <LoadingSkeleton lines={8} />;

  const split = evalData.splits[activeSplit];
  if (!split) return <EmptyState title={`No ${activeSplit} split data`} />;

  const targets = evalData.targets;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-serif text-2xl font-bold text-ink">Scorecard</h2>
        <div className="flex items-center gap-1 bg-border-light rounded-lg p-0.5">
          {(['dev', 'holdout'] as const).filter(s => evalData.splits[s]).map(s => (
            <button
              key={s}
              onClick={() => setActiveSplit(s)}
              className={`px-4 py-1.5 text-xs font-medium rounded-md capitalize transition-colors ${
                activeSplit === s ? 'bg-white text-ink shadow-sm' : 'text-ink-muted hover:text-ink'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Banner */}
      <div className="bg-amended-bg/40 border border-amended/20 rounded-lg px-6 py-3 text-sm text-amended">
        {evalData.banner}
      </div>

      {/* Global metrics */}
      <div className="grid grid-cols-2 gap-3">
        {GLOBAL_METRICS.map((m) => {
          const val = evalData.global[m.key];
          const target = targets[m.targetKey];
          const met = val != null && target != null && m.compare(val, target);
          return (
            <MetricTile key={m.key} label={m.label} value={m.format(val)} target={m.format(target)} met={met} />
          );
        })}
      </div>

      {/* Split metrics */}
      <div className="grid grid-cols-3 gap-3">
        {METRICS.map((m) => {
          const val = (split as Record<string, unknown>)[m.key];
          const target = targets[m.targetKey];
          const met = val != null && target != null && m.compare(val, target);
          return (
            <MetricTile key={m.key} label={m.label} value={m.format(val)} target={m.format(target)} met={met} />
          );
        })}
      </div>

      {/* Decisions table */}
      {split.decisions_table && split.decisions_table.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-ink-light mb-3">Decisions ({split.decisions_table.length})</h3>
          <div className="bg-white border border-border rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-border-light/30">
                  <th className="text-left px-4 py-2 font-medium text-ink-muted">GT ID</th>
                  <th className="text-left px-4 py-2 font-medium text-ink-muted">Ground Truth</th>
                  <th className="text-left px-4 py-2 font-medium text-ink-muted">Result</th>
                  <th className="text-left px-4 py-2 font-medium text-ink-muted">Predicted</th>
                </tr>
              </thead>
              <tbody>
                {split.decisions_table.map((row) => (
                  <>
                    <tr
                      key={row.gt_id}
                      onClick={() => setExpandedRow(expandedRow === row.gt_id ? null : row.gt_id)}
                      className="border-b border-border-light hover:bg-border-light/20 cursor-pointer"
                    >
                      <td className="px-4 py-2 font-mono text-ink-muted">{row.gt_id}</td>
                      <td className="px-4 py-2 text-ink">{row.gt_text}</td>
                      <td className="px-4 py-2">
                        <MatchBadge match={row.result} />
                      </td>
                      <td className="px-4 py-2 text-ink-muted">{row.pred_id ?? '—'}</td>
                    </tr>
                    {expandedRow === row.gt_id && (
                      <tr key={`${row.gt_id}-detail`} className="bg-border-light/20">
                        <td colSpan={4} className="px-4 py-3">
                          <div className="grid grid-cols-2 gap-4 text-xs">
                            <div>
                              <div className="font-medium text-ink-light mb-1">Ground Truth</div>
                              <div className="text-ink">{row.gt_text}</div>
                              {row.gt_status && <div className="text-ink-muted mt-1">Status: {row.gt_status}</div>}
                            </div>
                            <div>
                              <div className="font-medium text-ink-light mb-1">Predicted</div>
                              <div className="text-ink">{row.pred_text ?? 'No match'}</div>
                              {row.pred_status && (
                                <div className="text-ink-muted mt-1">Status: {row.pred_status}</div>
                              )}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Q&A table */}
      {split.qa && split.qa.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-ink-light mb-3">Q&A ({split.qa.length})</h3>
          <div className="bg-white border border-border rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-border-light/30">
                  <th className="text-left px-4 py-2 font-medium text-ink-muted">Question</th>
                  <th className="text-left px-4 py-2 font-medium text-ink-muted">Score</th>
                  <th className="text-left px-4 py-2 font-medium text-ink-muted">Status</th>
                  <th className="text-left px-4 py-2 font-medium text-ink-muted">Expected</th>
                </tr>
              </thead>
              <tbody>
                {split.qa.map((row, i) => (
                  <tr key={i} className="border-b border-border-light">
                    <td className="px-4 py-2 text-ink max-w-md">{row.question}</td>
                    <td className="px-4 py-2">
                      <span className={`font-medium ${row.score >= 1 ? 'text-active' : row.score >= 0.5 ? 'text-amended' : 'text-contested'}`}>
                        {row.score.toFixed(1)}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-ink-muted capitalize">{row.status}</td>
                    <td className="px-4 py-2 text-ink-muted capitalize">{row.expected_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricTile({ label, value, target, met }: { label: string; value: string; target: string; met: boolean }) {
  return (
    <div className={`p-4 rounded-lg border ${met ? 'bg-active-bg/30 border-active/20' : 'bg-contested-bg/20 border-contested/20'}`}>
      <div className="text-xs text-ink-muted mb-1">{label}</div>
      <div className={`text-xl font-semibold ${met ? 'text-active' : 'text-contested'}`}>{value}</div>
      <div className="text-[10px] text-ink-muted mt-0.5">Target: {target}</div>
    </div>
  );
}

function MatchBadge({ match }: { match: string }) {
  const styles: Record<string, string> = {
    hit: 'bg-active-bg text-active',
    partial: 'bg-amended-bg text-amended',
    miss: 'bg-contested-bg text-contested',
  };
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium capitalize ${styles[match] ?? 'bg-gray-100 text-gray-600'}`}>
      {match}
    </span>
  );
}

function pct(v: unknown): string { return `${(Number(v) * 100).toFixed(1)}%`; }
function num(v: unknown): string { return String(v ?? '—'); }
function ms(v: unknown): string { return `${Number(v).toLocaleString()}ms`; }
function frac(v: unknown): string { return String(v ?? '—'); }
function gte(v: unknown, t: unknown): boolean { return Number(v) >= Number(t); }
function lte(v: unknown, t: unknown): boolean { return Number(v) <= Number(t); }
