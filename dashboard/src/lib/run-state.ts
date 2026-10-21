import { STAGES, type RunDetail, type RunEvent, type RunSummary, type Stage } from '../types';

export type BoardPlacement =
  | { kind: 'stage'; stage: Stage }
  | { kind: 'unclassified'; reason: string };

const knownStatuses = new Set(['queued', 'running', 'completed', 'blocked', 'interrupted', 'orphaned', 'failed', 'timed_out']);

export function boardPlacement(run: RunSummary): BoardPlacement {
  if (['interrupted', 'orphaned', 'blocked', 'failed', 'timed_out'].includes(run.status || '')) return { kind: 'stage', stage: 'Blocked' };
  if (!STAGES.includes(run.stage as Stage)) {
    return { kind: 'unclassified', reason: 'Stage is unavailable or unsupported.' };
  }
  if (run.stage === 'Ready' && (run.status !== 'completed' || run.delivery_status !== 'verified_candidate')) {
    return { kind: 'unclassified', reason: 'Ready delivery verification is incomplete.' };
  }
  return { kind: 'stage', stage: run.stage as Stage };
}

export function statusLabel(status?: string): string {
  if (!status || !knownStatuses.has(status)) return 'Unknown status';
  return status[0].toUpperCase() + status.slice(1);
}

export function statusTone(status?: string): 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'completed') return 'neutral';
  if (status === 'running') return 'warning';
  if (['blocked', 'interrupted', 'orphaned', 'failed', 'timed_out'].includes(status || '')) return 'danger';
  return 'neutral';
}

export function runStatusPresentation(run: RunSummary): { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' } {
  if (run.status === 'orphaned') return { label: 'Interrupted — recovery required', tone: 'danger' };
  if (run.status === 'interrupted') return { label: 'Interrupted', tone: 'danger' };
  if (run.status === 'failed') return { label: 'Failed', tone: 'danger' };
  if (run.status === 'timed_out') return { label: 'Timed out', tone: 'danger' };
  if (run.status === 'completed') {
    if (run.stage === 'Ready' && run.delivery_status === 'verified_candidate') return { label: 'Verified', tone: 'success' };
    return { label: 'Verification pending', tone: 'warning' };
  }
  return { label: statusLabel(run.status), tone: statusTone(run.status) };
}

export function deliveryEvidence(detail: Pick<RunDetail, 'status' | 'delivery_status' | 'history' | 'events' | 'report'>) {
  const history = detail.history ?? detail.events ?? [];
  const verifiedEvent = history.some((event) => event.type === 'delivery_verified');
  const blocked = detail.delivery_status === 'blocked' || ['blocked', 'interrupted', 'orphaned', 'failed', 'timed_out'].includes(detail.status || '');
  const eventCandidate = detail.delivery_status === 'verified_candidate' && verifiedEvent;
  const reportStatus = typeof detail.report?.status === 'string' && detail.report.status.trim() ? detail.report.status : null;

  if (blocked) return { kind: 'blocked' as const, verifiedEvent, reportStatus };
  if (eventCandidate && !detail.report) return { kind: 'unavailable' as const, verifiedEvent, reportStatus };
  if (eventCandidate && reportStatus !== 'verified_candidate') return { kind: 'mismatch' as const, verifiedEvent, reportStatus };
  if (eventCandidate) return { kind: 'verified' as const, verifiedEvent, reportStatus };
  return { kind: 'pending' as const, verifiedEvent, reportStatus };
}

export function formatElapsed(seconds?: number): string {
  if (!Number.isFinite(seconds) || seconds === undefined || seconds < 0) return '—';
  const total = Math.floor(seconds);
  const days = Math.floor(total / 86400);
  const remainingHours = Math.floor((total % 86400) / 3600);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remainder = total % 60;
  if (days > 0) return days + 'd ' + remainingHours + 'h';
  if (hours > 0) return hours + 'h ' + minutes + 'm';
  if (minutes > 0) return minutes + 'm ' + remainder + 's';
  return remainder + 's';
}

export function parseRunEvent(raw: string, eventId?: string): RunEvent | null {
  try {
    const event = JSON.parse(raw) as Partial<RunEvent>;
    if (!event || typeof event.run_id !== 'string' || typeof event.type !== 'string') return null;
    const rawSequence = eventId || event.seq || event.id;
    const sequence = Number(rawSequence);
    const hasSequence = rawSequence !== undefined && rawSequence !== null && rawSequence !== '' && Number.isSafeInteger(sequence) && sequence >= 0;
    return {
      ...event,
      id: hasSequence ? sequence : event.id,
      seq: hasSequence ? sequence : event.seq,
      run_id: event.run_id,
      type: event.type,
      data: event.data && typeof event.data === 'object' ? event.data : undefined,
    };
  } catch {
    return null;
  }
}

export function mergeRunEvent(runs: RunSummary[], event: RunEvent): RunSummary[] {
  return runs.map((run) => {
    if (run.id !== event.run_id) return run;
    const data = event.data ?? {};
    return {
      ...run,
      stage: typeof data.stage === 'string' ? data.stage : run.stage,
      status: typeof data.status === 'string' ? data.status : run.status,
      round: typeof data.round === 'number' ? data.round : run.round,
      updated_at: event.timestamp ?? run.updated_at,
    };
  });
}
