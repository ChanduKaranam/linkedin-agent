import { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, Search, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useBackendStatus } from '@/context/BackendStatusContext';
import type { GeneratedPost, TrendListItem, SearchHistoryItem } from '@/types';

interface NewPostDialogProps {
  open: boolean;
  kind: 'linkedin' | 'blog';
  onClose: () => void;
  onCreated: (post: GeneratedPost) => void;
}

interface SourceItem {
  label: string;        // headline / topic shown in the list
  subLabel: string;     // date or "Search · topic"
  slug: string;
  date: string;         // run_date YYYY-MM-DD
  runId: string | null; // null = daily trend
}

export default function NewPostDialog({ open, kind, onClose, onCreated }: NewPostDialogProps) {
  const { availableDates } = useBackendStatus();
  const [activeTab, setActiveTab] = useState<'trends' | 'searches'>('trends');

  // All available source items loaded from the backend
  const [allSources, setAllSources] = useState<SourceItem[]>([]);
  const [loadingSources, setLoadingSources] = useState(false);

  // The item the user picked from the list
  const [selected, setSelected] = useState<SourceItem | null>(null);

  // Search query for filtering the list
  const [searchQuery, setSearchQuery] = useState('');

  // Instructions textarea
  const [instructions, setInstructions] = useState('');

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Style selection
  const [style, setStyle] = useState<'leadership' | 'technical'>('leadership');

  // Load all sources when dialog opens
  useEffect(() => {
    if (!open) return;
    setActiveTab('trends');
    setSelected(null);
    setSearchQuery('');
    setInstructions('');
    setStyle('leadership');
    setError(null);
    setLoadingSources(true);

    const loads: Promise<void>[] = [];

    // Load daily trends for all available dates (newest date first)
    const dailyItems: SourceItem[] = [];
    const trendLoads = availableDates.slice(0, 7).map((date) =>
      fetch(`/api/trends/by-date/${date}`)
        .then((r) => (r.ok ? r.json() : []))
        .then((list: TrendListItem[]) => {
          for (const t of list) {
            dailyItems.push({
              label: t.headline,
              subLabel: date,
              slug: t.slug,
              date,
              runId: null,
            });
          }
        })
        .catch(() => {}),
    );
    loads.push(...trendLoads);

    // Load search runs
    const searchItems: SourceItem[] = [];
    const searchLoad = fetch('/api/search/history')
      .then((r) => (r.ok ? r.json() : []))
      .then(async (runs: SearchHistoryItem[]) => {
        const completed = runs.filter(
          (r) => r.state === 'completed' || r.state === 'completed_with_warnings',
        );
        await Promise.all(
          completed.slice(0, 10).map((run) =>
            fetch(`/api/search/runs/${run.run_id}/trends`)
              .then((r) => (r.ok ? r.json() : []))
              .then((list: TrendListItem[]) => {
                for (const t of list) {
                  searchItems.push({
                    label: t.headline,
                    subLabel: `Search · ${run.topic}`,
                    slug: t.slug,
                    date: run.run_date,
                    runId: run.run_id,
                  });
                }
              })
              .catch(() => {}),
          ),
        );
      })
      .catch(() => {});
    loads.push(searchLoad);

    Promise.all(loads).then(() => {
      // Daily first (newest date), then search results
      setAllSources([...dailyItems, ...searchItems]);
      setLoadingSources(false);
    });
  }, [open, availableDates]);

  // Filter the list based on the search query
  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return allSources;
    return allSources.filter(
      (s) =>
        s.label.toLowerCase().includes(q) ||
        s.subLabel.toLowerCase().includes(q) ||
        s.slug.toLowerCase().includes(q),
    );
  }, [allSources, searchQuery]);

  // Group filtered items: daily first (by date bucket) then searches
  const { dailyGroups, searchItems } = useMemo(() => {
    const dg: Record<string, SourceItem[]> = {};
    const si: SourceItem[] = [];
    for (const s of filtered) {
      if (s.runId === null) {
        if (!dg[s.date]) dg[s.date] = [];
        dg[s.date].push(s);
      } else {
        si.push(s);
      }
    }
    return { dailyGroups: dg, searchItems: si };
  }, [filtered]);

  const sortedDates = Object.keys(dailyGroups).sort((a, b) => b.localeCompare(a));
  const visibleCount = activeTab === 'trends'
    ? sortedDates.reduce((n, date) => n + dailyGroups[date].length, 0)
    : searchItems.length;

  function labelForDate(d: string) {
    const today = new Date(); today.setHours(0,0,0,0);
    const yesterday = new Date(today); yesterday.setDate(yesterday.getDate()-1);
    const dt = new Date(d + 'T00:00:00');
    if (dt.getTime() === today.getTime()) return 'Today';
    if (dt.getTime() === yesterday.getTime()) return 'Yesterday';
    return d;
  }

  async function handleGenerate() {
    if (!selected || generating) return;
    setGenerating(true);
    setError(null);

    const url = selected.runId
      ? `/api/posts/runs/${selected.runId}/${selected.slug}/${kind}`
      : `/api/posts/${selected.date}/${selected.slug}/${kind}`;

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_instructions: instructions.trim(),
          style: style,
        }),
        signal: AbortSignal.timeout(120_000),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({})) as Record<string, unknown>;
        setError(String(err.detail ?? err.error ?? 'Generation failed.'));
        return;
      }
      onCreated(await res.json());
      setInstructions('');
    } catch (e: unknown) {
      setError(
        e instanceof Error && e.name === 'TimeoutError'
          ? 'Generation timed out — try again.'
          : 'Network error. Is the backend running?',
      );
    } finally {
      setGenerating(false);
    }
  }

  function handleClose() {
    if (generating) return;
    onClose();
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 z-[200]"
            onClick={handleClose}
          />

          {/* Dialog */}
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl h-[92vh] bg-white border-2 border-primary shadow-2xl z-[210] flex flex-col"
            style={{ maxHeight: '92vh' }}
          >
            {/* Header */}
            <div className="flex justify-between items-center px-6 py-4 border-b border-outline-variant shrink-0">
              <span className="label-bold">
                New {kind === 'linkedin' ? 'LinkedIn Post' : 'Blog Post'}
              </span>
              <button onClick={handleClose} disabled={generating} className="hover:bg-surface-container p-1 transition-colors disabled:opacity-50">
                <X size={16} />
              </button>
            </div>

            <div className="flex flex-col flex-1 overflow-hidden">
              {/* Selected source display (or placeholder) */}
              <div className={cn(
                'px-6 py-2 border-b border-outline-variant shrink-0',
                selected ? 'bg-primary text-on-primary' : 'bg-surface-container-low',
              )}>
                {selected ? (
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="label-bold text-[9px] text-on-primary opacity-70 mb-0.5">
                        {selected.runId ? 'Search result' : 'Daily trend'} · {selected.date}
                      </p>
                      <p className="text-sm font-bold leading-snug line-clamp-2">{selected.label}</p>
                    </div>
                    <button
                      onClick={() => setSelected(null)}
                      className="flex-shrink-0 opacity-70 hover:opacity-100 mt-0.5 transition-opacity"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ) : (
                  <p className="label-bold text-[10px] text-outline">
                    Search below and select a trend or search result to generate from
                  </p>
                )}
              </div>

              {/* Search input */}
              <div className="px-4 py-2 border-b border-outline-variant shrink-0">
                <div className="relative flex items-center">
                  <Search size={14} className="absolute left-3 text-outline pointer-events-none" />
                  <input
                    autoFocus
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search trends and research topics…"
                    className="w-full pl-9 pr-8 py-1.5 text-sm border border-outline-variant bg-surface-container-low outline-none focus:border-primary focus:border-2 transition-all font-sans placeholder:text-outline"
                  />
                  {searchQuery && (
                    <button onClick={() => setSearchQuery('')} className="absolute right-2.5 text-outline hover:text-on-surface transition-colors">
                      <X size={12} />
                    </button>
                  )}
                </div>
              </div>

              {/* Source tabs */}
              <div className="px-4 py-1.5 border-b border-outline-variant shrink-0 bg-surface-container-low">
                <div className="inline-flex border border-outline-variant">
                  <button
                    onClick={() => setActiveTab('trends')}
                    className={cn(
                      'px-4 py-1.5 text-[10px] font-bold uppercase tracking-widest border-r border-outline-variant transition-colors',
                      activeTab === 'trends'
                        ? 'bg-primary text-on-primary'
                        : 'bg-surface-container-lowest text-on-surface-variant hover:text-primary',
                    )}
                  >
                    Trends
                  </button>
                  <button
                    onClick={() => setActiveTab('searches')}
                    className={cn(
                      'px-4 py-1.5 text-[10px] font-bold uppercase tracking-widest transition-colors',
                      activeTab === 'searches'
                        ? 'bg-primary text-on-primary'
                        : 'bg-surface-container-lowest text-on-surface-variant hover:text-primary',
                    )}
                  >
                    Searches
                  </button>
                </div>
              </div>

              {/* Scrollable source list */}
              <div className="flex-1 overflow-y-auto min-h-0">
                {loadingSources && (
                  <div className="flex items-center justify-center gap-2 py-8">
                    <span className="w-4 h-4 border-2 border-primary border-t-transparent animate-spin" />
                    <span className="label-bold text-[9px] text-outline">Loading trends…</span>
                  </div>
                )}

                {!loadingSources && visibleCount === 0 && (
                  <div className="flex flex-col items-center justify-center py-10 px-4 text-center gap-2">
                    <p className="text-sm font-bold uppercase tracking-tight">No results</p>
                    <p className="text-xs text-on-surface-variant">
                      {activeTab === 'trends'
                        ? 'No daily trends match this search.'
                        : 'No search-run trends match this search.'}
                    </p>
                  </div>
                )}

                {/* Daily trends grouped by date */}
                {activeTab === 'trends' && sortedDates.map((date) => (
                  <div key={date}>
                    <div className="px-4 py-1.5 bg-surface-container border-b border-outline-variant sticky top-0">
                      <span className="label-bold text-[9px] text-outline">
                        {labelForDate(date)} · Daily Trends
                      </span>
                    </div>
                    {dailyGroups[date].map((item) => (
                      <SourceRow
                        key={`${item.date}-${item.slug}`}
                        item={item}
                        isSelected={selected?.slug === item.slug && selected?.runId === item.runId}
                        onSelect={() => setSelected(item)}
                      />
                    ))}
                  </div>
                ))}

                {/* Search results */}
                {activeTab === 'searches' && searchItems.length > 0 && (
                  <div>
                    <div className="px-4 py-1.5 bg-surface-container border-b border-outline-variant sticky top-0">
                      <span className="label-bold text-[9px] text-outline">My Searches</span>
                    </div>
                    {searchItems.map((item) => (
                      <SourceRow
                        key={`${item.runId}-${item.slug}`}
                        item={item}
                        isSelected={selected?.slug === item.slug && selected?.runId === item.runId}
                        onSelect={() => setSelected(item)}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Instructions + Generate */}
              <div className="px-6 py-3 border-t border-outline-variant shrink-0 flex flex-col gap-2.5">
                {/* Style Selector */}
                <div className="flex flex-col gap-1.5">
                  <label className="label-bold text-[10px]">Style Selection</label>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setStyle('leadership')}
                      className={cn(
                        'flex-1 py-1.5 text-[10px] font-bold uppercase tracking-widest border transition-colors',
                        style === 'leadership'
                          ? 'bg-primary text-on-primary border-primary'
                          : 'bg-surface-container-lowest text-on-surface-variant border-outline-variant hover:border-primary hover:text-primary',
                      )}
                    >
                      Leadership Style
                    </button>
                    <button
                      type="button"
                      onClick={() => setStyle('technical')}
                      className={cn(
                        'flex-1 py-1.5 text-[10px] font-bold uppercase tracking-widest border transition-colors',
                        style === 'technical'
                          ? 'bg-primary text-on-primary border-primary'
                          : 'bg-surface-container-lowest text-on-surface-variant border-outline-variant hover:border-primary hover:text-primary',
                      )}
                    >
                      Technical Style
                    </button>
                  </div>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="label-bold text-[10px]">
                    Instructions{' '}
                    <span className="text-outline normal-case tracking-normal font-normal">(optional)</span>
                  </label>
                  <textarea
                    value={instructions}
                    onChange={(e) => setInstructions(e.target.value)}
                    rows={1}
                    placeholder={
                      kind === 'linkedin'
                        ? 'e.g. start with a provocative question, keep it under 200 words…'
                        : 'e.g. write for a technical audience, include code examples…'
                    }
                    className="input-field py-2 resize-none text-sm"
                  />
                </div>

                {error && (
                  <p className="text-[11px] text-red-600 font-mono bg-red-50 border border-red-200 px-3 py-2">{error}</p>
                )}

                <div className="flex gap-2">
                  <button
                    onClick={handleClose}
                    disabled={generating}
                    className="flex-1 py-3 text-[10px] font-bold uppercase tracking-widest bg-surface-container-high border border-outline-variant hover:bg-surface-dim transition-colors disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleGenerate}
                    disabled={!selected || generating}
                    className="flex-1 btn-primary py-3 text-[10px] disabled:opacity-50"
                  >
                    {generating ? (
                      <span className="flex items-center gap-2 justify-center">
                        <span className="w-3.5 h-3.5 border-2 border-on-primary border-t-transparent animate-spin" />
                        Generating…
                      </span>
                    ) : (
                      'Generate'
                    )}
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function SourceRow({
  item,
  isSelected,
  onSelect,
}: {
  item: SourceItem;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        'w-full text-left px-4 py-4 border-b border-outline-variant transition-all border-l-2 flex items-start justify-between gap-2 group',
        isSelected
          ? 'bg-surface-container-low border-l-primary'
          : 'border-l-transparent hover:bg-surface-container hover:border-l-primary',
      )}
    >
      <div className="min-w-0 flex-1">
        <p className={cn(
          'text-sm font-semibold leading-snug line-clamp-3',
          isSelected ? 'text-primary' : 'text-on-surface group-hover:text-primary transition-colors',
        )}>
          {item.label}
        </p>
        <p className="label-bold text-[9px] text-outline mt-1">{item.subLabel}</p>
      </div>
      <ChevronRight
        size={14}
        className={cn(
          'flex-shrink-0 mt-0.5 transition-colors',
          isSelected ? 'text-primary' : 'text-outline group-hover:text-primary',
        )}
      />
    </button>
  );
}
