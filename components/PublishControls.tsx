"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { markPublished } from "@/lib/publish";

const REFRESH_MS = 30_000;

/** Re-renders the server page periodically so new exports appear without a reload. */
export function PublishAutoRefresh() {
  const router = useRouter();
  useEffect(() => {
    const timer = window.setInterval(() => router.refresh(), REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [router]);
  return null;
}

export function MarkPublishedButton({
  projectId,
  published,
}: {
  projectId: string;
  published: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  const handleClick = async () => {
    setBusy(true);
    setError(null);
    try {
      await markPublished(projectId, !published);
      startTransition(() => router.refresh());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update publish status");
    } finally {
      setBusy(false);
    }
  };

  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        data-action={published ? "unmark-published" : "mark-published"}
        onClick={() => void handleClick()}
        disabled={busy}
        className="inline-flex items-center gap-1.5 rounded-[8px] border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--muted)] transition-colors hover:text-[var(--foreground)] disabled:opacity-55"
      >
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
        {published ? "Undo published" : "Mark as published"}
      </button>
      {error ? <span className="text-xs text-red-400">{error}</span> : null}
    </span>
  );
}
