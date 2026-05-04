interface EmptyStateProps {
  variant: 'unreachable' | 'no_run' | 'no_trends';
  nextScheduled?: string;
}

export default function EmptyState({ variant, nextScheduled }: EmptyStateProps) {
  const messages: Record<typeof variant, { title: string; body: string }> = {
    unreachable: {
      title: 'Agent service is unreachable',
      body: 'Make sure the backend is running on port 8000. Start it with: uvicorn backend.api.main:app --port 8000',
    },
    no_run: {
      title: "No trends yet today",
      body: nextScheduled
        ? `The agent runs at ${nextScheduled}. To trigger a run now, set DEBUG=true and POST /admin/run-now.`
        : "The agent hasn't run yet. Set DEBUG=true in .env and POST to /admin/run-now to trigger manually.",
    },
    no_trends: {
      title: "Today's scan found no trends",
      body: "The pipeline completed but couldn't cluster any trends. This can happen if sources were all blocked or too short. Try again tomorrow or check logs.",
    },
  };

  const { title, body } = messages[variant];
  const icon = variant === 'unreachable' ? '⚠' : '□';

  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] text-center px-8 gap-6">
      <div className="w-16 h-16 border-2 border-outline-variant flex items-center justify-center">
        <span className="text-2xl font-mono text-on-surface-variant">{icon}</span>
      </div>
      <div className="max-w-md">
        <h2 className="text-xl font-bold uppercase tracking-tight mb-3">{title}</h2>
        <p className="text-sm text-on-surface-variant leading-relaxed font-mono">{body}</p>
      </div>
    </div>
  );
}
