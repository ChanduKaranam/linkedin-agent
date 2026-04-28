"use client";

interface DateSelectorProps {
  dates: string[];
  selectedDate: string;
  onSelect: (date: string) => void;
}

function formatDateLabel(dateStr: string): { primary: string; secondary: string } {
  const d = new Date(dateStr + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const primary = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });

  if (d.getTime() === today.getTime()) return { primary, secondary: "Today" };
  if (d.getTime() === yesterday.getTime()) return { primary, secondary: "Yesterday" };

  return {
    primary,
    secondary: d.toLocaleDateString("en-US", { weekday: "short" }),
  };
}

export default function DateSelector({ dates, selectedDate, onSelect }: DateSelectorProps) {
  if (dates.length === 0) return null;

  return (
    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin scrollbar-thumb-slate-300">
      {dates.map((date) => {
        const isActive = date === selectedDate;
        const { primary, secondary } = formatDateLabel(date);
        return (
          <button
            key={date}
            onClick={() => onSelect(date)}
            className={`
              flex-shrink-0 flex flex-col items-center px-4 py-2 rounded-xl border text-xs font-medium
              transition-all duration-150 min-w-[68px]
              ${isActive
                ? "bg-indigo-600 border-indigo-600 text-white shadow-sm"
                : "bg-white border-slate-200 text-slate-600 hover:border-indigo-300 hover:bg-indigo-50"
              }
            `}
          >
            <span className={`text-[11px] font-semibold ${isActive ? "text-indigo-200" : "text-slate-400"}`}>
              {secondary}
            </span>
            <span className="text-sm font-bold leading-tight">{primary}</span>
          </button>
        );
      })}
    </div>
  );
}
