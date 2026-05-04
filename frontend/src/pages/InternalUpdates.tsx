import React, { useState } from 'react';
import { MessageSquare, ExternalLink, Bookmark, Paperclip, Send } from 'lucide-react';
import { cn } from '../lib/utils';
import { useWorkspace } from '../context/WorkspaceContext';
import ComingSoonBadge from '../components/ComingSoonBadge';

interface UpdateItemData {
  id: string;
  category: string;
  time: string;
  title: string;
  tag: string;
  comments: number;
  content: string;
  author: string;
}

export default function InternalUpdates() {
  const { workspace } = useWorkspace();
  const isTilicho = workspace === 'TILICHO_LABS';

  const linkedinUpdates: UpdateItemData[] = [
    {
      id: 'l1',
      category: "SLACK INTELLIGENCE",
      time: "10:42 AM",
      title: "Q3 Logistics Platform Architecture Review Notes",
      tag: "ENGINEERING",
      comments: 12,
      author: "Sarah Jenkins",
      content: "Following up on the sync today regarding the routing engine overhaul. The consensus is that we need to migrate the core dispatcher service to the new event-driven architecture by end of sprint 4."
    },
    {
      id: 'l2',
      category: "SLACK INTELLIGENCE",
      time: "Yesterday",
      title: "Weekly UX Sync: Component Library Updates",
      tag: "DESIGN",
      comments: 4,
      author: "Marcus Kline",
      content: "We've finalized the new design tokens for the dashboard. Please review the updated Figma file and prepare for implementation in the next cycle."
    }
  ];

  const tilichoUpdates: UpdateItemData[] = [
    {
      id: 't1',
      category: "INFRA STATUS",
      time: "10:42 AM",
      title: "Asia-East Region Migration Completion",
      tag: "OPS",
      comments: 12,
      author: "Sarah Jenkins",
      content: "All core services have been successfully migrated to the new region. The transition was completed at 10:42 AM. Latency markers show a 30% improvement."
    },
    {
      id: 't2',
      category: "GITHUB EVENTS",
      time: "Yesterday",
      title: "PR #402: Optimized Batch Processing",
      tag: "CORE",
      comments: 4,
      author: "Marcus Kline",
      content: "Merged the new batch processing logic. We reduced memory footprint by 20% during heavy ingestion phases. Monitoring the cluster performance now."
    }
  ];

  const updates = isTilicho ? tilichoUpdates : linkedinUpdates;
  const [activeUpdateId, setActiveUpdateId] = useState(updates[0].id);
  const activeUpdate = updates.find(u => u.id === activeUpdateId) || updates[0];

  const [isBookmarked, setIsBookmarked] = useState(false);
  const [newComment, setNewComment] = useState('');
  const [comments, setComments] = useState([
    {
      initials: "MK",
      name: "Marcus Kline",
      time: "10:45 AM",
      text: isTilicho ? "Did we verify the fallback nodes in Hong Kong? Success rate was hovering around 98%." : "Are we confident the new event bus can handle the throughput for the NYC zones?"
    },
    {
      initials: "SJ",
      name: "Sarah Jenkins",
      time: "10:48 AM",
      isAuthor: true,
      text: isTilicho ? "Yes, HK nodes are healthy now. The minor drop was due to a stale cache entry during DNS propagation." : "Yes, I've provisioned dedicated shard clusters for the dense urban sectors."
    }
  ]);

  const handlePostComment = () => {
    if (!newComment.trim()) return;
    const comment = {
      initials: "ME",
      name: "YOU",
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      text: newComment
    };
    setComments([...comments, comment]);
    setNewComment('');
  };

  return (
    <div className="flex-1 flex overflow-hidden relative">
      <ComingSoonBadge />
      {/* Pane 1: Left - Updates List */}
      <aside className="w-[320px] h-full border-r border-outline-variant bg-surface-container-lowest flex flex-col shrink-0">
        <div className="px-6 py-4 border-b border-outline-variant flex items-center justify-between bg-surface-container-low">
          <h2 className="label-bold text-primary">{isTilicho ? "Dev Logs" : "Update Stream"}</h2>
        </div>
        <div className="flex-1 overflow-y-auto">
          {updates.map(item => (
            <UpdateItem 
              key={item.id}
              active={activeUpdateId === item.id}
              category={item.category} 
              time={item.time} 
              title={item.title}
              tag={item.tag}
              comments={item.comments}
              onClick={() => setActiveUpdateId(item.id)}
            />
          ))}
        </div>
      </aside>

      {/* Pane 2: Middle - Content & Chat */}
      <section className="flex-1 h-full flex flex-col bg-surface overflow-hidden relative border-r border-outline-variant">
        <div className="p-8 border-b border-outline-variant bg-surface-container-lowest">
          <div className="flex items-center gap-2 mb-4">
            <span className="bg-primary text-on-primary px-2 py-1 text-[10px] font-bold uppercase tracking-widest">
              {isTilicho ? "Production Log" : "Extracted Update"}
            </span>
            <span className="text-sm text-on-surface-variant">Thread started by <span className="font-semibold text-on-surface">{activeUpdate.author}</span></span>
          </div>
          <h1 className="text-2xl font-bold mb-4">
            {activeUpdate.title}
          </h1>
          <p className="text-sm text-on-surface-variant leading-relaxed mb-6">
            {activeUpdate.content}
          </p>
          <div className="flex gap-4">
            <button className="btn-secondary h-10 px-4 text-xs">
              <ExternalLink size={14} /> {isTilicho ? "View Deployment Logs" : "View Original in Slack"}
            </button>
            <button 
              onClick={() => setIsBookmarked(!isBookmarked)}
              className={cn(
                "btn-secondary h-10 px-4 text-xs transition-colors",
                isBookmarked ? "bg-primary text-on-primary border-primary" : "border-outline-variant bg-surface-container text-on-surface-variant"
              )}
            >
              <Bookmark size={14} fill={isBookmarked ? "currentColor" : "none"} /> {isBookmarked ? "Saved to KB" : "Save to Knowledge Base"}
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-8 flex flex-col gap-6">
          <div className="text-center">
            <span className="bg-surface-container border border-outline-variant px-3 py-1 label-bold text-[10px]">
              {isTilicho ? "SYSTEM ANNOTATIONS" : "INTERNAL DISCUSSION"}
            </span>
          </div>
          {comments.map((comment, idx) => (
            <DiscussionItem 
              key={idx}
              initials={comment.initials}
              name={comment.name}
              time={comment.time}
              text={comment.text}
              isAuthor={comment.isAuthor}
            />
          ))}
        </div>

        <div className="p-8 border-t border-outline-variant bg-surface-container-lowest">
          <div className="relative flex items-end">
            <textarea 
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              className="w-full bg-transparent border border-outline-variant p-4 pr-16 min-h-[100px] text-sm resize-none focus:outline-none focus:border-primary focus:border-2"
              placeholder={isTilicho ? "Add technical context..." : "Add context or ask a question..."}
            />
            <div className="absolute right-4 bottom-4 flex items-center gap-3">
              <Paperclip size={18} className="text-on-surface-variant cursor-pointer hover:text-primary transition-colors" />
              <button 
                onClick={handlePostComment}
                className="btn-primary py-1.5 px-4 text-xs h-8"
              >
                Post
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Pane 3: Right - Metadata */}
      <aside className="w-[280px] h-full bg-surface-container-lowest flex flex-col shrink-0">
        <div className="px-6 py-6 border-b border-outline-variant bg-surface-container-low">
          <h3 className="label-bold text-primary">Metadata</h3>
        </div>
        <div className="p-6 flex flex-col gap-8">
          <div>
            <span className="label-bold text-[10px] mb-2 block">Source Origin</span>
            <div className="flex items-center gap-2 bg-surface p-2 border border-outline-variant">
              <MessageSquare size={14} />
              <span className="text-xs font-semibold">{isTilicho ? "Internal CI/CD" : "Slack Workspace"}</span>
            </div>
          </div>

          <div>
            <span className="label-bold text-[10px] mb-2 block">Key Entities</span>
            <div className="flex flex-wrap gap-2">
              {(isTilicho ? ['Asia-East', 'Migration', 'Latency', 'DNS'] : ['Routing Engine', 'Dispatcher Service', 'Event-Driven', 'Sprint 4']).map(tag => (
                <span key={tag} className="bg-surface-container border border-outline-variant px-2 py-1 text-[10px] font-bold">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}

function UpdateItem({ active, category, time, title, tag, comments, onClick }: any) {
  return (
    <div 
      onClick={onClick}
      className={cn(
        "p-4 border-b border-outline-variant cursor-pointer transition-colors relative border-l-4",
        active ? "bg-surface-container-highest border-l-primary" : "hover:bg-surface-container-low border-l-transparent"
      )}
    >
      <div className="flex justify-between items-start mb-2">
        <span className={cn("label-bold", active ? "text-primary" : "text-on-surface-variant")}>{category}</span>
        <span className="text-[10px] font-bold text-outline uppercase">{time}</span>
      </div>
      <h3 className="text-sm font-bold mb-3 leading-tight">{title}</h3>
      <div className="flex items-center gap-3">
        <span className="bg-surface-container border border-outline-variant px-2 py-0.5 text-[10px] font-bold tracking-tighter">
          #{tag}
        </span>
        <div className="flex items-center gap-1 text-on-surface-variant">
          <MessageSquare size={12} />
          <span className="text-[10px] font-bold">{comments}</span>
        </div>
      </div>
    </div>
  );
}

function DiscussionItem({ initials, name, time, text, isAuthor }: any) {
  return (
    <div className="flex gap-4 animate-in fade-in slide-in-from-bottom-2">
      <div className={cn(
        "w-10 h-10 flex items-center justify-center font-bold text-xs shrink-0",
        isAuthor ? "bg-primary text-on-primary" : "bg-surface-container-high border border-outline-variant"
      )}>
        {initials}
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-bold text-sm tracking-tight">{name}</span>
          <span className="text-[10px] font-bold text-outline uppercase">{time}</span>
          {isAuthor && <span className="bg-surface-container px-1 py-0.5 text-[8px] border border-outline-variant uppercase font-black">Author</span>}
        </div>
        <div className="bg-surface-container-lowest border border-outline-variant p-4 text-sm leading-relaxed relative">
           {!isAuthor && <div className="absolute inset-0 border border-primary translate-x-[2px] translate-y-[2px] -z-10 bg-surface-container-highest" />}
           {text}
        </div>
      </div>
    </div>
  );
}
