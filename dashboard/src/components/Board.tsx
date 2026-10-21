import { RefreshCw } from 'lucide-react';
import { boardPlacement } from '../lib/run-state';
import { STAGES, type RunSummary, type Stage } from '../types';
import { RunCard } from './RunCard';

interface BoardProps {
  runs: RunSummary[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onOpenRun: (id: string, trigger: HTMLButtonElement) => void;
}

export function Board({ runs, loading, error, onRetry, onOpenRun }: BoardProps) {
  const groups = new Map<Stage, RunSummary[]>(STAGES.map((stage) => [stage, []]));
  const unclassified = runs.flatMap((run) => {
    const placement = boardPlacement(run);
    if (placement.kind === 'stage') groups.get(placement.stage)?.push(run);
    return placement.kind === 'unclassified' ? [{ run, reason: placement.reason }] : [];
  });

  return (
    <section aria-labelledby="board-title" className="min-w-0">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 id="board-title" className="section-title">Run board</h2>
          <p className="mt-1 text-xs text-muted">Stages, agent activity, and verification evidence</p>
        </div>
        {error && (
          <div className="flex items-center gap-2 text-sm text-danger" role="alert">
            <span>{error}</span>
            <button className="icon-button" type="button" onClick={onRetry} aria-label="Retry loading runs">
              <RefreshCw size={15} aria-hidden="true" />
            </button>
          </div>
        )}
      </div>

      <nav className="stage-jumps" aria-label="Jump to run stage">
        {STAGES.map((stage) => {
          const count = groups.get(stage)?.length ?? 0;
          return <button
            className="stage-jump"
            type="button"
            key={stage}
            aria-label={'Jump to ' + stage + ', ' + count + ' ' + (count === 1 ? 'run' : 'runs')}
            onClick={() => document.getElementById('lane-' + stage.toLowerCase())?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' })}
          >
            <span>{stage}</span><span className="stage-jump-count" aria-hidden="true">{count}</span>
          </button>;
        })}
      </nav>

      {unclassified.length > 0 && (
        <aside className="mb-3 rounded-md border border-warning bg-raised px-3 py-2" aria-label="Runs needing classification">
          <p className="text-sm font-medium text-warning">{unclassified.length} run{unclassified.length === 1 ? '' : 's'} need verification or a supported stage</p>
          <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
            {unclassified.map(({ run, reason }) => (
              <li key={run.id}>
                <button type="button" className="text-left underline decoration-border-strong underline-offset-2 hover:text-text" onClick={(event) => onOpenRun(run.id, event.currentTarget)}>
                  {run.id}: {reason}
                </button>
              </li>
            ))}
          </ul>
        </aside>
      )}

      <div
        className="board-scroll"
        role="region"
        aria-label="Run stages. Use the left and right arrow keys to scroll horizontally."
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.target !== event.currentTarget || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
          event.preventDefault();
          event.currentTarget.scrollBy({ left: event.key === 'ArrowRight' ? 220 : -220, behavior: 'smooth' });
        }}
      >
        <div className="board-grid">
          {STAGES.map((stage) => {
            const items = groups.get(stage) ?? [];
            return (
              <section className="board-column" key={stage} aria-labelledby={'lane-' + stage.toLowerCase()}>
                <header className="lane-header">
                  <h3 id={'lane-' + stage.toLowerCase()}>{stage}</h3>
                  <span className="lane-count" aria-label={items.length + ' ' + (items.length === 1 ? 'run' : 'runs')}>{items.length}</span>
                </header>
                {loading && runs.length === 0 ? (
                  <div className="space-y-2" aria-busy="true" aria-label={'Loading ' + stage + ' runs'}>
                    <div className="skeleton h-36" />
                    <div className="skeleton h-28" />
                  </div>
                ) : items.length > 0 ? (
                  <div className="space-y-2.5">
                    {items.map((run) => <RunCard key={run.id} run={run} onOpen={onOpenRun} />)}
                  </div>
                ) : (
                  <p className="empty-lane">No runs in this stage</p>
                )}
              </section>
            );
          })}
        </div>
      </div>
    </section>
  );
}
