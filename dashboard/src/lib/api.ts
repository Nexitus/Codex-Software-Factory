import type { CreateRunRequest, CreateRunResponse, HealthResponse, RunDetail, RunsResponse } from '../types';

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = 'ApiError';
  }
}

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, { credentials: 'same-origin', ...init });
  } catch {
    throw new ApiError('The local factory service could not be reached.');
  }
  if (!response.ok) {
    const message = response.status === 403
      ? 'The request was not authorized. Refresh the page and try again.'
      : 'The factory service returned an error (' + response.status + ').';
    throw new ApiError(message, response.status);
  }
  try {
    return await response.json() as T;
  } catch {
    throw new ApiError('The factory service returned an unreadable response.', response.status);
  }
}

export const api = {
  health: () => json<HealthResponse>('/api/health'),
  runs: async () => {
    if (import.meta.env.DEV) {
      const fixtures = await import('./dev-fixtures');
      const mode = fixtures.readDevFixtureMode();
      if (mode) {
        if (mode === 'error') throw new ApiError('Fixture response: local run service is unavailable (503).', 503);
        return fixtures.buildDevRuns(mode);
      }
    }
    return json<RunsResponse>('/api/runs');
  },
  run: async (id: string, signal?: AbortSignal) => {
    if (import.meta.env.DEV) {
      const fixtures = await import('./dev-fixtures');
      const mode = fixtures.readDevFixtureMode();
      if (mode) {
        const detail = fixtures.buildDevDetail(mode, id);
        if (!detail) throw new ApiError('That fixture run is not available.', 404);
        return detail;
      }
    }
    return json<RunDetail>('/api/runs/' + encodeURIComponent(id), { signal });
  },
  createRun: (input: CreateRunRequest, csrfToken: string) => json<CreateRunResponse>('/api/runs', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,
    },
    body: JSON.stringify(input),
  }),
};
