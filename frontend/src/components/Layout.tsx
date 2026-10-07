import { NavLink } from 'react-router-dom';
import { useAppContext } from '../context';
import type { Stats } from '../api';

const navItems = [
  { to: '/', label: 'Ingest', icon: '↓' },
  { to: '/timeline', label: 'Timeline', icon: '◈' },
  { to: '/ask', label: 'Ask', icon: '?' },
  { to: '/conflicts', label: 'Conflicts', icon: '⚡' },
  { to: '/scorecard', label: 'Scorecard', icon: '✓' },
];

export function Layout({ stats, children }: { stats: Stats | null; children: React.ReactNode }) {
  const { demoMode, setDemoMode, redactMode, setRedactMode } = useAppContext();

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Left rail */}
      <nav className="w-48 flex-shrink-0 bg-white border-r border-border flex flex-col" role="navigation">
        <div className="p-4 border-b border-border">
          <h1 className="font-serif text-lg font-bold text-ink tracking-tight">Precedent</h1>
        </div>
        <div className="flex-1 py-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-4 py-2.5 text-sm font-medium transition-colors ${
                  isActive ? 'bg-border-light text-ink' : 'text-ink-muted hover:text-ink hover:bg-border-light/50'
                }`
              }
            >
              <span className="w-5 text-center text-base opacity-60">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Main area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-border">
          {/* Counter strip */}
          <div className="flex items-center gap-4 text-xs text-ink-muted">
            {stats ? (
              <>
                <span><strong className="text-ink font-semibold">{stats.emails}</strong> emails</span>
                <span className="text-border">·</span>
                <span><strong className="text-ink font-semibold">{stats.candidate_threads}</strong> candidate threads</span>
                <span className="text-border">·</span>
                <span><strong className="text-ink font-semibold">{stats.decisions}</strong> decisions</span>
              </>
            ) : (
              <span>Loading stats…</span>
            )}
          </div>
          {/* Toggles */}
          <div className="flex items-center gap-4">
            <Toggle label="PII redaction" checked={redactMode} onChange={setRedactMode} />
            <Toggle label="Demo mode" checked={demoMode} onChange={setDemoMode} />
          </div>
        </header>

        {/* Scope banner */}
        <div className="px-6 py-2 bg-amended-bg/40 border-b border-amended/20 text-xs text-amended">
          Precedent only sees the mail it was given; decisions made by phone or in person are missing.
        </div>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <span className="text-xs text-ink-muted">{label}</span>
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative w-8 h-[18px] rounded-full transition-colors ${checked ? 'bg-active' : 'bg-border'}`}
      >
        <span className={`absolute top-[2px] left-[2px] w-[14px] h-[14px] bg-white rounded-full shadow transition-transform ${checked ? 'translate-x-[14px]' : ''}`} />
      </button>
    </label>
  );
}
