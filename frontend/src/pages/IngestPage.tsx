import { useState, useCallback, useRef, useEffect } from 'react';
import { api, type SSEEvent, type Stats } from '../api';
import { useAppContext } from '../context';
import { useStats } from '../hooks';
import { LoadingSkeleton, ErrorState } from '../components/States';

const STAGES = ['parse', 'triage', 'extract', 'cluster', 'reconcile', 'index'] as const;
const STAGE_LABELS: Record<string, string> = {
  parse: 'Parse', triage: 'Triage', extract: 'Extract',
  cluster: 'Cluster', reconcile: 'Reconcile', index: 'Index',
};

interface StageProgress {
  status: 'pending' | 'active' | 'done';
  done: number;
  total: number;
  stats?: Record<string, unknown>;
}

interface FoundDecision {
  id: string;
  text: string;
  date: string;
  status?: string;
}

export default function IngestPage() {
  const { demoMode } = useAppContext();
  const { stats } = useStats();
  const [dragOver, setDragOver] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [stages, setStages] = useState<Record<string, StageProgress>>({});
  const [found, setFound] = useState<FoundDecision[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const cleanup = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
  }, []);

  useEffect(() => cleanup, [cleanup]);

  const subscribe = useCallback((rid: string) => {
    cleanup();
    setRunId(rid);
    setRunning(true);
    setDone(false);
    setError(null);
    setStages({});
    setFound([]);

    const es = api.subscribeRun(rid,
      (ev: SSEEvent) => {
        switch (ev.event) {
          case 'stage_start':
            setStages(prev => ({
              ...prev,
              [ev.stage!]: { status: 'active', done: 0, total: 0 },
            }));
            break;
          case 'progress':
            setStages(prev => ({
              ...prev,
              [ev.stage!]: { ...prev[ev.stage!], status: 'active', done: ev.done ?? 0, total: ev.total ?? 0 },
            }));
            break;
          case 'stage_done':
            setStages(prev => ({
              ...prev,
              [ev.stage!]: { ...prev[ev.stage!], status: 'done', done: prev[ev.stage!]?.total || 0 },
            }));
            break;
          case 'decision_found':
            setFound(prev => [...prev, {
              id: ev.decision_id || ev.record_id || '?',
              text: ev.text || '',
              date: ev.date || '',
              status: ev.status,
            }]);
            break;
          case 'run_done':
            setRunning(false);
            setDone(true);
            es.close();
            break;
          case 'error':
            setError(ev.message || 'Pipeline error');
            setRunning(false);
            es.close();
            break;
        }
      },
      () => {
        setError('Lost connection to pipeline');
        setRunning(false);
      },
    );
    esRef.current = es;
  }, [cleanup]);

  const handleFiles = useCallback(async (files: File[]) => {
    if (demoMode) { setError('Turn off demo mode to ingest files.'); return; }
    try {
      setError(null);
      const res = await api.ingest(files);
      subscribe(res.run_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ingest failed');
    }
  }, [demoMode, subscribe]);

  const handleCorpus = useCallback(async () => {
    if (demoMode) { setError('Turn off demo mode to run the corpus pipeline.'); return; }
    try {
      setError(null);
      const res = await api.ingestCorpus();
      subscribe(res.run_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Corpus ingest failed');
    }
  }, [demoMode, subscribe]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length) handleFiles(files);
  }, [handleFiles]);

  if (demoMode && !runId) {
    return <DemoFunnel stats={stats} />;
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h2 className="font-serif text-2xl font-bold text-ink">Ingest</h2>

      {/* Drop zone */}
      {!running && !done && (
        <>
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors
              ${dragOver ? 'border-active bg-active-bg/30' : 'border-border hover:border-ink-muted'}`}
          >
            <div className="text-ink-light text-sm font-medium mb-1">
              Drop .eml files, a .zip, or an .mbox here
            </div>
            <div className="text-ink-muted text-xs">or click to browse</div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".eml,.zip,.mbox"
              className="hidden"
              onChange={(e) => {
                const files = Array.from(e.target.files || []);
                if (files.length) handleFiles(files);
              }}
            />
          </div>
          <div className="text-center">
            <button
              onClick={handleCorpus}
              className="px-4 py-2 text-sm font-medium text-ink bg-white border border-border rounded-md hover:bg-border-light transition-colors"
            >
              Load demo corpus
            </button>
          </div>
        </>
      )}

      {error && <ErrorState message={error} onRetry={() => setError(null)} />}

      {/* Pipeline stepper */}
      {(running || done) && (
        <div className="bg-white border border-border rounded-lg p-6">
          <div className="flex items-center gap-1 mb-6">
            {STAGES.map((s, i) => {
              const sp = stages[s];
              const status = sp?.status || 'pending';
              return (
                <div key={s} className="flex items-center flex-1">
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-xs font-medium ${status === 'done' ? 'text-active' : status === 'active' ? 'text-ink' : 'text-ink-muted'}`}>
                        {STAGE_LABELS[s]}
                      </span>
                      {sp && sp.total > 0 && (
                        <span className="text-[10px] text-ink-muted">{sp.done}/{sp.total}</span>
                      )}
                    </div>
                    <div className="h-1.5 bg-border-light rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${status === 'done' ? 'bg-active' : status === 'active' ? 'bg-amended' : 'bg-transparent'}`}
                        style={{ width: sp && sp.total > 0 ? `${Math.round((sp.done / sp.total) * 100)}%` : status === 'done' ? '100%' : '0%' }}
                      />
                    </div>
                  </div>
                  {i < STAGES.length - 1 && <div className="w-4 h-px bg-border mx-1 mt-3" />}
                </div>
              );
            })}
          </div>
          {done && (
            <div className="text-center text-sm text-active font-medium">Pipeline complete</div>
          )}
        </div>
      )}

      {/* Live decision feed */}
      {found.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-ink-light">Decisions found ({found.length})</h3>
          <div className="space-y-1.5 max-h-80 overflow-y-auto">
            {found.map((d, i) => (
              <div key={i} className="flex items-start gap-3 p-3 bg-white border border-border rounded-md animate-[fadeIn_0.3s_ease]">
                <span className="text-[10px] font-mono text-ink-muted mt-0.5">{d.id}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-ink truncate">{d.text}</div>
                  <div className="text-xs text-ink-muted mt-0.5">{d.date}</div>
                </div>
                {d.status && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium capitalize
                    ${d.status === 'active' ? 'bg-active-bg text-active' :
                      d.status === 'superseded' ? 'bg-superseded-bg text-superseded' :
                      d.status === 'amended' ? 'bg-amended-bg text-amended' :
                      'bg-contested-bg text-contested'}`}>
                    {d.status}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Funnel readout */}
      {(running || done) && stats && <Funnel stats={stats} />}
    </div>
  );
}

function Funnel({ stats }: { stats: Stats }) {
  const items = [
    { label: 'Emails', value: stats.emails },
    { label: 'Candidate threads', value: stats.candidate_threads },
    { label: 'Records', value: stats.records },
    { label: 'Decisions', value: stats.decisions },
    { label: 'Evidence verified', value: `${Math.round(stats.evidence_verified_ratio * 100)}%` },
  ];
  return (
    <div className="flex items-center justify-center gap-2 text-sm text-ink-muted">
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-2">
          {i > 0 && <span className="text-border">→</span>}
          <span><strong className="text-ink font-semibold">{item.value}</strong> {item.label.toLowerCase()}</span>
        </span>
      ))}
    </div>
  );
}

function DemoFunnel({ stats }: { stats: Stats | null }) {
  if (!stats) return <LoadingSkeleton lines={4} />;
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h2 className="font-serif text-2xl font-bold text-ink">Ingest</h2>
      <div className="bg-white border border-border rounded-lg p-8">
        <div className="text-center mb-6">
          <div className="text-sm font-medium text-ink-light mb-1">Demo mode — corpus already processed</div>
          <div className="text-xs text-ink-muted">Turn off demo mode to run the pipeline live</div>
        </div>
        <Funnel stats={stats} />
        <div className="mt-6 grid grid-cols-2 gap-4 max-w-md mx-auto">
          {Object.entries(stats.decisions_by_status).map(([status, count]) => (
            <div key={status} className="text-center p-3 bg-border-light/50 rounded">
              <div className="text-lg font-semibold text-ink">{count}</div>
              <div className="text-xs text-ink-muted capitalize">{status}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
