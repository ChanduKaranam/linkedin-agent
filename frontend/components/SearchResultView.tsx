"use client";

import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import type { TrendDetail } from "@/types";
import ChatPanel from "@/components/ChatPanel";

interface SearchResultViewProps {
  trend: TrendDetail;
  topic: string;
  onBack: () => void;
  chatApiBase?: string;
  insightsApiBase?: string;
}

export default function SearchResultView({ trend, topic, onBack, chatApiBase, insightsApiBase }: SearchResultViewProps) {
  const sourceCount = trend.sources.length;

  return (
    <div className="max-w-3xl mx-auto px-2">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-800 font-medium mb-5 transition-colors"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
        </svg>
        Back to daily trends
      </button>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-8 py-7 border-b border-slate-100">
          <span className="inline-block px-2.5 py-1 rounded-full bg-indigo-100 text-indigo-700 text-[10px] font-bold uppercase tracking-widest mb-4">
            Research Brief
          </span>
          <h1 className="text-2xl font-bold text-slate-900 leading-snug mb-2">
            {trend.headline}
          </h1>
          <p className="text-base text-slate-500 leading-relaxed mb-3">
            {trend.one_liner}
          </p>
          <p className="text-xs text-slate-400">
            Query: &ldquo;{topic}&rdquo; &nbsp;·&nbsp; {sourceCount} source{sourceCount !== 1 ? "s" : ""}
          </p>
        </div>

        <div className="px-8 py-6">
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

          <div className="prose prose-slate prose-sm max-w-none mb-8 leading-relaxed">
            <ReactMarkdown rehypePlugins={[rehypeSanitize]}>
              {trend.detailed_markdown}
            </ReactMarkdown>
          </div>

          <div className="border-t border-slate-100 pt-5">
            <h2 className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-3">
              Sources &mdash; {sourceCount}
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
        </div>
        {chatApiBase && insightsApiBase && (
          <div className="px-8 pb-6">
            <ChatPanel chatApiBase={chatApiBase} insightsApiBase={insightsApiBase} />
          </div>
        )}
      </div>
    </div>
  );
}
