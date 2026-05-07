/**
 * Collapsible Post Studio panel used inside TrendDetail / SearchResultView.
 * Handles auto-fetch of existing posts and tab switching,
 * then delegates the actual editor UI to PostEditor.
 */
import { useEffect, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import PostEditor from './PostEditor';
import type { GeneratedPost } from '@/types';

interface PostStudioProps {
  postsApiBase: string;
  linkedinApiBase: string;
  blogApiBase: string;
  insightsApiBase: string;
  lockedTab?: 'linkedin' | 'blog';
}

type Tab = 'linkedin' | 'blog';

export default function PostStudio({ postsApiBase, linkedinApiBase, blogApiBase, insightsApiBase, lockedTab }: PostStudioProps) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>(lockedTab ?? 'linkedin');
  const [linkedinPost, setLinkedinPost] = useState<GeneratedPost | null>(null);
  const [blogPost, setBlogPost] = useState<GeneratedPost | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentPost = tab === 'linkedin' ? linkedinPost : blogPost;

  // Always fetch posts when postsApiBase changes (e.g. user switches trends).
  // Clear stale post data immediately so we don't show a previous trend's post.
  useEffect(() => {
    setLinkedinPost(null);
    setBlogPost(null);
    setError(null);
    if (!postsApiBase) return;
    let cancelled = false;
    fetch(postsApiBase)
      .then((r) => (r.ok ? r.json() : []))
      .then((posts: GeneratedPost[]) => {
        if (cancelled) return;
        const li = posts.find((p) => p.kind === 'linkedin') ?? null;
        const blog = posts.find((p) => p.kind === 'blog') ?? null;
        setLinkedinPost(li);
        setBlogPost(blog);
        // Auto-open if existing posts are found for this trend
        if (li || blog) setOpen(true);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [postsApiBase]);

  async function handleGenerateFirst() {
    setGenerating(true);
    setError(null);
    const url = tab === 'linkedin' ? linkedinApiBase : blogApiBase;
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_instructions: '' }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({})) as Record<string, unknown>;
        setError(String(err.detail ?? err.error ?? 'Generation failed.'));
        return;
      }
      const post: GeneratedPost = await res.json();
      if (tab === 'linkedin') setLinkedinPost(post); else setBlogPost(post);
    } catch { setError('Network error. Is the backend running?'); }
    finally { setGenerating(false); }
  }

  function handleUpdated(updated: GeneratedPost) {
    if (updated.kind === 'linkedin') setLinkedinPost(updated);
    else setBlogPost(updated);
  }

  function handleDeleted(postId: number) {
    if (linkedinPost?.id === postId) setLinkedinPost(null);
    if (blogPost?.id === postId) setBlogPost(null);
  }

  const tabs: Tab[] = lockedTab ? [lockedTab] : ['linkedin', 'blog'];

  return (
    <div className="border-t border-outline-variant mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-6 py-4 text-left hover:bg-surface-container transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 border border-outline-variant flex items-center justify-center flex-shrink-0">
            <span className="text-[8px] font-black text-on-surface-variant">PS</span>
          </div>
          <div>
            <p className="text-sm font-bold uppercase tracking-tight">Post Studio</p>
            <p className="label-bold text-[9px] text-outline mt-0.5">
              {(linkedinPost || blogPost)
                ? `${[linkedinPost && 'LinkedIn', blogPost && 'Blog'].filter(Boolean).join(' + ')} post ready`
                : 'Generate LinkedIn post or blog in your voice'}
            </p>
          </div>
        </div>
        <ChevronDown size={14} className={cn('text-on-surface-variant transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="flex flex-col">
          {/* Tab bar */}
          {!lockedTab && (
            <div className="flex border-b border-outline-variant px-6">
              {tabs.map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={cn(
                    'px-4 py-2 text-[10px] font-bold uppercase tracking-widest transition-colors border-b-2 -mb-px',
                    tab === t ? 'border-primary text-primary' : 'border-transparent text-on-surface-variant hover:text-on-surface',
                  )}
                >
                  {t === 'linkedin' ? 'LinkedIn Post' : 'Blog Post'}
                  {t === 'linkedin' && linkedinPost?.status === 'published' && (
                    <span className="ml-1.5 bg-primary text-on-primary px-1.5 py-0.5 text-[8px] font-black">PUB</span>
                  )}
                </button>
              ))}
            </div>
          )}

          {error && (
            <p className="mx-6 mt-4 text-[11px] text-red-600 border border-red-200 bg-red-50 px-3 py-2 font-mono">{error}</p>
          )}

          {!currentPost ? (
            <div className="flex flex-col items-center gap-4 py-8 px-6 text-center">
              <p className="text-sm text-on-surface-variant max-w-sm">
                {tab === 'linkedin'
                  ? 'Generate a LinkedIn post based on this trend and your conversation.'
                  : 'Generate a blog post based on this trend and your conversation.'}
              </p>
              <button onClick={handleGenerateFirst} disabled={generating} className="btn-primary py-2 px-6 text-[10px] disabled:opacity-50">
                {generating ? 'Generating…' : `Generate ${tab === 'linkedin' ? 'LinkedIn Post' : 'Blog Post'}`}
              </button>
            </div>
          ) : (
            <PostEditor
              post={currentPost}
              kind={tab}
              linkedinApiBase={linkedinApiBase}
              blogApiBase={blogApiBase}
              insightsApiBase={insightsApiBase}
              onUpdated={handleUpdated}
              onDeleted={handleDeleted}
              showPublish={tab === 'linkedin'}
            />
          )}
        </div>
      )}
    </div>
  );
}
