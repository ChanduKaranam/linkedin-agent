import { X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useToast } from '@/context/ToastContext';

export default function ToastViewport() {
  const { toasts, dismissToast } = useToast();

  return (
    <div className="fixed right-4 top-4 z-[90] flex w-[min(360px,calc(100vw-2rem))] flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={cn(
            'flex items-start justify-between gap-3 border px-3 py-2 text-xs shadow-[3px_3px_0px_0px_rgba(0,0,0,1)]',
            toast.kind === 'success' && 'border-green-300 bg-green-50 text-green-900',
            toast.kind === 'error' && 'border-red-300 bg-red-50 text-red-900',
            toast.kind === 'info' && 'border-outline-variant bg-surface-container-lowest text-on-surface',
          )}
        >
          <p className="leading-relaxed">{toast.message}</p>
          <button
            type="button"
            onClick={() => dismissToast(toast.id)}
            className="text-outline hover:text-on-surface transition-colors"
            aria-label="Dismiss notification"
          >
            <X size={12} />
          </button>
        </div>
      ))}
    </div>
  );
}
