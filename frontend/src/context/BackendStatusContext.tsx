import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
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

  const bootstrap = useCallback(async () => {
    try {
      const [healthRes, datesRes, scheduleRes] = await Promise.all([
        fetch('/api/health'),
        fetch('/api/trends/dates'),
        fetch('/api/admin/schedule'),
      ]);

      // Health check
      if (!healthRes.ok) {
        setBackendStatus('unreachable');
        return;
      }
      const health: Health & { error?: string } = await healthRes.json();
      if (health.error === 'backend_unreachable') {
        setBackendStatus('unreachable');
        return;
      }

      // Dates (only completed runs are returned by the API)
      const dates: string[] = datesRes.ok ? await datesRes.json() : [];

      if (health.pipeline_running) {
        setBackendStatus('running');
        // Still populate previous completed-run dates so the user can browse history
        setAvailableDates(dates);
        if (dates.length > 0) {
          const urlDate = new URLSearchParams(window.location.search).get('d');
          setSelectedDate(urlDate && dates.includes(urlDate) ? urlDate : dates[0]);
        }
        if (scheduleRes.ok) {
          const s: ScheduleConfig = await scheduleRes.json();
          setSchedule(s);
        }
        return;
      }

      if (dates.length === 0) {
        setBackendStatus('no_run');
        setAvailableDates([]);
        return;
      }

      setAvailableDates(dates);
      // Read ?d= param from URL or fall back to first date
      const urlDate = new URLSearchParams(window.location.search).get('d');
      setSelectedDate(urlDate && dates.includes(urlDate) ? urlDate : dates[0]);
      setBackendStatus('ok');

      // Schedule (best-effort)
      if (scheduleRes.ok) {
        const s: ScheduleConfig = await scheduleRes.json();
        setSchedule(s);
      }
    } catch {
      setBackendStatus('unreachable');
    }
  }, []);

  useEffect(() => { bootstrap(); }, [bootstrap]);
  // Poll every 5s while the pipeline is running so completion is detected quickly.
  // Fall back to 15s when idle to reduce unnecessary requests.
  useEffect(() => {
    const interval = backendStatus === 'running' ? 5000 : 15000;
    const id = window.setInterval(() => { void bootstrap(); }, interval);
    return () => window.clearInterval(id);
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
