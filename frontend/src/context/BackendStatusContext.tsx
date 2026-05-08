import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import type { BackendStatus, Health, ScheduleConfig } from '@/types';

interface BackendStatusContextType {
  backendStatus: BackendStatus;
  schedule: ScheduleConfig | null;
  availableDates: string[];
  selectedDate: string;
  setSelectedDate: (d: string) => void;
  setSchedule: (s: ScheduleConfig) => void;
  refresh: () => void;
}

const BackendStatusContext = createContext<BackendStatusContextType | undefined>(undefined);

export function BackendStatusProvider({ children }: { children: React.ReactNode }) {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('ok');
  const [schedule, setSchedule] = useState<ScheduleConfig | null>(null);
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState('');
  const consecutiveFailures = useRef(0);

  const bootstrap = useCallback(async () => {
    try {
      const [healthRes, datesRes, scheduleRes] = await Promise.all([
        fetch('/api/health'),
        fetch('/api/trends/dates'),
        fetch('/api/admin/schedule'),
      ]);

      if (!healthRes.ok) {
        consecutiveFailures.current += 1;
        setBackendStatus('unreachable');
        return;
      }
      const health: Health & { error?: string } = await healthRes.json();
      if (health.error === 'backend_unreachable') {
        consecutiveFailures.current += 1;
        setBackendStatus('unreachable');
        return;
      }

      consecutiveFailures.current = 0;
      const dates: string[] = datesRes.ok ? await datesRes.json() : [];

      if (health.pipeline_running) {
        setBackendStatus('running');
        setAvailableDates(dates);
        if (dates.length > 0) {
          const urlDate = new URLSearchParams(window.location.search).get('d');
          setSelectedDate(urlDate && dates.includes(urlDate) ? urlDate : dates[0]);
        }
        if (scheduleRes.ok) setSchedule(await scheduleRes.json());
        return;
      }

      if (dates.length === 0) {
        setBackendStatus('no_run');
        setAvailableDates([]);
        return;
      }

      setAvailableDates(dates);
      const urlDate = new URLSearchParams(window.location.search).get('d');
      setSelectedDate(urlDate && dates.includes(urlDate) ? urlDate : dates[0]);
      setBackendStatus('ok');
      if (scheduleRes.ok) setSchedule(await scheduleRes.json());
    } catch {
      consecutiveFailures.current += 1;
      setBackendStatus('unreachable');
    }
  }, []);

  useEffect(() => { bootstrap(); }, [bootstrap]);

  useEffect(() => {
    // Base interval: 5s when pipeline running, 15s when idle
    const base = backendStatus === 'running' ? 5_000 : 15_000;
    // Exponential backoff on consecutive failures: 15s → 30s → 60s (cap)
    const backoff = consecutiveFailures.current > 0
      ? Math.min(15_000 * 2 ** (consecutiveFailures.current - 1), 60_000)
      : base;

    const scheduleNext = () => {
      const id = window.setTimeout(() => {
        // Pause polling when tab is hidden — resume when visible again
        if (document.visibilityState === 'hidden') {
          scheduleNext();
          return;
        }
        void bootstrap().then(() => scheduleNext());
      }, backoff);
      return id;
    };

    const id = scheduleNext();
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') void bootstrap();
    };
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      window.clearTimeout(id);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [bootstrap, backendStatus]);

  return (
    <BackendStatusContext.Provider value={{ backendStatus, schedule, availableDates, selectedDate, setSelectedDate, setSchedule, refresh: bootstrap }}>
      {children}
    </BackendStatusContext.Provider>
  );
}

export function useBackendStatus() {
  const ctx = useContext(BackendStatusContext);
  if (!ctx) throw new Error('useBackendStatus must be used within BackendStatusProvider');
  return ctx;
}
