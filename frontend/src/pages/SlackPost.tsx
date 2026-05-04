import { type FormEvent, useState } from 'react';
import { MessageSquare, Send } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { apiPost } from '@/lib/api';
import type { SlackChatReply, SlackSendResult } from '@/types';
import { useToast } from '@/context/ToastContext';

type Msg = { role: 'user' | 'assistant'; text: string; time: string };

export default function SlackPost() {
  const { pushToast } = useToast();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [prompt, setPrompt] = useState('');
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleChatSubmit(e: FormEvent) {
    e.preventDefault();
    if (!prompt.trim()) return;
    const text = prompt.trim();
    setPrompt('');
    setError(null);
    const user: Msg = { role: 'user', text, time: new Date().toLocaleTimeString() };
    setMessages((prev) => [...prev, user]);
    setLoading(true);
    try {
      const res = await apiPost<SlackChatReply>('/api/slack/chat', {
        channel_id: '',
        selected_message: draft,
        content: text,
        history: [],
      });
      setMessages((prev) => [...prev, { role: 'assistant', text: res.reply, time: new Date().toLocaleTimeString() }]);
      if (!draft.trim()) setDraft(res.reply);
      pushToast('Draft response generated.', 'success');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to chat.');
      pushToast('Failed to generate draft response.', 'error');
    } finally {
      setLoading(false);
    }
  }

  async function sendToSlack() {
    if (!draft.trim()) return;
    setSending(true);
    setError(null);
    try {
      const out = await apiPost<SlackSendResult>('/api/slack/post', { channel_id: 'default', text: draft });
      setStatus(`Sent to Slack channel ${out.channel}`);
      pushToast('Message posted to Slack successfully.', 'success');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message.');
      pushToast('Posting message to Slack failed.', 'error');
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex-1 w-full max-w-[1400px] mx-auto px-6 py-6 flex gap-6 overflow-hidden">
      <section className="flex-1 flex flex-col bg-surface-container-low border border-outline-variant">
        <div className="p-4 border-b border-outline-variant bg-white flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare size={18} className="text-primary" />
            <h2 className="text-lg font-bold">Slack Ideation Chat</h2>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4">
          {messages.map((m, i) => (
            <div key={i} className={m.role === 'user' ? 'self-end max-w-[80%] bg-primary text-on-primary p-3' : 'self-start max-w-[80%] bg-white border border-outline-variant p-3'}>
              <p className="text-sm whitespace-pre-wrap">{m.text}</p>
            </div>
          ))}
        </div>
        <form onSubmit={handleChatSubmit} className="p-4 border-t border-outline-variant bg-white flex gap-2">
          <input
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            className="flex-1 border border-outline-variant px-3 py-2 text-sm"
            placeholder="Describe your idea..."
          />
          <button type="submit" disabled={loading || !prompt.trim()} className="btn-primary px-3">
            <Send size={14} />
          </button>
        </form>
      </section>

      <aside className="w-[480px] flex flex-col gap-4 border border-outline-variant bg-white p-4">
        <h2 className="text-lg font-bold">Draft to Send</h2>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="w-full min-h-[360px] border border-outline-variant p-3 font-mono text-sm"
          placeholder="Your Slack post draft appears here..."
        />
        <div className="border border-outline-variant bg-surface-container-low p-3 max-h-[280px] overflow-y-auto">
          <p className="label-bold text-[9px] text-outline mb-2 uppercase">Formatted Preview</p>
          {draft.trim() ? (
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{draft}</ReactMarkdown>
            </div>
          ) : (
            <p className="text-xs text-on-surface-variant">Markdown preview will appear here.</p>
          )}
        </div>
        {error && <p className="text-red-600 text-xs">{error}</p>}
        {status && <p className="text-green-700 text-xs">{status}</p>}
        <button onClick={sendToSlack} disabled={sending || !draft.trim()} className="btn-primary">
          <Send size={14} /> {sending ? 'Sending...' : 'Send to Slack'}
        </button>
      </aside>
    </div>
  );
}
