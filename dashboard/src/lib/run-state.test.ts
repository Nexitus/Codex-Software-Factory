import { describe, expect, it } from 'vitest';
import { boardPlacement, deliveryEvidence, formatElapsed, mergeRunEvent, parseRunEvent, runStatusPresentation, statusLabel } from './run-state';
import type { RunDetail, RunSummary } from '../types';

const baseRun: RunSummary = {
  id: 'run-1',
  stage: 'Build',
  status: 'running',
};

describe('factory run state', () => {
  it('keeps Ready gated on completed verified delivery', () => {
    expect(boardPlacement({ ...baseRun, stage: 'Ready', status: 'completed' }).kind).toBe('unclassified');
    expect(boardPlacement({ ...baseRun, stage: 'Ready', status: 'running', delivery_status: 'verified_candidate' }).kind).toBe('unclassified');
    expect(boardPlacement({ ...baseRun, stage: 'Ready', status: 'completed', delivery_status: 'verified_candidate' })).toEqual({ kind: 'stage', stage: 'Ready' });
  });

  it('does not convert unsupported stages or statuses into success', () => {
    expect(boardPlacement({ ...baseRun, stage: 'Done' }).kind).toBe('unclassified');
    expect(statusLabel('stopped')).toBe('Unknown status');
    expect(statusLabel('interrupted')).toBe('Interrupted');
    expect(boardPlacement({ ...baseRun, stage: 'Build', status: 'interrupted' })).toEqual({ kind: 'stage', stage: 'Blocked' });
    expect(boardPlacement({ ...baseRun, stage: 'Blocked', status: 'orphaned' })).toEqual({ kind: 'stage', stage: 'Blocked' });
    expect(runStatusPresentation({ ...baseRun, status: 'orphaned' })).toEqual({ label: 'Interrupted — recovery required', tone: 'danger' });
    expect(runStatusPresentation({ ...baseRun, status: 'interrupted' })).toEqual({ label: 'Interrupted', tone: 'danger' });
  });

  it('shows completion as verified only when the explicit delivery proof is present', () => {
    expect(runStatusPresentation({ ...baseRun, stage: 'Ready', status: 'completed' })).toEqual({ label: 'Verification pending', tone: 'warning' });
    expect(runStatusPresentation({ ...baseRun, stage: 'Ready', status: 'completed', delivery_status: 'verified_candidate' })).toEqual({ label: 'Verified', tone: 'success' });
    expect(runStatusPresentation({ ...baseRun, stage: 'Review', status: 'completed', delivery_status: 'verified_candidate' })).toEqual({ label: 'Verification pending', tone: 'warning' });
  });

  it('keeps missing or contradictory report evidence visible in run details', () => {
    const verified: RunDetail = {
      ...baseRun,
      status: 'completed',
      stage: 'Ready',
      delivery_status: 'verified_candidate',
      history: [{ run_id: 'run-1', type: 'delivery_verified' }],
      report: { status: 'verified_candidate' },
    };
    expect(deliveryEvidence(verified).kind).toBe('verified');
    expect(deliveryEvidence({ ...verified, report: null }).kind).toBe('unavailable');
    expect(deliveryEvidence({ ...verified, report: { status: 'blocked' } })).toMatchObject({ kind: 'mismatch', reportStatus: 'blocked' });
    expect(deliveryEvidence({ ...verified, status: 'orphaned' }).kind).toBe('blocked');
    expect(deliveryEvidence({ ...verified, history: [] }).kind).toBe('pending');
  });

  it('parses sequenced events and merges only authoritative run state', () => {
    const event = parseRunEvent('{"run_id":"run-1","type":"stage_changed","data":{"stage":"Review","status":"running","round":2}}', '42');
    expect(event?.seq).toBe(42);
    expect(mergeRunEvent([baseRun], event!)[0]).toMatchObject({ stage: 'Review', status: 'running', round: 2 });
    expect(parseRunEvent('{broken')).toBeNull();
    expect(parseRunEvent('{"run_id":"run-1","type":"heartbeat"}', '')?.seq).toBeUndefined();
  });

  it('formats elapsed time without inventing a value', () => {
    expect(formatElapsed(undefined)).toBe('—');
    expect(formatElapsed(65)).toBe('1m 5s');
    expect(formatElapsed(3660)).toBe('1h 1m');
    expect(formatElapsed(77040)).toBe('21h 24m');
    expect(formatElapsed(90000)).toBe('1d 1h');
  });
});
