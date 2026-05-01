"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import type { GeneratedPost, LinkedInStatus } from "@/types";

interface PostStudioProps {
  postsApiBase: string;
  linkedinApiBase: string;
  blogApiBase: string;
}

type Tab = "linkedin" | "blog";
type ViewMode = "edit" | "preview";

// LinkedIn post preview card
function LinkedInPreviewCard({
  content,
  hashtags,
  photoUrl,
}: {
  content: string;
  hashtags: string[];
  photoUrl: string | null;
}) {
  // Strip hashtags from content body if they appear at the end
  const bodyText = content
    .replace(/#[\w\d]+/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden bg-white shadow-sm max-w-[560px] mx-auto font-sans">
      {/* Header */}
      <div className="flex items-start gap-3 px-4 pt-4 pb-2">
        <div className="w-11 h-11 rounded-full bg-gradient-to-br from-violet-400 to-blue-500 flex items-center justify-center flex-shrink-0 text-white font-bold text-base">
          Y
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-semibold text-slate-900 leading-tight">You</p>
          <p className="text-[11px] text-slate-500 leading-tight">Your title here · 1st</p>
          <div className="flex items-center gap-1 mt-0.5">
            <span className="text-[10px] text-slate-400">Just now ·</span>
            <svg className="w-3 h-3 text-slate-400" fill="currentColor" viewBox="0 0 16 16">
              <path d="M8 0a8 8 0 100 16A8 8 0 008 0zM4.5 7.5a.5.5 0 010-1h5.793L8.146 4.354a.5.5 0 11.708-.708l3 3a.5.5 0 010 .708l-3 3a.5.5 0 11-.708-.708L10.293 7.5H4.5z"/>
            </svg>
          </div>
        </div>
        <button className="text-[#0A66C2] text-xs font-semibold hover:underline flex-shrink-0">+ Follow</button>
      </div>

      {/* Post body */}
      <div className="px-4 pb-3">
        <p className="text-[13px] text-slate-800 whitespace-pre-line leading-[1.6]">{bodyText}</p>
        {hashtags.length > 0 && (
          <p className="text-[13px] text-[#0A66C2] mt-2 leading-relaxed">
            {hashtags.map((h) => `#${h}`).join(" ")}
          </p>
        )}
      </div>

      {/* Post image */}
      {photoUrl && (
        <div className="w-full bg-slate-100">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={photoUrl} alt="Post attachment" className="w-full max-h-[400px] object-cover" />
        </div>
      )}

      {/* Engagement bar */}
      <div className="px-4 py-1 border-t border-slate-100">
        <div className="flex items-center gap-0.5 text-[11px] text-slate-500 py-1">
          <span className="flex -space-x-0.5 mr-1">
            <span className="w-4 h-4 rounded-full bg-blue-500 flex items-center justify-center text-[8px]">👍</span>
            <span className="w-4 h-4 rounded-full bg-red-500 flex items-center justify-center text-[8px]">❤️</span>
          </span>
          <span>Be the first to react</span>
        </div>
      </div>
      <div className="grid grid-cols-4 border-t border-slate-100">
        {[
          { icon: "👍", label: "Like" },
          { icon: "💬", label: "Comment" },
          { icon: "🔁", label: "Repost" },
          { icon: "📤", label: "Send" },
        ].map(({ icon, label }) => (
          <button
            key={label}
            className="flex items-center justify-center gap-1.5 py-2.5 text-[11px] font-semibold text-slate-500 hover:bg-slate-50 transition-colors"
          >
            <span>{icon}</span> {label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function PostStudio({ postsApiBase, linkedinApiBase, blogApiBase }: PostStudioProps) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("linkedin");
  const [linkedinPost, setLinkedinPost] = useState<GeneratedPost | null>(null);
  const [blogPost, setBlogPost] = useState<GeneratedPost | null>(null);
  const [liStatus, setLiStatus] = useState<LinkedInStatus | null>(null);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [editedContent, setEditedContent] = useState("");
  const [editedTags, setEditedTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("edit");
  const [regenInstructions, setRegenInstructions] = useState("");

  // Photo upload
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const currentPost = tab === "linkedin" ? linkedinPost : blogPost;

  // Parse hashtags from LinkedIn post content
  const parsedHashtags = editedTags;

  useEffect(() => {
    if (!open) return;

    fetch(postsApiBase)
      .then((r) => (r.ok ? r.json() : []))
      .then((posts: GeneratedPost[]) => {
        const li = posts.find((p) => p.kind === "linkedin");
        const blog = posts.find((p) => p.kind === "blog");
        if (li) setLinkedinPost(li);
        if (blog) setBlogPost(blog);
      })
      .catch(() => {});

    fetch("/api/admin/linkedin/status")
      .then((r) => (r.ok ? r.json() : null))
      .then((s: LinkedInStatus | null) => setLiStatus(s))
      .catch(() => {});
  }, [open, postsApiBase]);

  useEffect(() => {
    if (currentPost) {
      setEditedContent(currentPost.content_markdown);
      setEditedTags([...currentPost.tags]);
    } else {
      setEditedContent("");
      setEditedTags([]);
    }
    setViewMode("edit");
    setError(null);
  }, [currentPost?.id, tab]);

  // Clean up object URL on unmount or photo change
  useEffect(() => {
    return () => {
      if (photoUrl) URL.revokeObjectURL(photoUrl);
    };
  }, [photoUrl]);

  function handlePhotoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (photoUrl) URL.revokeObjectURL(photoUrl);
    setPhotoUrl(URL.createObjectURL(file));
  }

  function removePhoto() {
    if (photoUrl) URL.revokeObjectURL(photoUrl);
    setPhotoUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    const url = tab === "linkedin" ? linkedinApiBase : blogApiBase;
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_instructions: regenInstructions.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || err.error || "Generation failed. Please try again.");
        return;
      }
      const post: GeneratedPost = await res.json();
      if (tab === "linkedin") setLinkedinPost(post);
      else setBlogPost(post);
      setRegenInstructions("");
    } catch {
      setError("Network error. Is the backend running?");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSaveEdits() {
    if (!currentPost) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`/api/posts/by-id/${currentPost.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content_markdown: editedContent, tags: editedTags }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || "Failed to save edits.");
        return;
      }
      const updated: GeneratedPost = await res.json();
      if (tab === "linkedin") setLinkedinPost(updated);
      else setBlogPost(updated);
    } catch {
      setError("Network error.");
    } finally {
      setSaving(false);
    }
  }

  async function handlePublish() {
    if (!linkedinPost) return;
    setPublishing(true);
    setError(null);
    try {
      const res = await fetch(`/api/posts/by-id/${linkedinPost.id}/publish`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || "Publish failed. Check your LinkedIn connection.");
        return;
      }
      const result = await res.json();
      setLinkedinPost((prev) =>
        prev ? { ...prev, status: "published", linkedin_post_urn: result.post_urn } : prev
      );
    } catch {
      setError("Network error during publish.");
    } finally {
      setPublishing(false);
    }
  }

  function handleCopy() {
    if (!currentPost) return;
    navigator.clipboard.writeText(editedContent).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function handleDownload() {
    if (!currentPost) return;
    const blob = new Blob([editedContent], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `blog-post-${currentPost.slug}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function addTag() {
    const t = tagInput.trim().replace(/^#/, "");
    if (t && !editedTags.includes(t)) {
      setEditedTags((prev) => [...prev, t]);
    }
    setTagInput("");
  }

  const isDirty = currentPost
    ? editedContent !== currentPost.content_markdown ||
      JSON.stringify(editedTags) !== JSON.stringify(currentPost.tags)
    : false;

  return (
    <div className="border-t border-slate-100 mt-2">
      {/* Toggle header */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-8 py-4 text-left hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <span className="w-7 h-7 rounded-lg bg-violet-100 flex items-center justify-center flex-shrink-0">
            <svg
              className="w-3.5 h-3.5 text-violet-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536M9 11l6-6 3 3-6 6H9v-3z" />
            </svg>
          </span>
          <div>
            <p className="text-sm font-semibold text-slate-800">Post Studio</p>
            <p className="text-[11px] text-slate-400">Generate LinkedIn post or blog in your voice</p>
          </div>
        </div>
        <svg
          className={`w-4 h-4 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="px-8 pb-8 flex flex-col gap-4">
          {/* Tab bar */}
          <div className="flex gap-1 border-b border-slate-100">
            {(["linkedin", "blog"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-2 text-xs font-semibold rounded-t-lg transition-colors capitalize ${
                  tab === t
                    ? "bg-white border border-b-white border-slate-200 text-violet-700 -mb-px"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {t === "linkedin" ? "LinkedIn Post" : "Blog Post"}
                {t === "linkedin" && linkedinPost?.status === "published" && (
                  <span className="ml-1.5 text-[9px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full font-bold uppercase">
                    Published
                  </span>
                )}
              </button>
            ))}
          </div>

          {error && (
            <p className="text-xs text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          {/* No post yet */}
          {!currentPost ? (
            <div className="flex flex-col items-center gap-3 py-6 text-center">
              <p className="text-sm text-slate-400">
                {tab === "linkedin"
                  ? "Generate a LinkedIn post based on this trend and your conversation."
                  : "Generate a blog post based on this trend and your conversation."}
              </p>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-violet-600 text-white text-sm font-semibold hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {generating ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                      />
                    </svg>
                    Generating…
                  </>
                ) : (
                  <>
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Generate {tab === "linkedin" ? "LinkedIn Post" : "Blog Post"}
                  </>
                )}
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {/* Toolbar */}
              <div className="flex items-center gap-2 flex-wrap">
                {isDirty && (
                  <button
                    onClick={handleSaveEdits}
                    disabled={saving}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 text-white text-xs font-semibold hover:bg-violet-700 disabled:opacity-50 transition-colors"
                  >
                    {saving ? "Saving…" : "Save Edits"}
                  </button>
                )}

                <button
                  onClick={handleCopy}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  {copied ? "Copied!" : "Copy"}
                </button>

                {/* Preview toggle — both tabs */}
                <button
                  onClick={() => setViewMode((v) => (v === "edit" ? "preview" : "edit"))}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-colors ${
                    viewMode === "preview"
                      ? "bg-slate-800 border-slate-800 text-white"
                      : "border-slate-200 text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {viewMode === "preview" ? (
                    <>
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                      Edit
                    </>
                  ) : (
                    <>
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                      Preview
                    </>
                  )}
                </button>

                {tab === "blog" && (
                  <button
                    onClick={handleDownload}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
                  >
                    Download .md
                  </button>
                )}

                {tab === "linkedin" && currentPost.status === "published" && (
                  <span className="ml-auto inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-green-100 text-green-700 text-[10px] font-bold uppercase">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                    Published
                  </span>
                )}
              </div>

              {/* Regeneration instructions */}
              <div className="flex gap-2 items-start">
                <textarea
                  value={regenInstructions}
                  onChange={(e) => setRegenInstructions(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                      e.preventDefault();
                      handleGenerate();
                    }
                  }}
                  rows={1}
                  placeholder="Describe changes for next generation… (optional)"
                  className="flex-1 resize-none border border-slate-200 bg-slate-50 text-slate-800 rounded-lg px-3 py-2 text-xs leading-relaxed focus:outline-none focus:ring-2 focus:ring-violet-300 placeholder:text-slate-400 overflow-hidden"
                  style={{ minHeight: "2.25rem", maxHeight: "8rem" }}
                  onInput={(e) => {
                    const el = e.currentTarget;
                    el.style.height = "auto";
                    el.style.height = `${Math.min(el.scrollHeight, 128)}px`;
                  }}
                />
                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  title="Regenerate with these instructions (⌘Enter)"
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-violet-600 text-white text-xs font-semibold hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
                >
                  {generating ? (
                    <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  ) : (
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  )}
                  {generating ? "Generating…" : "Regenerate"}
                </button>
              </div>

              {/* Photo upload row */}
              <div className="flex items-center gap-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handlePhotoChange}
                  className="hidden"
                  id="post-photo-upload"
                />
                <label
                  htmlFor="post-photo-upload"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-dashed border-slate-300 text-xs font-semibold text-slate-500 hover:bg-slate-50 hover:border-violet-300 hover:text-violet-600 cursor-pointer transition-colors"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  {photoUrl ? "Change photo" : "Add photo"}
                </label>
                {photoUrl && (
                  <div className="flex items-center gap-2">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={photoUrl} alt="Preview thumbnail" className="w-8 h-8 rounded object-cover border border-slate-200" />
                    <button
                      onClick={removePhoto}
                      className="text-[10px] text-slate-400 hover:text-red-500 transition-colors"
                    >
                      Remove
                    </button>
                  </div>
                )}
              </div>

              {/* Content editor / preview */}
              {viewMode === "preview" ? (
                tab === "linkedin" ? (
                  <LinkedInPreviewCard
                    content={editedContent}
                    hashtags={parsedHashtags}
                    photoUrl={photoUrl}
                  />
                ) : (
                  <div className="border border-slate-100 rounded-xl overflow-hidden bg-white">
                    {photoUrl && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={photoUrl}
                        alt="Blog header"
                        className="w-full max-h-[300px] object-cover"
                      />
                    )}
                    <div className="prose prose-slate prose-sm max-w-none p-6 max-h-[600px] overflow-y-auto">
                      <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{editedContent}</ReactMarkdown>
                    </div>
                  </div>
                )
              ) : (
                <textarea
                  value={editedContent}
                  onChange={(e) => setEditedContent(e.target.value)}
                  className="w-full resize-y border border-slate-200 bg-white text-slate-900 rounded-xl px-4 py-3 text-sm font-mono leading-relaxed focus:outline-none focus:ring-2 focus:ring-violet-300 placeholder:text-slate-400 min-h-[200px] max-h-[500px]"
                  placeholder="Generated content will appear here…"
                />
              )}

              {/* Tag editor */}
              <div>
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest mb-2">
                  {tab === "linkedin" ? "Hashtags" : "Tags"}
                </p>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {editedTags.map((tag, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-violet-50 border border-violet-100 text-violet-700 text-xs font-medium"
                    >
                      {tab === "linkedin" ? "#" : ""}
                      {tag}
                      <button
                        onClick={() => setEditedTags((prev) => prev.filter((_, j) => j !== i))}
                        className="text-violet-400 hover:text-violet-700 ml-0.5"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === ",") {
                        e.preventDefault();
                        addTag();
                      }
                    }}
                    placeholder="Add tag…"
                    className="text-xs border border-slate-200 bg-white text-slate-900 rounded-lg px-3 py-1.5 w-40 focus:outline-none focus:ring-2 focus:ring-violet-300"
                  />
                  <button
                    onClick={addTag}
                    className="text-[10px] font-semibold text-violet-600 hover:text-violet-800"
                  >
                    Add
                  </button>
                </div>
              </div>

              {/* LinkedIn-specific: connect + publish */}
              {tab === "linkedin" && currentPost.status !== "published" && (
                <div className="flex items-center gap-3 border-t border-slate-100 pt-4">
                  {liStatus?.connected ? (
                    <button
                      onClick={handlePublish}
                      disabled={publishing || isDirty}
                      className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#0A66C2] text-white text-sm font-semibold hover:bg-[#004182] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      title={isDirty ? "Save your edits first" : "Publish to LinkedIn"}
                    >
                      {publishing ? (
                        "Publishing…"
                      ) : (
                        <>
                          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M20.447 20.452H16.89v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a1.974 1.974 0 01-1.97-1.977 1.974 1.974 0 011.97-1.977 1.974 1.974 0 011.97 1.977 1.974 1.974 0 01-1.97 1.977zm1.959 13.019H3.374V9h3.922v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                          </svg>
                          Publish to LinkedIn
                        </>
                      )}
                    </button>
                  ) : (
                    <a
                      href="/api/admin/linkedin/authorize"
                      className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border-2 border-[#0A66C2] text-[#0A66C2] text-sm font-semibold hover:bg-blue-50 transition-colors"
                    >
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M20.447 20.452H16.89v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a1.974 1.974 0 01-1.97-1.977 1.974 1.974 0 011.97-1.977 1.974 1.974 0 011.97 1.977 1.974 1.974 0 01-1.97 1.977zm1.959 13.019H3.374V9h3.922v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                      </svg>
                      Connect LinkedIn
                    </a>
                  )}
                  {isDirty && (
                    <p className="text-[10px] text-amber-600">Save your edits before publishing.</p>
                  )}
                </div>
              )}

              {/* Published confirmation */}
              {tab === "linkedin" &&
                currentPost.status === "published" &&
                currentPost.linkedin_post_urn && (
                  <div className="border border-green-100 bg-green-50 rounded-xl px-4 py-3 text-xs text-green-800 flex items-center gap-2">
                    <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                    Post published to LinkedIn successfully.
                  </div>
                )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
