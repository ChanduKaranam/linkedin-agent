import { cn } from '@/lib/utils';

interface DateSelectorProps {
  dates: string[];
  selectedDate: string;
  onSelect: (date: string) => void;
}

function formatDateLabel(dateStr: string): { primary: string; secondary: string } {
  const d = new Date(dateStr + 'T00:00:00');
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const primary = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  if (d.getTime() === today.getTime()) return { primary, secondary: 'Today' };
  if (d.getTime() === yesterday.getTime()) return { primary, secondary: 'Yesterday' };
  return { primary, secondary: d.toLocaleDateString('en-US', { weekday: 'short' }) };
}

export default function DateSelector({ dates, selectedDate, onSelect }: DateSelectorProps) {
  if (dates.length === 0) return null;
  return (
    <div className="flex gap-2 overflow-x-auto pb-1">
      {dates.map((date) => {
        const isActive = date === selectedDate;
        const { primary, secondary } = formatDateLabel(date);
        return (
          <button
            key={date}
            onClick={() => onSelect(date)}
            className={cn(
              'flex-shrink-0 flex flex-col items-center px-4 py-2 border text-xs font-medium transition-all min-w-[68px]',
              isActive
                ? 'bg-primary border-primary text-on-primary'
                : 'bg-surface-container-lowest border-outline-variant text-on-surface-variant hover:border-primary hover:bg-surface-container-low',
            )}
          >
            <span className={cn('text-[11px] font-bold uppercase tracking-widest', isActive ? 'text-on-primary opacity-70' : 'text-outline')}>
              {secondary}
            </span>
            <span className="text-sm font-black leading-tight font-mono">{primary}</span>
          </button>
        );
      })}
    </div>
  );
}
