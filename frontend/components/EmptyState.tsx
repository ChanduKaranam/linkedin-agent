"use client";

interface EmptyStateProps {
  variant: "unreachable" | "no_run" | "no_trends";
  nextScheduled?: string;
}

export default function EmptyState({ variant, nextScheduled }: EmptyStateProps) {
  const messages: Record<typeof variant, { title: string; body: string }> = {
    unreachable: {
      title: "Agent service is unreachable",
      body: "Make sure the backend is running on port 8000. Start it with: uvicorn backend.api.main:app --port 8000",
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

  return (
    <div className="flex flex-col items-center justify-center min-h-[40vh] text-center px-6">
      <div className="text-5xl mb-4">{variant === "unreachable" ? "⚠️" : "📭"}</div>
      <h2 className="text-xl font-semibold text-gray-800 mb-2">{title}</h2>
      <p className="text-gray-500 max-w-md text-sm">{body}</p>
    </div>
  );
}
