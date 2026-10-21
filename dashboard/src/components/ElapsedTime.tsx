import { useEffect, useRef, useState } from 'react';
import { formatElapsed } from '../lib/run-state';

interface ElapsedTimeProps {
  seconds?: number;
  status?: string;
}

export function ElapsedTime({ seconds, status }: ElapsedTimeProps) {
  const running = status === 'running';
  const anchor = useRef({ seconds, status, receivedAt: Date.now() });
  if (anchor.current.seconds !== seconds || anchor.current.status !== status) {
    anchor.current = { seconds, status, receivedAt: Date.now() };
  }
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [running]);

  const displayedSeconds = running && typeof seconds === 'number' && Number.isFinite(seconds)
    ? seconds + Math.max(0, Math.floor((now - anchor.current.receivedAt) / 1000))
    : seconds;
  const label = formatElapsed(displayedSeconds);
  return <time data-testid="elapsed-time" aria-label={'Elapsed execution time ' + label}>{label}</time>;
}
