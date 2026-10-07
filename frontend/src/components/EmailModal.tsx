import { useState, useEffect, useCallback } from 'react';
import { api, type EmailDetail } from '../api';
import { LoadingSkeleton, ErrorState } from './States';

interface EmailModalProps {
  messageId: string;
  highlightQuote?: string;
  onClose: () => void;
}

export function EmailModal({ messageId, highlightQuote, onClose }: EmailModalProps) {
  const [email, setEmail] = useState<EmailDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setEmail(await api.email(messageId));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load email');
    }
  }, [messageId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl w-[720px] max-h-[80vh] flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h3 className="font-serif text-lg font-bold text-ink truncate">
            {email?.subject ?? 'Loading…'}
          </h3>
          <button onClick={onClose} className="text-ink-muted hover:text-ink text-lg">×</button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto p-6">
          {error && <ErrorState message={error} onRetry={load} />}
          {!error && !email && <LoadingSkeleton lines={6} />}
          {email && (
            <div className="space-y-4">
              {/* Headers */}
              <div className="text-xs space-y-1 text-ink-muted border-b border-border-light pb-4">
                <div><span className="font-medium text-ink-light">From:</span> {email.sender} &lt;{email.sender_addr}&gt;</div>
                <div><span className="font-medium text-ink-light">Role:</span> {email.sender_role}</div>
                <div><span className="font-medium text-ink-light">To:</span> {email.to.join(', ')}</div>
                {email.cc.length > 0 && <div><span className="font-medium text-ink-light">Cc:</span> {email.cc.join(', ')}</div>}
                <div><span className="font-medium text-ink-light">Date:</span> {email.date}</div>
              </div>

              {/* New text with highlighted quote */}
              <div className="text-sm text-ink leading-relaxed whitespace-pre-wrap">
                {highlightQuote ? highlightText(email.new_text, highlightQuote) : email.new_text}
              </div>

              {/* Quoted text */}
              {email.quoted_text && (
                <Collapsible title="Quoted text">
                  <div className="text-xs text-ink-muted whitespace-pre-wrap">{email.quoted_text}</div>
                </Collapsible>
              )}

              {/* Forwarded text */}
              {email.fwd_text && (
                <Collapsible title="Forwarded message">
                  <div className="text-xs text-ink-muted whitespace-pre-wrap">{email.fwd_text}</div>
                </Collapsible>
              )}

              {/* Thread */}
              {email.thread.length > 1 && (
                <div className="border-t border-border-light pt-4">
                  <div className="text-xs font-medium text-ink-light mb-2">Thread ({email.thread.length} messages)</div>
                  <div className="space-y-1">
                    {email.thread.map((t) => (
                      <div
                        key={t.message_id}
                        className={`text-xs p-2 rounded ${t.message_id === messageId ? 'bg-amended-bg/40 text-ink' : 'text-ink-muted'}`}
                      >
                        <span className="font-medium">{t.sender}</span> · {t.date}
                        <div className="truncate">{t.subject}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Collapsible({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-border-light rounded">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full px-3 py-2 text-xs font-medium text-ink-muted hover:text-ink"
      >
        {title}
        <span>{open ? '▾' : '▸'}</span>
      </button>
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  );
}

function highlightText(text: string, quote: string): React.ReactNode {
  const lower = text.toLowerCase();
  const qLower = quote.toLowerCase();
  const idx = lower.indexOf(qLower);
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-amended-bg/60 px-0.5 rounded">{text.slice(idx, idx + quote.length)}</mark>
      {text.slice(idx + quote.length)}
    </>
  );
}
