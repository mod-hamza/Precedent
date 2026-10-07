import type { DecisionStatus } from '../api';

const statusStyles: Record<DecisionStatus, string> = {
  active: 'bg-active-bg text-active',
  superseded: 'bg-superseded-bg text-superseded line-through',
  amended: 'bg-amended-bg text-amended',
  contested: 'bg-contested-bg text-contested',
};

export function StatusBadge({ status }: { status: DecisionStatus }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize ${statusStyles[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  );
}

export function TypeChip({ type }: { type: string }) {
  if (type === 'implicit')
    return <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-chip-implicit-bg text-chip-implicit">Implicit</span>;
  return null;
}

export function CrossThreadChip() {
  return <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-chip-crossthread-bg text-chip-crossthread">Cross-thread</span>;
}

export function AuthorityChip() {
  return <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-chip-authority-bg text-chip-authority">Authority?</span>;
}
