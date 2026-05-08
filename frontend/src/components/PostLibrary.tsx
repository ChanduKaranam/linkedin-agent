import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Plus, Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { GeneratedPostWithHeadline } from '@/types';

interface PostLibraryProps {
  kind: 'linkedin' | 'blog';
  activeId: number | null;
  onSelect: (post: GeneratedPostWithHeadline) => void;
  onNewPost: () => void;
  refreshKey?: number;
  /** Called with the first (most-recently-updated) post once the initial fetch completes. */
  onFirstLoad?: (post: GeneratedPostWithHeadline) => void;
}

function dateBucket(isoDateStr: string): string {
  // isoDateStr is run_date: YYYY-MM-DD
  const d = new Date(isoDateStr + 'T00:00:00');
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
  const weekAgo = new Date(today); weekAgo.setDate(weekAgo.getDate() - 7);
  if (d >= today) return 'Today';
  if (d >= yesterday) return 'Yesterday';
  if (d >= weekAgo) return 'This Week';
  return 'Older';
}

const BUCKET_ORDER = ['Today', 'Yesterday', 'This Week', 'Older'];

const STATUS_CLASSES: Record<string, string> = {
  published: 'bg-primary text-on-primary border-primary',
  edited: 'border-outline-variant text-primary bg-surface-container-low',
  draft: 'border-outline-variant text-on-surface-variant',
};

export default function PostLibrary({ kind, activeId, onSelect, onNewPost, refreshKey = 0, onFirstLoad }: PostLibraryProps) {
  const [posts, setPosts] = useState<GeneratedPostWithHeadline[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);
  const [sortMode, setSortMode] = useState<'latest' | 'oldest' | 'chatted' | 'created_linkedin' | 'created_blog'>('latest');
  const [contextStats, setContextStats] = useState<Record<string, { chats: number; linkedin: number; blog: number }>>({});
  const onFirstLoadRef = useRef(onFirstLoad);

  useEffect(() => {
    onFirstLoadRef.current = onFirstLoad;
  }, [onFirstLoad]);

  const loadPosts = useCallback(async (attempt = 0) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/posts/all?kind=${kind}&limit=200`);
      if (!response.ok) {
        const err = new Error(`HTTP ${response.status}`) as Error & { status?: number };
        err.status = response.status;
        throw err;
      }
      const data = (await response.json()) as GeneratedPostWithHeadline[];
      setPosts(data);
      if (data.length > 0 && onFirstLoadRef.current) onFirstLoadRef.current(data[0]);
    } catch (err) {
      const status = (err as { status?: number })?.status;
      const transient = status === 503 || status === 504;
      if (transient && attempt < 2) {
        const backoffMs = 400 * (attempt + 1);
        window.setTimeout(() => {
          void loadPosts(attempt + 1);
        }, backoffMs);
      } else {
        setError(
          status
            ? `Could not load posts right now (HTTP ${status}).`
            : 'Could not load posts right now.',
        );
      }
    } finally {
      setLoading(false);
    }
  }, [kind]);

  useEffect(() => {
    void loadPosts();
  }, [kind, refreshKey, retryTick, loadPosts]);

  useEffect(() => {
    const needsStats = sortMode === 'chatted' || sortMode === 'created_linkedin' || sortMode === 'created_blog';
    if (posts.length === 0 || !needsStats) return;
    const ac = new AbortController();
    const keys = Array.from(new Set(posts.map((p) => `${p.run_id}::${p.run_date}::${p.slug}`)));
    void Promise.all(
      keys.map(async (key) => {
        const [runId, runDate, slug] = key.split('::');
        const opts = { signal: ac.signal };
        const [chatRows, postRows] = await Promise.all([
          fetch(`/api/chat/runs/${runId}/${slug}/messages`, opts)
            .then((r) => (r.ok ? r.json() : [] as unknown[]))
            .catch(() => [] as unknown[]),
          fetch(`/api/posts/${runDate}/${slug}`, opts)
            .then((r) => (r.ok ? r.json() : [] as Array<{ kind: 'linkedin' | 'blog' }>))
            .catch(() => [] as Array<{ kind: 'linkedin' | 'blog' }>),
        ]);
        return [key, {
          chats: chatRows.length,
          linkedin: postRows.filter((p: { kind: 'linkedin' | 'blog' }) => p.kind === 'linkedin').length,
          blog: postRows.filter((p: { kind: 'linkedin' | 'blog' }) => p.kind === 'blog').length,
        }] as const;
      }),
    ).then((rows) => {
      if (!ac.signal.aborted) setContextStats(Object.fromEntries(rows));
    }).catch(() => {});
    return () => ac.abort();
  }, [posts, sortMode]);

  // Client-side filter — matched against headline, slug, and tags
  const filtered = useMemo(() => {
    const sorted = [...posts];
    const statKey = (p: GeneratedPostWithHeadline) => `${p.run_id}::${p.run_date}::${p.slug}`;
    if (sortMode === 'latest') {
      sorted.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
    } else if (sortMode === 'oldest') {
      sorted.sort((a, b) => new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime());
    } else {
      const metric = (p: GeneratedPostWithHeadline) => {
        const s = contextStats[statKey(p)];
        if (!s) return 0;
        if (sortMode === 'chatted') return s.chats;
        if (sortMode === 'created_linkedin') return s.linkedin;
        return s.blog;
      };
      sorted.sort((a, b) => metric(b) - metric(a));
    }

    const q = query.trim().toLowerCase();
    if (!q) return sorted;
    return sorted.filter(
      (p) =>
        p.headline.toLowerCase().includes(q) ||
        p.slug.toLowerCase().includes(q) ||
        p.tags.some((t) => t.toLowerCase().includes(q)),
    );
  }, [posts, query, sortMode, contextStats]);

  // Group by date bucket, newest first
  const groups = useMemo(() => {
    const g: Record<string, GeneratedPostWithHeadline[]> = {};
    for (const p of filtered) {
      const b = dateBucket(p.run_date);
      if (!g[b]) g[b] = [];
      g[b].push(p);
    }
    return g;
  }, [filtered]);

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="p-4 border-b border-outline-variant bg-surface-container-low shrink-0">
        <p className="label-bold mb-3">{kind === 'linkedin' ? 'LinkedIn Posts' : 'Blog Posts'}</p>
        <button onClick={onNewPost} className="btn-primary w-full py-2.5 text-[10px] gap-1.5 mb-3">
          <Plus size={13} /> New Post
        </button>
        {/* Search filter */}
        <div className="relative flex items-center">
          <Search size={13} className="absolute left-2.5 text-outline pointer-events-none" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search posts…"
            className="w-full pl-8 pr-7 py-1.5 text-xs border border-outline-variant bg-surface-container-lowest outline-none focus:border-primary transition-all placeholder:text-outline font-sans"
          />
          {query && (
            <button onClick={() => setQuery('')} className="absolute right-2 text-outline hover:text-on-surface transition-colors">
              <X size={12} />
            </button>
          )}
        </div>
        <div className="mt-3">
          <select
            value={sortMode}
            onChange={(e) => setSortMode(e.target.value as typeof sortMode)}
            className="w-full text-[10px] font-bold uppercase tracking-widest border border-outline-variant bg-surface-container-lowest px-2 py-1.5 outline-none focus:border-primary"
            aria-label="Sort posts"
          >
            <option value="latest">Latest</option>
            <option value="oldest">Oldest</option>
            <option value="chatted">Chatted About</option>
            <option value="created_linkedin">Created LinkedIn Posts</option>
            <option value="created_blog">Created Blog Posts</option>
          </select>
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {loading && (
          <div className="flex items-center justify-center py-8 gap-2">
            <span className="w-4 h-4 border-2 border-primary border-t-transparent animate-spin" />
            <span className="label-bold text-[9px] text-outline">Loading…</span>
          </div>
        )}

        {!loading && posts.length === 0 && !error && (
          <div className="flex flex-col items-center justify-center py-12 px-4 text-center gap-3">
            <div className="w-8 h-8 border border-outline-variant flex items-center justify-center">
              <span className="text-outline font-mono text-xs">0</span>
            </div>
            <p className="text-sm font-bold uppercase tracking-tight">No posts yet</p>
            <p className="text-xs text-on-surface-variant leading-snug max-w-[200px]">
              Click + New Post to generate your first one from a trend or search.
            </p>
          </div>
        )}

        {!loading && error && (
          <div className="m-4 border border-outline-variant bg-surface-container-low p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wider mb-2">Library unavailable</p>
            <p className="text-xs text-on-surface-variant mb-3">{error}</p>
            <button
              onClick={() => setRetryTick((n) => n + 1)}
              className="btn-secondary py-1.5 px-3 text-[10px]"
            >
              Retry
            </button>
          </div>
        )}

        {!loading && error && posts.length > 0 && (
          <div className="mx-4 mt-4 border border-outline-variant bg-surface-container-low p-3">
            <p className="text-xs text-on-surface-variant">
              Showing last loaded posts. Refresh failed.
            </p>
          </div>
        )}

        {!loading && posts.length > 0 && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-10 px-4 text-center gap-2">
            <p className="text-sm font-bold uppercase tracking-tight">No matches</p>
            <p className="text-xs text-on-surface-variant">Try a different search term.</p>
          </div>
        )}

        {!loading && BUCKET_ORDER.map((bucket) => {
          const items = groups[bucket];
          if (!items || items.length === 0) return null;
          return (
            <div key={bucket}>
              <div className="px-4 py-2 bg-surface-container border-b border-outline-variant sticky top-0 z-10">
                <span className="label-bold text-[9px] text-outline">{bucket}</span>
                <span className="label-bold text-[9px] text-outline ml-2">({items.length})</span>
              </div>
              {items.map((post) => {
                const isActive = post.id === activeId;
                return (
                  <button
                    key={post.id}
                    onClick={() => onSelect(post)}
                    className={cn(
                      'w-full text-left p-4 border-b border-outline-variant transition-all border-l-2 group',
                      isActive
                        ? 'bg-surface-container-low border-l-primary'
                        : 'hover:bg-surface-container border-l-transparent',
                    )}
                  >
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className={cn(
                        'text-[9px] font-black tracking-widest px-1.5 py-0.5 border flex-shrink-0',
                        STATUS_CLASSES[post.status] ?? STATUS_CLASSES.draft,
                      )}>
                        {post.status.toUpperCase()}
                      </span>
                      <span className="label-bold text-[9px] text-outline flex-shrink-0 font-mono">
                        {post.run_date}
                      </span>
                    </div>
                    <p className={cn(
                      'text-sm font-semibold leading-snug line-clamp-2',
                      isActive ? 'text-primary' : 'text-on-surface group-hover:text-primary transition-colors',
                    )}>
                      {post.headline}
                    </p>
                    {post.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {post.tags.slice(0, 3).map((t) => (
                          <span key={t} className="text-[9px] text-outline font-mono">#{t}</span>
                        ))}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
