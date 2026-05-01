"use client";

import { useEffect, useState, Suspense } from "react";
import SearchBar from "@/components/SearchBar";
import TrendList from "@/components/TrendList";
import TrendDetail from "@/components/TrendDetail";
import DateSelector from "@/components/DateSelector";
import ScheduleEditor from "@/components/ScheduleEditor";
import SearchResultView from "@/components/SearchResultView";
import SearchHistory from "@/components/SearchHistory";
import EmptyState from "@/components/EmptyState";
import type {
  BackendStatus,
  TrendDetail as TrendDetailType,
  TrendListItem,
  ScheduleConfig,
} from "@/types";

type Mode = "daily" | "search";
type SidebarTab = "trends" | "searches";

export default function Home() {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("ok");

  // ── Schedule config ────────────────────────────────────────────────────
  const [schedule, setSchedule] = useState<ScheduleConfig | null>(null);

  // ── Available dates ────────────────────────────────────────────────────
  const [availableDates, setAvailableDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>("");

  // ── Trends for selected date ───────────────────────────────────────────
  const [dailyTrends, setDailyTrends] = useState<TrendListItem[]>([]);
  const [loadingTrends, setLoadingTrends] = useState(false);

  // ── Mode ───────────────────────────────────────────────────────────────
  const [mode, setMode] = useState<Mode>("daily");
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>("trends");
  const [searchTopic, setSearchTopic] = useState<string>("");
  const [searchRunId, setSearchRunId] = useState<string>("");

  // ── Selected trend detail ──────────────────────────────────────────────
  const [activeSlug, setActiveSlug] = useState<string>("");
  const [dailyDetail, setDailyDetail] = useState<TrendDetailType | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // ── Search result state ────────────────────────────────────────────────
  const [searchBrief, setSearchBrief] = useState<TrendDetailType | null>(null);
  const [loadingBrief, setLoadingBrief] = useState(false);

  // ── Bootstrap: health check + available dates + schedule ──────────────
  useEffect(() => {
    Promise.all([
      fetch("/api/health").then((r) => r.json()).catch(() => null),
      fetch("/api/trends/dates").then((r) => r.json()).catch(() => []),
      // Fetch schedule — try the debug-gated admin endpoint first, fall back to the
      // public read endpoint so the badge always shows even when DEBUG=false.
      fetch("/api/admin/schedule")
        .then((r) => r.ok ? r.json() : fetch("/api/schedule").then((r2) => r2.json()))
        .catch(() => null),
    ]).then(([health, dates, sched]) => {
      if (!health || health?.error === "backend_unreachable") {
        setBackendStatus("unreachable");
        return;
      }
      if (sched && !sched.error) setSchedule(sched);

      const validDates: string[] = Array.isArray(dates) ? dates : [];
      setAvailableDates(validDates);

      if (validDates.length === 0) {
        setBackendStatus("no_run");
        return;
      }

      // Auto-select latest date (or date from URL)
      const params = new URLSearchParams(window.location.search);
      const urlDate = params.get("d");
      const initial = urlDate && validDates.includes(urlDate) ? urlDate : validDates[0];
      setSelectedDate(initial);
    });
  }, []);

  // ── Load trends when selected date changes ─────────────────────────────
  useEffect(() => {
    if (!selectedDate || mode !== "daily") return;
    setLoadingTrends(true);
    setDailyTrends([]);
    setDailyDetail(null);
    setActiveSlug("");

    fetch(`/api/trends/by-date/${selectedDate}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((list: TrendListItem[]) => {
        setDailyTrends(list);
        setLoadingTrends(false);
        if (list.length > 0) {
          const params = new URLSearchParams(window.location.search);
          const urlSlug = params.get("t");
          const initial = urlSlug && list.find((t) => t.slug === urlSlug) ? urlSlug : list[0].slug;
          setActiveSlug(initial);
        }
      })
      .catch(() => setLoadingTrends(false));
  }, [selectedDate, mode]);

  // ── Load detail when active slug changes ──────────────────────────────
  useEffect(() => {
    if (!activeSlug || !selectedDate || mode !== "daily") return;
    setLoadingDetail(true);
    setDailyDetail(null);
    fetch(`/api/trends/${selectedDate}/${activeSlug}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d && !d.error) setDailyDetail(d);
        setLoadingDetail(false);
      })
      .catch(() => setLoadingDetail(false));
  }, [activeSlug, selectedDate, mode]);

  // ── Handlers ───────────────────────────────────────────────────────────
  function handleDateSelect(date: string) {
    setSelectedDate(date);
    const url = new URL(window.location.href);
    url.searchParams.set("d", date);
    url.searchParams.delete("t");
    window.history.replaceState({}, "", url.toString());
  }

  function handleTrendSelect(slug: string) {
    setActiveSlug(slug);
    const url = new URL(window.location.href);
    url.searchParams.set("t", slug);
    window.history.replaceState({}, "", url.toString());
  }

  function handleSearchResults(runId: string, topic: string, trends: TrendListItem[]) {
    setSearchRunId(runId);
    setSearchTopic(topic);
    setMode("search");
    setSidebarTab("searches");
    setSearchBrief(null);
    const only = trends[0];
    if (!only) return;
    setLoadingBrief(true);
    fetch(`/api/search/runs/${runId}/trends/${only.slug}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d && !d.error) setSearchBrief(d); setLoadingBrief(false); })
      .catch(() => setLoadingBrief(false));
  }

  function handleSearchClear() {
    setMode("daily");
    setSidebarTab("trends");
    setSearchRunId("");
    setSearchTopic("");
    setSearchBrief(null);
    const url = new URL(window.location.href);
    url.searchParams.delete("q");
    window.history.pushState({}, "", url.toString());
  }

  // ── Early exits ────────────────────────────────────────────────────────
  if (backendStatus === "unreachable") return <EmptyState variant="unreachable" />;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-5 py-3 flex items-center gap-4">
          {/* Brand */}
          <div className="flex items-center gap-2.5 flex-shrink-0">
            <div className="w-8 h-8 rounded-xl bg-indigo-600 flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <h1 className="text-sm font-bold text-slate-900 leading-none">AI Trend Agent</h1>
              <p className="text-[10px] text-slate-400 mt-0.5">Daily intelligence digest</p>
            </div>
          </div>

          {/* Search bar (fills middle) */}
          <div className="flex-1 min-w-0">
            <Suspense fallback={<div className="h-9 bg-slate-100 rounded-lg animate-pulse" />}>
              <SearchBar onResults={handleSearchResults} onClear={handleSearchClear} />
            </Suspense>
          </div>

          {/* Schedule editor */}
          <div className="flex-shrink-0">
            <ScheduleEditor schedule={schedule} onSaved={setSchedule} />
          </div>
        </div>
      </header>

      {/* ── Main ────────────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-5 py-5 flex flex-col gap-4">

        {/* No-run empty state — only in daily mode before first run */}
        {mode === "daily" && backendStatus === "no_run" && (
          <EmptyState variant="no_run" nextScheduled={
            schedule ? `${String(schedule.hour).padStart(2,"0")}:${String(schedule.minute).padStart(2,"0")} ${schedule.timezone}` : undefined
          } />
        )}

        {(availableDates.length > 0 || mode === "search") && (
          <>
                {/* Date selector — daily mode only */}
                {mode === "daily" && availableDates.length > 0 && (
                  <div>
                    <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest mb-2">
                      Browse by date
                    </p>
                    <DateSelector
                      dates={availableDates}
                      selectedDate={selectedDate}
                      onSelect={handleDateSelect}
                    />
                  </div>
                )}

                {/* Two-column panel */}
                <div className="flex-1 flex rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden"
                     style={{ minHeight: "calc(100vh - 220px)" }}>

                  {/* Left sidebar — tabbed: Trends / Searches */}
                  <div className="w-72 flex-shrink-0 border-r border-slate-100 overflow-hidden flex flex-col">
                    {/* Tab bar */}
                    <div className="flex border-b border-slate-100 flex-shrink-0">
                      <button
                        onClick={() => setSidebarTab("trends")}
                        className={`flex-1 py-2.5 text-xs font-semibold transition-colors ${
                          sidebarTab === "trends"
                            ? "text-indigo-600 border-b-2 border-indigo-500 -mb-px bg-indigo-50/50"
                            : "text-slate-400 hover:text-slate-600"
                        }`}
                      >
                        Trends
                      </button>
                      <button
                        onClick={() => setSidebarTab("searches")}
                        className={`flex-1 py-2.5 text-xs font-semibold transition-colors ${
                          sidebarTab === "searches"
                            ? "text-indigo-600 border-b-2 border-indigo-500 -mb-px bg-indigo-50/50"
                            : "text-slate-400 hover:text-slate-600"
                        }`}
                      >
                        Searches
                      </button>
                    </div>

                    {/* Tab content */}
                    <div className="flex-1 overflow-hidden flex flex-col">
                      {sidebarTab === "trends" && (
                        loadingTrends ? (
                          <div className="flex items-center justify-center py-16 text-slate-400">
                            <span className="w-5 h-5 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" />
                          </div>
                        ) : dailyTrends.length > 0 ? (
                          <TrendList
                            trends={dailyTrends}
                            activeSlug={activeSlug}
                            onSelect={(slug) => { setMode("daily"); handleTrendSelect(slug); }}
                            date={selectedDate}
                          />
                        ) : (
                          <div className="flex flex-col items-center justify-center py-16 px-6 text-center gap-2">
                            <p className="text-3xl">📭</p>
                            <p className="text-sm font-medium text-slate-600">No trends for this date</p>
                            <p className="text-xs text-slate-400">Try selecting a different day</p>
                          </div>
                        )
                      )}

                      {sidebarTab === "searches" && (
                        <SearchHistory
                          onOpen={handleSearchResults}
                          activeRunId={mode === "search" ? searchRunId : undefined}
                        />
                      )}
                    </div>
                  </div>

                  {/* Right panel — daily detail or search result */}
                  <div className="flex-1 overflow-hidden">
                    {/* Search result inside the two-column layout */}
                    {mode === "search" && sidebarTab === "searches" && (
                      <>
                        {loadingBrief && (
                          <div className="flex items-center justify-center h-full text-slate-400">
                            <span className="w-6 h-6 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" />
                          </div>
                        )}
                        {!loadingBrief && searchBrief && (
                          <div className="h-full overflow-y-auto">
                            <SearchResultView
                              trend={searchBrief}
                              topic={searchTopic}
                              onBack={handleSearchClear}
                              chatApiBase={`/api/chat/runs/${searchRunId}/${searchBrief.slug}`}
                              insightsApiBase={`/api/insights/runs/${searchRunId}/${searchBrief.slug}`}
                              postsApiBase={`/api/posts/runs/${searchRunId}/${searchBrief.slug}`}
                              linkedinApiBase={`/api/posts/runs/${searchRunId}/${searchBrief.slug}/linkedin`}
                              blogApiBase={`/api/posts/runs/${searchRunId}/${searchBrief.slug}/blog`}
                            />
                          </div>
                        )}
                        {!loadingBrief && !searchBrief && (
                          <div className="flex items-center justify-center h-full text-slate-400 text-sm">
                            No results
                          </div>
                        )}
                      </>
                    )}

                    {/* Daily trend detail */}
                    {mode === "daily" && (
                      <>
                        {loadingDetail && (
                          <div className="flex items-center justify-center h-full text-slate-400">
                            <span className="w-6 h-6 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" />
                          </div>
                        )}
                        {!loadingDetail && dailyDetail && (
                          <TrendDetail
                            trend={dailyDetail}
                            chatApiBase={`/api/chat/${selectedDate}/${activeSlug}`}
                            insightsApiBase={`/api/insights/${selectedDate}/${activeSlug}`}
                          />
                        )}
                        {!loadingDetail && !dailyDetail && dailyTrends.length > 0 && !loadingTrends && (
                          <div className="flex items-center justify-center h-full text-slate-400 text-sm">
                            Select a trend to read
                          </div>
                        )}
                        {!loadingDetail && !dailyDetail && dailyTrends.length === 0 && !loadingTrends && (
                          <div className="flex items-center justify-center h-full text-slate-400 text-sm">
                            No data available
                          </div>
                        )}
                      </>
                    )}

                    {/* Searches tab but no search active */}
                    {mode !== "search" && sidebarTab === "searches" && (
                      <div className="flex flex-col items-center justify-center h-full text-slate-400 text-sm gap-2">
                        <span className="text-3xl">🔍</span>
                        <p>Select a search from the left to view its results</p>
                      </div>
                    )}
                  </div>
                </div>
          </>
        )}
      </main>
    </div>
  );
}
