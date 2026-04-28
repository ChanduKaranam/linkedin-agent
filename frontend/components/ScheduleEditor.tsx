"use client";

import { useState, useRef, useEffect } from "react";
import type { ScheduleConfig } from "@/types";

interface ScheduleEditorProps {
  schedule: ScheduleConfig | null;
  onSaved: (newSchedule: ScheduleConfig) => void;
}

export default function ScheduleEditor({ schedule, onSaved }: ScheduleEditorProps) {
  const [open, setOpen] = useState(false);
  const [hour, setHour] = useState(schedule?.hour ?? 17);
  const [minute, setMinute] = useState(schedule?.minute ?? 35);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (schedule) {
      setHour(schedule.hour);
      setMinute(schedule.minute);
    }
  }, [schedule]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/admin/schedule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hour, minute }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data?.detail ?? "Could not save. Is DEBUG=true set?");
        return;
      }
      const updated: ScheduleConfig = await res.json();
      onSaved(updated);
      setSaved(true);
      setTimeout(() => { setSaved(false); setOpen(false); }, 1500);
    } catch {
      setError("Network error");
    } finally {
      setSaving(false);
    }
  }

  const displayTime = schedule
    ? `${String(schedule.hour).padStart(2, "0")}:${String(schedule.minute).padStart(2, "0")}`
    : "--:--";

  const tzShort = schedule?.timezone === "Asia/Kolkata" ? "IST" : (schedule?.timezone ?? "");

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={`
          flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
          ${open
            ? "bg-indigo-100 text-indigo-700"
            : "bg-slate-100 text-slate-600 hover:bg-slate-200"
          }
        `}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        Daily {displayTime} {tzShort}
        <svg className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-64 bg-white rounded-xl shadow-lg border border-slate-200 p-4 z-50">
          <p className="text-xs font-semibold text-slate-700 mb-3">Update schedule</p>

          <div className="flex gap-2 items-center mb-3">
            <div className="flex-1">
              <label className="text-[10px] text-slate-400 font-medium uppercase tracking-wide">Hour</label>
              <input
                type="number"
                min={0}
                max={23}
                value={hour}
                onChange={(e) => setHour(Number(e.target.value))}
                className="w-full mt-1 px-2.5 py-1.5 text-sm font-semibold text-slate-900 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
            <span className="text-slate-400 font-bold mt-4">:</span>
            <div className="flex-1">
              <label className="text-[10px] text-slate-400 font-medium uppercase tracking-wide">Minute</label>
              <input
                type="number"
                min={0}
                max={59}
                value={minute}
                onChange={(e) => setMinute(Number(e.target.value))}
                className="w-full mt-1 px-2.5 py-1.5 text-sm font-semibold text-slate-900 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
          </div>

          <p className="text-[10px] text-slate-400 mb-3 leading-relaxed">
            Saves to topics.yaml. Requires DEBUG=true. Restart to apply to Windows Task Scheduler.
          </p>

          {error && <p className="text-[11px] text-red-500 mb-2">{error}</p>}

          <button
            onClick={handleSave}
            disabled={saving || saved}
            className={`
              w-full py-1.5 rounded-lg text-xs font-semibold transition-colors
              ${saved
                ? "bg-emerald-500 text-white"
                : "bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-50"
              }
            `}
          >
            {saved ? "Saved!" : saving ? "Saving…" : "Save"}
          </button>
        </div>
      )}
    </div>
  );
}
