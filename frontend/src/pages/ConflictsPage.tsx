import { useState, useEffect, useCallback } from 'react';
import { api, type Conflict } from '../api';
import { LoadingSkeleton, ErrorState, EmptyState } from '../components/States';
import { EmailModal } from '../components/EmailModal';

export default function ConflictsPage() {
  const [conflicts, setConflicts] = useState<Conflict[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [emailModal, setEmailModal] = useState<{ messageId: string; quote?: string } | null>(null);

  const load = useCallback(async () => {
    try {
      setConflicts(await api.conflicts());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load conflicts');
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!conflicts) return <LoadingSkeleton lines={5} />;
  if (conflicts.length === 0) return <EmptyState title="No conflicts" description="No contested decisions found in the corpus." />;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h2 className="font-serif text-2xl font-bold text-ink">Conflicts</h2>

      {conflicts.map((conflict) => (
        <div key={conflict.conflict_id} className="bg-white border border-border rounded-lg overflow-hidden">
          {/* Header */}
          <div className="px-6 py-4 border-b border-border bg-contested-bg/20">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-mono text-ink-muted">{conflict.conflict_id}</span>
              <span className="text-xs px-2 py-0.5 rounded bg-contested-bg text-contested font-medium">Contested</span>
            </div>
            <h3 className="font-serif text-base font-bold text-ink">{conflict.topic}</h3>
            <p className="text-sm text-ink-light mt-1">{conflict.summary}</p>
          </div>

          {/* Split view */}
          <div className="grid grid-cols-2 divide-x divide-border">
            {conflict.sides.map((side) => (
              <div key={side.side} className="p-6">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xs font-medium text-ink bg-border-light rounded px-2 py-0.5">Version {side.side}</span>
                  <span className="text-sm font-medium text-ink">{side.claimant}</span>
                </div>
                <div className="text-sm text-ink leading-relaxed mb-4">{side.claim}</div>
                <div className="space-y-2">
                  {side.evidence.map((ev, i) => (
                    <div key={i} className="border-l-2 border-border-light pl-3">
                      <div className="text-xs text-ink-muted mb-0.5">
                        {ev.sender} · {ev.date}
                        {ev.sender_role && <span className="ml-1 text-[10px]">({ev.sender_role})</span>}
                      </div>
                      <div className="text-sm text-ink-light italic">"{ev.quote}"</div>
                      <button
                        onClick={() => setEmailModal({ messageId: ev.message_id, quote: ev.quote })}
                        className="text-[10px] text-ink-muted hover:text-ink mt-1 underline"
                      >
                        Open email
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Footer note */}
          <div className="px-6 py-3 bg-border-light/30 border-t border-border text-xs text-ink-muted italic">
            {conflict.note}
          </div>
        </div>
      ))}

      {emailModal && (
        <EmailModal
          messageId={emailModal.messageId}
          highlightQuote={emailModal.quote}
          onClose={() => setEmailModal(null)}
        />
      )}
    </div>
  );
}
