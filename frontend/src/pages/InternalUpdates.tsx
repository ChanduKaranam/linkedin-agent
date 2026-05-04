import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, RefreshCw, Send } from 'lucide-react';
import { apiGet, apiPost } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { ChatMessage, LinkedInStatus, SlackChatReply, SlackGeneratedPost, SlackHistory, SlackLinkedInPublishResult } from '@/types';
import { useToast } from '@/context/ToastContext';
import { buildLinkedInAuthorizeUrl } from '@/lib/linkedinAuth';

const BACKEND_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;

export default function InternalUpdates() {
  const { pushToast } = useToast();
  const [fetched, setFetched] = useState<SlackHistory['messages']>([]);
  const [activeTs, setActiveTs] = useState<string | null>(null);
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [prompt, setPrompt] = useState('');
  const [postOpen, setPostOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [postKind, setPostKind] = useState<'linkedin' | 'blog'>('linkedin');
  const [generatedDraft, setGeneratedDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [liStatus, setLiStatus] = useState<LinkedInStatus | null>(null);
  const [publishedUrn, setPublishedUrn] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const activeItem = useMemo(
    () => fetched.find((m) => m.ts === activeTs) ?? fetched[0] ?? null,
    [fetched, activeTs],
  );
  const activeDate = useMemo(() => {
    if (!activeItem?.ts) return '';
    const n = Number(activeItem.ts.split('.')[0]) * 1000;
    return Number.isFinite(n) ? new Date(n).toLocaleString() : '';
  }, [activeItem]);
  const keyPoints = useMemo(() => {
    if (!activeItem?.text) return [];
    const chunks = activeItem.text
      .split(/[.\n]/)
      .map((x) => x.trim())
      .filter(Boolean);
    return chunks.slice(0, 4);
  }, [activeItem]);
  const groupedByDate = useMemo(() => {
    const groups = new Map<string, SlackHistory['messages']>();
    for (const item of fetched) {
      const ms = Number(item.ts.split('.')[0]) * 1000;
      const key = Number.isFinite(ms) ? new Date(ms).toLocaleDateString() : 'Unknown Date';
      const existing = groups.get(key) ?? [];
      existing.push(item);
      groups.set(key, existing);
    }
    return Array.from(groups.entries());
  }, [fetched]);

  function tsToNumber(ts: string): number {
    const n = Number(ts);
    return Number.isFinite(n) ? n : 0;
  }

  async function loadChannel() {
    setLoading(true);
    setError(null);
    try {
      const latestKnownTs =
        fetched.length > 0
          ? fetched.reduce((max, item) => (tsToNumber(item.ts) > tsToNumber(max) ? item.ts : max), fetched[0].ts)
          : null;
      const qs = latestKnownTs ? `?limit=60&since_ts=${encodeURIComponent(latestKnownTs)}` : '?limit=60';
      const data = await apiGet<SlackHistory>(`${BACKEND_BASE}/slack/channels/default/messages${qs}`);

      if (latestKnownTs) {
        if (data.messages.length > 0) {
          setFetched((prev) => {
            const seen = new Set(prev.map((m) => m.ts));
            const onlyNew = data.messages.filter((m) => !seen.has(m.ts));
            return [...onlyNew, ...prev];
          });
          pushToast(`Fetched ${data.messages.length} new Slack updates.`, 'success');
        } else {
          pushToast('No new Slack updates found.', 'info');
        }
      } else {
        setFetched(data.messages);
        setActiveTs(data.messages[0]?.ts ?? null);
        pushToast(`Fetched ${data.messages.length} Slack updates.`, 'success');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch Slack channel data from default channel.');
      pushToast('Slack data fetch failed.', 'error');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadChannel();
  }, []);

  useEffect(() => {
    setChat([]);
    setGeneratedDraft('');
    setPrompt('');
    setPublishedUrn(null);
  }, [activeTs]);

  useEffect(() => {
    fetch('/api/admin/linkedin/status')
      .then((r) => (r.ok ? r.json() : null))
      .then((s: LinkedInStatus | null) => setLiStatus(s))
      .catch(() => {});
  }, []);

  async function onAsk() {
    if (!prompt.trim() || !activeItem) return;
    const question = prompt.trim();
    const userMsg: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: question,
      citations: [],
      used_web: false,
      created_at: new Date().toISOString(),
    };
    setChat((prev) => [...prev, userMsg]);
    setPrompt('');
    setLoading(true);
    setError(null);
    try {
      const res = await apiPost<SlackChatReply>(`${BACKEND_BASE}/slack/chat`, {
        channel_id: '',
        selected_message: activeItem?.text ?? '',
        content: question,
        history: chat.slice(-20),
      });
      const asstMsg: ChatMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: res.reply,
        citations: [],
        used_web: false,
        created_at: new Date().toISOString(),
      };
      setChat((prev) => [...prev, asstMsg]);
      pushToast('Assistant response received.', 'success');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to chat with assistant.');
      pushToast('Failed to get assistant response.', 'error');
    } finally {
      setLoading(false);
    }
  }

  async function generatePost(kind: 'linkedin' | 'blog') {
    if (!activeItem) return;
    setGenerating(true);
    setError(null);
    setPostKind(kind);
    setPublishedUrn(null);
    try {
      const latestUserQuestion = [...chat].reverse().find((m) => m.role === 'user')?.content ?? '';
      const res = await apiPost<SlackGeneratedPost>(`${BACKEND_BASE}/slack/generate/${kind}`, {
        channel_id: '',
        selected_message: activeItem?.text ?? '',
        user_instructions: latestUserQuestion,
      });
      setGeneratedDraft(res.content_markdown);
      pushToast(`${kind === 'linkedin' ? 'LinkedIn' : 'Blog'} draft generated.`, 'success');
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to generate ${kind} post.`);
      pushToast(`Failed to generate ${kind} draft.`, 'error');
    } finally {
      setGenerating(false);
    }
  }

  async function handlePublishLinkedIn() {
    if (!generatedDraft.trim()) return;
    setPublishing(true);
    setError(null);
    try {
      const out = await apiPost<SlackLinkedInPublishResult>(`${BACKEND_BASE}/slack/publish/linkedin`, {
        content: generatedDraft,
      });
      setPublishedUrn(out.post_urn);
      pushToast('Post published to LinkedIn.', 'success');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Publish failed. Check LinkedIn connection.');
      pushToast('LinkedIn publish failed.', 'error');
    } finally {
      setPublishing(false);
    }
  }

  return (
    <div className="flex-1 min-h-0 flex overflow-hidden border-l border-r border-outline-variant">
      <aside className="w-[320px] min-w-[320px] min-h-0 border-r border-outline-variant bg-surface-container-lowest flex flex-col">
        <div className="px-5 py-3 border-b border-outline-variant bg-surface-container-low">
          <h2 className="label-bold text-primary mb-3">Fetched Slack Data</h2>
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className="text-xs text-on-surface-variant">
              {fetched.length} update{fetched.length !== 1 ? 's' : ''} · mentions only
            </span>
            <button onClick={loadChannel} disabled={loading} className="btn-secondary h-8 px-3 text-[10px]">
              <RefreshCw size={12} />
              Fetch
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto overscroll-contain">
          {fetched.length === 0 ? (
            <p className="p-4 text-xs text-on-surface-variant">Load a channel to view fetched messages.</p>
          ) : (
            groupedByDate.map(([dateKey, items]) => (
              <div key={dateKey}>
                <div className="sticky top-0 z-10 px-4 py-2 bg-surface-container-low border-y border-outline-variant">
                  <p className="label-bold text-[9px] text-on-surface-variant uppercase">{dateKey}</p>
                </div>
                {items.map((item, i) => (
                  <button
                    key={item.ts}
                    onClick={() => setActiveTs(item.ts)}
                    className={cn(
                      'w-full text-left p-4 border-b border-outline-variant transition-colors border-l-2',
                      activeItem?.ts === item.ts && 'bg-surface-container-highest border-l-4 border-l-primary',
                      activeItem?.ts !== item.ts && 'hover:bg-surface-container-low border-l-transparent',
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <span
                        className={cn(
                          'flex-shrink-0 mt-0.5 w-5 h-5 flex items-center justify-center text-[10px] font-black border',
                          activeItem?.ts === item.ts ? 'bg-primary text-on-primary border-primary' : 'bg-surface-container-high border-outline-variant text-on-surface-variant',
                        )}
                      >
                        {i + 1}
                      </span>
                      <div className="min-w-0">
                        <p className="label-bold text-[9px] text-primary mb-1">{item.user}</p>
                        <p className="text-xs line-clamp-3 leading-snug">{item.text}</p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            ))
          )}
        </div>
      </aside>

      <section className="flex-1 min-h-0 bg-background overflow-y-auto overscroll-contain">
        {activeItem ? (
          <article className="px-8 py-8">
            <div className="max-w-3xl">
              <p className="label-bold text-[10px] mb-4">
                {activeDate || 'Latest update'} · Default Slack channel
              </p>
              <h1 className="text-3xl font-black leading-tight mb-3">
                Slack App Mention by {activeItem.user}
              </h1>
              <p className="text-base text-on-surface-variant leading-relaxed mb-8">
                Selected message from the channel feed. Use Discuss This Topic to ask the LLM about this update.
              </p>

              <div className="bg-surface-container-low border border-outline-variant p-6 mb-8">
                <h2 className="label-bold mb-4">Key Takeaways</h2>
                <ul className="flex flex-col gap-3">
                  {(keyPoints.length > 0 ? keyPoints : ['No key points extracted yet.']).map((point, i) => (
                    <li key={i} className="flex items-start gap-3 text-sm text-on-surface leading-snug">
                      <span className="flex-shrink-0 mt-0.5 w-5 h-5 bg-primary text-on-primary flex items-center justify-center text-[10px] font-black">
                        {i + 1}
                      </span>
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="border-t border-outline-variant pt-6 mb-8">
                <h2 className="label-bold mb-3">Message Content</h2>
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{activeItem.text}</p>
              </div>

              <div className="border-t border-outline-variant pt-2">
                <button
                  onClick={() => setChatOpen((v) => !v)}
                  className="w-full flex items-center justify-between px-2 py-4 text-left hover:bg-surface-container transition-colors"
                >
                  <div>
                    <p className="text-sm font-bold uppercase tracking-tight">Discuss This Topic</p>
                    <p className="label-bold text-[9px] text-outline mt-0.5">
                      Ask questions, share perspective
                    </p>
                  </div>
                  <ChevronDown size={14} className={cn('text-on-surface-variant transition-transform', chatOpen && 'rotate-180')} />
                </button>
                {chatOpen && (
                  <div className="px-2 pb-6 flex flex-col gap-4">
                    <div className="flex flex-col gap-3 max-h-80 overflow-y-auto pr-1">
                      {chat.length === 0 && (
                        <p className="label-bold text-[10px] text-outline text-center py-4">
                          Start chatting about this selected update.
                        </p>
                      )}
                      {chat.map((m) => (
                        <div
                          key={m.id}
                          className={cn(
                            'max-w-[85%] p-4 text-sm leading-relaxed border',
                            m.role === 'user'
                              ? 'self-end bg-primary text-on-primary border-primary'
                              : 'self-start bg-surface-container-lowest border-outline-variant',
                          )}
                        >
                          {m.content}
                        </div>
                      ))}
                    </div>

                    {error && <p className="text-[11px] text-red-600 border border-red-200 bg-red-50 px-3 py-2 font-mono">{error}</p>}

                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        void onAsk();
                      }}
                      className="flex gap-2 items-end"
                    >
                      <textarea
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        className="flex-1 resize-none border border-outline-variant bg-surface-container-low text-on-surface px-4 py-2.5 text-sm outline-none focus:border-primary focus:border-2 disabled:opacity-50 transition-all"
                        placeholder="Ask about this update… (Enter to send)"
                        rows={2}
                        disabled={loading}
                        onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void onAsk(); } }}
                      />
                      <button
                        type="submit"
                        disabled={!prompt.trim() || loading}
                        className="flex-shrink-0 w-10 h-10 bg-primary text-on-primary flex items-center justify-center hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                      >
                        <Send size={14} />
                      </button>
                    </form>
                  </div>
                )}
              </div>

              <div className="border-t border-outline-variant">
                <button
                  onClick={() => setPostOpen((v) => !v)}
                  className="w-full flex items-center justify-between px-2 py-4 text-left hover:bg-surface-container transition-colors"
                >
                  <div>
                    <p className="text-sm font-bold uppercase tracking-tight">Post Studio</p>
                    <p className="label-bold text-[9px] text-outline mt-0.5">
                      Generate LinkedIn post or blog in your voice
                    </p>
                  </div>
                  <ChevronDown size={14} className={cn('text-on-surface-variant transition-transform', postOpen && 'rotate-180')} />
                </button>
                {postOpen && (
                  <div className="px-2 pb-6 flex flex-col gap-4">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => generatePost('linkedin')}
                        disabled={generating}
                        className={cn('px-4 py-2 text-[10px] font-bold uppercase tracking-widest border-b-2 transition-colors', postKind === 'linkedin' ? 'border-primary text-primary' : 'border-transparent text-on-surface-variant')}
                      >
                        LinkedIn Post
                      </button>
                      <button
                        onClick={() => generatePost('blog')}
                        disabled={generating}
                        className={cn('px-4 py-2 text-[10px] font-bold uppercase tracking-widest border-b-2 transition-colors', postKind === 'blog' ? 'border-primary text-primary' : 'border-transparent text-on-surface-variant')}
                      >
                        Blog Post
                      </button>
                      <span className="text-[10px] text-on-surface-variant">
                        {generating ? 'Generating...' : generatedDraft ? 'Draft ready' : ''}
                      </span>
                    </div>

                    {!generatedDraft ? (
                      <div className="flex flex-col items-center gap-4 py-8 px-6 text-center border border-outline-variant bg-surface-container-low">
                        <p className="text-sm text-on-surface-variant max-w-sm">
                          Generate a draft based on the selected update and your conversation.
                        </p>
                        <button
                          onClick={() => generatePost(postKind)}
                          disabled={generating}
                          className="btn-primary py-2 px-6 text-[10px] disabled:opacity-50"
                        >
                          {generating ? 'Generating…' : `Generate ${postKind === 'linkedin' ? 'LinkedIn Post' : 'Blog Post'}`}
                        </button>
                      </div>
                    ) : (
                      <textarea
                        value={generatedDraft}
                        onChange={(e) => {
                          setGeneratedDraft(e.target.value);
                          setPublishedUrn(null);
                        }}
                        className="w-full min-h-[180px] bg-white border border-outline-variant p-3 text-xs font-mono outline-none focus:border-primary focus:border-2"
                      />
                    )}

                    {postKind === 'linkedin' && generatedDraft.trim() && !publishedUrn && (
                      <div className="flex items-center gap-3 border-t border-outline-variant pt-4">
                        {liStatus?.connected ? (
                          <button
                            onClick={handlePublishLinkedIn}
                            disabled={publishing}
                            className="btn-primary py-2.5 px-6 text-[10px] bg-[#0A66C2] hover:bg-[#004182] disabled:opacity-50"
                          >
                            <Send size={12} />
                            {publishing ? 'Publishing…' : 'Publish to LinkedIn'}
                          </button>
                        ) : (
                          <a
                            href={buildLinkedInAuthorizeUrl()}
                            className="btn-secondary py-2.5 px-6 text-[10px] border-[#0A66C2] text-[#0A66C2] hover:bg-blue-50"
                          >
                            Connect LinkedIn Account
                          </a>
                        )}
                      </div>
                    )}

                    {postKind === 'linkedin' && publishedUrn && (
                      <div className="border border-outline-variant bg-surface-container-low px-4 py-3 text-[11px] font-mono flex items-center gap-2">
                        <span className="text-primary font-bold">✓</span>
                        Post published to LinkedIn successfully.
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </article>
        ) : (
          <div className="flex items-center justify-center h-full">
            <p className="label-bold text-outline">Select an update to read the full brief</p>
          </div>
        )}
      </section>
    </div>
  );
}
