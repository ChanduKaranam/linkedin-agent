import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import type { SearchHistoryItem, TrendListItem } from '@/types';

interface SearchHistoryProps {
  onOpen: (runId: string, topic: string, trends: TrendListItem[]) => void;
  activeRunId?: string;
  onPaneScroll?: (scrollTop: number) => void;
}

export default function SearchHistory({ onOpen, activeRunId, onPaneScroll }: SearchHistoryProps) {
  const [items, setItems] = useState<SearchHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [openingRunId, setOpeningRunId] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<'latest' | 'oldest' | 'chatted' | 'created_linkedin' | 'created_blog'>('latest');
  const [runStats, setRunStats] = useState<Record<string, { chats: number; linkedin: number; blog: number }>>({});

  useEffect(() => {
    fetch('/api/search/history')
      .then((r) => (r.ok ? r.json() : []))
      .then((data: SearchHistoryItem[]) => { setItems(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (items.length === 0) return;
    let cancelled = false;
    const sample = items.slice(0, 20);
    void Promise.all(
      sample.map(async (item) => {
        const trends = await fetch(`/api/search/runs/${item.run_id}/trends`)
          .then((r) => (r.ok ? r.json() : [] as TrendListItem[]))
          .catch(() => [] as TrendListItem[]);
        const stats = await Promise.all(
          trends.map(async (t: TrendListItem) => {
            const [chats, posts] = await Promise.all([
              fetch(`/api/chat/runs/${item.run_id}/${t.slug}/messages`).then((r) => (r.ok ? r.json() : [] as unknown[])).catch(() => [] as unknown[]),
              fetch(`/api/posts/runs/${item.run_id}/${t.slug}`).then((r) => (r.ok ? r.json() : [] as Array<{ kind: 'linkedin' | 'blog' }>)).catch(() => [] as Array<{ kind: 'linkedin' | 'blog' }>),
            ]);
            return {
              chats: chats.length,
              linkedin: posts.filter((p: { kind: 'linkedin' | 'blog' }) => p.kind === 'linkedin').length,
              blog: posts.filter((p: { kind: 'linkedin' | 'blog' }) => p.kind === 'blog').length,
            };
          }),
        );
        const total = stats.reduce((acc, s) => ({
          chats: acc.chats + s.chats,
          linkedin: acc.linkedin + s.linkedin,
          blog: acc.blog + s.blog,
        }), { chats: 0, linkedin: 0, blog: 0 });
        return [item.run_id, total] as const;
      }),
    ).then((rows) => {
      if (cancelled) return;
      setRunStats((prev) => ({ ...prev, ...Object.fromEntries(rows) }));
    });
    return () => {
      cancelled = true;
    };
  }, [items]);

  const sortedItems = (() => {
    if (sortMode === 'latest') {
      return [...items].sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime());
    }
    if (sortMode === 'oldest') {
      return [...items].sort((a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime());
    }
    const metric = (id: string) => {
      const s = runStats[id];
      if (!s) return 0;
      if (sortMode === 'chatted') return s.chats;
      if (sortMode === 'created_linkedin') return s.linkedin;
      return s.blog;
    };
    return [...items].sort((a, b) => metric(b.run_id) - metric(a.run_id));
  })();

  async function handleOpen(item: SearchHistoryItem) {
    if (openingRunId) return;
    setOpeningRunId(item.run_id);
    try {
      const res = await fetch(`/api/search/runs/${item.run_id}/trends`);
      if (!res.ok) return;
      const trends: TrendListItem[] = await res.json();
      onOpen(item.run_id, item.topic, trends);
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

  if (items.length === 0) {
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
              {items.length} topic{items.length !== 1 ? 's' : ''}
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
            <option value="chatted">Chatted About</option>
            <option value="created_linkedin">Created LinkedIn Posts</option>
            <option value="created_blog">Created Blog Posts</option>
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
          return (
            <button
              key={item.run_id}
              onClick={() => handleOpen(item)}
              disabled={!!openingRunId}
              className={cn(
                'w-full text-left p-4 border-b border-outline-variant transition-all border-l-2 disabled:opacity-60',
                isActive ? 'bg-surface-container-low border-l-primary' : 'hover:bg-surface-container border-l-transparent',
              )}
            >
              <div className="flex items-start gap-3">
                <span className={cn(
                  'flex-shrink-0 mt-0.5 w-5 h-5 flex items-center justify-center border',
                  isActive ? 'bg-primary text-on-primary border-primary' : 'bg-surface-container border-outline-variant text-on-surface-variant',
                )}>
                  {isOpening ? (
                    <span className="w-2.5 h-2.5 border border-current border-t-transparent animate-spin" />
                  ) : (
                    <span className="text-[9px] font-mono">S</span>
                  )}
                </span>
                <div className="min-w-0 flex-1">
                  <p className={cn('text-sm font-semibold leading-snug line-clamp-2', isActive ? 'text-primary' : 'text-on-surface')}>
                    {item.topic}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="label-bold text-[9px] text-outline">
                      {new Date(item.started_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </span>
                    <span className="label-bold text-[9px] text-outline">
                      {item.trend_count} result{item.trend_count !== 1 ? 's' : ''}
                    </span>
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
