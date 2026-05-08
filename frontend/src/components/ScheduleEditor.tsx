import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Settings, X } from 'lucide-react';
import type { ScheduleConfig } from '@/types';

interface ScheduleEditorProps {
  schedule: ScheduleConfig | null;
  onSaved: (newSchedule: ScheduleConfig) => void;
}

export default function ScheduleEditor({ schedule, onSaved }: ScheduleEditorProps) {
  const [open, setOpen] = useState(false);
  const [hour, setHour] = useState(schedule?.hour ?? 4);
  const [minute, setMinute] = useState(schedule?.minute ?? 0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (schedule) { setHour(schedule.hour); setMinute(schedule.minute); }
  }, [schedule]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch('/api/admin/schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hour, minute }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({})) as Record<string, unknown>;
        setError(String(data?.detail ?? 'Could not save — backend unreachable.'));
        return;
      }
      const updated: ScheduleConfig = await res.json();
      onSaved(updated);
      setSaved(true);
      setTimeout(() => { setSaved(false); setOpen(false); }, 1500);
    } catch {
      setError('Network error');
    } finally {
      setSaving(false);
    }
  }

  const displayTime = schedule
    ? `${String(schedule.hour).padStart(2, '0')}:${String(schedule.minute).padStart(2, '0')}`
    : '--:--';
  const tzShort = schedule?.timezone === 'Asia/Kolkata' ? 'IST' : (schedule?.timezone ?? '');

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 px-3 py-1.5 border border-outline-variant bg-surface-container-low text-xs font-bold uppercase tracking-widest hover:border-primary transition-colors"
      >
        <Settings size={12} />
        <span className="font-mono">{displayTime}</span>
        {tzShort && <span className="text-outline">{tzShort}</span>}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.12 }}
            className="absolute right-0 top-full mt-2 w-72 bg-white border-2 border-primary shadow-xl p-6 z-[100]"
          >
            <div className="flex justify-between items-center mb-5">
              <span className="label-bold">Update Schedule</span>
              <button onClick={() => setOpen(false)} className="hover:bg-surface-container p-1 transition-colors">
                <X size={14} />
              </button>
            </div>

            <div className="flex items-center justify-center gap-2 mb-4">
              <div className="flex flex-col items-center gap-1">
                <span className="label-bold text-[9px]">Hour (24h)</span>
                <input
                  type="number"
                  min={0}
                  max={23}
                  value={hour}
                  onChange={(e) => setHour(Number(e.target.value))}
                  className="w-20 bg-surface-container-low border border-outline-variant p-2 text-2xl font-mono text-center outline-none focus:border-primary"
                />
              </div>
              <span className="text-2xl font-bold pt-5 text-outline-variant">:</span>
              <div className="flex flex-col items-center gap-1">
                <span className="label-bold text-[9px]">Min</span>
                <input
                  type="number"
                  min={0}
                  max={59}
                  value={minute}
                  onChange={(e) => setMinute(Number(e.target.value))}
                  className="w-20 bg-surface-container-low border border-outline-variant p-2 text-2xl font-mono text-center outline-none focus:border-primary"
                />
              </div>
            </div>

            <p className="text-[10px] text-outline leading-relaxed mb-3">
              Saves to topics.yaml. Restart to apply to Windows Task Scheduler.
            </p>

            {error && <p className="text-[11px] text-red-600 mb-2">{error}</p>}

            <div className="flex gap-2">
              <button
                onClick={() => setOpen(false)}
                className="flex-1 py-2.5 text-[10px] font-bold uppercase tracking-widest bg-surface-container-high border border-outline-variant hover:bg-surface-dim transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving || saved}
                className="flex-1 py-2.5 text-[10px] font-bold uppercase tracking-widest bg-primary text-on-primary hover:opacity-90 disabled:opacity-50 transition-all"
              >
                {saved ? '✓ Saved' : saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
