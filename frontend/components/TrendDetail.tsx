"use client";

import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import type { TrendDetail } from "@/types";
import ChatPanel from "@/components/ChatPanel";

interface TrendDetailProps {
  trend: TrendDetail;
  chatApiBase?: string;
  insightsApiBase?: string;
}

export default function TrendDetail({ trend, chatApiBase, insightsApiBase }: TrendDetailProps) {
  const formattedDate = new Date(trend.run_date + "T00:00:00").toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <article
      role="tabpanel"
      id={`panel-${trend.slug}`}
      aria-labelledby={`tab-${trend.slug}`}
      className="h-full overflow-y-auto"
    >
      <div className="px-8 py-6 max-w-3xl">
        {/* Meta */}
        <p className="text-[11px] font-semibold text-indigo-500 uppercase tracking-widest mb-3">
          {formattedDate}
        </p>

        {/* Headline + one liner */}
        <h1 className="text-2xl font-bold text-slate-900 leading-snug mb-2">
          {trend.headline}
        </h1>
        <p className="text-base text-slate-500 leading-relaxed mb-6">
          {trend.one_liner}
        </p>

        {/* Key takeaways */}
        <div className="bg-indigo-50 border border-indigo-100 rounded-2xl p-5 mb-6">
          <h2 className="text-[11px] font-bold text-indigo-600 uppercase tracking-widest mb-3">
            Key Takeaways
          </h2>
          <ul className="space-y-2">
            {trend.key_points.map((point, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-slate-700 leading-snug">
                <span className="flex-shrink-0 mt-0.5 w-4 h-4 rounded-full bg-indigo-200 text-indigo-700 text-[10px] font-bold flex items-center justify-center">
                  {i + 1}
                </span>
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Full write-up */}
        <div className="prose prose-slate prose-sm max-w-none mb-8 leading-relaxed">
          <ReactMarkdown rehypePlugins={[rehypeSanitize]}>
            {trend.detailed_markdown}
          </ReactMarkdown>
        </div>

        {/* Sources */}
        <div className="border-t border-slate-100 pt-5">
          <h2 className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-3">
            Sources &mdash; {trend.sources.length}
          </h2>
          <div className="flex flex-wrap gap-2">
            {trend.sources.map((source, i) => (
              <a
                key={i}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-100
                           hover:bg-slate-200 text-xs text-slate-600 transition-colors border border-slate-200"
              >
                <img
                  src={`https://www.google.com/s2/favicons?domain=${source.domain}&sz=16`}
                  alt=""
                  className="w-3 h-3 flex-shrink-0"
                />
                <span className="max-w-[180px] truncate">{source.title || source.domain}</span>
              </a>
            ))}
          </div>
        </div>
        {chatApiBase && insightsApiBase && (
          <ChatPanel chatApiBase={chatApiBase} insightsApiBase={insightsApiBase} />
        )}
      </div>
    </article>
  );
}
