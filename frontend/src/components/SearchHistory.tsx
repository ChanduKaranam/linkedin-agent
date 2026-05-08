import { useEffect, useMemo, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { useSearchMode } from '@/context/SearchModeContext';
import type { SearchHistoryItem, SearchState, TrendListItem } from '@/types';

const IN_PROGRESS: SearchState[] = ['pending', 'discovering', 'scraping', 'clustering', 'summarizing'];
const PHASE_SHORT: Partial<Record<SearchState, string>> = {
  pending: 'Starting',
  discovering: 'Discovering',
  scraping: 'Scraping',
  clustering: 'Clustering',
  summarizing: 'Summarizing',
};

interface SearchHistoryProps {
  activeRunId?: string;
  onPaneScroll?: (scrollTop: number) => void;
}

export default function SearchHistory({ activeRunId, onPaneScroll }: SearchHistoryProps) {
  const { enterSearch, resumeSearch, activeTopic, activePhase } = useSearchMode();
  const [items, setItems] = useState<SearchHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [openingRunId, setOpeningRunId] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<'latest' | 'oldest'>('latest');

  const activeStartedAtRef = useRef('');

  useEffect(() => {
    if (!activeRunId || activePhase === 'idle') {
      activeStartedAtRef.current = '';
      return;
    }
    if (!activeStartedAtRef.current) activeStartedAtRef.current = new Date().toISOString();
  }, [activeRunId, activePhase]);

  useEffect(() => {
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    const FAST_POLL_MS = 30000;
    const SLOW_POLL_MS = 120000;

    const loadHistory = async () => {
      try {
        const res = await fetch('/api/search/history');
        const data = res.ok ? await res.json() as SearchHistoryItem[] : [];
        if (!cancelled) {
          setItems(data);
          setLoading(false);
        }
      } catch {
        if (!cancelled) setLoading(false);
      }
    };

    const schedule = () => {
      if (cancelled) return;
      const delay = document.visibilityState === 'visible' ? FAST_POLL_MS : SLOW_POLL_MS;
      timeoutId = setTimeout(async () => {
        await loadHistory();
        schedule();
      }, delay);
    };

    const onVisibility = () => {
      if (document.visibilityState !== 'visible') return;
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
      void loadHistory();
      schedule();
    };

    void loadHistory();
    schedule();
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  const displayItems = useMemo(() => {
    if (!activeRunId || activePhase === 'idle' || !IN_PROGRESS.includes(activePhase)) return items;
    const started_at = activeStartedAtRef.current || new Date().toISOString();
    const run_date = started_at.slice(0, 10);
    const optimistic: SearchHistoryItem = {
      run_id: activeRunId,
      topic: activeTopic,
      run_date,
      state: activePhase,
      trend_count: 0,
      started_at,
    };
    const existingIdx = items.findIndex((item) => item.run_id === activeRunId);
    if (existingIdx === -1) return [optimistic, ...items];
    const updated = [...items];
    updated[existingIdx] = { ...updated[existingIdx], topic: activeTopic || updated[existingIdx].topic, state: activePhase };
    return updated;
  }, [items, activeRunId, activePhase, activeTopic]);

  const sortedItems = (() => {
    if (sortMode === 'latest') {
      return [...displayItems].sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime());
    }
    if (sortMode === 'oldest') {
      return [...displayItems].sort((a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime());
    }
    return displayItems;
  })();

  async function handleOpen(item: SearchHistoryItem) {
    if (openingRunId) return;
    // In-progress runs: resume polling instead of trying to load trends
    if (IN_PROGRESS.includes(item.state as SearchState)) {
      resumeSearch(item.run_id, item.topic, item.state as SearchState);
      return;
    }
    setOpeningRunId(item.run_id);
    try {
      const res = await fetch(`/api/search/runs/${item.run_id}/trends`);
      if (!res.ok) return;
      const trends: TrendListItem[] = await res.json();
      await enterSearch(item.run_id, item.topic, trends);
    } finally {
      setOpeningRunId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10 text-on-surface-variant">
        <span className="w-4 h-4 border-2 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  if (displayItems.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 px-5 text-center gap-3">
        <div className="w-8 h-8 border border-outline-variant flex items-center justify-center">
          <span className="text-outline font-mono text-xs">?</span>
        </div>
        <p className="text-sm font-bold uppercase tracking-tight">No searches yet</p>
        <p className="text-xs text-on-surface-variant leading-snug max-w-[200px]">
          Use the search bar above to research any AI or tech topic.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3 border-b border-outline-variant bg-surface-container-low">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="label-bold">Your Searches</p>
            <p className="text-xs text-on-surface-variant mt-0.5 font-mono">
              {displayItems.length} topic{displayItems.length !== 1 ? 's' : ''}
            </p>
          </div>
          <select
            value={sortMode}
            onChange={(e) => setSortMode(e.target.value as typeof sortMode)}
            className="text-[10px] font-bold uppercase tracking-widest border border-outline-variant bg-surface-container-lowest px-2 py-1 outline-none focus:border-primary"
            aria-label="Sort searches"
          >
            <option value="latest">Latest</option>
            <option value="oldest">Oldest</option>
          </select>
        </div>
      </div>
      <div
        className="flex-1 overflow-y-auto overscroll-contain"
        onScroll={(e) => onPaneScroll?.(e.currentTarget.scrollTop)}
      >
        {sortedItems.map((item) => {
          const isActive = item.run_id === activeRunId;
          const isOpening = openingRunId === item.run_id;
          const isInProgress = IN_PROGRESS.includes(item.state as SearchState);
          return (
            <button
              key={item.run_id}
              onClick={() => handleOpen(item)}
              disabled={!!openingRunId && !isInProgress}
              className={cn(
                'w-full text-left p-4 border-b border-outline-variant transition-all border-l-2 disabled:opacity-60',
                isActive ? 'bg-surface-container-low border-l-primary' : 'hover:bg-surface-container border-l-transparent',
              )}
            >
              <div className="flex items-start gap-3 min-w-0">
                <span className={cn(
                  'flex-shrink-0 mt-0.5 w-5 h-5 flex items-center justify-center border',
                  isActive ? 'bg-primary text-on-primary border-primary' : 'bg-surface-container border-outline-variant text-on-surface-variant',
                )}>
                  {isOpening || isInProgress ? (
                    <span className="w-2.5 h-2.5 border border-current border-t-transparent animate-spin" />
                  ) : (
                    <span className="text-[9px] font-mono">S</span>
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <p className={cn('text-sm font-semibold leading-snug line-clamp-2 break-words', isActive ? 'text-primary' : 'text-on-surface')}>
                    {item.topic}
                  </p>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <span className="label-bold text-[9px] text-outline">
                      {new Date(item.started_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </span>
                    {isInProgress ? (
                      <span className="label-bold text-[9px] text-primary">{PHASE_SHORT[item.state as SearchState] ?? 'Running'}…</span>
                    ) : (
                      <span className="label-bold text-[9px] text-outline">
                        {item.trend_count} result{item.trend_count !== 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
