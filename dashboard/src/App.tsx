import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, SearchX } from 'lucide-react';
import { Board } from './components/Board';
import { NewRunDialog } from './components/NewRunDialog';
import { RunDetailsDialog } from './components/RunDetailsDialog';
import { TopBar } from './components/TopBar';
import { useDashboard } from './hooks/useDashboard';
import type { CreateRunRequest } from './types';

export default function App() {
  const dashboard = useDashboard();
  const [search, setSearch] = useState('');
  const [newRunOpen, setNewRunOpen] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    try {
      return localStorage.getItem('factory-console-theme') === 'light' ? 'light' : 'dark';
    } catch {
      return 'dark';
    }
  });
  const searchRef = useRef<HTMLInputElement>(null);
  const lastFocusedCardId = useRef<string | null>(null);
  const restoreRunId = useRef<string | null>(null);
  const priorSelected = useRef<string | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem('factory-console-theme', theme);
    } catch {
      // Theme remains usable for the current page when storage is unavailable.
    }
  }, [theme]);

  useEffect(() => {
    const rememberCard = (event: FocusEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const card = target.closest<HTMLElement>('[data-run-id]');
      if (card?.dataset.runId) lastFocusedCardId.current = card.dataset.runId;
    };
    document.addEventListener('focusin', rememberCard);
    return () => document.removeEventListener('focusin', rememberCard);
  }, []);

  useLayoutEffect(() => {
    if (document.activeElement !== document.body || selectedRunId) return;
    const id = lastFocusedCardId.current;
    if (!id) return;
    requestAnimationFrame(() => {
      if (document.activeElement !== document.body) return;
      const card = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-run-id]')).find((element) => element.dataset.runId === id);
      (card || searchRef.current)?.focus();
    });
  }, [dashboard.runs, search, selectedRunId]);

  useEffect(() => {
    if (!selectedRunId && priorSelected.current) {
      const id = restoreRunId.current;
      requestAnimationFrame(() => {
        const card = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-run-id]')).find((element) => element.dataset.runId === id);
        (card || searchRef.current)?.focus();
      });
    }
    priorSelected.current = selectedRunId;
  }, [selectedRunId]);

  const visibleRuns = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    if (!query) return dashboard.runs;
    return dashboard.runs.filter((run) => [run.id, run.project_name, run.requirement].some((value) => value?.toLocaleLowerCase().includes(query)));
  }, [dashboard.runs, search]);

  function openRun(id: string, _trigger: HTMLButtonElement) {
    restoreRunId.current = id;
    setSelectedRunId(id);
  }

  async function createRun(input: CreateRunRequest) {
    return dashboard.createRun(input);
  }

  function taskCreated(id: string) {
    setNewRunOpen(false);
    restoreRunId.current = id;
    setSelectedRunId(id);
  }

  return (
    <div className="app-shell">
      <TopBar
        health={dashboard.health}
        connection={dashboard.connection}
        search={search}
        onSearch={setSearch}
        searchRef={searchRef}
        theme={theme}
        onToggleTheme={() => setTheme((current) => current === 'dark' ? 'light' : 'dark')}
        onNewRun={() => setNewRunOpen(true)}
      />
      <main id="main" className="app-main">
        <div className="page-heading">
          <h1>Software factory</h1>
          <p className="page-heading-note">Read the stage, then inspect the evidence behind each run.</p>
        </div>

        {dashboard.healthError && (
          <div className="service-banner" role="alert">
            <AlertCircle size={16} aria-hidden="true" />
            <span>{dashboard.healthError}</span>
            <button className="text-button" type="button" onClick={dashboard.retry}>Retry</button>
          </div>
        )}
        {search && visibleRuns.length === 0 && !dashboard.isLoading && (
          <div className="search-empty" role="status">
            <SearchX size={17} aria-hidden="true" />
            <span>No runs match “{search}”.</span>
            <button className="text-button" type="button" onClick={() => { setSearch(''); searchRef.current?.focus(); }}>Clear search</button>
          </div>
        )}

        <Board
          runs={visibleRuns}
          loading={dashboard.isLoading}
          error={dashboard.runError}
          onRetry={dashboard.refreshRuns}
          onOpenRun={openRun}
        />
      </main>
      <NewRunDialog
        open={newRunOpen}
        health={dashboard.health}
        onClose={() => setNewRunOpen(false)}
        onCreate={createRun}
        onCreated={taskCreated}
      />
      <RunDetailsDialog runId={selectedRunId} refreshToken={dashboard.revision} onClose={() => setSelectedRunId(null)} />
    </div>
  );
}
