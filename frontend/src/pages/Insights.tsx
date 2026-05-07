import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { Plus, RotateCcw, Search as SearchIcon, Send } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatMessage, InsightListItem } from '@/types';

type SseEvent =
  | { type: 'user_message'; message: ChatMessage }
  | { type: 'token'; text: string }
  | { type: 'assistant_message'; message: ChatMessage }
  | { type: 'tool_call'; name: string }
  | { type: 'error'; detail: string };

const STREAMING_ID = -9999;

function formatTime(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - d.getTime()) / 86400_000);
  if (diffDays === 0) return `Today ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  if (diffDays === 1) return `Yesterday ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function chatBase(it: InsightListItem) {
  return it.context_kind === 'search'
    ? `/api/chat/runs/${it.run_id}/${it.slug}`
    : `/api/chat/${it.run_date}/${it.slug}`;
}

export default function Insights() {
  const [items, setItems] = useState<InsightListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedInsight, setSelectedInsight] = useState<InsightListItem | null>(null);
  const [resettingKey, setResettingKey] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [sending, setSending] = useState(false);
  const [toolStatus, setToolStatus] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setLoading(true);
    fetch('/api/insights/all')
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: InsightListItem[]) => setItems(rows))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = (() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((it) =>
      it.user_perspective.toLowerCase().includes(q) ||
      it.summary.toLowerCase().includes(q) ||
      it.topic.toLowerCase().includes(q) ||
      it.headline.toLowerCase().includes(q) ||
      it.slug.toLowerCase().includes(q),
    );
  })();

  async function selectInsight(it: InsightListItem) {
    setSelectedInsight(it);
    setLoadingMessages(true);
    setChatError(null);
    try {
      const res = await fetch(`${chatBase(it)}/messages`);
      setMessages(res.ok ? await res.json() as ChatMessage[] : []);
    } catch {
      setMessages([]);
      setChatError('Failed to load chat history.');
    } finally {
      setLoadingMessages(false);
    }
  }

  async function resetChat(it: InsightListItem) {
    const key = `${it.run_id}:${it.slug}`;
    setResettingKey(key);
    try {
      await fetch(`${chatBase(it)}/messages`, { method: 'DELETE' });
    } catch {
      // best-effort
    } finally {
      setResettingKey(null);
      setSelectedInsight(it);
      setMessages([]);
    }
  }

  async function handleSend() {
    if (!selectedInsight || sending) return;
    const content = chatInput.trim();
    if (!content) return;
    setSending(true);
    setChatError(null);
    setToolStatus(null);
    setChatInput('');

    const tempUserMsg: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content,
      citations: [],
      used_web: false,
      created_at: new Date().toISOString(),
    };
    const streamingMsg: ChatMessage = {
      id: STREAMING_ID,
      role: 'assistant',
      content: '',
      citations: [],
      used_web: false,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg, streamingMsg]);

    let streamingContent = '';

    try {
      const res = await fetch(`${chatBase(selectedInsight)}/messages/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
        signal: AbortSignal.timeout(120_000),
      });

      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({})) as Record<string, unknown>;
        setChatError(String(err.detail ?? 'Failed to send message.'));
        setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id && m.id !== STREAMING_ID));
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const rawData = line.slice(6).trim();
          if (rawData === '[DONE]') break;
          let evt: SseEvent;
          try { evt = JSON.parse(rawData) as SseEvent; } catch { continue; }

          if (evt.type === 'user_message') {
            setMessages((prev) => prev.map((m) => m.id === tempUserMsg.id ? evt.message : m));
          } else if (evt.type === 'tool_call') {
            setToolStatus(evt.name === 'web_search' ? 'Searching the web…' : 'Reading page…');
          } else if (evt.type === 'token') {
            streamingContent += evt.text;
            setToolStatus(null);
            setMessages((prev) => prev.map((m) =>
              m.id === STREAMING_ID ? { ...m, content: streamingContent } : m
            ));
          } else if (evt.type === 'assistant_message') {
            setMessages((prev) => prev.map((m) => m.id === STREAMING_ID ? evt.message : m));
            // Refresh insight list so new auto-saved insight appears
            fetch('/api/insights/all')
              .then((r) => (r.ok ? r.json() : []))
              .then((rows: InsightListItem[]) => setItems(rows))
              .catch(() => {});
          } else if (evt.type === 'error') {
            setChatError(evt.detail);
            setMessages((prev) => prev.filter((m) => m.id !== STREAMING_ID));
          }
        }
      }
    } catch {
      setChatError('Network error while sending.');
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id && m.id !== STREAMING_ID));
    } finally {
      setSending(false);
      setToolStatus(null);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex-1 w-full max-w-[1400px] mx-auto px-6 py-8 overflow-y-auto">
      <div className="mb-6 flex flex-col gap-3">
        <h1 className="text-3xl font-black">Insights</h1>
        <p className="text-on-surface-variant text-sm">
          Every meaningful chat message is captured here and used for tone/style + post context.
        </p>
        <div className="relative max-w-xl">
          <SearchIcon size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search insights, topics, trends..."
            className="w-full pl-9 pr-3 py-2 text-sm border border-outline-variant bg-surface-container-lowest outline-none focus:border-primary"
          />
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-2 py-8">
          <span className="w-4 h-4 border-2 border-primary border-t-transparent animate-spin" />
          <span className="label-bold text-[10px] text-outline">Loading insights…</span>
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="border border-outline-variant bg-surface-container-low p-6">
          <p className="text-sm font-bold mb-1">No insights yet</p>
          <p className="text-xs text-on-surface-variant">Open a trend/search and start chatting. Messages are auto-saved as insights.</p>
        </div>
      )}

      {!loading && filtered.length > 0 && (
        <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_1fr] gap-4 min-h-[620px]">
          {/* Left pane — flat list of all insights */}
          <div className="border border-outline-variant bg-surface-container-lowest overflow-y-auto max-h-[75vh]">
            {filtered.map((it) => {
              const key = `${it.run_id}:${it.slug}`;
              const isActive = selectedInsight
                ? it.run_id === selectedInsight.run_id && it.slug === selectedInsight.slug && it.id === selectedInsight.id
                : false;
              const resetting = resettingKey === key;
              const firstLine = it.user_perspective.split('\n')[0].slice(0, 120);

              return (
                <div
                  key={it.id}
                  className={cn(
                    'p-4 border-b border-outline-variant cursor-pointer transition-colors border-l-4',
                    isActive
                      ? 'bg-surface-container-low border-l-primary'
                      : 'border-l-transparent hover:bg-surface-container',
                  )}
                  onClick={() => void selectInsight(it)}
                >
                  {/* Metadata row */}
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="label-bold text-[9px] text-outline">
                      {it.context_kind === 'search' ? 'SEARCH' : 'TREND'} · {it.headline.slice(0, 40)}{it.headline.length > 40 ? '…' : ''}
                    </span>
                    <span className="label-bold text-[9px] text-outline whitespace-nowrap">{formatTime(it.created_at)}</span>
                  </div>
                  {/* First question */}
                  <p className="text-sm leading-snug text-on-surface">
                    "{firstLine}{it.user_perspective.length > 120 ? '…' : ''}"
                  </p>
                  {/* Actions — only shown for active item */}
                  {isActive && (
                    <div className="flex gap-2 mt-3" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => void resetChat(it)}
                        disabled={resetting}
                        className="btn-primary py-1 px-3 text-[9px] disabled:opacity-60"
                      >
                        {resetting ? <RotateCcw size={10} className="animate-spin" /> : <Plus size={10} />}
                        {resetting ? 'Starting…' : 'New Chat'}
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Right pane — conversation */}
          <div className="border border-outline-variant bg-surface-container-lowest flex flex-col min-h-[620px]">
            <div className="p-4 border-b border-outline-variant">
              <p className="label-bold text-[10px]">Conversation</p>
              {selectedInsight ? (
                <>
                  <p className="text-sm font-bold mt-1 line-clamp-2">{selectedInsight.headline}</p>
                  <p className="text-[11px] text-on-surface-variant mt-1">
                    {selectedInsight.context_kind === 'search'
                      ? `Search: ${selectedInsight.topic}`
                      : `Trend · ${selectedInsight.run_date}`}
                  </p>
                </>
              ) : (
                <p className="text-xs text-on-surface-variant mt-1">Click an insight on the left to open its conversation.</p>
              )}
            </div>

            <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
              {loadingMessages && <p className="label-bold text-[10px] text-outline">Loading history…</p>}
              {!loadingMessages && selectedInsight && messages.length === 0 && (
                <p className="text-xs text-on-surface-variant">No prior messages in this chat. Start a new one below.</p>
              )}
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={cn(
                    'max-w-[90%] px-3 py-2 text-sm',
                    m.role === 'user'
                      ? 'self-end bg-primary text-on-primary'
                      : 'self-start bg-surface-container-low border border-outline-variant',
                  )}
                >
                  {m.role === 'assistant' ? (
                    m.id === STREAMING_ID && m.content === '' ? (
                      <div className="flex gap-1 items-center h-4">
                        <span className="w-1.5 h-1.5 bg-on-surface-variant animate-bounce [animation-delay:0ms]" />
                        <span className="w-1.5 h-1.5 bg-on-surface-variant animate-bounce [animation-delay:150ms]" />
                        <span className="w-1.5 h-1.5 bg-on-surface-variant animate-bounce [animation-delay:300ms]" />
                      </div>
                    ) : (
                      <div className="prose prose-sm prose-neutral max-w-none [&>p]:my-1">
                        <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{m.content}</ReactMarkdown>
                      </div>
                    )
                  ) : (
                    <p className="whitespace-pre-wrap">{m.content}</p>
                  )}
                </div>
              ))}
              {toolStatus && (
                <p className="label-bold text-[10px] text-outline text-center animate-pulse">{toolStatus}</p>
              )}
              <div ref={bottomRef} />
            </div>

            <div className="p-4 border-t border-outline-variant">
              {chatError && <p className="text-[11px] text-red-600 mb-2">{chatError}</p>}
              <div className="flex gap-2 items-end">
                <textarea
                  ref={inputRef}
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      void handleSend();
                    }
                  }}
                  disabled={!selectedInsight || sending}
                  rows={2}
                  placeholder={selectedInsight ? 'Continue this chat… (Enter to send)' : 'Select an insight first'}
                  className="flex-1 resize-none border border-outline-variant bg-surface-container-low px-3 py-2 text-sm outline-none focus:border-primary disabled:opacity-60"
                />
                <button
                  onClick={() => void handleSend()}
                  disabled={!selectedInsight || !chatInput.trim() || sending}
                  className="btn-primary py-2 px-3 text-[10px] disabled:opacity-50"
                >
                  <Send size={12} />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
