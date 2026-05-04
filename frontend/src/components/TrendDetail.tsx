import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import type { TrendDetail as TrendDetailType } from '@/types';
import ChatPanel from './ChatPanel';
import PostStudio from './PostStudio';

interface TrendDetailProps {
  trend: TrendDetailType;
  chatApiBase?: string;
  insightsApiBase?: string;
  onPaneScroll?: (scrollTop: number) => void;
}

export default function TrendDetail({ trend, chatApiBase, insightsApiBase, onPaneScroll }: TrendDetailProps) {
  const formattedDate = new Date(trend.run_date + 'T00:00:00').toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  });

  return (
    <article
      className="h-full min-h-0 overflow-y-auto overscroll-contain"
      onScroll={(e) => onPaneScroll?.(e.currentTarget.scrollTop)}
    >
      <div className="px-8 py-8">
        <div className="max-w-3xl">
          {/* Meta */}
          <p className="label-bold text-[10px] mb-4">{formattedDate}</p>

          {/* Headline */}
          <h1 className="text-3xl font-black leading-tight mb-3">{trend.headline}</h1>
          <p className="text-base text-on-surface-variant leading-relaxed mb-8">{trend.one_liner}</p>

          {/* Key takeaways */}
          <div className="bg-surface-container-low border border-outline-variant p-6 mb-8">
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

          {/* Full write-up */}
          <div className="prose prose-neutral prose-sm max-w-none mb-10 leading-relaxed">
            <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{trend.detailed_markdown}</ReactMarkdown>
          </div>

          {/* Sources */}
          <div className="border-t border-outline-variant pt-6">
            <h2 className="label-bold mb-4">Sources — {trend.sources.length}</h2>
            <div className="flex flex-wrap gap-2">
              {trend.sources.map((source, i) => (
                <a
                  key={i}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-outline-variant bg-surface-container-low hover:border-primary text-xs font-medium transition-colors"
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
      </div>

      {chatApiBase && insightsApiBase && (
        <ChatPanel chatApiBase={chatApiBase} insightsApiBase={insightsApiBase} />
      )}
      {chatApiBase && (
        <PostStudio
          postsApiBase={`/api/posts/${trend.run_date}/${trend.slug}`}
          linkedinApiBase={`/api/posts/${trend.run_date}/${trend.slug}/linkedin`}
          blogApiBase={`/api/posts/${trend.run_date}/${trend.slug}/blog`}
          insightsApiBase={`/api/insights/${trend.run_date}/${trend.slug}`}
        />
      )}
    </article>
  );
}
