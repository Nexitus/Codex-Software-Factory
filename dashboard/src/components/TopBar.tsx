import { Moon, Plus, Sun } from 'lucide-react';
import { useEffect, type RefObject } from 'react';
import type { ConnectionState } from '../hooks/useDashboard';
import type { HealthResponse } from '../types';

interface TopBarProps {
  health: HealthResponse | null;
  connection: ConnectionState;
  search: string;
  onSearch: (value: string) => void;
  searchRef: RefObject<HTMLInputElement>;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
  onNewRun: () => void;
}

function modeLabel(mode?: string) {
  if (mode === 'demo') return 'Demo mode';
  if (mode === 'live') return 'Live mode';
  return 'Mode unavailable';
}

function connectionLabel(state: ConnectionState) {
  if (state === 'connected') return 'Updates connected';
  if (state === 'reconnecting') return 'Reconnecting';
  if (state === 'unavailable') return 'Live updates unavailable';
  return 'Connecting';
}

export function TopBar({ health, connection, search, onSearch, searchRef, theme, onToggleTheme, onNewRun }: TopBarProps) {
  const canCreate = Boolean(health?.csrf_token && health.projects?.length);
  useEffect(() => {
    function focusSearch(event: KeyboardEvent) {
      const target = event.target;
      if (event.key === '/' && !(target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)))) {
        event.preventDefault();
        searchRef.current?.focus();
      }
    }
    window.addEventListener('keydown', focusSearch);
    return () => window.removeEventListener('keydown', focusSearch);
  }, [searchRef]);
  return (
    <header className="topbar">
      <a className="brand-mark" href="#main" aria-label="Factory Console home">
        <span className="brand-icon" aria-hidden="true"><span /><span /><span /></span>
        <span className="brand-copy">
          <strong>Factory</strong>
          <span>Run console</span>
        </span>
      </a>

      <div className="topbar-state" aria-label="Factory connection status">
        <span className={'connection-light connection-' + connection} aria-hidden="true" />
        <span>{connectionLabel(connection)}</span>
        <span className="mode-badge">{modeLabel(health?.mode)}</span>
      </div>

      <div className="topbar-controls">
        <label className="search-box">
          <span className="sr-only">Search runs</span>
          <span aria-hidden="true" className="search-glyph">⌕</span>
          <input
            ref={searchRef}
            type="search"
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            placeholder="Search runs"
            aria-label="Search runs"
          />
          <kbd aria-hidden="true">/</kbd>
        </label>
        <button className="icon-button theme-toggle" type="button" onClick={onToggleTheme} aria-label={'Switch to ' + (theme === 'dark' ? 'light' : 'dark') + ' theme'}>
          {theme === 'dark' ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
        </button>
        <button className="button-primary new-run-button" type="button" onClick={onNewRun} disabled={!canCreate} title={canCreate ? undefined : 'Projects and request authorization are not available'}>
          <Plus size={15} aria-hidden="true" />
          <span>New task</span>
        </button>
      </div>
    </header>
  );
}
