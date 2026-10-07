import { useState, useEffect, useCallback } from 'react';
import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { api, setRedactMode as setApiRedact } from './api';
import { AppContext } from './context';
import { useStats } from './hooks';
import { Layout } from './components/Layout';
import IngestPage from './pages/IngestPage';
import TimelinePage from './pages/TimelinePage';
import AskPage from './pages/AskPage';
import ConflictsPage from './pages/ConflictsPage';
import ScorecardPage from './pages/ScorecardPage';

function AppInner() {
  const [demoMode, setDemoModeState] = useState(false);
  const [redactMode, setRedactModeState] = useState(false);
  const { stats, reload: reloadStats } = useStats();
  const navigate = useNavigate();

  useEffect(() => {
    api.health().then((h) => setDemoModeState(h.demo_mode)).catch(() => {});
  }, []);

  const setDemoMode = useCallback(async (v: boolean) => {
    try {
      const res = await api.demoLoad(v);
      setDemoModeState(res.demo_mode);
      reloadStats();
    } catch { /* ignore */ }
  }, [reloadStats]);

  const setRedactMode = useCallback((v: boolean) => {
    setRedactModeState(v);
    setApiRedact(v);
  }, []);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const tag = (e.target as HTMLElement).tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
        e.preventDefault();
        navigate('/ask');
      }
    }
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [navigate]);

  return (
    <AppContext.Provider value={{ demoMode, setDemoMode, redactMode, setRedactMode }}>
      <Layout stats={stats}>
        <Routes>
          <Route path="/" element={<IngestPage />} />
          <Route path="/timeline" element={<TimelinePage />} />
          <Route path="/ask" element={<AskPage />} />
          <Route path="/conflicts" element={<ConflictsPage />} />
          <Route path="/scorecard" element={<ScorecardPage />} />
        </Routes>
      </Layout>
    </AppContext.Provider>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppInner />
    </BrowserRouter>
  );
}
