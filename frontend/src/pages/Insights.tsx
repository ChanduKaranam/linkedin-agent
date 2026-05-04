import { useEffect, useMemo, useRef, useState } from 'react';
import { MessageSquare, Plus, RotateCcw, Search as SearchIcon, Send } from 'lucide-react';
import type { ChatMessage, InsightListItem } from '@/types';

export default function Insights() {
  const [items, setItems] = useState<InsightListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [resettingKey, setResettingKey] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLoading(true);
    fetch('/api/insights/all')
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: InsightListItem[]) => setItems(rows))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((it) =>
      it.user_perspective.toLowerCase().includes(q) ||
      it.summary.toLowerCase().includes(q) ||
      it.topic.toLowerCase().includes(q) ||
      it.headline.toLowerCase().includes(q) ||
      it.slug.toLowerCase().includes(q),
    );
  }, [items, query]);

  const selected = useMemo(() => {
    if (!selectedKey) return filtered[0] ?? null;
    return filtered.find((it) => `${it.run_id}:${it.slug}` === selectedKey) ?? filtered[0] ?? null;
  }, [filtered, selectedKey]);

  function chatBase(it: InsightListItem) {
    return it.context_kind === 'search'
      ? `/api/chat/runs/${it.run_id}/${it.slug}`
      : `/api/chat/${it.run_date}/${it.slug}`;
  }

  async function loadMessages(it: InsightListItem | null) {
    if (!it) {
      setMessages([]);
      return;
    }
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

  async function resetAndStay(it: InsightListItem) {
    const key = `${it.run_id}:${it.slug}`;
    setResettingKey(key);
    try {
      await fetch(`${chatBase(it)}/messages`, { method: 'DELETE' });
    } catch {
      // best-effort reset
    } finally {
      setResettingKey(null);
      setSelectedKey(key);
      setMessages([]);
    }
  }

  async function continueChat(it: InsightListItem) {
    setSelectedKey(`${it.run_id}:${it.slug}`);
    await loadMessages(it);
  }

  async function handleSend() {
    if (!selected || sending) return;
    const content = chatInput.trim();
    if (!content) return;
    setSending(true);
    setChatError(null);
    setChatInput('');
    try {
      const res = await fetch(`${chatBase(selected)}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({})) as Record<string, unknown>;
        setChatError(String(err.detail ?? 'Failed to send message.'));
        return;
      }
      const data = await res.json() as { user_message: ChatMessage; assistant_message: ChatMessage };
      setMessages((prev) => [...prev, data.user_message, data.assistant_message]);
      // Refresh insight cards so new auto-saved insight appears.
      setLoading(true);
      fetch('/api/insights/all')
        .then((r) => (r.ok ? r.json() : []))
        .then((rows: InsightListItem[]) => setItems(rows))
        .catch(() => {})
        .finally(() => setLoading(false));
    } catch {
      setChatError('Network error while sending.');
    } finally {
      setSending(false);
    }
  }

  useEffect(() => {
    if (!selected) return;
    void loadMessages(selected);
  }, [selected?.run_id, selected?.slug]);

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
          <div className="border border-outline-variant bg-surface-container-lowest overflow-y-auto max-h-[70vh]">
            {filtered.map((it) => {
              const key = `${it.run_id}:${it.slug}`;
              const resetting = resettingKey === key;
              const active = selected ? `${selected.run_id}:${selected.slug}` === key : false;
              return (
                <div key={it.id} className={`p-4 border-b border-outline-variant ${active ? 'bg-surface-container-low' : ''}`}>
                  <div className="flex items-center justify-between gap-3 mb-2">
                    <span className="label-bold text-[9px] text-outline">
                      {it.context_kind === 'search' ? 'SEARCH' : 'TREND'} · {it.run_date}
                    </span>
                    <span className="label-bold text-[9px] text-outline">{new Date(it.created_at).toLocaleDateString()}</span>
                  </div>
                  <p className="text-sm font-bold leading-snug mb-1 line-clamp-2">{it.headline}</p>
                  <p className="text-[11px] text-on-surface-variant mb-3 line-clamp-1">
                    {it.context_kind === 'search' ? `Topic: ${it.topic}` : `Slug: ${it.slug}`}
                  </p>
                  <p className="text-sm leading-relaxed mb-2 line-clamp-3">"{it.user_perspective}"</p>
                  {it.summary && <p className="text-xs text-on-surface-variant mb-3 line-clamp-2">{it.summary}</p>}
                  <div className="flex gap-2">
                    <button onClick={() => void continueChat(it)} className="btn-secondary py-1.5 px-3 text-[10px]">
                      <MessageSquare size={11} /> Continue Chat
                    </button>
                    <button
                      onClick={() => void resetAndStay(it)}
                      disabled={resetting}
                      className="btn-primary py-1.5 px-3 text-[10px] disabled:opacity-60"
                    >
                      {resetting ? <RotateCcw size={11} className="animate-spin" /> : <Plus size={11} />}
                      {resetting ? 'Starting…' : 'New Chat'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="border border-outline-variant bg-surface-container-lowest flex flex-col min-h-[620px]">
            <div className="p-4 border-b border-outline-variant">
              <p className="label-bold text-[10px]">Conversation</p>
              {selected ? (
                <>
                  <p className="text-sm font-bold mt-1 line-clamp-2">{selected.headline}</p>
                  <p className="text-[11px] text-on-surface-variant mt-1">
                    {selected.context_kind === 'search' ? `Search topic: ${selected.topic}` : `Trend: ${selected.slug}`}
                  </p>
                </>
              ) : (
                <p className="text-xs text-on-surface-variant mt-1">Pick an insight to open or continue chat.</p>
              )}
            </div>

            <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
              {loadingMessages && <p className="label-bold text-[10px] text-outline">Loading history…</p>}
              {!loadingMessages && selected && messages.length === 0 && (
                <p className="text-xs text-on-surface-variant">No prior messages in this chat. Start a new one below.</p>
              )}
              {messages.map((m) => (
                <div key={m.id} className={`${m.role === 'user' ? 'self-end bg-primary text-on-primary' : 'self-start bg-surface-container-low border border-outline-variant'} max-w-[90%] px-3 py-2 text-sm`}>
                  <p className="whitespace-pre-wrap">{m.content}</p>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>

            <div className="p-4 border-t border-outline-variant">
              {chatError && <p className="text-[11px] text-red-600 mb-2">{chatError}</p>}
              <div className="flex gap-2 items-end">
                <textarea
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      void handleSend();
                    }
                  }}
                  disabled={!selected || sending}
                  rows={2}
                  placeholder={selected ? 'Continue this chat…' : 'Select an insight context first'}
                  className="flex-1 resize-none border border-outline-variant bg-surface-container-low px-3 py-2 text-sm outline-none focus:border-primary disabled:opacity-60"
                />
                <button
                  onClick={() => void handleSend()}
                  disabled={!selected || !chatInput.trim() || sending}
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
