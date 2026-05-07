import { FormEvent, useEffect, useState } from 'react';
import { Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSearchMode } from '@/context/SearchModeContext';
import type { SearchState } from '@/types';

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

interface SearchBarProps {
  onClear?: () => void;
  /** If provided, auto-triggers a search for this topic on mount (used for ?q= URL hydration). */
  initialQuery?: string;
}

export default function SearchBar({ onClear, initialQuery }: SearchBarProps) {
  const { activePhase, activeTopic, activeError, activeRunId, startSearch, cancelActiveSearch } = useSearchMode();
  const [query, setQuery] = useState(initialQuery ?? '');

  const isSearching = activePhase !== 'idle' && !TERMINAL.includes(activePhase);
  const isDone = activePhase === 'completed' || activePhase === 'completed_with_warnings';

  // Keep input in sync when context drives topic changes (e.g. resume from history)
  useEffect(() => {
    if (activeTopic && activeTopic !== query) setQuery(activeTopic);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTopic]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || isSearching) return;
    const url = new URL(window.location.href);
    url.searchParams.set('q', trimmed);
    url.searchParams.delete('t');
    window.history.pushState({}, '', url.toString());
    void startSearch(trimmed, true);
  }

  function handleClear() {
    cancelActiveSearch();
    setQuery('');
    const url = new URL(window.location.href);
    url.searchParams.delete('q');
    url.searchParams.delete('run_id');
    url.searchParams.delete('t');
    window.history.pushState({}, '', url.toString());
    onClear?.();
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
          {(isDone || activePhase === 'failed') && (
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

      {activePhase !== 'idle' && (
        <div className="flex items-center gap-2 text-[11px] font-mono text-on-surface-variant pl-1">
          {isSearching && <span className="w-3 h-3 border-2 border-primary border-t-transparent animate-spin" />}
          <span className="label-bold text-[10px]">{PHASE_LABELS[activePhase]}</span>
        </div>
      )}

      {activeError && <p className="text-[11px] text-red-600 pl-1 font-mono">{activeError}</p>}
    </div>
  );
}
