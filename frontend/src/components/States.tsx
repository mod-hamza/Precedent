export function LoadingSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="animate-pulse space-y-3 p-6">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="h-4 bg-border-light rounded" style={{ width: `${80 - i * 15}%` }} />
      ))}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center">
      <div className="text-contested text-sm font-medium mb-2">Something went wrong</div>
      <div className="text-ink-muted text-sm mb-4">{message}</div>
      {onRetry && (
        <button onClick={onRetry} className="px-4 py-2 text-sm font-medium text-ink bg-white border border-border rounded-md hover:bg-border-light transition-colors">
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center">
      <div className="text-ink-light text-sm font-medium mb-1">{title}</div>
      {description && <div className="text-ink-muted text-sm">{description}</div>}
    </div>
  );
}
