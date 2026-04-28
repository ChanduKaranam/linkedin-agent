"use client";

import { useState, useRef, useEffect, FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import type { SearchRunStatus, SearchState, TrendListItem } from "@/types";

interface SearchBarProps {
  onResults: (runId: string, topic: string, trends: TrendListItem[]) => void;
  onClear: () => void;
}

const PHASE_LABELS: Record<SearchState, string> = {
  idle: "",
  pending: "Starting…",
  discovering: "Discovering sources…",
  scraping: "Scraping articles…",
  clustering: "Clustering trends…",
  summarizing: "Writing summaries…",
  completed: "Done",
  completed_with_warnings: "Done (with warnings)",
  failed: "Failed",
};

const TERMINAL_STATES: SearchState[] = ["completed", "completed_with_warnings", "failed"];

export default function SearchBar({ onResults, onClear }: SearchBarProps) {
  const searchParams = useSearchParams();
  // Always start with "" so server and client render identically (no hydration mismatch).
  // The URL query is read client-side only via useEffect.
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState<SearchState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [isCached, setIsCached] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const didAutoSearch = useRef(false);

  const isSearching = phase !== "idle" && !TERMINAL_STATES.includes(phase);
  const isDone = phase === "completed" || phase === "completed_with_warnings";

  // On mount, read ?q= from URL and auto-trigger a search (client-only)
  useEffect(() => {
    const q = searchParams.get("q") ?? "";
    if (q && !didAutoSearch.current) {
      didAutoSearch.current = true;
      setQuery(q);
      startSearch(q);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function startSearch(topic: string, force = false) {
    stopPolling();
    setError(null);
    setPhase("pending");
    setIsCached(false);

    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, force }),
      });

      if (res.status === 429) {
        setPhase("idle");
        setError("Too many searches. Please wait a few minutes and try again.");
        return;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setPhase("idle");
        setError(data?.detail ?? "Search failed. Please try again.");
        return;
      }

      const searchResp = await res.json();
      const runId: string = searchResp.run_id;
      const cached: boolean = searchResp.cached;
      setIsCached(cached);

      if (cached) {
        await fetchAndDeliverResults(runId, topic);
        setPhase("completed");
        return;
      }

      // Poll for state updates
      pollRef.current = setInterval(async () => {
        try {
          const statusRes = await fetch(`/api/search/runs/${runId}`);
          if (!statusRes.ok) return;
          const status: SearchRunStatus = await statusRes.json();
          setPhase(status.state);

          if (status.state === "failed") {
            stopPolling();
            setError(status.last_error ?? "The search pipeline failed.");
            return;
          }

          if (status.state === "completed" || status.state === "completed_with_warnings") {
            stopPolling();
            await fetchAndDeliverResults(runId, topic);
          }
        } catch {
          // network hiccup — keep polling
        }
      }, 2000);
    } catch {
      setPhase("idle");
      setError("Could not reach the backend. Is the server running?");
    }
  }

  async function fetchAndDeliverResults(runId: string, topic: string) {
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
    url.searchParams.set("q", trimmed);
    url.searchParams.delete("t");
    window.history.pushState({}, "", url.toString());
    startSearch(trimmed);
  }

  function handleClear() {
    stopPolling();
    setQuery("");
    setPhase("idle");
    setError(null);
    const url = new URL(window.location.href);
    url.searchParams.delete("q");
    url.searchParams.delete("t");
    window.history.pushState({}, "", url.toString());
    onClear();
  }

  function handleRefresh() {
    if (!query.trim() || isSearching) return;
    startSearch(query.trim(), true);
  }

  return (
    <div className="space-y-2">
      <form onSubmit={handleSubmit} className="relative flex items-center w-full group transition-all">
        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
          <svg className="h-5 w-5 text-indigo-400 group-focus-within:text-indigo-600 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search any tech or AI trend... e.g. Quantum Computing"
          disabled={isSearching}
          className="w-full pl-11 pr-32 py-3 rounded-full border border-slate-200 bg-white text-[15px] shadow-sm
                     transition-all focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 focus:shadow-md
                     disabled:bg-slate-50 disabled:text-slate-400 text-slate-800 placeholder-slate-400"
        />
        <div className="absolute inset-y-0 right-1.5 flex items-center gap-1.5">
          {isDone && (
            <button
              type="button"
              onClick={handleClear}
              className="p-1.5 rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors focus:outline-none"
              title="Clear search"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
          <button
            type="submit"
            disabled={!query.trim() || isSearching}
            className="px-5 py-2 rounded-full bg-indigo-600 text-white text-sm font-semibold shadow-sm
                       hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed
                       focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-indigo-600"
          >
            {isSearching ? "Searching…" : "Search"}
          </button>
        </div>
      </form>

      {/* Phase indicator */}
      {phase !== "idle" && (
        <div className="flex items-center gap-2 text-xs text-gray-500 pl-1">
          {isSearching && (
            <span className="inline-block w-3 h-3 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
          )}
          <span>{PHASE_LABELS[phase]}</span>
          {isCached && isDone && (
            <>
              <span className="text-gray-300">·</span>
              <span className="text-gray-400">Cached result</span>
              <button onClick={handleRefresh} className="text-blue-500 hover:underline">
                Refresh
              </button>
            </>
          )}
        </div>
      )}

      {/* Error */}
      {error && <p className="text-xs text-red-600 pl-1">{error}</p>}
    </div>
  );
}
