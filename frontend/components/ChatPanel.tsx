"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import type { ChatMessage, Insight } from "@/types";

interface ChatPanelProps {
  /** Base API path, e.g. /api/chat/2024-04-27/some-slug  or  /api/chat/runs/abc/some-slug */
  chatApiBase: string;
  /** Matching insights base, e.g. /api/insights/2024-04-27/some-slug */
  insightsApiBase: string;
}

export default function ChatPanel({ chatApiBase, insightsApiBase }: ChatPanelProps) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [savingInsightFor, setSavingInsightFor] = useState<number | null>(null);
  const [insightInput, setInsightInput] = useState("");
  const [showInsights, setShowInsights] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load history and insights when panel opens or chatApiBase changes
  useEffect(() => {
    setMessages([]);
    setInsights([]);
    setError(null);
    if (!open) return;

    fetch(`${chatApiBase}/messages`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setMessages)
      .catch(() => {});

    fetch(insightsApiBase)
      .then((r) => (r.ok ? r.json() : []))
      .then(setInsights)
      .catch(() => {});
  }, [chatApiBase, insightsApiBase, open]);

  // Reload insights when panel opens
  useEffect(() => {
    if (!open) return;
    fetch(insightsApiBase)
      .then((r) => (r.ok ? r.json() : []))
      .then(setInsights)
      .catch(() => {});
  }, [insightsApiBase, open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);
    setError(null);

    try {
      const res = await fetch(`${chatApiBase}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || "Something went wrong. Please try again.");
        setSending(false);
        return;
      }
      const data = await res.json();
      setMessages((prev) => [...prev, data.user_message, data.assistant_message]);
    } catch {
      setError("Network error. Is the backend running?");
    } finally {
      setSending(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  async function handleSaveInsight(messageContent: string) {
    if (!insightInput.trim()) return;
    setSavingInsightFor(null);
    try {
      const res = await fetch(insightsApiBase, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_perspective: insightInput.trim(), summary: messageContent }),
      });
      if (res.ok) {
        const insight: Insight = await res.json();
        setInsights((prev) => [...prev, insight]);
        setInsightInput("");
      }
    } catch {
      /* silent */
    }
  }

  return (
    <div className="border-t border-slate-100 mt-6">
      {/* Toggle header */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-8 py-4 text-left hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <span className="w-7 h-7 rounded-lg bg-indigo-100 flex items-center justify-center flex-shrink-0">
            <svg className="w-3.5 h-3.5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          </span>
          <div>
            <p className="text-sm font-semibold text-slate-800">Discuss This Topic</p>
            <p className="text-[11px] text-slate-400">Ask questions, share your perspective</p>
          </div>
        </div>
        <svg
          className={`w-4 h-4 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="px-8 pb-6 flex flex-col gap-4">
          {/* Insights toggle */}
          {insights.length > 0 && (
            <div>
              <button
                onClick={() => setShowInsights((v) => !v)}
                className="text-[11px] font-semibold text-indigo-600 uppercase tracking-widest hover:text-indigo-800 transition-colors"
              >
                {showInsights ? "Hide" : "Show"} saved insights ({insights.length})
              </button>
              {showInsights && (
                <div className="mt-3 space-y-2">
                  {insights.map((ins) => (
                    <div key={ins.id} className="bg-amber-50 border border-amber-100 rounded-xl p-3 text-sm text-slate-700">
                      <p className="font-medium text-amber-800 text-[11px] uppercase tracking-wide mb-1">Your perspective</p>
                      <p>{ins.user_perspective}</p>
                      {ins.tags.length > 0 && (
                        <div className="flex gap-1.5 flex-wrap mt-2">
                          {ins.tags.map((t, i) => (
                            <span key={i} className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-medium">{t}</span>
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
          <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
            {messages.length === 0 && !sending && (
              <p className="text-xs text-slate-400 text-center py-4">
                Ask anything about this topic, or share your perspective.
              </p>
            )}
            {messages.map((msg) => (
              <div key={msg.id} className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end" : "items-start"}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-indigo-600 text-white rounded-br-sm"
                      : "bg-slate-100 text-slate-800 rounded-bl-sm"
                  }`}
                >
                  {msg.role === "assistant" ? (
                    <div className="prose prose-sm prose-slate max-w-none [&>p]:my-1 [&>ul]:my-1 [&>ol]:my-1">
                      <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{msg.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <p>{msg.content}</p>
                  )}
                </div>

                {/* Citations */}
                {msg.role === "assistant" && msg.citations.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 max-w-[85%]">
                    {msg.used_web && (
                      <span className="text-[10px] text-slate-400 font-medium self-center">Sources:</span>
                    )}
                    {msg.citations.slice(0, 4).map((c, i) => (
                      <a
                        key={i}
                        href={c.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 hover:bg-slate-200 text-[10px] text-slate-600 border border-slate-200 transition-colors"
                      >
                        {msg.used_web && <span className="text-blue-500">🌐</span>}
                        <span className="max-w-[120px] truncate">{c.title || new URL(c.url).hostname}</span>
                      </a>
                    ))}
                  </div>
                )}

                {/* Save as insight (user messages only) */}
                {msg.role === "user" && (
                  <div className="flex items-center gap-2">
                    {savingInsightFor === msg.id ? (
                      <div className="flex items-center gap-2 mt-1">
                        <input
                          value={insightInput}
                          onChange={(e) => setInsightInput(e.target.value)}
                          placeholder="Your perspective on this..."
                          className="text-xs border border-slate-200 bg-white text-slate-900 rounded-lg px-3 py-1.5 w-64 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleSaveInsight(msg.content);
                            if (e.key === "Escape") setSavingInsightFor(null);
                          }}
                          autoFocus
                        />
                        <button
                          onClick={() => handleSaveInsight(msg.content)}
                          className="text-[10px] font-semibold text-indigo-600 hover:text-indigo-800"
                        >Save</button>
                        <button
                          onClick={() => setSavingInsightFor(null)}
                          className="text-[10px] text-slate-400 hover:text-slate-600"
                        >Cancel</button>
                      </div>
                    ) : (
                      <button
                        onClick={() => { setSavingInsightFor(msg.id); setInsightInput(""); }}
                        className="text-[10px] text-slate-400 hover:text-indigo-600 transition-colors"
                      >
                        + Save as insight
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}

            {sending && (
              <div className="flex items-start gap-2">
                <div className="bg-slate-100 rounded-2xl rounded-bl-sm px-4 py-3">
                  <div className="flex gap-1 items-center h-4">
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:0ms]" />
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:150ms]" />
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:300ms]" />
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {error && (
            <p className="text-xs text-red-500 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</p>
          )}

          {/* Input */}
          <div className="flex gap-2 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Ask about this topic… (Enter to send, Shift+Enter for newline)"
              rows={2}
              className="flex-1 resize-none border border-slate-200 bg-white text-slate-900 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 placeholder:text-slate-400"
              disabled={sending}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || sending}
              className="flex-shrink-0 w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
