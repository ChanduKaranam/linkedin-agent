import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import { ArrowLeftRight, Check, LogOut } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useWorkspace, type Workspace } from '../../context/WorkspaceContext';
import { useBackendStatus } from '../../context/BackendStatusContext';
import { useAuth } from '../../context/AuthContext';
import ScheduleEditor from '../ScheduleEditor';
import { buildLinkedInAuthorizeUrl } from '@/lib/linkedinAuth';
import { useToast } from '@/context/ToastContext';
import type { LinkedInStatus } from '@/types';

export default function Navbar() {
  const { workspace, setWorkspace } = useWorkspace();
  const { schedule, setSchedule } = useBackendStatus();
  const navigate = useNavigate();
  const { pushToast } = useToast();
  const { user, logout } = useAuth();
  const [liStatus, setLiStatus] = useState<LinkedInStatus | null>(null);

  const [isWorkspaceMenuOpen, setIsWorkspaceMenuOpen] = useState(false);
  const [isHeaderVisible, setIsHeaderVisible] = useState(true);

  React.useEffect(() => {
    const handleVisibility = (event: Event) => {
      const customEvent = event as CustomEvent<{ visible?: boolean } | boolean>;
      const detail = customEvent.detail;
      if (typeof detail === 'boolean') {
        setIsHeaderVisible(detail);
        return;
      }
      setIsHeaderVisible(detail?.visible ?? true);
    };

    window.addEventListener('trends-header-visibility', handleVisibility as EventListener);
    return () => window.removeEventListener('trends-header-visibility', handleVisibility as EventListener);
  }, []);

  const toggleWorkspace = (ws: Workspace) => {
    setWorkspace(ws);
    setIsWorkspaceMenuOpen(false);
    // Navigate to workspace landing
    navigate(ws === 'TILICHO_LABS' ? '/updates' : '/');
  };

  React.useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const auth = params.get('li_auth');
    if (!auth) return;
    if (auth === 'success') {
      pushToast('LinkedIn connected successfully.', 'success');
    } else if (auth === 'failed') {
      pushToast(params.get('msg') ?? 'LinkedIn authorization failed.', 'error');
    }
    params.delete('li_auth');
    params.delete('msg');
    const next = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ''}${window.location.hash}`;
    window.history.replaceState({}, '', next);
  }, [pushToast]);

  React.useEffect(() => {
    let cancelled = false;
    async function loadLinkedInStatus() {
      try {
        const res = await fetch('/api/admin/linkedin/status');
        if (!res.ok) return;
        const data = await res.json() as LinkedInStatus;
        if (!cancelled) setLiStatus(data);
      } catch {
        // ignore status fetch failures in navbar
      }
    }
    void loadLinkedInStatus();
    const id = window.setInterval(() => { void loadLinkedInStatus(); }, 120000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return (
    <header className="bg-white border-b border-outline-variant flex flex-col w-full px-6 sticky top-0 z-50">
      <div
        className={cn(
          'transition-all duration-300 ease-out',
          isHeaderVisible
            ? 'overflow-visible max-h-52 opacity-100 translate-y-0'
            : 'overflow-hidden max-h-0 opacity-0 -translate-y-2 pointer-events-none',
        )}
      >
        <div className="flex items-center justify-between py-4">
          {/* Brand & Switcher */}
          <div className="flex items-center gap-6 relative">
            <button
              onClick={() => setIsWorkspaceMenuOpen(!isWorkspaceMenuOpen)}
              className="flex items-center gap-2 group transition-transform active:scale-95"
            >
              <span className="text-xl font-bold tracking-tighter uppercase whitespace-nowrap">
                {workspace === 'TILICHO_LABS' ? 'Tilicho Labs' : 'LinkedIn Agent'}
              </span>
              <ArrowLeftRight size={16} className="text-on-surface-variant group-hover:text-black transition-colors" />
            </button>

            <AnimatePresence>
              {isWorkspaceMenuOpen && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  className="absolute left-0 top-full mt-2 w-64 bg-white border-2 border-primary shadow-xl z-[60] p-2"
                >
                  {(['LINKEDIN_AGENT', 'TILICHO_LABS'] as Workspace[]).map((ws) => (
                    <button
                      key={ws}
                      onClick={() => toggleWorkspace(ws)}
                      className={cn(
                        'w-full text-left p-3 flex justify-between items-center hover:bg-surface-container transition-colors',
                        workspace === ws && 'bg-surface-container',
                      )}
                    >
                      <span className="font-bold text-sm uppercase">{ws === 'LINKEDIN_AGENT' ? 'LinkedIn Agent' : 'Tilicho Labs'}</span>
                      {workspace === ws && <Check size={14} />}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-2 text-[10px] font-mono">
              <span className={cn('px-2 py-1 border', liStatus?.connected ? 'border-green-300 bg-green-50 text-green-800' : 'border-outline-variant bg-surface-container-low text-on-surface-variant')}>
                {liStatus?.connected ? 'CONNECTED' : 'NOT CONNECTED'}
              </span>
              {liStatus?.connected && (
                <span className="text-on-surface-variant max-w-[220px] truncate" title={liStatus.member_name ?? undefined}>
                  {liStatus.member_name ?? 'LinkedIn Account'}
                </span>
              )}
            </div>
            <a
              href={buildLinkedInAuthorizeUrl()}
              className="btn-secondary py-1.5 px-3 text-[10px] border-[#0A66C2] text-[#0A66C2] hover:bg-blue-50"
            >
              {liStatus?.connected ? 'Switch LinkedIn Account' : 'Connect LinkedIn'}
            </a>
            {/* Schedule editor — LinkedIn workspace only */}
            {workspace === 'LINKEDIN_AGENT' && (
              <ScheduleEditor schedule={schedule} onSaved={setSchedule} />
            )}
            {user && (
              <button
                onClick={() => void logout()}
                title={`Logged in as ${user.username}`}
                className="flex items-center gap-1.5 text-[10px] font-mono text-on-surface-variant hover:text-black border border-outline-variant px-2 py-1 transition-colors"
              >
                <span className="hidden md:inline">{user.username}</span>
                <LogOut size={12} />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Sub Nav */}
      <nav className="flex gap-8 font-bold uppercase tracking-widest text-[11px] h-12">
        {workspace === 'TILICHO_LABS' ? (
          <>
            <NavItem to="/updates">Internal Updates</NavItem>
            <NavItem to="/slack-post">Slack Post</NavItem>
            <NavItem to="/linkedin-post">LinkedIn Post</NavItem>
          </>
        ) : (
          <>
            <NavItem to="/">Trends</NavItem>
            <NavItem to="/searches">My Searches</NavItem>
            <NavItem to="/insights">Insights</NavItem>
            <NavItem to="/blog-post">Blog Post</NavItem>
            <NavItem to="/linkedin-post">LinkedIn Post</NavItem>
          </>
        )}
      </nav>
    </header>
  );
}

function NavItem({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        cn('flex items-center border-b-2 border-transparent hover:text-black transition-all pt-1',
          isActive ? 'text-black border-black' : 'text-on-surface-variant')
      }
    >
      {children}
    </NavLink>
  );
}
