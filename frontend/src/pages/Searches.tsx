import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { useWorkspace } from '@/context/WorkspaceContext';
import { useSearchMode } from '@/context/SearchModeContext';
import SearchBar from '@/components/SearchBar';
import SearchHistory from '@/components/SearchHistory';
import SearchResultView from '@/components/SearchResultView';
import type { SearchState } from '@/types';

// Tilicho mock history items
const TILICHO_HISTORY = [
  { id: 't1', title: 'Llama-3 70B Quantization', time: '10:42 AM', query: 'Analyze performance impact of 4-bit vs 8-bit quantization on logic reasoning tasks.', results: '3 Snapshots', saved: true },
  { id: 't2', title: 'K8s Cluster Autoscaler Logs', time: '09:15 AM', query: 'Search logs for OOM errors in the production cluster during peak traffic yesterday.', results: '18 Errors', saved: false },
];

const TERMINAL: SearchState[] = ['completed', 'completed_with_warnings', 'failed'];
const IN_PROGRESS: SearchState[] = ['pending', 'discovering', 'scraping', 'clustering', 'summarizing'];

export default function Searches() {
  const { workspace } = useWorkspace();
  const isTilicho = workspace === 'TILICHO_LABS';
  const {
    mode, searchTopic, searchRunId, searchBrief,
    enterSearch, clearSearch,
    activePhase, activeRunId, resumeSearch,
  } = useSearchMode();

  const [isTopSectionVisible, setIsTopSectionVisible] = useState(true);
  const isTopSectionVisibleRef = useRef(true);
  const leftScrollTopRef = useRef(0);
  const rightScrollTopRef = useRef(0);
  const lastScrolledPaneRef = useRef<'left' | 'right'>('right');

  // Read URL params once (for initialQuery and deep-link hydration)
  const urlParams = new URLSearchParams(window.location.search);
  const urlQuery = urlParams.get('q') ?? '';
  const urlRunId = urlParams.get('run_id') ?? '';

  function setHeaderVisibility(visible: boolean) {
    if (isTopSectionVisibleRef.current === visible) return;
    isTopSectionVisibleRef.current = visible;
    setIsTopSectionVisible(visible);
    window.dispatchEvent(new CustomEvent('trends-header-visibility', { detail: { visible } }));
  }

  function handlePaneScroll(pane: 'left' | 'right', scrollTop: number) {
    lastScrolledPaneRef.current = pane;
    if (pane === 'left') leftScrollTopRef.current = scrollTop;
    else rightScrollTopRef.current = scrollTop;

    const activeTop = pane === 'left' ? leftScrollTopRef.current : rightScrollTopRef.current;
    const otherTop = pane === 'left' ? rightScrollTopRef.current : leftScrollTopRef.current;
    if (activeTop < 8 && otherTop < 8) { setHeaderVisibility(true); return; }
    if (isTopSectionVisibleRef.current && activeTop > 72) { setHeaderVisibility(false); return; }
    if (!isTopSectionVisibleRef.current && activeTop < 24) setHeaderVisibility(true);
  }

  useEffect(() => {
    return () => {
      window.dispatchEvent(new CustomEvent('trends-header-visibility', { detail: { visible: true } }));
    };
  }, []);

  // Deep-link hydration: if ?run_id= is in the URL, reattach to that run.
  // This fires when the component mounts (navigation back) or on hard refresh.
  useEffect(() => {
    if (isTilicho || !urlRunId) return;
    // If context already tracks this run (still in progress), nothing to do.
    if (activeRunId === urlRunId) return;

    let cancelled = false;
    void (async () => {
      try {
        const [statusRes, trendsRes] = await Promise.all([
          fetch(`/api/search/runs/${urlRunId}`),
          fetch(`/api/search/runs/${urlRunId}/trends`),
        ]);
        if (!statusRes.ok || cancelled) return;
        const status = await statusRes.json() as { topic: string; state: SearchState };
        const topic = status.topic.split('#')[0];

        if (IN_PROGRESS.includes(status.state)) {
          // Run is still going — hand off to context polling
          resumeSearch(urlRunId, topic, status.state);
        } else if (TERMINAL.includes(status.state) && status.state !== 'failed') {
          // Run completed — load results
          if (!trendsRes.ok || cancelled) return;
          const trends = await trendsRes.json() as Array<{ slug: string; headline: string; one_liner: string; source_count: number }>;
          if (cancelled || trends.length === 0) return;
          const urlSlug = new URLSearchParams(window.location.search).get('slug') ?? '';
          const ordered = urlSlug
            ? [...trends].sort((a, b) => (a.slug === urlSlug ? -1 : b.slug === urlSlug ? 1 : 0))
            : trends;
          await enterSearch(urlRunId, topic, ordered);
        }
      } catch { /* ignore deep-link hydration errors */ }
    })();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlRunId]);

  // Default hydration: on refresh without run_id, load the latest completed search result.
  useEffect(() => {
    if (isTilicho || urlRunId || mode === 'search' || activeRunId) return;

    let cancelled = false;
    void (async () => {
      try {
        const historyRes = await fetch('/api/search/history');
        if (!historyRes.ok || cancelled) return;
        const history = await historyRes.json() as Array<{
          run_id: string;
          topic: string;
          state: SearchState;
          started_at: string;
        }>;
        const latestCompleted = [...history]
          .filter((item) => item.state === 'completed' || item.state === 'completed_with_warnings')
          .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())[0];
        if (!latestCompleted || cancelled) return;

        const trendsRes = await fetch(`/api/search/runs/${latestCompleted.run_id}/trends`);
        if (!trendsRes.ok || cancelled) return;
        const trends = await trendsRes.json() as Array<{ slug: string; headline: string; one_liner: string; source_count: number }>;
        if (cancelled || trends.length === 0) return;

        await enterSearch(latestCompleted.run_id, latestCompleted.topic, trends);

        const url = new URL(window.location.href);
        url.searchParams.set('run_id', latestCompleted.run_id);
        url.searchParams.set('q', latestCompleted.topic);
        window.history.replaceState({}, '', url.toString());
      } catch { /* ignore default hydration errors */ }
    })();

    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlRunId, mode, activeRunId]);

  if (isTilicho) {
    return (
      <div className="flex-1 flex overflow-hidden max-w-[1400px] mx-auto px-6 py-6 gap-6 relative">
        <div className="absolute top-4 right-6 z-20 pointer-events-none">
          <span className="label-bold bg-primary text-on-primary px-3 py-1.5 border border-primary">TILICHO · COMING SOON</span>
        </div>
        <aside className="w-1/3 min-w-[320px] flex flex-col border border-outline-variant bg-surface">
          <div className="px-5 py-3 border-b border-outline-variant bg-surface-container-low">
            <h2 className="label-bold text-on-surface">Experiment History</h2>
          </div>
          <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-3">
            {TILICHO_HISTORY.map((item) => (
              <div key={item.id} className="p-4 border-l-2 border-l-transparent bg-white hover:bg-surface-container-low cursor-pointer transition-all">
                <div className="flex justify-between items-start mb-2">
                  <span className="text-sm font-bold truncate pr-2">{item.title}</span>
                  <span className="label-bold text-[10px] text-outline shrink-0">{item.time}</span>
                </div>
                <p className="text-[11px] text-on-surface-variant italic line-clamp-2">{item.query}</p>
                <div className="flex gap-2 mt-2">
                  <span className="px-2 py-0.5 border border-outline-variant label-bold text-[9px]">{item.results}</span>
                  {item.saved && <span className="px-2 py-0.5 border border-outline-variant label-bold text-[9px] bg-surface-container text-primary">Saved</span>}
                </div>
              </div>
            ))}
          </div>
        </aside>
        <section className="flex-1 bg-surface-container-lowest border border-outline-variant p-8">
          <h1 className="text-2xl font-bold mb-4">Tilicho Research</h1>
          <p className="text-on-surface-variant">Backend wiring coming soon. Mock experiment data is shown.</p>
        </section>
      </div>
    );
  }

  return (
    <div className="flex-1 min-h-0 flex overflow-hidden max-w-[1400px] mx-auto px-6 py-6 gap-6">
      {/* Search History Sidebar */}
      <aside className="w-1/3 min-w-[300px] min-h-0 flex flex-col border border-outline-variant bg-surface overflow-visible shrink-0">
        <div className="px-5 py-3 border-b border-outline-variant bg-surface-container-low">
          <h2 className="label-bold">Search History</h2>
        </div>
        <SearchHistory
          activeRunId={searchRunId || activeRunId || undefined}
          onPaneScroll={(top) => handlePaneScroll('left', top)}
        />
      </aside>

      {/* Main workspace */}
      <section className="flex-1 min-h-0 flex flex-col gap-6 overflow-hidden min-w-0">
        {/* Search bar */}
        <div
          className={cn(
            'bg-surface-container-lowest border border-outline-variant shrink-0 overflow-hidden transition-all duration-300 ease-out',
            isTopSectionVisible
              ? 'p-6 opacity-100 translate-y-0 max-h-60'
              : 'p-0 opacity-0 -translate-y-2 max-h-0 pointer-events-none',
          )}
        >
          <h1 className="text-2xl font-bold mb-4">Research Any Topic</h1>
          <SearchBar
            initialQuery={urlQuery}
            onClear={clearSearch}
          />
        </div>

        {/* Results */}
        <div
          className="flex-1 min-h-0 overflow-y-auto overscroll-contain"
          onScroll={(e) => handlePaneScroll('right', e.currentTarget.scrollTop)}
          onWheelCapture={(e) => e.stopPropagation()}
          onTouchMoveCapture={(e) => e.stopPropagation()}
        >
          {mode === 'search' && searchBrief ? (
            <SearchResultView
              trend={searchBrief}
              topic={searchTopic}
              onBack={clearSearch}
              chatApiBase={`/api/chat/runs/${searchRunId}/${searchBrief.slug}`}
              insightsApiBase={`/api/insights/runs/${searchRunId}/${searchBrief.slug}`}
              postsApiBase={`/api/posts/runs/${searchRunId}/${searchBrief.slug}`}
              linkedinApiBase={`/api/posts/runs/${searchRunId}/${searchBrief.slug}/linkedin`}
              blogApiBase={`/api/posts/runs/${searchRunId}/${searchBrief.slug}/blog`}
            />
          ) : mode === 'search' && !searchBrief ? (
            <div className="bg-surface-container-lowest border border-outline-variant p-8 flex items-center gap-3">
              <span className="w-5 h-5 border-2 border-primary border-t-transparent animate-spin flex-shrink-0" />
              <p className="label-bold text-[10px]">Loading research brief for "{searchTopic}"…</p>
            </div>
          ) : (
            <div className="bg-surface-container-lowest border border-outline-variant p-8 text-center">
              <p className="label-bold text-outline">Enter a topic above to start researching.</p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
