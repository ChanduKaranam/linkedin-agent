/**
 * Presentational post editor — no collapsible wrapper, no tab bar, no auto-fetch.
 * Used directly by BlogPost / LinkedInPost pages.
 * PostStudio keeps its own collapsible+tabs wrapper and renders this internally.
 */
import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { Copy, Download, Image, X, Send, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { GeneratedPost, LinkedInStatus, Insight } from '@/types';
import { useToast } from '@/context/ToastContext';

interface PostEditorProps {
  post: GeneratedPost;
  kind: 'linkedin' | 'blog';
  linkedinApiBase: string;
  blogApiBase: string;
  /** Kept for API compatibility — edits are recorded as style samples server-side. */
  insightsApiBase?: string;
  onUpdated: (updated: GeneratedPost) => void;
  onDeleted?: (postId: number) => void;
  /** Show LinkedIn connect/publish section. Default true. */
  showPublish?: boolean;
}

type ViewMode = 'edit' | 'preview';

export function LinkedInPreviewCard({
  content,
  hashtags,
  photoUrl,
}: {
  content: string;
  hashtags: string[];
  photoUrl: string | null;
}) {
  const bodyText = content.replace(/#[\w\d]+/g, '').replace(/\n{3,}/g, '\n\n').trim();
  return (
    <div className="border border-outline-variant bg-surface-container-lowest max-w-[560px] mx-auto overflow-hidden shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
      <div className="flex items-start gap-3 px-4 pt-4 pb-2">
        <div className="w-10 h-10 bg-primary text-on-primary flex items-center justify-center flex-shrink-0 font-bold text-sm">Y</div>
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-semibold leading-tight">You</p>
          <p className="text-[11px] text-on-surface-variant leading-tight">Your title here · 1st</p>
          <p className="text-[10px] text-outline mt-0.5">Just now · 🌐</p>
        </div>
        <button className="text-[#0A66C2] text-xs font-bold hover:underline flex-shrink-0">+ Follow</button>
      </div>
      <div className="px-4 pb-3">
        <p className="text-[13px] text-on-surface whitespace-pre-line leading-[1.6]">{bodyText}</p>
        {hashtags.length > 0 && (
          <p className="text-[13px] text-[#0A66C2] mt-2">{hashtags.map((h) => `#${h}`).join(' ')}</p>
        )}
      </div>
      {photoUrl && (
        <div className="w-full bg-surface-container-high">
          <img src={photoUrl} alt="Post attachment" className="w-full max-h-[400px] object-cover" />
        </div>
      )}
      <div className="px-4 py-2 border-t border-outline-variant">
        <div className="flex items-center gap-1 text-[11px] text-on-surface-variant">
          <span className="flex -space-x-0.5 mr-1">
            <span className="w-4 h-4 bg-blue-500 flex items-center justify-center text-[8px]">👍</span>
            <span className="w-4 h-4 bg-red-400 flex items-center justify-center text-[8px]">❤️</span>
          </span>
          <span>Be the first to react</span>
        </div>
      </div>
      <div className="grid grid-cols-4 border-t border-outline-variant">
        {['Like', 'Comment', 'Repost', 'Send'].map((label) => (
          <button key={label} className="py-2.5 text-[11px] font-bold text-on-surface-variant hover:bg-surface-container transition-colors uppercase tracking-widest">
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function PostEditor({
  post,
  kind,
  linkedinApiBase,
  blogApiBase,
  insightsApiBase,
  onUpdated,
  onDeleted,
  showPublish = true,
}: PostEditorProps) {
  const { pushToast } = useToast();
  const [editedContent, setEditedContent] = useState(post.content_markdown);
  const [editedTags, setEditedTags] = useState<string[]>([...post.tags]);
  const [tagInput, setTagInput] = useState('');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('edit');
  const [regenInstructions, setRegenInstructions] = useState('');
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [liStatus, setLiStatus] = useState<LinkedInStatus | null>(null);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reset when post changes
  useEffect(() => {
    setEditedContent(post.content_markdown);
    setEditedTags([...post.tags]);
    setViewMode('edit');
    setError(null);
    setRegenInstructions('');
  }, [post.id]);

  // Fetch LinkedIn status when kind is linkedin
  useEffect(() => {
    if (kind !== 'linkedin' || !showPublish) return;
    fetch('/api/admin/linkedin/status')
      .then((r) => (r.ok ? r.json() : null))
      .then((s: LinkedInStatus | null) => setLiStatus(s))
      .catch(() => {});
  }, [kind, showPublish]);

  useEffect(() => () => { if (photoUrl) URL.revokeObjectURL(photoUrl); }, [photoUrl]);

  function handlePhotoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (photoUrl) URL.revokeObjectURL(photoUrl);
    setPhotoUrl(URL.createObjectURL(file));
  }

  function removePhoto() {
    if (photoUrl) URL.revokeObjectURL(photoUrl);
    setPhotoUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    const url = kind === 'linkedin' ? linkedinApiBase : blogApiBase;
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_instructions: regenInstructions.trim() }),
        signal: AbortSignal.timeout(120_000),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({})) as Record<string, unknown>;
        setError(String(err.detail ?? err.error ?? 'Generation failed. Please try again.'));
        pushToast('Post generation failed.', 'error');
        return;
      }
      const updated: GeneratedPost = await res.json();
      onUpdated(updated);
      setRegenInstructions('');
      pushToast('Post generated successfully.', 'success');
    } catch {
      setError('Network error. Is the backend running?');
      pushToast('Post generation failed due to network error.', 'error');
    }
    finally { setGenerating(false); }
  }

  async function handleSaveEdits() {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`/api/posts/by-id/${post.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_markdown: editedContent, tags: editedTags }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({})) as Record<string, unknown>;
        setError(String(err.detail ?? 'Failed to save edits.'));
        pushToast('Saving post edits failed.', 'error');
        return;
      }
      const updated: GeneratedPost = await res.json();
      onUpdated(updated);
      pushToast('Post edits saved.', 'success');
      // Note: the backend's PATCH handler already records the edited content as a
      // style sample (add_style_sample "post_edit"). We do NOT save it as an insight
      // here — post drafts are not "user perspectives about this topic" and would
      // confuse future generation by making the LLM copy its own previous output.
    } catch {
      setError('Network error.');
      pushToast('Saving post edits failed due to network error.', 'error');
    }
    finally { setSaving(false); }
  }

  async function handlePublish() {
    setPublishing(true);
    setError(null);
    try {
      const res = await fetch(`/api/posts/by-id/${post.id}/publish`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({})) as Record<string, unknown>;
        setError(String(err.detail ?? 'Publish failed. Check your LinkedIn connection.'));
        pushToast('LinkedIn publish failed.', 'error');
        return;
      }
      const result = await res.json() as { post_urn: string };
      onUpdated({ ...post, status: 'published', linkedin_post_urn: result.post_urn });
      pushToast('Post published to LinkedIn.', 'success');
    } catch {
      setError('Network error during publish.');
      pushToast('LinkedIn publish failed due to network error.', 'error');
    }
    finally { setPublishing(false); }
  }

  async function confirmDelete() {
    setDeleting(true);
    setError(null);
    try {
      const res = await fetch(`/api/posts/by-id/${post.id}`, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({})) as Record<string, unknown>;
        setError(String(err.detail ?? 'Failed to delete post.'));
        pushToast('Deleting post failed.', 'error');
        return;
      }
      onDeleted?.(post.id);
      pushToast('Post deleted.', 'success');
    } catch {
      setError('Network error while deleting.');
      pushToast('Deleting post failed due to network error.', 'error');
    } finally {
      setDeleting(false);
      setConfirmDeleteOpen(false);
    }
  }

  function handleCopy() {
    navigator.clipboard.writeText(editedContent).then(() => {
      setCopied(true);
      pushToast('Copied post content.', 'success');
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function handleDownload() {
    const blob = new Blob([editedContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `${kind}-post-${post.slug}.md`; a.click();
    URL.revokeObjectURL(url);
    pushToast('Downloaded markdown file.', 'success');
  }

  function addTag() {
    const t = tagInput.trim().replace(/^#/, '');
    if (t && !editedTags.includes(t)) setEditedTags((prev) => [...prev, t]);
    setTagInput('');
  }

  const isDirty = editedContent !== post.content_markdown || JSON.stringify(editedTags) !== JSON.stringify(post.tags);

  return (
    <div className="flex flex-col gap-5 p-8">
      {error && <p className="text-[11px] text-red-600 border border-red-200 bg-red-50 px-3 py-2 font-mono">{error}</p>}

      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap">
        {isDirty && (
          <button onClick={handleSaveEdits} disabled={saving} className="btn-primary py-1.5 px-4 text-[10px] disabled:opacity-50">
            {saving ? 'Saving…' : 'Save Edits'}
          </button>
        )}
        <button onClick={handleCopy} className="btn-secondary py-1.5 px-3 text-[10px]">
          <Copy size={11} /> {copied ? 'Copied!' : 'Copy'}
        </button>
        <button
          onClick={() => setViewMode((v) => (v === 'edit' ? 'preview' : 'edit'))}
          className={cn('py-1.5 px-3 text-[10px] font-bold uppercase tracking-widest border transition-colors',
            viewMode === 'preview' ? 'bg-primary text-on-primary border-primary' : 'border-outline-variant text-on-surface-variant hover:border-primary')}
        >
          {viewMode === 'preview' ? 'Edit' : 'Preview'}
        </button>
        {kind === 'blog' && (
          <button onClick={handleDownload} className="btn-secondary py-1.5 px-3 text-[10px]">
            <Download size={11} /> Download .md
          </button>
        )}
        {kind === 'linkedin' && post.status === 'published' && (
          <span className="ml-auto label-bold text-[9px] bg-primary text-on-primary px-2 py-1">✓ Published</span>
        )}
        <button
          onClick={() => setConfirmDeleteOpen(true)}
          disabled={deleting}
          className="btn-secondary py-1.5 px-3 text-[10px] border-red-300 text-red-700 hover:bg-red-50 disabled:opacity-50"
          title={`Delete ${kind} post`}
        >
          <Trash2 size={11} /> {deleting ? 'Deleting…' : 'Delete'}
        </button>
      </div>

      {confirmDeleteOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="w-full max-w-sm border border-outline-variant bg-surface-container-lowest p-5 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
            <p className="text-sm font-bold mb-2">Are you sure you want to delete this post?</p>
            <p className="text-xs text-on-surface-variant mb-4">This action cannot be undone.</p>
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setConfirmDeleteOpen(false)}
                disabled={deleting}
                className="btn-secondary py-1.5 px-4 text-[10px] disabled:opacity-50"
              >
                No
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="btn-primary py-1.5 px-4 text-[10px] bg-red-700 hover:bg-red-800 disabled:opacity-50"
              >
                {deleting ? 'Deleting…' : 'Yes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Regen instructions */}
      <div className="flex gap-2 items-start">
        <textarea
          value={regenInstructions}
          onChange={(e) => setRegenInstructions(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); handleGenerate(); } }}
          rows={1}
          placeholder="Describe changes for next generation… (⌘Enter to regenerate)"
          className="flex-1 resize-none border border-outline-variant bg-surface-container-low text-on-surface px-3 py-2 text-xs outline-none focus:border-primary transition-all font-sans placeholder:text-outline"
          style={{ minHeight: '2.25rem', maxHeight: '8rem' }}
          onInput={(e) => { const el = e.currentTarget; el.style.height = 'auto'; el.style.height = `${Math.min(el.scrollHeight, 128)}px`; }}
        />
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="btn-primary py-2 px-3 text-[10px] flex-shrink-0 disabled:opacity-50"
          title="Regenerate (⌘Enter)"
        >
          {generating ? '…' : '↺ Regenerate'}
        </button>
      </div>

      {/* Photo upload */}
      <div className="flex items-center gap-3">
        <input ref={fileInputRef} type="file" accept="image/*" onChange={handlePhotoChange} className="hidden" id={`photo-upload-${post.id}`} />
        <label
          htmlFor={`photo-upload-${post.id}`}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-dashed border-outline-variant text-[10px] font-bold uppercase tracking-widest text-on-surface-variant hover:border-primary hover:text-primary cursor-pointer transition-colors"
        >
          <Image size={12} /> {photoUrl ? 'Change photo' : 'Add photo'}
        </label>
        {photoUrl && (
          <div className="flex items-center gap-2">
            <img src={photoUrl} alt="Preview thumbnail" className="w-8 h-8 object-cover border border-outline-variant" />
            <button onClick={removePhoto} className="text-[10px] text-outline hover:text-red-600 transition-colors"><X size={12} /></button>
          </div>
        )}
      </div>

      {/* Content editor / preview */}
      {viewMode === 'preview' ? (
        kind === 'linkedin' ? (
          <LinkedInPreviewCard content={editedContent} hashtags={editedTags} photoUrl={photoUrl} />
        ) : (
          <div className="border border-outline-variant bg-surface-container-lowest overflow-hidden">
            {photoUrl && <img src={photoUrl} alt="Blog header" className="w-full max-h-[300px] object-cover" />}
            <div className="prose prose-neutral prose-sm max-w-none p-6 max-h-[600px] overflow-y-auto">
              <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{editedContent}</ReactMarkdown>
            </div>
          </div>
        )
      ) : (
        <textarea
          value={editedContent}
          onChange={(e) => setEditedContent(e.target.value)}
          className="w-full resize-y border border-outline-variant bg-surface-container-lowest text-on-surface px-4 py-3 text-sm font-mono leading-relaxed outline-none focus:border-primary focus:border-2 placeholder:text-outline min-h-[300px] max-h-[600px] transition-all"
          placeholder="Generated content will appear here…"
        />
      )}

      {/* Tag editor */}
      <div>
        <p className="label-bold text-[9px] mb-2">{kind === 'linkedin' ? 'Hashtags' : 'Tags'}</p>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {editedTags.map((tag, i) => (
            <span key={i} className="inline-flex items-center gap-1 px-2.5 py-1 border border-outline-variant bg-surface-container-low text-[10px] font-bold uppercase">
              {kind === 'linkedin' ? '#' : ''}{tag}
              <button onClick={() => setEditedTags((prev) => prev.filter((_, j) => j !== i))} className="text-outline hover:text-red-600 ml-0.5">×</button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            value={tagInput}
            onChange={(e) => setTagInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag(); } }}
            placeholder="Add tag…"
            className="text-[11px] border border-outline-variant bg-surface-container-low px-3 py-1.5 w-36 outline-none focus:border-primary transition-all"
          />
          <button onClick={addTag} className="label-bold text-[9px] text-primary hover:text-black">Add</button>
        </div>
      </div>

      {/* LinkedIn connect/publish */}
      {kind === 'linkedin' && showPublish && post.status !== 'published' && (
        <div className="flex items-center gap-3 border-t border-outline-variant pt-4">
          {liStatus?.connected ? (
            <button
              onClick={handlePublish}
              disabled={publishing || isDirty}
              title={isDirty ? 'Save your edits first' : 'Publish to LinkedIn'}
              className="btn-primary py-2.5 px-6 text-[10px] bg-[#0A66C2] hover:bg-[#004182] disabled:opacity-50"
            >
              <Send size={12} />
              {publishing ? 'Publishing…' : 'Publish to LinkedIn'}
            </button>
          ) : null}
          {isDirty && <p className="text-[10px] text-on-surface-variant font-mono">Save edits before publishing.</p>}
        </div>
      )}

      {kind === 'linkedin' && post.status === 'published' && post.linkedin_post_urn && (
        <div className="border border-outline-variant bg-surface-container-low px-4 py-3 text-[11px] font-mono flex items-center gap-2">
          <span className="text-primary font-bold">✓</span>
          Post published to LinkedIn successfully.
        </div>
      )}
    </div>
  );
}
