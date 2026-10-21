import { AlertTriangle, Check, Circle, Clock3, OctagonAlert } from 'lucide-react';
import { runStatusPresentation } from '../lib/run-state';
import type { Agent, FindingCounts, RunSummary } from '../types';
import { ElapsedTime } from './ElapsedTime';

function StatusMark({ status }: { status?: string }) {
  if (status === 'completed') return <Check aria-hidden="true" size={13} />;
  if (status === 'blocked') return <OctagonAlert aria-hidden="true" size={13} />;
  if (status === 'running') return <span className="status-pulse" aria-hidden="true" />;
  if (status === 'interrupted') return <Circle aria-hidden="true" size={12} />;
  return <Clock3 aria-hidden="true" size={13} />;
}

function AgentRows({ agents }: { agents?: Agent[] }) {
  if (!agents?.length) return <p className="text-xs text-muted">Agents not reported</p>;
  const priority = (status?: string) => {
    if (status === 'running') return 0;
    if (['blocked', 'failed', 'timed_out', 'orphaned'].includes(status || '')) return 1;
    if (['succeeded', 'completed', 'passed'].includes(status || '')) return 2;
    return 3;
  };
  const ordered = [...agents].sort((left, right) => priority(left.status) - priority(right.status));
  return (
    <ul className="space-y-1.5" aria-label="Agent status">
      {ordered.map((agent, index) => (
        <li className="flex min-w-0 items-center gap-2 text-xs" key={agent.role + '-' + index}>
          <span className={'agent-light agent-light-' + (agent.status === 'running' ? 'running' : ['completed', 'succeeded', 'passed'].includes(agent.status || '') ? 'complete' : ['blocked', 'failed', 'timed_out', 'orphaned'].includes(agent.status || '') ? 'blocked' : 'idle')} aria-hidden="true" />
          <span className="agent-role text-text" title={agent.role || 'Agent'}>{agent.role || 'Agent'}</span>
          <span className="truncate font-mono text-muted" title={[agent.provider, agent.model].filter(Boolean).join(' / ')}>
            {[agent.provider, agent.model].filter(Boolean).join(' / ') || 'Provider not reported'}
          </span>
          <span className="shrink-0 text-muted">{agent.status || 'unknown'}</span>
        </li>
      ))}
    </ul>
  );
}

function FindingSummary({ counts }: { counts?: FindingCounts }) {
  if (!counts) return <span className="text-xs text-muted">Findings not reported</span>;
  const entries = (['critical', 'high', 'medium', 'low'] as const)
    .filter((severity) => Number(counts[severity]) > 0)
    .map((severity) => ({ severity, count: Number(counts[severity]) }));
  if (!entries.length) return <span className="inline-flex items-center gap-1.5 text-xs text-muted"><Check aria-hidden="true" size={13} />No active findings</span>;
  return (
    <span className="flex flex-wrap gap-1.5" aria-label="Active findings by severity">
      {entries.map(({ severity, count }) => (
        <span className={'finding-count finding-' + severity} key={severity}>
          {severity} {count}
        </span>
      ))}
    </span>
  );
}

function GateSummary({ gates }: { gates?: RunSummary['gates'] }) {
  if (!gates) return <span className="text-xs text-muted">Verification not reported</span>;
  if (!gates.length) return <span className="text-xs text-muted">Verification pending</span>;
  const passed = gates.filter((gate) => gate.pass === true).length;
  const complete = gates.every((gate) => gate.pass === true || gate.pass === false);
  return <span className="text-xs text-muted">{complete ? passed + ' of ' + gates.length + ' checks passed' : passed + ' checks passed · more pending'}</span>;
}

export function RunCard({ run, onOpen }: { run: RunSummary; onOpen: (id: string, trigger: HTMLButtonElement) => void }) {
  const presentation = runStatusPresentation(run);
  const tone = presentation.tone;
  const label = presentation.label;
  const requirement = run.requirement || 'Requirement unavailable';
  return (
    <button
      className="run-card group w-full text-left"
      data-run-id={run.id}
      onClick={(event) => onOpen(run.id, event.currentTarget)}
      aria-label={run.id + ', ' + label + ', ' + requirement}
      title={run.id + '\n' + requirement}
      type="button"
    >
      <span className="flex items-start justify-between gap-3">
        <span className="line-clamp-3 min-w-0 flex-1 text-sm font-medium leading-5 text-text">{requirement}</span>
        <span className={'status-badge status-' + tone}>
          <StatusMark status={run.status} />
          {label}
        </span>
      </span>
      <span className="mt-2 flex items-center justify-between gap-2 text-xs text-muted">
        <span className="truncate" title={run.project_name || 'Project unavailable'}>{run.project_name || 'Project unavailable'}</span>
        <span className="shrink-0 font-mono" title={run.id}>{run.id.slice(0, 8)}</span>
      </span>
      <span className="mt-3 border-t border-border pt-3">
        <AgentRows agents={run.agents} />
      </span>
      <span className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
        <span className="font-mono text-xs tabular-nums text-muted">
          Round {run.round ?? '—'}{run.max_rounds ? ' / ' + run.max_rounds : ''}
        </span>
        <span className="font-mono text-xs tabular-nums text-muted"><ElapsedTime seconds={run.elapsed_seconds} status={run.status} /></span>
      </span>
      <span className="mt-3 flex items-center gap-2">
        {['blocked', 'interrupted', 'orphaned', 'failed', 'timed_out'].includes(run.status || '') && <AlertTriangle aria-hidden="true" size={14} className="shrink-0 text-danger" />}
        <FindingSummary counts={run.finding_counts} />
      </span>
      <span className="mt-2 block"><GateSummary gates={run.gates} /></span>
    </button>
  );
}
