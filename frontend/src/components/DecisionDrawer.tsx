import { useState, useEffect, useCallback } from 'react';
import { api, type DecisionDetail } from '../api';
import { StatusBadge, TypeChip, CrossThreadChip, AuthorityChip } from './StatusBadge';
import { LoadingSkeleton, ErrorState } from './States';
import { EmailModal } from './EmailModal';

interface DecisionDrawerProps {
  decisionId: string;
  onClose: () => void;
  onNavigate: (id: string) => void;
}

export function DecisionDrawer({ decisionId, onClose, onNavigate }: DecisionDrawerProps) {
  const [detail, setDetail] = useState<DecisionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [emailModal, setEmailModal] = useState<{ messageId: string; quote?: string } | null>(null);
  const [disputeNote, setDisputeNote] = useState('');
  const [disputeOpen, setDisputeOpen] = useState(false);
  const [disputeSent, setDisputeSent] = useState(false);

  const load = useCallback(async () => {
    try {
      setDetail(await api.decision(decisionId));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load decision');
    }
  }, [decisionId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && !emailModal) onClose(); };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose, emailModal]);

  const handleDispute = async () => {
    if (!disputeNote.trim()) return;
    try {
      await api.dispute(decisionId, disputeNote);
      setDisputeSent(true);
      setDisputeOpen(false);
    } catch { /* ignore */ }
  };

  return (
    <>
      <div className="fixed inset-y-0 right-0 w-[480px] bg-white border-l border-border shadow-xl z-40 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <span className="text-xs font-mono text-ink-muted">{decisionId}</span>
          <button onClick={onClose} className="text-ink-muted hover:text-ink text-lg">×</button>
        </div>

        <div className="flex-1 overflow-auto p-6 space-y-6">
          {error && <ErrorState message={error} onRetry={load} />}
          {!error && !detail && <LoadingSkeleton lines={8} />}
          {detail && (
            <>
              {/* Title + badges */}
              <div>
                <h3 className={`font-serif text-lg font-bold text-ink leading-snug mb-2 ${detail.status === 'superseded' ? 'line-through text-superseded' : ''}`}>
                  {detail.text}
                </h3>
                <div className="flex flex-wrap items-center gap-1.5">
                  <StatusBadge status={detail.status} />
                  <TypeChip type={detail.decision_type} />
                  {detail.cross_thread && <CrossThreadChip />}
                  {detail.authority_flag && <AuthorityChip />}
                </div>
              </div>

              {/* Meta */}
              <div className="text-xs text-ink-muted space-y-1">
                <div><span className="font-medium text-ink-light">Decided by:</span> {detail.decided_by.join(', ')}</div>
                <div><span className="font-medium text-ink-light">Date:</span> {detail.decided_at}</div>
                <div><span className="font-medium text-ink-light">Topic:</span> {detail.topic}</div>
              </div>

              {/* Rationale */}
              {detail.rationale && (
                <div>
                  <div className="text-xs font-medium text-ink-light mb-1">Rationale</div>
                  <div className="text-sm text-ink leading-relaxed">{detail.rationale}</div>
                </div>
              )}

              {/* Alternatives */}
              {detail.alternatives.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-ink-light mb-1">Alternatives considered</div>
                  <ul className="text-sm text-ink-light space-y-1">
                    {detail.alternatives.map((a, i) => <li key={i} className="pl-3 border-l-2 border-border-light">{a}</li>)}
                  </ul>
                </div>
              )}

              {/* History chain */}
              {detail.history.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-ink-light mb-2">History</div>
                  <div className="space-y-0">
                    {detail.history.map((h, i) => {
                      const edge = detail.edges.find(e => e.src === h.decision_id || e.dst === h.decision_id);
                      return (
                        <div key={h.decision_id} className="flex gap-3">
                          <div className="flex flex-col items-center">
                            <div className={`w-2.5 h-2.5 rounded-full border-2 flex-shrink-0 ${h.decision_id === decisionId ? 'bg-ink border-ink' : 'bg-white border-border'}`} />
                            {i < detail.history.length - 1 && <div className="w-px flex-1 bg-border" />}
                          </div>
                          <div className="pb-4 min-w-0">
                            <button
                              onClick={() => h.decision_id !== decisionId && onNavigate(h.decision_id)}
                              className={`text-sm text-left leading-snug ${h.decision_id === decisionId ? 'text-ink font-medium' : 'text-ink-light hover:text-ink cursor-pointer'} ${h.status === 'superseded' ? 'line-through' : ''}`}
                            >
                              {h.text}
                            </button>
                            <div className="flex items-center gap-2 mt-1">
                              <span className="text-[10px] text-ink-muted">{h.decided_at}</span>
                              <StatusBadge status={h.status} />
                              {edge && <span className="text-[10px] text-ink-muted italic">{edge.kind}</span>}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Current state */}
              {detail.current_state && (
                <div className="bg-border-light/50 rounded p-3">
                  <div className="text-xs font-medium text-ink-light mb-1">Current state</div>
                  <div className="text-sm text-ink leading-relaxed">{detail.current_state}</div>
                </div>
              )}

              {/* Evidence */}
              {detail.evidence.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-ink-light mb-2">Evidence ({detail.evidence.length})</div>
                  <div className="space-y-2">
                    {detail.evidence.map((ev, i) => (
                      <div key={i} className="border border-border-light rounded p-3">
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className="text-xs font-medium text-ink">{ev.forwarded ? (ev.original_author || ev.sender) : ev.sender}</span>
                          <span className="text-[10px] text-ink-muted">{ev.forwarded ? (ev.original_date || ev.date) : ev.date}</span>
                          <span className="text-[10px] px-1.5 py-0.5 bg-border-light rounded font-medium text-ink-muted capitalize">{ev.role}</span>
                          {ev.forwarded && <span className="text-[10px] text-chip-crossthread">forwarded</span>}
                        </div>
                        <div className="text-sm text-ink-light italic leading-relaxed border-l-2 border-border pl-3">
                          "{ev.quote}"
                        </div>
                        <button
                          onClick={() => setEmailModal({ messageId: ev.message_id, quote: ev.quote })}
                          className="text-[10px] text-ink-muted hover:text-ink mt-1.5 underline"
                        >
                          Open email
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Authority note */}
              {detail.authority_note && (
                <div className="bg-chip-authority-bg rounded p-3 text-sm text-chip-authority">
                  <span className="font-medium">Authority note:</span> {detail.authority_note}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {detail && (
          <div className="border-t border-border px-6 py-3 space-y-2">
            <div className="flex items-center justify-between">
              <div className="text-xs text-ink-muted group relative">
                Confidence: <span className="font-medium text-ink">{detail.confidence_label.label}</span>
                <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block bg-ink text-white text-[10px] rounded px-2 py-1 w-60 shadow-lg z-10">
                  {detail.confidence_label.why}
                </div>
              </div>
              {!disputeSent ? (
                disputeOpen ? (
                  <div className="flex items-center gap-2">
                    <input
                      value={disputeNote}
                      onChange={(e) => setDisputeNote(e.target.value)}
                      placeholder="Why is this wrong?"
                      className="text-xs border border-border rounded px-2 py-1 w-48"
                      onKeyDown={(e) => e.key === 'Enter' && handleDispute()}
                    />
                    <button onClick={handleDispute} className="text-xs text-contested font-medium">Send</button>
                    <button onClick={() => setDisputeOpen(false)} className="text-xs text-ink-muted">Cancel</button>
                  </div>
                ) : (
                  <button onClick={() => setDisputeOpen(true)} className="text-xs text-contested hover:underline">
                    Dispute this decision
                  </button>
                )
              ) : (
                <span className="text-xs text-active">Dispute recorded</span>
              )}
            </div>
          </div>
        )}
      </div>

      {emailModal && (
        <EmailModal
          messageId={emailModal.messageId}
          highlightQuote={emailModal.quote}
          onClose={() => setEmailModal(null)}
        />
      )}
    </>
  );
}
