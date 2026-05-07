import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import type { SearchState, TrendDetail, TrendListItem } from '@/types';

const TERMINAL: SearchState[] = ['completed', 'completed_with_warnings', 'failed'];

interface SearchModeContextType {
  // Completed-search result state (shown in the right pane)
  mode: 'daily' | 'search';
  searchTopic: string;
  searchRunId: string;
  searchTrends: TrendListItem[];
  searchBrief: TrendDetail | null;
  enterSearch: (runId: string, topic: string, trends: TrendListItem[]) => Promise<void>;
  clearSearch: () => void;
  // Active in-progress search (persists across navigation)
  activeRunId: string;
  activePhase: SearchState;
  activeTopic: string;
  activeError: string | null;
  activeIsCached: boolean;
  startSearch: (topic: string, force?: boolean) => Promise<void>;
  resumeSearch: (runId: string, topic: string, currentPhase: SearchState) => void;
  cancelActiveSearch: () => void;
}

const SearchModeContext = createContext<SearchModeContextType | undefined>(undefined);

export function SearchModeProvider({ children }: { children: React.ReactNode }) {
  // Completed-search state
  const [mode, setMode] = useState<'daily' | 'search'>('daily');
  const [searchTopic, setSearchTopic] = useState('');
  const [searchRunId, setSearchRunId] = useState('');
  const [searchTrends, setSearchTrends] = useState<TrendListItem[]>([]);
  const [searchBrief, setSearchBrief] = useState<TrendDetail | null>(null);

  // Active in-progress search state
  const [activeRunId, setActiveRunId] = useState('');
  const [activePhase, setActivePhase] = useState<SearchState>('idle');
  const [activeTopic, setActiveTopic] = useState('');
  const [activeError, setActiveError] = useState<string | null>(null);
  const [activeIsCached, setActiveIsCached] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Ref so the polling interval always reads the latest topic without closure staleness
  const activeTopicRef = useRef('');
  useEffect(() => { activeTopicRef.current = activeTopic; }, [activeTopic]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  const enterSearch = useCallback(async (runId: string, topic: string, trends: TrendListItem[]) => {
    setMode('search');
    setSearchTopic(topic);
    setSearchRunId(runId);
    setSearchTrends(trends);
    setSearchBrief(null);
    if (trends.length > 0) {
      try {
        const res = await fetch(`/api/search/runs/${runId}/trends/${trends[0].slug}`);
        if (res.ok) setSearchBrief(await res.json() as TrendDetail);
      } catch { /* ignore */ }
    }
  }, []);

  // Polling lives in the provider — survives any child component unmount.
  useEffect(() => {
    if (!activeRunId) { stopPolling(); return; }

    const runId = activeRunId;

    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/search/runs/${runId}`);
        if (!res.ok) return;
        const status = await res.json() as { state: SearchState; last_error?: string; topic: string };
        setActivePhase(status.state);

        if (status.state === 'failed') {
          stopPolling();
          setActiveError(status.last_error ?? 'The search pipeline failed.');
          return;
        }

        if (status.state === 'completed' || status.state === 'completed_with_warnings') {
          stopPolling();
          const trendsRes = await fetch(`/api/search/runs/${runId}/trends`);
          if (trendsRes.ok) {
            const trends: TrendListItem[] = await trendsRes.json();
            const topic = activeTopicRef.current || status.topic.split('#')[0];
            await enterSearch(runId, topic, trends);
          }
          // Clear active state — search is done
          setActiveRunId('');
          setActivePhase('idle');
          setActiveTopic('');
        }
      } catch { /* keep polling */ }
    }, 2000);

    return stopPolling;
  }, [activeRunId, stopPolling, enterSearch]);

  async function startSearch(topic: string, force = true) {
    stopPolling();
    setActiveError(null);
    setActivePhase('pending');
    setActiveTopic(topic);
    setActiveIsCached(false);
    setMode('search');
    setSearchTopic(topic);
    setSearchRunId('');
    setSearchTrends([]);
    setSearchBrief(null);

    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, force }),
      });

      if (res.status === 429) {
        setActivePhase('idle');
        setActiveError('Too many searches. Please wait a few minutes and try again.');
        return;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({})) as Record<string, unknown>;
        setActivePhase('idle');
        setActiveError(String(data?.detail ?? 'Search failed. Please try again.'));
        return;
      }

      const searchResp = await res.json() as { run_id: string; cached: boolean };
      const runId = searchResp.run_id;
      setActiveIsCached(searchResp.cached);

      // Persist run_id in URL so navigating away and back can rehydrate polling
      const url = new URL(window.location.href);
      url.searchParams.set('run_id', runId);
      window.history.replaceState({}, '', url.toString());

      if (searchResp.cached) {
        const trendsRes = await fetch(`/api/search/runs/${runId}/trends`);
        if (trendsRes.ok) {
          const trends: TrendListItem[] = await trendsRes.json();
          await enterSearch(runId, topic, trends);
        }
        setActivePhase('idle');
        return;
      }

      // Trigger polling via the effect
      setActiveRunId(runId);
    } catch {
      setActivePhase('idle');
      setActiveError('Could not reach the backend. Is the server running?');
    }
  }

  function resumeSearch(runId: string, topic: string, currentPhase: SearchState) {
    stopPolling();
    setActiveError(null);
    setActiveIsCached(false);
    setActiveTopic(topic);
    setActivePhase(currentPhase);
    setActiveRunId(runId); // triggers the polling useEffect
  }

  function cancelActiveSearch() {
    stopPolling();
    setActiveRunId('');
    setActivePhase('idle');
    setActiveTopic('');
    setActiveError(null);
    setActiveIsCached(false);
    const url = new URL(window.location.href);
    url.searchParams.delete('run_id');
    window.history.replaceState({}, '', url.toString());
  }

  function clearSearch() {
    setMode('daily');
    setSearchTopic('');
    setSearchRunId('');
    setSearchTrends([]);
    setSearchBrief(null);
    const url = new URL(window.location.href);
    url.searchParams.delete('q');
    window.history.pushState({}, '', url.toString());
  }

  return (
    <SearchModeContext.Provider value={{
      mode, searchTopic, searchRunId, searchTrends, searchBrief, enterSearch, clearSearch,
      activeRunId, activePhase, activeTopic, activeError, activeIsCached,
      startSearch, resumeSearch, cancelActiveSearch,
    }}>
      {children}
    </SearchModeContext.Provider>
  );
}

export function useSearchMode() {
  const ctx = useContext(SearchModeContext);
  if (!ctx) throw new Error('useSearchMode must be used within SearchModeProvider');
  return ctx;
}
