import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { ChevronDown, Send } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatMessage, Insight } from '@/types';

interface ChatPanelProps {
  chatApiBase: string;
  insightsApiBase: string;
}

export default function ChatPanel({ chatApiBase, insightsApiBase }: ChatPanelProps) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [showInsights, setShowInsights] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setMessages([]);
    setInsights([]);
    setError(null);
    if (!open) return;
    fetch(`${chatApiBase}/messages`).then((r) => (r.ok ? r.json() : [])).then(setMessages).catch(() => {});
    fetch(insightsApiBase).then((r) => (r.ok ? r.json() : [])).then(setInsights).catch(() => {});
  }, [chatApiBase, insightsApiBase, open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    setSending(true);
    setError(null);
    try {
      const res = await fetch(`${chatApiBase}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: text }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({})) as Record<string, unknown>;
        setError(String(err.detail ?? 'Something went wrong. Please try again.'));
        setSending(false);
        return;
      }
      const data = await res.json() as { user_message: ChatMessage; assistant_message: ChatMessage };
      setMessages((prev) => [...prev, data.user_message, data.assistant_message]);

      // Silently auto-save the user's message as an insight for this topic.
      // Only save substantive messages (≥30 chars) — short replies like "thanks",
      // "yes", or "ok" don't reveal the user's thinking and pollute the insight set.
      if (data.user_message.content.trim().length >= 30) {
        fetch(insightsApiBase, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_perspective: data.user_message.content,
            summary: data.assistant_message.content.slice(0, 500),
            tags: [],
          }),
        })
          .then((r) => (r.ok ? r.json() : null))
          .then((ins: Insight | null) => { if (ins) setInsights((prev) => [...prev, ins]); })
          .catch(() => {});
      }
    } catch {
      setError('Network error. Is the backend running?');
    } finally {
      setSending(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  return (
    <div className="border-t border-outline-variant mt-6">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-6 py-4 text-left hover:bg-surface-container transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 bg-primary flex items-center justify-center flex-shrink-0">
            <span className="text-on-primary text-[8px] font-black">AI</span>
          </div>
          <div>
            <p className="text-sm font-bold uppercase tracking-tight">Discuss This Topic</p>
            <p className="label-bold text-[9px] text-outline mt-0.5">
              Ask questions, share your perspective
              {insights.length > 0 && ` · ${insights.length} insight${insights.length !== 1 ? 's' : ''} saved`}
            </p>
          </div>
        </div>
        <ChevronDown size={14} className={cn('text-on-surface-variant transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="px-6 pb-6 flex flex-col gap-4">
          {/* Insights viewer */}
          {insights.length > 0 && (
            <div>
              <button
                onClick={() => setShowInsights((v) => !v)}
                className="label-bold text-[10px] text-primary hover:text-black transition-colors"
              >
                {showInsights ? '▲ Hide' : '▼ Show'} saved insights ({insights.length})
              </button>
              {showInsights && (
                <div className="mt-3 flex flex-col gap-2">
                  {insights.map((ins) => (
                    <div key={ins.id} className="bg-surface-container-low border border-outline-variant p-3 text-sm">
                      <p className="label-bold text-[9px] mb-1">Your perspective</p>
                      <p className="text-on-surface text-xs leading-relaxed line-clamp-3">{ins.user_perspective}</p>
                      {ins.tags.length > 0 && (
                        <div className="flex gap-1.5 flex-wrap mt-2">
                          {ins.tags.map((t, i) => (
                            <span key={i} className="px-2 py-0.5 border border-outline-variant text-[9px] font-bold uppercase">{t}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Chat transcript */}
          <div className="flex flex-col gap-3 max-h-96 overflow-y-auto pr-1">
            {messages.length === 0 && !sending && (
              <p className="label-bold text-[10px] text-outline text-center py-4">
                Ask anything about this topic. Your exchanges are saved as insights automatically.
              </p>
            )}
            {messages.map((msg) => (
              <div key={msg.id} className={cn('flex flex-col gap-1', msg.role === 'user' ? 'items-end' : 'items-start')}>
                <span className="label-bold text-[9px] text-outline">
                  {msg.role === 'user' ? 'YOU' : 'AGENT'}
                </span>
                <div className={cn(
                  'max-w-[85%] px-4 py-3 text-sm leading-relaxed',
                  msg.role === 'user'
                    ? 'bg-primary text-on-primary'
                    : 'bg-surface-container-lowest border border-outline-variant text-on-surface',
                )}>
                  {msg.role === 'assistant' ? (
                    <div className="prose prose-sm prose-neutral max-w-none [&>p]:my-1 [&>ul]:my-1 [&>ol]:my-1">
                      <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{msg.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <p>{msg.content}</p>
                  )}
                </div>

                {msg.role === 'assistant' && msg.citations.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 max-w-[85%]">
                    {msg.used_web && <span className="label-bold text-[9px] text-outline self-center">Sources:</span>}
                    {msg.citations.slice(0, 4).map((c, i) => (
                      <a
                        key={i}
                        href={c.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 px-2 py-0.5 border border-outline-variant bg-surface-container-low hover:border-primary text-[10px] font-bold transition-colors"
                      >
                        {msg.used_web && <span>🌐</span>}
                        <span className="max-w-[120px] truncate">{c.title || new URL(c.url).hostname}</span>
                      </a>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {sending && (
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 bg-primary flex items-center justify-center flex-shrink-0">
                  <span className="text-on-primary text-[8px] font-black">AI</span>
                </div>
                <div className="bg-surface-container-lowest border border-outline-variant px-4 py-3">
                  <div className="flex gap-1 items-center h-4">
                    <span className="w-1.5 h-1.5 bg-on-surface-variant animate-bounce [animation-delay:0ms]" />
                    <span className="w-1.5 h-1.5 bg-on-surface-variant animate-bounce [animation-delay:150ms]" />
                    <span className="w-1.5 h-1.5 bg-on-surface-variant animate-bounce [animation-delay:300ms]" />
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {error && <p className="text-[11px] text-red-600 border border-red-200 bg-red-50 px-3 py-2 font-mono">{error}</p>}

          <div className="flex gap-2 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              placeholder="Ask about this topic… (Enter to send)"
              rows={2}
              disabled={sending}
              className="flex-1 resize-none border border-outline-variant bg-surface-container-low text-on-surface px-4 py-2.5 text-sm outline-none focus:border-primary focus:border-2 disabled:opacity-50 transition-all font-sans placeholder:text-outline"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || sending}
              className="flex-shrink-0 w-10 h-10 bg-primary text-on-primary flex items-center justify-center hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              <Send size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
