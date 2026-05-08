import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { useWorkspace } from '@/context/WorkspaceContext';
import { useBackendStatus } from '@/context/BackendStatusContext';
import EmptyState from '@/components/EmptyState';
import DateSelector from '@/components/DateSelector';
import TrendList from '@/components/TrendList';
import TrendDetail from '@/components/TrendDetail';
import type { TrendListItem, TrendDetail as TrendDetailType } from '@/types';

// Mock data for Tilicho workspace (static preview only)
const TILICHO_HEADLINES = [
  { id: 't1', title: 'New breakthroughs in context window scaling for LLMs', source: 'TILICHO RESEARCH', time: '09:00 AM' },
  { id: 't2', title: 'Vector database efficiency benchmark results released', source: 'ARXIV', time: '08:45 AM' },
  { id: 't3', title: 'Deployment of distributed inference nodes in Asia-East', source: 'INTERNAL', time: 'YESTERDAY' },
];

export default function Trends() {
  const { workspace } = useWorkspace();
  const isTilicho = workspace === 'TILICHO_LABS';
  const { backendStatus, availableDates, selectedDate, setSelectedDate, schedule, refresh } = useBackendStatus();

  const [dailyTrends, setDailyTrends] = useState<TrendListItem[]>([]);
  const [sortMode, setSortMode] = useState<'latest' | 'oldest' | 'chatted' | 'created_linkedin' | 'created_blog'>('latest');
  const [trendStats, setTrendStats] = useState<Record<string, { chats: number; linkedin: number; blog: number }>>({});
  const [loadingTrends, setLoadingTrends] = useState(false);
  const [activeSlug, setActiveSlug] = useState('');
  const [detail, setDetail] = useState<TrendDetailType | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [isTopSectionVisible, setIsTopSectionVisible] = useState(true);
  const isTopSectionVisibleRef = useRef(true);
  const leftScrollTopRef = useRef(0);
  const rightScrollTopRef = useRef(0);

  function setHeaderVisibility(visible: boolean) {
    if (isTopSectionVisibleRef.current === visible) return;
    isTopSectionVisibleRef.current = visible;
    setIsTopSectionVisible(visible);
    window.dispatchEvent(new CustomEvent('trends-header-visibility', { detail: { visible } }));
  }

  // Tilicho: keep mock state
  const [tilichoActive, setTilichoActive] = useState(TILICHO_HEADLINES[0].id);

  // Load trends list when date changes (LinkedIn only)
  useEffect(() => {
    if (isTilicho || !selectedDate) return;
    setLoadingTrends(true);
    setDetail(null);
    fetch(`/api/trends/by-date/${selectedDate}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((trends: TrendListItem[]) => {
        setDailyTrends(trends);
        setTrendStats({});
        const urlSlug = new URLSearchParams(window.location.search).get('t');
        const firstSlug = urlSlug && trends.find((t) => t.slug === urlSlug) ? urlSlug : trends[0]?.slug ?? '';
        setActiveSlug(firstSlug);
      })
      .catch(() => setDailyTrends([]))
      .finally(() => setLoadingTrends(false));
  }, [selectedDate, isTilicho]);

  useEffect(() => {
    if (isTilicho || !selectedDate || dailyTrends.length === 0) return;
    const ac = new AbortController();
    void Promise.all(
      dailyTrends.map(async (trend) => {
        const opts = { signal: ac.signal };
        const [chatRes, postRes] = await Promise.all([
          fetch(`/api/chat/${selectedDate}/${trend.slug}/messages`, opts).then((r) => (r.ok ? r.json() : [] as unknown[])).catch(() => [] as unknown[]),
          fetch(`/api/posts/${selectedDate}/${trend.slug}`, opts).then((r) => (r.ok ? r.json() : [] as Array<{ kind: 'linkedin' | 'blog' }>)).catch(() => [] as Array<{ kind: 'linkedin' | 'blog' }>),
        ]);
        const linkedin = postRes.filter((p: { kind: 'linkedin' | 'blog' }) => p.kind === 'linkedin').length;
        const blog = postRes.filter((p: { kind: 'linkedin' | 'blog' }) => p.kind === 'blog').length;
        return [trend.slug, { chats: chatRes.length, linkedin, blog }] as const;
      }),
    ).then((rows) => {
      if (!ac.signal.aborted) setTrendStats(Object.fromEntries(rows));
    }).catch(() => {});
    return () => ac.abort();
  }, [dailyTrends, selectedDate, isTilicho]);

  const sortedTrends = (() => {
    const indexed = dailyTrends.map((t, i) => ({ t, i }));
    if (sortMode === 'latest') return dailyTrends;
    if (sortMode === 'oldest') return [...dailyTrends].reverse();
    const metric = (slug: string) => {
      const stats = trendStats[slug];
      if (!stats) return 0;
      if (sortMode === 'chatted') return stats.chats;
      if (sortMode === 'created_linkedin') return stats.linkedin;
      return stats.blog;
    };
    return [...indexed]
      .sort((a, b) => {
        const diff = metric(b.t.slug) - metric(a.t.slug);
        return diff !== 0 ? diff : a.i - b.i;
      })
      .map((x) => x.t);
  })();

  // Load detail when slug changes
  useEffect(() => {
    if (isTilicho || !activeSlug || !selectedDate) return;
    setLoadingDetail(true);
    fetch(`/api/trends/${selectedDate}/${activeSlug}`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoadingDetail(false));
  }, [activeSlug, selectedDate, isTilicho]);

  // Sync URL param on slug change
  function handleTrendSelect(slug: string) {
    setActiveSlug(slug);
    const url = new URL(window.location.href);
    url.searchParams.set('t', slug);
    window.history.replaceState({}, '', url.toString());
  }

  function handleDateSelect(date: string) {
    setSelectedDate(date);
    const url = new URL(window.location.href);
    url.searchParams.set('d', date);
    url.searchParams.delete('t');
    window.history.replaceState({}, '', url.toString());
  }

  function handlePaneScroll(pane: 'left' | 'right', scrollTop: number) {
    if (pane === 'left') {
      leftScrollTopRef.current = scrollTop;
    } else {
      rightScrollTopRef.current = scrollTop;
    }

    const activeTop = pane === 'left' ? leftScrollTopRef.current : rightScrollTopRef.current;
    const otherTop = pane === 'left' ? rightScrollTopRef.current : leftScrollTopRef.current;
    const bothNearTop = activeTop < 8 && otherTop < 8;
    if (bothNearTop) {
      setHeaderVisibility(true);
      return;
    }

    // Position-based hysteresis prevents rapid hide/show oscillation.
    if (isTopSectionVisibleRef.current && activeTop > 72) {
      setHeaderVisibility(false);
      return;
    }
    if (!isTopSectionVisibleRef.current && activeTop < 24) {
      setHeaderVisibility(true);
    }
  }

  useEffect(() => {
    return () => {
      window.dispatchEvent(new CustomEvent('trends-header-visibility', { detail: { visible: true } }));
    };
  }, []);

  // Empty states (LinkedIn only)
  if (!isTilicho && backendStatus === 'unreachable') return <EmptyState variant="unreachable" />;
  if (!isTilicho && backendStatus === 'no_run') {
    const tz = schedule?.timezone === 'Asia/Kolkata' ? 'IST' : (schedule?.timezone ?? '');
    const next = schedule ? `${String(schedule.hour).padStart(2, '0')}:${String(schedule.minute).padStart(2, '0')} ${tz}` : undefined;
    return <EmptyState variant="no_run" nextScheduled={next} />;
  }
  if (!isTilicho && backendStatus === 'running' && availableDates.length === 0) return <EmptyState variant="running" />;
  if (!isTilicho && backendStatus === 'no_trends') return <EmptyState variant="no_trends" />;

  if (isTilicho) {
    const activeTilicho = TILICHO_HEADLINES.find((h) => h.id === tilichoActive) ?? TILICHO_HEADLINES[0];
    return (
      <div className="flex-1 flex flex-row overflow-hidden w-full max-w-[1600px] mx-auto border-l border-r border-outline-variant bg-surface relative">
        {/* Coming soon overlay */}
        <div className="absolute top-4 right-6 z-20 pointer-events-none">
          <span className="label-bold bg-primary text-on-primary px-3 py-1.5 border border-primary">TILICHO · COMING SOON</span>
        </div>

        <aside className="w-[320px] min-w-[320px] border-r border-outline-variant bg-surface-container-lowest flex flex-col">
          <div className="p-6 border-b border-outline-variant flex flex-col gap-1">
            <div className="flex justify-between items-baseline">
              <h2 className="text-xl font-bold">Lab Feed</h2>
              <span className="label-bold">OCT 26</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-primary" />
              <span className="text-sm text-on-surface-variant font-medium">{TILICHO_HEADLINES.length} Research Signals</span>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {TILICHO_HEADLINES.map((h) => (
              <div
                key={h.id}
                onClick={() => setTilichoActive(h.id)}
                className={cn('p-4 border-b border-outline-variant cursor-pointer transition-colors border-l-4',
                  tilichoActive === h.id ? 'bg-surface-container-low border-l-primary' : 'hover:bg-surface border-l-transparent')}
              >
                <p className={cn('text-sm font-semibold leading-tight mb-4', tilichoActive === h.id ? 'text-primary' : 'text-on-surface')}>{h.title}</p>
                <div className="flex justify-between items-center">
                  <span className="label-bold">{h.source}</span>
                  <span className="label-bold text-outline">{h.time}</span>
                </div>
              </div>
            ))}
          </div>
        </aside>

        <section className="flex-1 flex flex-col min-w-0 bg-background p-10">
          <div className="flex flex-col gap-4 max-w-[80%]">
            <div className="flex gap-2">
              <span className="bg-surface-container-high px-2 py-1 label-bold">CORE INFRA</span>
              <span className="bg-surface-container-high px-2 py-1 label-bold">DATA ARCH</span>
            </div>
            <h1 className="text-4xl font-bold leading-tight">{activeTilicho.title}</h1>
          </div>
          <p className="text-lg text-on-surface-variant leading-relaxed max-w-3xl mt-6">
            Mock data — connect the Tilicho backend to see live research signals here.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col overflow-hidden w-full max-w-[1600px] mx-auto">
      {/* Pipeline-running banner */}
      {backendStatus === 'running' && (
        <div className="px-4 py-2 bg-surface-container border-b border-outline-variant flex items-center gap-3">
          <span className="w-3 h-3 border-2 border-primary border-t-transparent animate-spin flex-shrink-0" />
          <span className="text-xs font-mono text-on-surface-variant flex-1">Pipeline is running — showing previous results. New trends will appear automatically when complete.</span>
          <button onClick={refresh} className="text-xs font-mono text-primary underline underline-offset-2 hover:opacity-70 flex-shrink-0">Check now</button>
        </div>
      )}
      {/* Date selector */}
      {availableDates.length > 0 && (
        <div
          className={cn(
            'px-4 border-b border-outline-variant bg-surface-container-lowest overflow-hidden transition-all duration-300 ease-out',
            isTopSectionVisible
              ? 'py-3 opacity-100 translate-y-0 max-h-24'
              : 'py-0 opacity-0 -translate-y-2 max-h-0 pointer-events-none',
          )}
        >
          <DateSelector dates={availableDates} selectedDate={selectedDate} onSelect={handleDateSelect} />
        </div>
      )}

      <div className="flex flex-1 min-h-0 overflow-hidden border-l border-r border-outline-variant">
        {/* Left pane: trend list */}
        <aside className="w-[320px] min-w-[320px] min-h-0 border-r border-outline-variant bg-surface-container-lowest flex flex-col">
          {loadingTrends ? (
            <div className="flex items-center justify-center flex-1">
              <span className="w-5 h-5 border-2 border-primary border-t-transparent animate-spin" />
            </div>
          ) : dailyTrends.length === 0 ? (
            <EmptyState variant="no_trends" />
          ) : (
            <TrendList
              trends={sortedTrends}
              activeSlug={activeSlug}
              onSelect={handleTrendSelect}
              date={selectedDate}
              sortMode={sortMode}
              onSortChange={setSortMode}
              onPaneScroll={(top) => handlePaneScroll('left', top)}
            />
          )}
        </aside>

        {/* Right pane: trend detail */}
        <section className="flex-1 min-h-0 bg-background overflow-hidden">
          {loadingDetail ? (
            <div className="flex items-center justify-center h-full">
              <span className="w-5 h-5 border-2 border-primary border-t-transparent animate-spin" />
            </div>
          ) : detail ? (
            <TrendDetail
              trend={detail}
              chatApiBase={`/api/chat/${detail.run_date}/${detail.slug}`}
              insightsApiBase={`/api/insights/${detail.run_date}/${detail.slug}`}
              onPaneScroll={(top) => handlePaneScroll('right', top)}
            />
          ) : (
            <div className="flex items-center justify-center h-full">
              <p className="label-bold text-outline">Select a trend to read the full brief</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
