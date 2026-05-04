import { cn } from '@/lib/utils';
import type { TrendListItem } from '@/types';

interface TrendListProps {
  trends: TrendListItem[];
  activeSlug: string;
  onSelect: (slug: string) => void;
  date: string;
  sortMode: 'latest' | 'oldest' | 'chatted' | 'created_linkedin' | 'created_blog';
  onSortChange: (mode: 'latest' | 'oldest' | 'chatted' | 'created_linkedin' | 'created_blog') => void;
  onPaneScroll?: (scrollTop: number) => void;
}

export default function TrendList({
  trends,
  activeSlug,
  onSelect,
  date,
  sortMode,
  onSortChange,
  onPaneScroll,
}: TrendListProps) {
  const formattedDate = new Date(date + 'T00:00:00').toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });

  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3 border-b border-outline-variant bg-surface-container-low">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="label-bold text-on-surface-variant">{formattedDate}</p>
            <p className="text-xs text-on-surface-variant mt-0.5 font-mono">
              {trends.length} trend{trends.length !== 1 ? 's' : ''}
            </p>
          </div>
          <select
            value={sortMode}
            onChange={(e) => onSortChange(e.target.value as TrendListProps['sortMode'])}
            className="text-[10px] font-bold uppercase tracking-widest border border-outline-variant bg-surface-container-lowest px-2 py-1 outline-none focus:border-primary"
            aria-label="Sort trends"
          >
            <option value="latest">Latest</option>
            <option value="oldest">Oldest</option>
            <option value="chatted">Chatted About</option>
            <option value="created_linkedin">Created LinkedIn Posts</option>
            <option value="created_blog">Created Blog Posts</option>
          </select>
        </div>
      </div>
      <div
        className="flex-1 overflow-y-auto overscroll-contain"
        onScroll={(e) => onPaneScroll?.(e.currentTarget.scrollTop)}
      >
        {trends.map((trend, i) => {
          const isActive = trend.slug === activeSlug;
          return (
            <button
              key={trend.slug}
              onClick={() => onSelect(trend.slug)}
              className={cn(
                'w-full text-left p-4 border-b border-outline-variant transition-all border-l-2',
                isActive
                  ? 'bg-surface-container-low border-l-primary'
                  : 'hover:bg-surface-container border-l-transparent',
              )}
            >
              <div className="flex items-start gap-3">
                <span className={cn(
                  'flex-shrink-0 mt-0.5 w-5 h-5 flex items-center justify-center text-[10px] font-black border',
                  isActive ? 'bg-primary text-on-primary border-primary' : 'bg-surface-container-high border-outline-variant text-on-surface-variant',
                )}>
                  {i + 1}
                </span>
                <div className="min-w-0">
                  <p className={cn('text-sm font-semibold leading-snug line-clamp-2', isActive ? 'text-primary' : 'text-on-surface')}>
                    {trend.headline}
                  </p>
                  <p className="text-xs text-on-surface-variant mt-1 line-clamp-2 leading-snug">{trend.one_liner}</p>
                  <p className="label-bold text-[9px] mt-1.5 text-outline">
                    {trend.source_count} source{trend.source_count !== 1 ? 's' : ''}
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
