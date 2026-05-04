import { useCallback, useEffect, useState } from 'react';
import { useBackendStatus } from '@/context/BackendStatusContext';
import EmptyState from '@/components/EmptyState';
import PostLibrary from '@/components/PostLibrary';
import PostEditor from '@/components/PostEditor';
import NewPostDialog from '@/components/NewPostDialog';
import type { GeneratedPost, GeneratedPostWithHeadline } from '@/types';

export default function LinkedInPost() {
  const STORAGE_KEY = 'linkedin:lastSelectedPostId';
  const { backendStatus } = useBackendStatus();
  const [active, setActive] = useState<GeneratedPostWithHeadline | null>(null);
  const [savedId, setSavedId] = useState<number | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const id = raw ? Number(raw) : NaN;
    if (Number.isFinite(id) && id > 0) {
      setSavedId(id);
    }
  }, [STORAGE_KEY]);

  useEffect(() => {
    if (!savedId) return;
    if (active?.id === savedId) return;
    let cancelled = false;
    void fetch(`/api/posts/by-id/${savedId}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<GeneratedPost>;
      })
      .then((post) => {
        if (cancelled) return;
        if (post.kind !== 'linkedin') {
          window.localStorage.removeItem(STORAGE_KEY);
          setSavedId(null);
          return;
        }
        setActive({
          ...post,
          headline: post.slug.replace(/-/g, ' '),
        });
      })
      .catch(() => {
        if (cancelled) return;
        window.localStorage.removeItem(STORAGE_KEY);
        setSavedId(null);
      });
    return () => {
      cancelled = true;
    };
  }, [active?.id, savedId, STORAGE_KEY]);

  if (backendStatus === 'unreachable') return <EmptyState variant="unreachable" />;

  const insightsApiBase = active ? `/api/insights/${active.run_date}/${active.slug}` : '';
  const linkedinApiBase = active ? `/api/posts/${active.run_date}/${active.slug}/linkedin` : '';
  const blogApiBase    = active ? `/api/posts/${active.run_date}/${active.slug}/blog` : '';

  function handleUpdated(updated: GeneratedPost) {
    if (!active) return;
    setActive({ ...active, ...updated });
    window.localStorage.setItem(STORAGE_KEY, String(updated.id));
    setSavedId(updated.id);
    setRefreshKey((k) => k + 1);
  }

  function handleCreated(post: GeneratedPost) {
    // Set a placeholder immediately so the editor opens right away.
    // onLibraryLoad will replace it with the full post (including real headline)
    // once the library refetch completes.
    setDialogOpen(false);
    setActive({ ...post, headline: post.slug.replace(/-/g, ' ') });
    window.localStorage.setItem(STORAGE_KEY, String(post.id));
    setSavedId(post.id);
    setRefreshKey((k) => k + 1);
  }

  function handleSelect(post: GeneratedPostWithHeadline) {
    setActive(post);
    window.localStorage.setItem(STORAGE_KEY, String(post.id));
    setSavedId(post.id);
  }

  function handleDeleted(postId: number) {
    if (active?.id === postId) {
      setActive(null);
    }
    window.localStorage.removeItem(STORAGE_KEY);
    setSavedId(null);
    setRefreshKey((k) => k + 1);
  }

  const handleLibraryLoad = useCallback((firstPost: GeneratedPostWithHeadline) => {
    setActive((prev) => {
      // No selection yet → select the most recent post automatically
      if (!prev) return firstPost;
      // After creating a new post, the library refreshes and returns the real post first —
      // update active so the header shows the real headline instead of the slug
      if (prev.id === firstPost.id) return { ...prev, ...firstPost };
      return prev;
    });
  }, []);

  return (
    <div className="flex-1 flex w-full overflow-hidden border-l border-r border-outline-variant">
      <aside className="w-[300px] min-w-[300px] border-r border-outline-variant flex flex-col">
        <PostLibrary
          kind="linkedin"
          activeId={active?.id ?? null}
          onSelect={handleSelect}
          onNewPost={() => setDialogOpen(true)}
          refreshKey={refreshKey}
          onFirstLoad={handleLibraryLoad}
        />
      </aside>

      <section className="flex-1 overflow-y-auto bg-background">
        {active ? (
          <>
            <div className="px-8 pt-8 pb-4 border-b border-outline-variant bg-surface-container-lowest">
              <p className="label-bold text-[9px] text-outline mb-1">{active.run_date} · LinkedIn Post</p>
              <h1 className="text-2xl font-black leading-tight">{active.headline}</h1>
            </div>
            <PostEditor
              post={active}
              kind="linkedin"
              linkedinApiBase={linkedinApiBase}
              blogApiBase={blogApiBase}
              insightsApiBase={insightsApiBase}
              onUpdated={handleUpdated}
              onDeleted={handleDeleted}
              showPublish={true}
            />
          </>
        ) : (
          <div className="h-full flex flex-col items-center justify-center gap-6 p-10 text-center">
            <div className="w-12 h-12 border border-outline-variant flex items-center justify-center">
              <span className="label-bold text-[10px] text-outline">LI</span>
            </div>
            <div>
              <h2 className="text-2xl font-bold mb-2">No post selected</h2>
              <p className="text-on-surface-variant max-w-sm">
                Pick a draft from the library on the left, or click + New Post to generate one.
              </p>
            </div>
            <button onClick={() => setDialogOpen(true)} className="btn-primary py-2.5 px-8 text-[10px]">
              + New Post
            </button>
          </div>
        )}
      </section>

      <NewPostDialog
        open={dialogOpen}
        kind="linkedin"
        onClose={() => setDialogOpen(false)}
        onCreated={handleCreated}
      />
    </div>
  );
}
