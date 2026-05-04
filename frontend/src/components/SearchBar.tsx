import { useState, useRef, useEffect, FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { SearchRunStatus, SearchState, TrendListItem } from '@/types';

interface SearchBarProps {
  onResults: (runId: string, topic: string, trends: TrendListItem[]) => void;
  onClear: () => void;
}

const PHASE_LABELS: Record<SearchState, string> = {
  idle: '',
  pending: 'Starting…',
  discovering: 'Discovering sources…',
  scraping: 'Scraping articles…',
  clustering: 'Clustering trends…',
  summarizing: 'Writing summaries…',
  completed: 'Done',
  completed_with_warnings: 'Done (with warnings)',
  failed: 'Failed',
};

const TERMINAL: SearchState[] = ['completed', 'completed_with_warnings', 'failed'];

export default function SearchBar({ onResults, onClear }: SearchBarProps) {
  const [searchParams] = useSearchParams();
  const [query, setQuery] = useState('');
  const [phase, setPhase] = useState<SearchState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [isCached, setIsCached] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const didAutoSearch = useRef(false);

  const isSearching = phase !== 'idle' && !TERMINAL.includes(phase);
  const isDone = phase === 'completed' || phase === 'completed_with_warnings';

  useEffect(() => {
    const q = searchParams.get('q') ?? '';
    if (q && !didAutoSearch.current) {
      didAutoSearch.current = true;
      setQuery(q);
      startSearch(q);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function stopPolling() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }

  async function startSearch(topic: string, force = false) {
    stopPolling();
    setError(null);
    setPhase('pending');
    setIsCached(false);
    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, force }),
      });
      if (res.status === 429) {
        setPhase('idle');
        setError('Too many searches. Please wait a few minutes and try again.');
        return;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({})) as Record<string, unknown>;
        setPhase('idle');
        setError(String(data?.detail ?? 'Search failed. Please try again.'));
        return;
      }
      const searchResp = await res.json() as { run_id: string; cached: boolean };
      const runId = searchResp.run_id;
      setIsCached(searchResp.cached);
      if (searchResp.cached) {
        await fetchAndDeliver(runId, topic);
        setPhase('completed');
        return;
      }
      pollRef.current = setInterval(async () => {
        try {
          const statusRes = await fetch(`/api/search/runs/${runId}`);
          if (!statusRes.ok) return;
          const status: SearchRunStatus = await statusRes.json();
          setPhase(status.state);
          if (status.state === 'failed') { stopPolling(); setError(status.last_error ?? 'The search pipeline failed.'); return; }
          if (status.state === 'completed' || status.state === 'completed_with_warnings') {
            stopPolling();
            await fetchAndDeliver(runId, topic);
          }
        } catch { /* keep polling */ }
      }, 2000);
    } catch {
      setPhase('idle');
      setError('Could not reach the backend. Is the server running?');
    }
  }

  async function fetchAndDeliver(runId: string, topic: string) {
    const res = await fetch(`/api/search/runs/${runId}/trends`);
    if (!res.ok) return;
    const trends: TrendListItem[] = await res.json();
    onResults(runId, topic, trends);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || isSearching) return;
    const url = new URL(window.location.href);
    url.searchParams.set('q', trimmed);
    url.searchParams.delete('t');
    window.history.pushState({}, '', url.toString());
    startSearch(trimmed);
  }

  function handleClear() {
    stopPolling();
    setQuery('');
    setPhase('idle');
    setError(null);
    const url = new URL(window.location.href);
    url.searchParams.delete('q');
    url.searchParams.delete('t');
    window.history.pushState({}, '', url.toString());
    onClear();
  }

  return (
    <div className="flex flex-col gap-2">
      <form onSubmit={handleSubmit} className="relative flex items-center w-full">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Search size={15} className="text-on-surface-variant" />
        </div>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search any AI or tech trend…"
          disabled={isSearching}
          className="w-full pl-9 pr-32 py-2.5 bg-surface-container-low border border-outline-variant text-sm outline-none focus:border-primary focus:border-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        />
        <div className="absolute inset-y-0 right-1 flex items-center gap-1">
          {isDone && (
            <button type="button" onClick={handleClear} className="p-1.5 text-on-surface-variant hover:text-on-surface transition-colors">
              <X size={14} />
            </button>
          )}
          <button
            type="submit"
            disabled={!query.trim() || isSearching}
            className={cn('btn-primary py-1.5 px-4 text-[10px] my-1 mr-0.5 disabled:opacity-50 disabled:cursor-not-allowed')}
          >
            {isSearching ? 'Searching…' : 'Search'}
          </button>
        </div>
      </form>

      {phase !== 'idle' && (
        <div className="flex items-center gap-2 text-[11px] font-mono text-on-surface-variant pl-1">
          {isSearching && <span className="w-3 h-3 border-2 border-primary border-t-transparent animate-spin" />}
          <span className="label-bold text-[10px]">{PHASE_LABELS[phase]}</span>
          {isCached && isDone && (
            <>
              <span className="text-outline-variant">·</span>
              <span className="text-outline">Cached result</span>
              <button onClick={() => startSearch(query.trim(), true)} className="text-primary hover:underline label-bold text-[10px]">
                Refresh
              </button>
            </>
          )}
        </div>
      )}

      {error && <p className="text-[11px] text-red-600 pl-1 font-mono">{error}</p>}
    </div>
  );
}
