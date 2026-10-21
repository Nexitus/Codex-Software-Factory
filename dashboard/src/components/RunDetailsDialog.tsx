import { useEffect, useRef, useState, type ReactNode } from 'react';
import { AlertTriangle, Check, Clock3, FileText, ShieldAlert, X } from 'lucide-react';
import { api, ApiError } from '../lib/api';
import { deliveryEvidence, formatElapsed, runStatusPresentation, statusLabel } from '../lib/run-state';
import type { ArtifactRef, Finding, Gate, LogRef, RunDetail, RunEvent } from '../types';
import { ElapsedTime } from './ElapsedTime';

interface RunDetailsDialogProps {
  runId: string | null;
  refreshToken: number;
  onClose: () => void;
}

function dateLabel(value?: string) {
  if (!value) return 'Timestamp unavailable';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 'Timestamp unavailable' : parsed.toLocaleString();
}

function textField(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}

function DataSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="detail-section" aria-label={title}>
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function GateList({ gates }: { gates?: Gate[] }) {
  if (!gates?.length) return <p className="empty-note">Verification gates are not reported.</p>;
  return (
    <ul className="detail-list">
      {gates.map((gate, index) => {
        const passed = gate.pass === true && !gate.timed_out;
        const failed = !passed && (gate.pass === false || gate.status === 'failed' || gate.status === 'timed_out' || gate.timed_out === true);
        const state = passed ? 'Passed' : failed ? 'Failed' : 'Pending';
        return (
          <li className="detail-row" key={gate.name + '-' + gate.round + '-' + index}>
            <span className={'detail-state ' + (passed ? 'text-success' : failed ? 'text-danger' : 'text-muted')}>
              {passed ? <Check aria-hidden="true" size={14} /> : failed ? <AlertTriangle aria-hidden="true" size={14} /> : <Clock3 aria-hidden="true" size={14} />}
              {state}
            </span>
            <span className="min-w-0 flex-1">{gate.name}</span>
            {gate.round !== undefined && <span className="font-mono text-xs text-muted">Round {gate.round}</span>}
            {gate.exit_code !== undefined && gate.exit_code !== null && <span className="font-mono text-xs text-muted">Exit {gate.exit_code}</span>}
            {gate.timed_out && <span className="text-xs text-danger">Timed out</span>}
          </li>
        );
      })}
    </ul>
  );
}

function Findings({ findings }: { findings?: Finding[] }) {
  if (!findings?.length) return <p className="empty-note">No active findings reported.</p>;
  return (
    <ul className="space-y-2">
      {findings.map((finding, index) => {
        const severity = ['critical', 'high', 'medium', 'low'].includes(finding.severity || '') ? finding.severity : 'unknown';
        return (
          <li className="finding-card" key={finding.id || finding.file || 'finding-' + index}>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className={'finding-count finding-' + severity}>{severity}</span>
              {finding.role && <span className="text-xs text-muted">{finding.role}</span>}
              {finding.round !== undefined && <span className="font-mono text-xs text-muted">Round {finding.round}</span>}
            </div>
            {finding.file && <p className="mt-2 break-all font-mono text-xs text-muted">{finding.file}</p>}
            {finding.evidence && <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-text">{finding.evidence}</p>}
            {finding.remediation && <p className="mt-2 text-sm leading-6 text-muted"><span className="font-medium text-text">Remediation: </span>{finding.remediation}</p>}
          </li>
        );
      })}
    </ul>
  );
}

function RunHistory({ events }: { events?: RunEvent[] }) {
  if (!events?.length) return <p className="empty-note">Run history is not reported.</p>;
  return (
    <ol className="history-list">
      {events.map((event, index) => {
        const data = event.data ?? {};
        const details = [
          typeof data.stage === 'string' ? data.stage : null,
          typeof data.status === 'string' ? statusLabel(data.status) : null,
          typeof data.round === 'number' ? 'Round ' + data.round : null,
          typeof data.attempt === 'number' ? 'Attempt ' + data.attempt : null,
        ].filter(Boolean).join(' · ');
        return (
          <li className="history-item" key={event.seq ?? event.id ?? event.type + '-' + index}>
            <span className="history-dot" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-text">{event.type.replaceAll('_', ' ')}</p>
              {details && <p className="mt-1 text-xs text-muted">{details}</p>}
            </div>
            <time className="shrink-0 text-right text-xs tabular-nums text-muted" dateTime={event.timestamp}>{dateLabel(event.timestamp)}</time>
          </li>
        );
      })}
    </ol>
  );
}

function ArtifactRefs({ artifacts, runId }: { artifacts?: ArtifactRef[]; runId: string }) {
  if (!artifacts?.length) return <p className="empty-note">No artifact references are reported.</p>;
  return (
    <ul className="detail-list">
      {artifacts.map((artifact, index) => (
        <li className="detail-row" key={artifact.path || artifact.name || 'artifact-' + index}>
          <FileText size={15} aria-hidden="true" className="shrink-0 text-muted" />
          <span className="min-w-0 flex-1">
            <span className="block break-words text-sm text-text">{artifact.name || 'Artifact'}</span>
            {artifact.path && <span className="mt-0.5 block break-all font-mono text-xs text-muted">{artifact.path}</span>}
          </span>
          <span className="flex shrink-0 flex-col items-end gap-1">
            <span className="text-xs text-muted">{artifact.kind || 'Reference'}{typeof artifact.size === 'number' ? ' · ' + artifact.size + ' bytes' : ''}</span>
            {artifact.path && <a
              className="text-button min-h-0 p-0 text-xs font-medium"
              href={'/api/runs/' + encodeURIComponent(runId) + '/artifacts?path=' + encodeURIComponent(artifact.path)}
              target="_blank"
              rel="noopener noreferrer"
              referrerPolicy="no-referrer"
              aria-label={'Open artifact ' + (artifact.name || artifact.path)}
            >Open</a>}
          </span>
        </li>
      ))}
    </ul>
  );
}

function LogReferences({ refs }: { refs?: Array<string | LogRef> }) {
  if (!refs?.length) return <p className="empty-note">No log references are reported.</p>;
  return (
    <ul className="detail-list">
      {refs.map((ref, index) => {
        const item = typeof ref === 'string' ? { path: ref } : ref;
        return <li className="detail-row" key={item.path || item.name || 'log-' + index}>
          <FileText size={15} aria-hidden="true" className="shrink-0 text-muted" />
          <span className="min-w-0 flex-1">
            <span className="block text-sm text-text">{item.name || item.role || 'Log reference'}</span>
            {item.path && <span className="mt-0.5 block break-all font-mono text-xs text-muted">{item.path}</span>}
          </span>
          {item.kind && <span className="text-xs text-muted">{item.kind}</span>}
        </li>;
      })}
    </ul>
  );
}

function AcceptanceCriteria({ detail }: { detail: RunDetail }) {
  const summary = textField(detail.plan?.summary);
  const criteria = detail.plan?.acceptance_criteria;
  return (
    <>
      {summary && <p className="whitespace-pre-wrap break-words text-sm leading-6 text-text">{summary}</p>}
      {Array.isArray(criteria) && criteria.length > 0 ? (
        <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-6 text-text">
          {criteria.map((criterion, index) => {
            const description = typeof criterion === 'string' ? criterion : criterion.description || criterion.id || 'Acceptance criterion';
            const verification = typeof criterion === 'string' ? null : criterion.verification;
            return <li key={(typeof criterion === 'string' ? criterion : criterion.id) || index}>
              <span>{description}</span>
              {verification && <span className="mt-1 block text-xs text-muted">Verification: {verification}</span>}
            </li>;
          })}
        </ol>
      ) : !summary ? <p className="empty-note">Plan and acceptance criteria are not reported.</p> : null}
    </>
  );
}

function DesignGuidance({ designs }: { designs?: RunDetail['design'] }) {
  if (!designs?.length) return <p className="empty-note">Design-role summaries are not reported.</p>;
  const sections = [
    ['Architecture guidance', 'guidance'],
    ['Checks', 'checks'],
    ['Risks', 'risks'],
    ['Blocking questions', 'blocking_questions'],
  ] as const;
  return <div className="space-y-4">{designs.map((design, index) => <article className="design-guidance" key={(design.role || 'design') + '-' + index}>
    <h4 className="text-sm font-medium text-text">{design.role || 'Design role'}</h4>
    <div className="mt-2 grid gap-3 sm:grid-cols-2">{sections.map(([title, key]) => {
      const entries = design[key];
      return <section key={key} aria-label={title}>
        <h5 className="text-xs font-semibold text-muted">{title}</h5>
        {entries?.length ? <ul className="mt-1 list-disc space-y-1 pl-4 text-sm leading-5 text-text">{entries.map((entry, itemIndex) => <li className="break-words" key={itemIndex}>{entry}</li>)}</ul> : <p className="mt-1 text-xs text-muted">None reported</p>}
      </section>;
    })}</div>
  </article>)}</div>;
}

function DeliverySummary({ detail }: { detail: RunDetail }) {
  const delivery = detail.delivery ?? {};
  const summary = textField(delivery.summary);
  const reason = textField(delivery.reason);
  const evidence = deliveryEvidence(detail);
  const tone = evidence.kind === 'verified' ? 'success' : evidence.kind === 'blocked' || evidence.kind === 'mismatch' ? 'danger' : 'warning';
  const headline = evidence.kind === 'verified' ? 'Verified candidate' : evidence.kind === 'unavailable' ? 'Delivery report unavailable' : evidence.kind === 'mismatch' ? 'Delivery report mismatch' : evidence.kind === 'blocked' ? 'Blocked delivery' : 'Delivery verification pending';
  const evidenceCopy = evidence.kind === 'verified'
    ? 'Persisted delivery_verified evidence and the sanitized delivery report agree.'
    : evidence.kind === 'unavailable'
      ? 'Persisted delivery_verified evidence is present, but the sanitized delivery report is unavailable in this detail snapshot.'
      : evidence.kind === 'mismatch'
        ? 'Persisted delivery_verified evidence is present, but the sanitized report status is ' + (evidence.reportStatus || 'unavailable') + '.'
        : evidence.verifiedEvent
          ? 'Persisted delivery_verified event is present.'
          : 'Persisted delivery_verified evidence is not available in this detail snapshot.';
  return (
    <div className="delivery-summary">
      <div className="flex items-start gap-2">
        {evidence.kind === 'verified' ? <Check size={16} aria-hidden="true" className="mt-0.5 text-success" /> : tone === 'danger' ? <ShieldAlert size={16} aria-hidden="true" className="mt-0.5 text-danger" /> : <Clock3 size={16} aria-hidden="true" className="mt-0.5 text-warning" />}
        <div>
          <p className={'text-sm font-medium ' + (tone === 'success' ? 'text-success' : tone === 'danger' ? 'text-danger' : 'text-warning')}>
            {headline}
          </p>
          <p className="mt-1 text-xs text-muted">{evidenceCopy}</p>
        </div>
      </div>
      {summary && <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-text">{summary}</p>}
      {reason && <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-muted">{reason}</p>}
    </div>
  );
}

export function RunDetailsDialog({ runId, refreshToken, onClose }: RunDetailsDialogProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryIndex, setRetryIndex] = useState(0);

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (runId && !element.open) element.showModal();
    if (!runId && element.open) element.close();
  }, [runId]);

  useEffect(() => {
    if (!runId) {
      setDetail(null);
      setError(null);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    api.run(runId, controller.signal).then((value) => {
      if (!controller.signal.aborted) setDetail(value);
    }).catch((cause) => {
      if (!controller.signal.aborted) setError(cause instanceof ApiError ? cause.message : 'Could not load run details.');
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [runId, refreshToken, retryIndex]);

  const close = () => dialog.current?.close();
  const findings = detail?.active_findings ?? detail?.findings;
  const history = detail?.history ?? detail?.events;
  const evidence = detail ? deliveryEvidence(detail) : null;
  const detailTone = evidence?.kind === 'verified' ? 'success' : evidence?.kind === 'blocked' || evidence?.kind === 'mismatch' ? 'danger' : evidence?.kind === 'unavailable' || detail?.status === 'completed' ? 'warning' : detail ? runStatusPresentation(detail).tone : 'neutral';
  const detailStatusLabel = evidence?.kind === 'unavailable' ? 'Delivery report unavailable' : evidence?.kind === 'mismatch' ? 'Delivery report mismatch' : evidence?.kind === 'verified' ? 'Verified candidate' : evidence?.kind === 'blocked' && detail?.delivery_status === 'blocked' ? 'Blocked delivery' : detail?.status === 'completed' ? 'Verification pending' : detail ? runStatusPresentation(detail).label : 'Run details';

  return (
    <dialog ref={dialog} className="factory-dialog detail-dialog" aria-labelledby="run-detail-title" onClose={onClose}>
      <div className="detail-shell">
        <header className="detail-header">
          <div className="min-w-0">
            <h2 id="run-detail-title" className="truncate">{detail?.requirement || 'Run details'}</h2>
            {runId && <p className="mt-1 font-mono text-xs text-muted">{runId}</p>}
          </div>
          <button className="icon-button shrink-0" type="button" onClick={close} aria-label="Close run details">
            <X size={17} aria-hidden="true" />
          </button>
        </header>

        {loading && !detail ? (
          <div className="space-y-3 p-5" aria-busy="true" aria-label="Loading run details">
            <div className="skeleton h-20" />
            <div className="skeleton h-32" />
            <div className="skeleton h-40" />
          </div>
        ) : error ? (
          <div className="m-5 rounded-md border border-danger bg-raised p-4" role="alert">
            <p className="text-sm text-danger">{error}</p>
            <button className="button-secondary mt-3" type="button" onClick={() => setRetryIndex((index) => index + 1)}>Retry</button>
          </div>
        ) : detail ? (
          <div className="detail-content">
            <section className="detail-overview" aria-label="Run overview">
              <span className={'status-badge status-' + detailTone}>
                {detailStatusLabel}
              </span>
              <span className="status-badge status-neutral">{detail.stage || 'Stage unavailable'}</span>
              <span className="text-xs text-muted">{detail.project_name || 'Project unavailable'}</span>
              <span className="ml-auto font-mono text-xs tabular-nums text-muted">Round {detail.round ?? '—'}{detail.max_rounds ? ' / ' + detail.max_rounds : ''} · <ElapsedTime seconds={detail.elapsed_seconds} status={detail.status} /></span>
            </section>

            <DataSection title="Requirement">
              <p className="whitespace-pre-wrap break-words text-sm leading-6 text-text">{detail.requirement || 'Requirement unavailable.'}</p>
            </DataSection>
            <DataSection title="Plan and acceptance"><AcceptanceCriteria detail={detail} /></DataSection>
            <DataSection title="Design guidance"><DesignGuidance designs={detail.design} /></DataSection>
            <DataSection title="Delivery"><DeliverySummary detail={detail} /></DataSection>
            <DataSection title="Agents">
              {detail.agents?.length ? <ul className="detail-list">{detail.agents.map((agent, index) => (
                <li className="detail-row" key={agent.role + '-' + index}>
                  <span className={'agent-light agent-light-' + (agent.status === 'running' ? 'running' : ['completed', 'succeeded', 'passed'].includes(agent.status || '') ? 'complete' : ['blocked', 'failed', 'timed_out', 'orphaned'].includes(agent.status || '') ? 'blocked' : 'idle')} aria-hidden="true" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm text-text">{agent.role}{agent.phase ? ' · ' + agent.phase : ''}</span>
                    <span className="mt-0.5 block break-words font-mono text-xs text-muted">{[agent.provider, agent.model].filter(Boolean).join(' / ') || 'Provider not reported'}</span>
                  </span>
                  <span className="text-right text-xs text-muted">{agent.status || 'Status unavailable'}{typeof agent.seconds === 'number' ? ' · ' + formatElapsed(agent.seconds) : ''}{agent.verdict ? ' · ' + agent.verdict : ''}</span>
                </li>
              ))}</ul> : <p className="empty-note">Agent details are not reported.</p>}
            </DataSection>
            <DataSection title="Verification gates"><GateList gates={detail.gates} /></DataSection>
            <DataSection title="Active findings"><Findings findings={findings} /></DataSection>
            <DataSection title="Round and repair history"><RunHistory events={history} /></DataSection>
            <DataSection title="Artifacts"><ArtifactRefs artifacts={detail.artifacts} runId={detail.id} /></DataSection>
            <DataSection title="Log references"><LogReferences refs={detail.log_refs} /><p className="mt-2 text-xs text-muted">Log contents are not shown here.</p></DataSection>
            <p className="text-xs text-muted">Created {dateLabel(detail.created_at)} · Updated {dateLabel(detail.updated_at)}</p>
          </div>
        ) : null}
      </div>
    </dialog>
  );
}
