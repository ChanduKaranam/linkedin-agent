"use client";

import { useEffect, useState } from "react";
import type { SearchHistoryItem, TrendListItem } from "@/types";

interface SearchHistoryProps {
  onOpen: (runId: string, topic: string, trends: TrendListItem[]) => void;
  activeRunId?: string;
}

export default function SearchHistory({ onOpen, activeRunId }: SearchHistoryProps) {
  const [items, setItems] = useState<SearchHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [openingRunId, setOpeningRunId] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/search/history")
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => { setItems(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

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

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10 text-slate-400">
        <span className="w-4 h-4 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" />
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 px-5 text-center gap-2">
        <span className="text-3xl">🔍</span>
        <p className="text-sm font-medium text-slate-600">No searches yet</p>
        <p className="text-xs text-slate-400 leading-snug">
          Use the search bar above to research any AI or tech topic.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-slate-100">
        <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
          Your searches
        </p>
        <p className="text-xs text-slate-500 mt-0.5">
          {items.length} topic{items.length !== 1 ? "s" : ""}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {items.map((item) => {
          const isActive = item.run_id === activeRunId;
          const isOpening = openingRunId === item.run_id;

          return (
            <button
              key={item.run_id}
              onClick={() => handleOpen(item)}
              disabled={!!openingRunId}
              className={`
                w-full text-left px-4 py-3.5 border-b border-slate-100 transition-all duration-100
                disabled:opacity-60
                ${isActive
                  ? "bg-indigo-50 border-l-[3px] border-l-indigo-500 pl-[13px]"
                  : "hover:bg-slate-50 border-l-[3px] border-l-transparent"
                }
              `}
            >
              <div className="flex items-start gap-2.5">
                <span className={`
                  flex-shrink-0 mt-0.5 w-5 h-5 rounded-full flex items-center justify-center
                  ${isActive ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-500"}
                `}>
                  {isOpening ? (
                    <span className="w-2.5 h-2.5 rounded-full border border-current border-t-transparent animate-spin" />
                  ) : (
                    <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                  )}
                </span>

                <div className="min-w-0 flex-1">
                  <p className={`text-sm font-semibold leading-snug line-clamp-2 ${isActive ? "text-indigo-900" : "text-slate-800"}`}>
                    {item.topic}
                  </p>
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className="text-[10px] text-slate-400">{formatDate(item.started_at)}</span>
                    <span className="text-slate-200">·</span>
                    <span className="text-[10px] text-slate-400">
                      {item.trend_count} result{item.trend_count !== 1 ? "s" : ""}
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
