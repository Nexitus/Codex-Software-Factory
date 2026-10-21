export const STAGES = [
  'Queue',
  'Planning',
  'Design',
  'Build',
  'Review',
  'Repair',
  'Ready',
  'Blocked',
] as const;

export type Stage = (typeof STAGES)[number];
export type RunStatus = 'queued' | 'running' | 'completed' | 'blocked' | 'interrupted' | 'orphaned';

export interface Agent {
  role: string;
  phase?: string;
  provider?: string;
  model?: string;
  status?: string;
  seconds?: number;
  verdict?: string;
}

export interface Gate {
  name: string;
  round?: number;
  pass?: boolean;
  status?: string;
  exit_code?: number | null;
  timed_out?: boolean;
}

export interface FindingCounts {
  critical?: number;
  high?: number;
  medium?: number;
  low?: number;
}

export interface Finding {
  id?: string;
  severity?: string;
  file?: string;
  evidence?: string;
  remediation?: string;
  role?: string;
  round?: number;
}

export interface RunEvent {
  id?: number | string;
  seq?: number;
  run_id: string;
  type: string;
  timestamp?: string;
  data?: {
    stage?: string;
    status?: string;
    round?: number;
    attempt?: number | null;
    delivery_status?: string | null;
    [key: string]: unknown;
  };
}

export interface ArtifactRef {
  path?: string;
  name?: string;
  kind?: string;
  size?: number;
}

export interface LogRef {
  path?: string;
  name?: string;
  kind?: string;
  role?: string;
}

export interface RunSummary {
  id: string;
  project_id?: string;
  project_name?: string;
  requirement?: string;
  status?: string;
  stage?: string;
  delivery_status?: string | null;
  round?: number;
  max_rounds?: number;
  elapsed_seconds?: number;
  finding_counts?: FindingCounts;
  gates?: Gate[];
  agents?: Agent[];
  created_at?: string;
  updated_at?: string;
}

export interface RunDetail extends RunSummary {
  plan?: {
    summary?: string;
    acceptance_criteria?: Array<string | { id?: string; description?: string; verification?: string }>;
    [key: string]: unknown;
  } | null;
  delivery?: Record<string, unknown> | null;
  report?: Record<string, unknown> | null;
  events?: RunEvent[];
  history?: RunEvent[];
  findings?: Finding[];
  active_findings?: Finding[];
  artifacts?: ArtifactRef[];
  log_refs?: Array<string | LogRef>;
  design?: Array<{
    role?: string;
    guidance?: string[];
    checks?: string[];
    risks?: string[];
    blocking_questions?: string[];
  }>;
}

export interface Project {
  id: string;
  name: string;
}

export interface HealthResponse {
  mode?: 'demo' | 'live' | string;
  csrf_token?: string;
  projects?: Project[];
}

export interface RunsResponse {
  runs: RunSummary[];
  active_run_id?: string | null;
  queued_run_ids?: string[];
  last_event_id?: number;
}

export interface CreateRunRequest {
  requirement: string;
  project_id: string;
  demo_outcome?: 'ready' | 'blocked';
}

export interface CreateRunResponse {
  run_id: string;
  status?: string;
}
