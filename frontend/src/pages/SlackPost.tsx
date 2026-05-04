import React, { useState } from 'react';
import { Send, MessageSquare, MoreHorizontal, Paperclip, Bot } from 'lucide-react';
import { cn } from '../lib/utils';
import { useWorkspace } from '../context/WorkspaceContext';
import ComingSoonBadge from '../components/ComingSoonBadge';

export default function SlackPost() {
  const { workspace } = useWorkspace();
  const isTilicho = workspace === 'TILICHO_LABS';

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [chatMessages, setChatMessages] = useState<any[]>([
    {
      isUser: true,
      text: "I need to draft an update for the #product channel about the new dashboard release. It needs to sound professional but exciting.",
      time: "10:42 AM"
    },
    {
      isBot: true,
      text: "Here are a few angles we could take for the #product channel update:",
      options: [
        "Focus on Efficiency: Highlight how the new dashboard reduces load times by 40% and speeds up workflow.",
        "Focus on Visuals: Emphasize the new 'Urban Mono' aesthetic and improved data visualization cards.",
        "Focus on Features: Detail the specific new components like the AI ideation pane and integrated timer."
      ],
      footer: "Which direction feels best, or should we combine a few elements?",
      time: "10:43 AM"
    },
    {
      isUser: true,
      text: "Let's combine Efficiency and Visuals. Make it punchy. Include a call to action to test it out.",
      time: "10:45 AM"
    }
  ]);

  const [message, setMessage] = useState('');
  const [draftContent, setDraftContent] = useState(`🚀 **New Dashboard Release is Live!**

Team, we've just rolled out the major update to the core dashboard interface. 

**What's new?**
• **Speed:** Load times are down 40%, ensuring a much faster workflow.
• **Aesthetic:** We've transitioned to the new 'Urban Mono' high-contrast visual language.`);

  const [status, setStatus] = useState<string | null>(null);

  const handleSendMessage = () => {
    if (!message.trim()) return;
    const newMsg = {
      isUser: true,
      text: message,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setChatMessages([...chatMessages, newMsg]);
    setMessage('');

    setTimeout(() => {
      setChatMessages(prev => [...prev, {
        isBot: true,
        text: "I've updated the draft content based on your request. Take a look at the right pane.",
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }]);
    }, 1000);
  };

  const handleSave = () => {
    setStatus("Draft saved successfully!");
    setTimeout(() => setStatus(null), 3000);
  };

  const handleSend = () => {
    setStatus("Post sent to Slack!");
    setTimeout(() => setStatus(null), 3000);
  };

  const handleEditMessage = (index: number, newText: string) => {
    setChatMessages(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], text: newText };
      return updated;
    });
  };

  return (
    <div className="flex-1 w-full max-w-[1400px] mx-auto px-6 py-6 flex gap-6 overflow-hidden relative">
      <ComingSoonBadge />
      {/* Left Column: Ideation Assistant */}
      <section className="flex-1 flex flex-col bg-surface-container-low border border-outline-variant relative">
        <div className="p-4 border-b border-outline-variant bg-white flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot size={18} className="text-primary" />
            <h2 className="text-lg font-bold">Ideation Assistant</h2>
          </div>
          <MoreHorizontal size={18} className="text-on-surface-variant cursor-pointer" />
        </div>

        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 font-sans">
          {chatMessages.map((msg, idx) => (
            <div key={idx}>
              {msg.isUser ? (
                <div className="self-end ml-12 mb-6 bg-white border border-outline-variant p-4 text-sm leading-relaxed shadow-sm">
                  <p>{msg.text}</p>
                  <div className="text-[10px] font-bold text-outline text-right uppercase mt-2">YOU - {msg.time}</div>
                </div>
              ) : (
                <SlackAssistantMessage 
                  text={msg.text}
                  time={msg.time}
                  options={msg.options}
                  footer={msg.footer}
                  onSave={(newText: string) => handleEditMessage(idx, newText)}
                />
              )}
            </div>
          ))}
        </div>

        <div className="p-4 bg-white border-t border-outline-variant">
           <form 
            onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }}
            className="relative flex items-center"
           >
              <input 
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                className="w-full bg-surface-container-low border border-outline-variant py-4 px-4 pr-12 text-sm outline-none focus:border-primary focus:border-2"
                placeholder="Type your message to the assistant..."
              />
              <button 
                type="submit"
                className="absolute right-3 text-on-surface-variant hover:text-black transition-colors"
              >
                <Send size={18} />
              </button>
           </form>
        </div>
      </section>

      {/* Right Column: Draft & Post */}
      <aside className="w-[480px] flex flex-col gap-6">
        <div className="card h-full flex flex-col relative">
          {status && (
            <div className="absolute top-4 right-4 bg-primary text-on-primary px-3 py-1 text-[10px] font-bold animate-in fade-in slide-in-from-top-2 z-50">
              {status}
            </div>
          )}
          <div className="flex justify-between items-center mb-6 border-b border-surface-variant pb-4">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <span className="p-1 border border-primary"><MessageSquare size={16} /></span>
              Draft & Post
            </h2>
            <div className="flex items-center gap-2">
              <span className="label-bold text-[10px]">Target:</span>
              <span className="bg-surface-container px-2 py-1 text-[10px] font-bold border border-outline-variant"># product-updates</span>
            </div>
          </div>

          <div className="flex flex-col gap-6 flex-1 overflow-y-auto pr-2">
            <div className="flex flex-col gap-2">
              <label className="label-bold">Message Content</label>
              <textarea 
                value={draftContent}
                onChange={(e) => setDraftContent(e.target.value)}
                className="w-full h-64 bg-surface-container-low border border-outline-variant p-4 font-mono text-sm leading-relaxed outline-none resize-none focus:border-primary focus:border-2"
              />
            </div>

            <div className="flex flex-col gap-2">
              <label className="label-bold">Attachments (1)</label>
              <div className="bg-surface-container-low border border-outline-variant p-3 flex justify-between items-center text-xs">
                <div className="flex items-center gap-2">
                  <Paperclip size={14} />
                  <span className="font-medium">dashboard_preview_v2.png</span>
                </div>
                <button className="text-outline hover:text-black">×</button>
              </div>
            </div>

            <div className="mt-4">
              <label className="label-bold mb-3 block text-primary">Live Preview</label>
              <div className="bg-white border-2 border-primary p-6 flex gap-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] relative overflow-hidden">
                <div className="absolute top-0 right-0 bg-primary text-on-primary px-2 py-0.5 text-[8px] font-black uppercase tracking-tighter">Slack Preview</div>
                <div className="w-10 h-10 bg-black text-white flex items-center justify-center shrink-0 font-black text-xs uppercase">TB</div>
                <div className="flex-1 overflow-hidden">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-bold text-sm">Tilicho Bot</span>
                    <span className="text-[10px] text-outline font-bold">10:48 AM</span>
                  </div>
                  <div className="text-sm leading-relaxed whitespace-pre-wrap break-words font-medium">
                    {draftContent}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="flex gap-4 pt-6 border-t border-surface-variant mt-auto">
            <button onClick={handleSave} className="btn-secondary flex-1">Save Draft</button>
            <button onClick={handleSend} className="btn-primary flex-1">
               <Send size={14} /> Send to Slack
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}

function SlackAssistantMessage({ text, time, options, footer, onSave }: any) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedText, setEditedText] = useState(text);

  const hasChanged = editedText !== text;

  return (
    <div className="self-start mr-12 mb-6 bg-black text-white p-6 relative group transition-all">
      <div className="absolute top-0 left-0 w-full h-full border border-primary translate-x-2 translate-y-2 -z-10 bg-surface-container-highest" />
      
      <div className="relative">
        <textarea
          className="bg-transparent border-none outline-none w-full resize-none h-auto min-h-[1em] text-sm leading-relaxed mb-4 text-white"
          value={editedText}
          onChange={(e) => {
            setEditedText(e.target.value);
            setIsEditing(true);
          }}
          rows={editedText.split('\n').length || 1}
        />
      </div>

      {options && (
        <ol className="text-sm space-y-4 list-decimal pl-4 mb-4 opacity-90">
          {options.map((opt: string, i: number) => {
            const [title, desc] = opt.split(':');
            return (
              <li key={i}>
                <span className="font-bold">{title}:</span>{desc}
              </li>
            );
          })}
        </ol>
      )}
      
      {footer && <p className="text-sm italic opacity-70 mb-4">{footer}</p>}
      
      <div className="flex justify-between items-end">
        <div className="text-[10px] font-bold text-surface-container-high uppercase">ASSISTANT - {time}</div>
        {isEditing && hasChanged && (
          <button 
            onClick={() => {
              onSave(editedText);
              setIsEditing(false);
            }}
            className="px-3 py-1 bg-primary text-on-primary text-[10px] font-bold uppercase tracking-widest hover:bg-white hover:text-black transition-colors"
          >
            Save Changes
          </button>
        )}
      </div>
    </div>
  );
}
