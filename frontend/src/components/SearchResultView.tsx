import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { ArrowLeft } from 'lucide-react';
import type { TrendDetail } from '@/types';
import ChatPanel from './ChatPanel';
import PostStudio from './PostStudio';

interface SearchResultViewProps {
  trend: TrendDetail;
  topic: string;
  onBack: () => void;
  chatApiBase?: string;
  insightsApiBase?: string;
  postsApiBase?: string;
  linkedinApiBase?: string;
  blogApiBase?: string;
}

export default function SearchResultView({
  trend, topic, onBack, chatApiBase, insightsApiBase, postsApiBase, linkedinApiBase, blogApiBase,
}: SearchResultViewProps) {
  const sourceCount = trend.sources.length;

  return (
    <div className="max-w-3xl mx-auto px-2">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 label-bold text-[10px] text-on-surface-variant hover:text-on-surface mb-6 transition-colors"
      >
        <ArrowLeft size={12} /> Back to daily trends
      </button>

      <div className="bg-surface-container-lowest border border-outline-variant overflow-hidden">
        <div className="px-8 py-6 border-b border-outline-variant">
          <span className="label-bold text-[9px] bg-primary text-on-primary px-2 py-1 mb-4 inline-block">Research Brief</span>
          <h1 className="text-2xl font-black leading-snug mb-2 mt-3">{trend.headline}</h1>
          <p className="text-base text-on-surface-variant leading-relaxed mb-3">{trend.one_liner}</p>
          <p className="label-bold text-[9px] text-outline">
            Query: "{topic}" · {sourceCount} source{sourceCount !== 1 ? 's' : ''}
          </p>
        </div>

        <div className="px-8 py-6">
          <div className="bg-surface-container-low border border-outline-variant p-5 mb-6">
            <h2 className="label-bold mb-4">Key Takeaways</h2>
            <ul className="flex flex-col gap-3">
              {trend.key_points.map((point, i) => (
                <li key={i} className="flex items-start gap-3 text-sm text-on-surface leading-snug">
                  <span className="flex-shrink-0 mt-0.5 w-5 h-5 bg-primary text-on-primary flex items-center justify-center text-[10px] font-black">
                    {i + 1}
                  </span>
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="prose prose-neutral prose-sm max-w-none mb-8 leading-relaxed">
            <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{trend.detailed_markdown}</ReactMarkdown>
          </div>

          <div className="border-t border-outline-variant pt-5">
            <h2 className="label-bold text-[9px] mb-3">Sources — {sourceCount}</h2>
            <div className="flex flex-wrap gap-2">
              {trend.sources.map((source, i) => (
                <a
                  key={i}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-outline-variant bg-surface-container-low hover:border-primary text-xs font-medium transition-colors"
                >
                  <img src={`https://www.google.com/s2/favicons?domain=${source.domain}&sz=16`} alt="" className="w-3 h-3 flex-shrink-0" />
                  <span className="max-w-[180px] truncate">{source.title || source.domain}</span>
                </a>
              ))}
            </div>
          </div>
        </div>

        {chatApiBase && insightsApiBase && (
          <div className="px-8 pb-2">
            <ChatPanel chatApiBase={chatApiBase} insightsApiBase={insightsApiBase} />
          </div>
        )}
        {postsApiBase && linkedinApiBase && blogApiBase && insightsApiBase && (
          <PostStudio postsApiBase={postsApiBase} linkedinApiBase={linkedinApiBase} blogApiBase={blogApiBase} insightsApiBase={insightsApiBase} />
        )}
      </div>
    </div>
  );
}
