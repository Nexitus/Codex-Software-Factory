import type { RunDetail, RunSummary, RunsResponse } from '../types';

export type DevFixtureMode = 'worst' | 'empty' | 'one' | 'many' | 'error';

const longRequirementText = 'Update the factory console for Aleksandra Wiśniewska-Kowalczyk: keep delivery verification visible, preserve the review evidence, and explain why a blocked run needs operator recovery. ';
export const longestRequirement = (longRequirementText.repeat(Math.ceil(20000 / longRequirementText.length))).slice(0, 20000);

const time = '2026-10-20T19:15:00-07:00';
const now = '2026-10-21T09:30:00-07:00';
const primaryId = '9f8e7d6c-5b4a-4c3d-8e2f-1a0b9c8d7e6f';

const blockedRun: RunSummary = {
  id: primaryId,
  project_id: 'project-terminal-operations',
  project_name: 'Aleksandra Wiśniewska-Kowalczyk — Operations Infrastructure',
  requirement: longestRequirement,
  status: 'orphaned',
  stage: 'Blocked',
  delivery_status: 'orphaned',
  round: 4,
  max_rounds: 4,
  elapsed_seconds: 77040,
  finding_counts: { critical: 0, high: 1, medium: 1284, low: 0 },
  gates: [
    { name: 'Factory lint and static checks', round: 4, pass: true, status: 'passed', exit_code: 0 },
    { name: 'Delivery verification', round: 4, pass: false, status: 'timed_out', timed_out: true },
  ],
  agents: [
    { role: 'reviewer', phase: 'independent review', provider: 'OpenAI', model: 'gpt-6.1-sol', status: 'running', seconds: 491 },
    { role: 'builder', phase: 'repair', provider: 'OpenCode', model: 'gpt-6-luna', status: 'failed', seconds: 1284 },
    { role: 'design', phase: 'architecture', provider: 'OpenAI', model: 'gpt-6.1-sol', status: 'succeeded', seconds: 116 },
    { role: 'planner', provider: 'OpenAI', model: 'gpt-6.1-sol', status: 'succeeded', seconds: 72 },
    { role: 'test', provider: 'OpenCode', model: 'gpt-6-luna', status: 'timed_out', seconds: 300 },
    { role: 'security', provider: 'OpenCode', model: 'gpt-6-luna', status: 'queued' },
    { role: 'docs', provider: 'OpenCode', model: 'gpt-6-luna', status: 'succeeded', seconds: 19 },
    { role: 'accessibility', provider: 'OpenCode', model: 'gpt-6-luna', status: 'queued' },
  ],
  created_at: time,
  updated_at: now,
};

const oneRun: RunSummary = {
  id: 'a4b3c2d1-0e9f-4876-8a5b-3c2d1e0f9a8b',
  project_id: 'terminal-ops',
  project_name: 'Factory Console',
  requirement: 'Jo',
  status: 'running',
  stage: 'Build',
  round: 1,
  max_rounds: 3,
  elapsed_seconds: 1,
  created_at: now,
  updated_at: now,
};

const runs: RunSummary[] = [
  blockedRun,
  {
    id: '80f8e9b8-4147-4db1-bcd7-b18d0a287c6e',
    project_id: 'terminal-ops',
    project_name: 'Operations / Design-System',
    requirement: 'Plan for multilingual requirements, including Đặng Thị Ngọc Hân and 王秀英.',
    status: 'running',
    stage: 'Planning',
    round: 1,
    max_rounds: 3,
    elapsed_seconds: 65,
    agents: [],
    finding_counts: { critical: 0, high: 0, medium: 0, low: 0 },
    gates: [],
    created_at: time,
    updated_at: now,
  },
  {
    id: 'd44c8a64-0a97-4a51-a31d-77f9204b19e2',
    project_id: 'terminal-ops',
    project_name: 'Factory Console',
    requirement: '<script>alert(1)</script> &amp; **literal text**\nSecond line',
    status: 'failed',
    stage: 'Review',
    round: 2,
    max_rounds: 3,
    elapsed_seconds: 1284,
    finding_counts: { critical: 1, high: 2, medium: 0, low: 0 },
    created_at: time,
    updated_at: now,
  },
  {
    id: '04ac5544-6062-42ed-b610-bc8f4beec9ae',
    project_id: 'terminal-ops',
    project_name: 'Factory Console',
    requirement: 'Document the persisted delivery verification for the repaired workflow.',
    status: 'completed',
    stage: 'Ready',
    delivery_status: 'verified_candidate',
    round: 3,
    max_rounds: 3,
    elapsed_seconds: 432,
    finding_counts: { critical: 0, high: 0, medium: 0, low: 0 },
    gates: [{ name: 'Delivery verification', round: 3, pass: true, status: 'passed', exit_code: 0 }],
    agents: [{ role: 'reviewer', provider: 'OpenAI', model: 'gpt-6.1-sol', status: 'succeeded', verdict: 'passed' }],
    created_at: time,
    updated_at: now,
  },
  { id: '2e36b090-8f23-4ea6-a972-fd665855fe0a', project_id: 'terminal-ops', project_name: 'Factory Console', requirement: 'Queue empty fields test', status: 'queued', stage: 'Queue' },
];

const repairHistoryRaw = [
  ['run_queued', 'Queue', 'queued', 1, 1],
  ['plan_started', 'Planning', 'running', 1, 1],
  ['plan_completed', 'Planning', 'running', 1, 1],
  ['design_started', 'Design', 'running', 1, 1],
  ['design_completed', 'Design', 'running', 1, 1],
  ['build_started', 'Build', 'running', 1, 1],
  ['build_completed', 'Build', 'running', 1, 1],
  ['review_started', 'Review', 'running', 1, 1],
  ['review_completed', 'Repair', 'running', 1, 1],
  ['repair_requested', 'Repair', 'running', 2, 1],
  ['repair_started', 'Repair', 'running', 2, 1],
  ['repair_completed', 'Review', 'running', 2, 1],
  ['review_started', 'Review', 'running', 2, 1],
  ['delivery_verified', 'Ready', 'completed', 2, 1],
];

const repairHistory = repairHistoryRaw.map(([type, stage, status, round, attempt], index) => ({
  id: index + 1,
  seq: index + 1,
  run_id: '04ac5544-6062-42ed-b610-bc8f4beec9ae',
  type: String(type),
  timestamp: new Date(Date.parse(now) - (repairHistoryRaw.length - index) * 60_000).toISOString(),
  data: { stage: String(stage), status: String(status), round: Number(round), attempt: Number(attempt) },
}));

const detail: RunDetail = {
  ...runs[3],
  requirement: 'Document the persisted delivery verification for the repaired workflow. Include a short operator-facing explanation and an architecture summary for planner and design roles.',
  plan: {
    summary: 'Keep event history authoritative, make the board stage explicit, and require persisted delivery verification before showing a successful result.',
    acceptance_criteria: [
      { id: 'AC-1', description: 'The run reaches Ready only after delivery_verified is persisted.', verification: 'Inspect the final event and delivery_status.' },
      { id: 'AC-2', description: 'A failed review produces a repair event before a passing review.', verification: 'Review the ordered run history.' },
      { id: 'AC-3', description: 'Responsive layouts keep the document body within the viewport.', verification: 'Measure scrollWidth at 320 and 390 pixels.' },
    ],
  },
  design: [
    {
      role: 'design',
      guidance: ['Show delivery verification as persisted evidence, with the related review and repair events in the same detail view.'],
      checks: ['The Ready badge and delivery summary agree on whether verification is present.', 'The status name remains visible without relying on its color.'],
      risks: ['Long role and model names may compete for the card status and identifier at 280 pixels.'],
      blocking_questions: [],
    },
    {
      role: 'planner',
      guidance: ['Preserve this project’s queue, worker, event-store, and checkout lifecycle contracts when changing the operator UI.'],
      checks: ['The initial list snapshot has a matching event cursor.', 'Recovery-required runs remain blocked until the supervisor proves cleanup.'],
      risks: ['Event replay after a backend restart can move a card to an earlier stage unless the snapshot cursor is re-established.'],
      blocking_questions: ['Should artifact JSON references become downloadable in a later version?'],
    },
  ],
  delivery: { summary: 'Verified after one repair round.', reason: 'Review findings were repaired and the final delivery gate passed.' },
  report: { status: 'verified_candidate', summary: 'Synthetic fixture report with a verified delivery status.' },
  events: repairHistory,
  history: repairHistory,
  active_findings: [
    { id: 'F-1', severity: 'high', role: 'reviewer', round: 1, file: 'dashboard/src/components/RunCard.tsx', evidence: 'The first review reported an operator state-label issue.', remediation: 'Keep the run status label visible and verify the delivery event before showing success.' },
    { id: 'F-2', severity: 'medium', role: 'design', round: 1, file: 'dashboard/src/App.tsx', evidence: 'Narrow lanes can hide later stages beyond the viewport.', remediation: 'Keep horizontal stage navigation visible and keyboard operable.' },
  ],
  findings: [],
  finding_counts: { critical: 0, high: 0, medium: 0, low: 0 },
  agents: blockedRun.agents,
  gates: [
    { name: 'Frontend unit tests', round: 2, pass: true, status: 'passed', exit_code: 0 },
    { name: 'Independent review', round: 1, pass: false, status: 'failed', exit_code: 1 },
    { name: 'Delivery verification', round: 2, pass: true, status: 'passed', exit_code: 0 },
    { name: 'Browser smoke test with a long descriptive label that wraps cleanly', round: 2, pass: false, status: 'timed_out', timed_out: true },
  ],
  artifacts: [{ path: 'dashboard/dist/artifacts/very-long-review-evidence-for-a-verified-factory-run-round-two.json', name: 'Q3 Board Deck — FINAL (revised) v12 [approved by legal].json', kind: 'json', size: 1284 }],
  log_refs: [{ path: 'runs/9f8e7d6c/agents/reviewer/events.jsonl', name: 'Reviewer event reference', kind: 'metadata', role: 'reviewer' }],
  created_at: time,
  updated_at: now,
  elapsed_seconds: 1284,
};

const stageCycle = ['Queue', 'Planning', 'Design', 'Build', 'Review', 'Repair', 'Ready', 'Blocked'] as const;
const manyRuns: RunSummary[] = Array.from({ length: 1000 }, (_, index) => {
  const stage = stageCycle[index % stageCycle.length];
  const status = stage === 'Ready' ? 'completed' : stage === 'Blocked' ? 'blocked' : stage === 'Queue' ? 'queued' : 'running';
  return {
    id: '00000000-0000-4000-8000-' + String(index + 1).padStart(12, '0'),
    project_id: 'terminal-ops',
    project_name: index % 3 === 0 ? 'Operations' : 'Factory Console',
    requirement: ['Review the operator queue and preserve audit evidence.', 'Add the missing status label for blocked delivery.', 'Document the repair attempt and its verification gate.'][index % 3],
    status,
    stage,
    ...(stage === 'Ready' ? { delivery_status: 'verified_candidate' } : {}),
    round: index % 4 + 1,
    max_rounds: 4,
    elapsed_seconds: index % 1284,
    finding_counts: { critical: 0, high: 0, medium: 0, low: 0 },
    created_at: time,
    updated_at: now,
  };
});

export function readDevFixtureMode(): DevFixtureMode | null {
  if (!import.meta.env.DEV || typeof window === 'undefined') return null;
  const value = new URLSearchParams(window.location.search).get('data');
  return ['worst', 'empty', 'one', 'many', 'error'].includes(value || '') ? value as DevFixtureMode : null;
}

export function buildDevRuns(mode: DevFixtureMode): RunsResponse {
  if (mode === 'error') throw new Error('Fixture response: local run service is unavailable (503).');
  if (mode === 'empty') return { runs: [], last_event_id: 0 };
  if (mode === 'one') return { runs: [oneRun], last_event_id: 0 };
  if (mode === 'many') return { runs: manyRuns, last_event_id: 0 };
  return { runs, last_event_id: 0 };
}

export function buildDevDetail(mode: DevFixtureMode, id: string): RunDetail | null {
  if (mode === 'error') return null;
  const candidate = mode === 'one' ? oneRun : mode === 'many' ? manyRuns.find((run) => run.id === id) : runs.find((run) => run.id === id);
  if (!candidate) return null;
  if (candidate.id === detail.id) return detail;
  return {
    ...candidate,
    plan: null,
    delivery: null,
    events: [],
    history: [],
    findings: [],
    active_findings: [],
    gates: candidate.gates ?? [],
    agents: candidate.agents ?? [],
    artifacts: mode === 'worst' && candidate.id === primaryId
      ? [{ path: 'ERROR.json', name: 'ERROR.json', kind: 'json', size: 310 }]
      : [],
    log_refs: [],
  };
}

export const devFixtureCounts = {
  worst: runs.length,
  empty: 0,
  one: 1,
  many: manyRuns.length,
};

