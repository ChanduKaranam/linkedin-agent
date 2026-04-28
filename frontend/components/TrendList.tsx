"use client";

import type { TrendListItem } from "@/types";

interface TrendListProps {
  trends: TrendListItem[];
  activeSlug: string;
  onSelect: (slug: string) => void;
  date: string;
}

export default function TrendList({ trends, activeSlug, onSelect, date }: TrendListProps) {
  const formattedDate = new Date(date + "T00:00:00").toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-slate-100">
        <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
          {formattedDate}
        </p>
        <p className="text-xs text-slate-500 mt-0.5">
          {trends.length} trend{trends.length !== 1 ? "s" : ""}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {trends.map((trend, i) => {
          const isActive = trend.slug === activeSlug;
          return (
            <button
              key={trend.slug}
              onClick={() => onSelect(trend.slug)}
              className={`
                w-full text-left px-4 py-3.5 border-b border-slate-100 transition-all duration-100
                ${isActive
                  ? "bg-indigo-50 border-l-[3px] border-l-indigo-500 pl-[13px]"
                  : "hover:bg-slate-50 border-l-[3px] border-l-transparent"
                }
              `}
            >
              <div className="flex items-start gap-2.5">
                <span className={`
                  flex-shrink-0 mt-0.5 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold
                  ${isActive ? "bg-indigo-600 text-white" : "bg-slate-200 text-slate-500"}
                `}>
                  {i + 1}
                </span>
                <div className="min-w-0">
                  <p className={`text-sm font-semibold leading-snug line-clamp-2 ${isActive ? "text-indigo-900" : "text-slate-800"}`}>
                    {trend.headline}
                  </p>
                  <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-snug">
                    {trend.one_liner}
                  </p>
                  <p className="text-[10px] text-slate-400 mt-1.5 font-medium">
                    {trend.source_count} source{trend.source_count !== 1 ? "s" : ""}
                  </p>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
