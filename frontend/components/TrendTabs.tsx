"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, KeyboardEvent } from "react";
import type { TrendListItem } from "@/types";

interface TrendTabsProps {
  trends: TrendListItem[];
  activeSlug: string;
  onSelect: (slug: string) => void;
}

export default function TrendTabs({ trends, activeSlug, onSelect }: TrendTabsProps) {
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (e.key === "ArrowRight") {
      const next = (index + 1) % trends.length;
      tabRefs.current[next]?.focus();
      onSelect(trends[next].slug);
    } else if (e.key === "ArrowLeft") {
      const prev = (index - 1 + trends.length) % trends.length;
      tabRefs.current[prev]?.focus();
      onSelect(trends[prev].slug);
    }
  };

  return (
    <div
      role="tablist"
      aria-label="AI & Tech Trends"
      className="flex gap-2 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-gray-300"
    >
      {trends.map((trend, i) => {
        const isActive = trend.slug === activeSlug;
        return (
          <button
            key={trend.slug}
            role="tab"
            aria-selected={isActive}
            aria-controls={`panel-${trend.slug}`}
            id={`tab-${trend.slug}`}
            ref={(el) => { tabRefs.current[i] = el; }}
            onClick={() => onSelect(trend.slug)}
            onKeyDown={(e) => handleKeyDown(e, i)}
            tabIndex={isActive ? 0 : -1}
            className={`
              flex-shrink-0 px-4 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap
              focus:outline-none focus:ring-2 focus:ring-blue-500
              ${isActive
                ? "bg-blue-600 text-white shadow-sm"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }
            `}
          >
            {trend.headline.length > 50 ? trend.headline.slice(0, 47) + "…" : trend.headline}
          </button>
        );
      })}
    </div>
  );
}
