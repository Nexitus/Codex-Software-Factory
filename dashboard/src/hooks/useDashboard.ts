import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../lib/api';
import { mergeRunEvent, parseRunEvent } from '../lib/run-state';
import type { CreateRunRequest, HealthResponse, RunSummary } from '../types';

export type ConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'unavailable';

const reconnectDelay = (attempt: number) => Math.min(1000 * 2 ** Math.min(attempt, 4), 15000);

function errorText(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback;
}

export function useDashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [runError, setRunError] = useState<string | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [connection, setConnection] = useState<ConnectionState>('connecting');
  const [revision, setRevision] = useState(0);
  const cursor = useRef(0);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const disposed = useRef(false);
  const streamRef = useRef<EventSource | null>(null);
  const reconnectRef = useRef<() => void>(() => undefined);
  const refreshRunsRef = useRef<() => Promise<void>>(async () => undefined);

  const refreshHealth = useCallback(async () => {
    try {
      const current = await api.health();
      if (!disposed.current) {
        setHealth(current);
        setHealthError(null);
      }
      return current;
    } catch (error) {
      if (!disposed.current) setHealthError(errorText(error, 'Could not load factory mode and projects.'));
      throw error;
    }
  }, []);

  const refreshRuns = useCallback(async () => {
    try {
      const snapshot = await api.runs();
      const snapshotCursor = Number(snapshot.last_event_id ?? 0);
      if (disposed.current) return;
      if (Number.isSafeInteger(snapshotCursor) && snapshotCursor < cursor.current) {
        if (refreshTimer.current) clearTimeout(refreshTimer.current);
        refreshTimer.current = setTimeout(() => void refreshRunsRef.current(), 100);
        return;
      }
      if (Number.isSafeInteger(snapshotCursor)) cursor.current = Math.max(cursor.current, snapshotCursor);
      setRuns(Array.isArray(snapshot.runs) ? snapshot.runs : []);
      setRevision((value) => value + 1);
      setRunError(null);
      setIsLoading(false);
    } catch (error) {
      if (!disposed.current) {
        setRunError(errorText(error, 'Could not load factory runs.'));
        setIsLoading(false);
      }
    }
  }, []);
  refreshRunsRef.current = refreshRuns;

  const scheduleRefresh = useCallback(() => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    refreshTimer.current = setTimeout(() => void refreshRunsRef.current(), 120);
  }, []);

  useEffect(() => {
    disposed.current = false;
    let reconnectAttempt = 0;
    let booting = false;

    const closeStream = () => {
      streamRef.current?.close();
      streamRef.current = null;
    };

    const scheduleReconnect = () => {
      if (disposed.current || reconnectTimer.current) return;
      setConnection('reconnecting');
      reconnectTimer.current = setTimeout(() => {
        reconnectTimer.current = null;
        void bootstrap();
      }, reconnectDelay(reconnectAttempt++));
    };

    const bootstrap = async () => {
      if (disposed.current || booting) return;
      booting = true;
      closeStream();
      setConnection(reconnectAttempt === 0 ? 'connecting' : 'reconnecting');
      try {
        // Health first establishes/refreshes the same-origin request authorization before opening SSE.
        await refreshHealth();
        const snapshot = await api.runs();
        if (disposed.current) return;
        const snapshotCursor = Number(snapshot.last_event_id ?? 0);
        const safeCursor = Number.isSafeInteger(snapshotCursor) && snapshotCursor >= 0 ? snapshotCursor : 0;
        // The stream is closed while bootstrapping, so a lower cursor means the backend event log reset.
        cursor.current = safeCursor;
        setRuns(Array.isArray(snapshot.runs) ? snapshot.runs : []);
        setRevision((value) => value + 1);
        setRunError(null);
        setIsLoading(false);

        if (typeof EventSource === 'undefined') {
          setConnection('unavailable');
          return;
        }
        const stream = new EventSource('/api/events?after=' + encodeURIComponent(String(safeCursor)));
        streamRef.current = stream;
        stream.onopen = () => {
          if (streamRef.current === stream) setConnection('connected');
        };
        stream.addEventListener('event', (message) => {
          const eventMessage = message as MessageEvent<string>;
          const messageCursor = Number(eventMessage.lastEventId);
          if (!Number.isSafeInteger(messageCursor) || messageCursor < 0 || messageCursor <= cursor.current) return;
          const missedEvents = messageCursor > cursor.current + 1;
          cursor.current = messageCursor;
          const event = parseRunEvent(eventMessage.data, eventMessage.lastEventId);
          if (event) setRuns((current) => mergeRunEvent(current, event));
          if (event || missedEvents) scheduleRefresh();
        });
        stream.onerror = () => {
          if (streamRef.current !== stream) return;
          closeStream();
          scheduleReconnect();
        };
      } catch (error) {
        if (!disposed.current) {
          setHealthError((previous) => previous || errorText(error, 'Could not connect to the local factory service.'));
          setRunError((previous) => previous || errorText(error, 'Could not load factory runs.'));
          setIsLoading(false);
          scheduleReconnect();
        }
      } finally {
        booting = false;
      }
    };

    reconnectRef.current = () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
      reconnectAttempt = 0;
      void bootstrap();
    };
    void bootstrap();

    return () => {
      disposed.current = true;
      closeStream();
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [refreshHealth, scheduleRefresh]);

  const retry = useCallback(() => {
    setHealthError(null);
    setRunError(null);
    setIsLoading(true);
    reconnectRef.current();
  }, []);

  const createRun = useCallback(async (input: CreateRunRequest) => {
    if (!health?.csrf_token) throw new ApiError('The request token is unavailable. Refresh before creating a run.');
    let created: Awaited<ReturnType<typeof api.createRun>>;
    try {
      created = await api.createRun(input, health.csrf_token);
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 403) throw error;
      const current = await refreshHealth();
      if (!current.csrf_token) throw error;
      // A backend restart can rotate authorization between health and submit; retry once after refreshing it.
      created = await api.createRun(input, current.csrf_token);
    }
    await refreshRunsRef.current();
    return created.run_id;
  }, [health, refreshHealth]);

  return {
    health,
    runs,
    isLoading,
    runError,
    healthError,
    connection,
    revision,
    refreshRuns,
    retry,
    createRun,
  };
}
