import { useState, useEffect, useRef, useCallback } from 'react';
import { api, ApiError, type AskResponse, type Citation, type Conflict } from '../api';
import { StatusBadge } from '../components/StatusBadge';
import { EmailModal } from '../components/EmailModal';
import { DecisionDrawer } from '../components/DecisionDrawer';
import { LoadingSkeleton, ErrorState } from '../components/States';

const SUGGESTED_QUESTIONS = [
  'Why did we switch payment providers?',
  'Which payment provider will we use from July, and when is the cutover?',
  'Did we decide to open a Lisbon office?',
  'What is the first-response SLA for Pro customers?',
  'What renewal discount did we approve for Redline?',
  'Why is the database still on NimbusHost?',
];

export default function AskPage() {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [emailModal, setEmailModal] = useState<{ messageId: string; quote?: string } | null>(null);
  const [drawerId, setDrawerId] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const tag = (e.target as HTMLElement).tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA') return;
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, []);

  const askQuestion = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setConflicts([]);
    try {
      const res = await api.ask(q);
      setResult(res);
      if (res.status === 'contested' && res.decision_ids.length > 0) {
        try {
          const allConflicts = await api.conflicts();
          setConflicts(allConflicts.filter(c => res.decision_ids.includes(c.decision_id)));
        } catch { /* ignore */ }
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 503) {
        setError('This question is not cached in demo mode. Try one of the suggested questions, or switch to live mode.');
      } else {
        setError(e instanceof Error ? e.message : 'Ask failed');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    askQuestion(question);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h2 className="font-serif text-2xl font-bold text-ink">Ask</h2>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex gap-3">
        <input
          ref={inputRef}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about a decision…"
          className="flex-1 px-4 py-3 text-sm border border-border rounded-lg focus:outline-none focus:border-ink-muted transition-colors"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="px-6 py-3 text-sm font-medium text-white bg-ink rounded-lg hover:bg-ink-light disabled:opacity-40 transition-colors"
        >
          {loading ? 'Asking…' : 'Ask'}
        </button>
      </form>

      {/* Suggested questions */}
      {!result && !loading && !error && (
        <div className="flex flex-wrap gap-2">
          {SUGGESTED_QUESTIONS.map((sq) => (
            <button
              key={sq}
              onClick={() => { setQuestion(sq); askQuestion(sq); }}
              className="text-xs px-3 py-1.5 rounded-full border border-border text-ink-muted hover:text-ink hover:border-ink-muted transition-colors"
            >
              {sq}
            </button>
          ))}
        </div>
      )}

      {error && <ErrorState message={error} onRetry={() => setError(null)} />}
      {loading && <LoadingSkeleton lines={5} />}

      {result && (
        <div className="flex gap-6">
          {/* Answer panel */}
          <div className="flex-1 min-w-0 space-y-4">
            {result.status === 'no_decision' ? (
              <NoDecisionPanel result={result} onOpenEmail={(id, q) => setEmailModal({ messageId: id, quote: q })} />
            ) : result.status === 'contested' ? (
              <ContestedPanel result={result} conflicts={conflicts} onCiteClick={(c) => setEmailModal({ messageId: c.message_id, quote: c.quote })} />
            ) : (
              <AnswerPanel result={result} onCiteClick={(c) => setEmailModal({ messageId: c.message_id, quote: c.quote })} />
            )}

            {/* Meta */}
            <div className="flex items-center gap-4 text-xs text-ink-muted">
              <span>Confidence: <span className="font-medium text-ink">{result.confidence}</span></span>
              <span>{result.latency_ms}ms</span>
              {result.caveats.length > 0 && (
                <span className="text-amended">
                  {result.caveats.join('; ')}
                </span>
              )}
            </div>
          </div>

          {/* Decisions used sidebar */}
          {result.decisions.length > 0 && (
            <div className="w-72 flex-shrink-0">
              <div className="text-xs font-medium text-ink-light mb-2">Decisions used</div>
              <div className="space-y-2">
                {result.decisions.map((d) => (
                  <button
                    key={d.decision_id}
                    onClick={() => setDrawerId(d.decision_id)}
                    className="w-full text-left p-3 bg-white border border-border rounded-md hover:border-ink-muted transition-colors"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-mono text-ink-muted">{d.decision_id}</span>
                      <StatusBadge status={d.status} />
                    </div>
                    <div className="text-xs text-ink leading-snug">{d.canonical_text}</div>
                    <div className="text-[10px] text-ink-muted mt-1">{d.decided_at}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {emailModal && (
        <EmailModal
          messageId={emailModal.messageId}
          highlightQuote={emailModal.quote}
          onClose={() => setEmailModal(null)}
        />
      )}

      {drawerId && (
        <DecisionDrawer
          decisionId={drawerId}
          onClose={() => setDrawerId(null)}
          onNavigate={setDrawerId}
        />
      )}
    </div>
  );
}

function AnswerPanel({ result, onCiteClick }: { result: AskResponse; onCiteClick: (c: Citation) => void }) {
  return (
    <div className="bg-white border border-border rounded-lg p-6">
      <RenderedAnswer markdown={result.answer_md} citations={result.citations} onCiteClick={onCiteClick} />
    </div>
  );
}

function NoDecisionPanel({ result, onOpenEmail }: { result: AskResponse; onOpenEmail: (id: string, quote?: string) => void }) {
  return (
    <div className="space-y-4">
      <div className="bg-amended-bg/40 border border-amended/30 rounded-lg p-6">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-sm font-medium text-amended">No decision found</span>
        </div>
        <div className="text-sm text-ink leading-relaxed">
          <RenderedAnswer markdown={result.answer_md} citations={result.citations} onCiteClick={(c) => onOpenEmail(c.message_id, c.quote)} />
        </div>
      </div>
      {result.closest.length > 0 && (
        <div>
          <div className="text-xs font-medium text-ink-light mb-2">Closest discussions</div>
          <div className="space-y-2">
            {result.closest.map((c, i) => (
              <button
                key={i}
                onClick={() => onOpenEmail(c.message_id)}
                className="w-full text-left p-3 bg-white border border-border-light rounded-md hover:border-ink-muted transition-colors"
              >
                <div className="text-xs font-medium text-ink">{c.sender} · {c.date}</div>
                <div className="text-xs text-ink-muted">{c.subject}</div>
                <div className="text-xs text-ink-light mt-1">{c.why}</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ContestedPanel({ result, conflicts, onCiteClick }: { result: AskResponse; conflicts: Conflict[]; onCiteClick: (c: Citation) => void }) {
  return (
    <div className="space-y-4">
      <div className="bg-contested-bg/40 border border-contested/30 rounded-lg p-6">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-sm font-medium text-contested">Contested</span>
        </div>
        <RenderedAnswer markdown={result.answer_md} citations={result.citations} onCiteClick={onCiteClick} />
      </div>

      {conflicts.map((conflict) => (
        <div key={conflict.conflict_id} className="grid grid-cols-2 gap-4">
          {conflict.sides.map((side) => (
            <div key={side.side} className="bg-white border border-border rounded-lg p-4">
              <div className="text-xs font-medium text-ink mb-1">Version {side.side} — {side.claimant}</div>
              <div className="text-sm text-ink mb-3">{side.claim}</div>
              {side.evidence.map((ev, i) => (
                <div key={i} className="text-xs text-ink-muted italic border-l-2 border-border-light pl-2 mb-1">
                  "{ev.quote}" — {ev.sender}, {ev.date}
                </div>
              ))}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function RenderedAnswer({ markdown, citations, onCiteClick }: { markdown: string; citations: Citation[]; onCiteClick: (c: Citation) => void }) {
  const citationMap = new Map(citations.map(c => [c.n, c]));
  const parts = markdown.split(/(\[\^\d+\])/g);

  return (
    <div className="text-sm text-ink leading-relaxed font-serif">
      {parts.map((part, i) => {
        const match = part.match(/^\[\^(\d+)\]$/);
        if (match) {
          const n = parseInt(match[1]);
          const cite = citationMap.get(n);
          if (!cite) return <sup key={i} className="text-ink-muted">[{n}]</sup>;
          return <CitationChip key={i} citation={cite} onClick={() => onCiteClick(cite)} />;
        }
        return <span key={i}>{part}</span>;
      })}
    </div>
  );
}

function CitationChip({ citation, onClick }: { citation: Citation; onClick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        onClick={onClick}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        className="inline-flex items-center justify-center w-4 h-4 text-[9px] font-bold text-white bg-ink rounded-full align-super cursor-pointer hover:bg-ink-light"
      >
        {citation.n}
      </button>
      {hover && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-72 bg-ink text-white text-xs rounded-lg p-3 shadow-xl z-50">
          <div className="font-medium mb-1">{citation.sender} · {citation.date}</div>
          <div className="text-gray-300 text-[10px] mb-1.5">{citation.subject}</div>
          <div className="italic">"{citation.quote}"</div>
        </div>
      )}
    </span>
  );
}
