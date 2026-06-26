"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { FlaggedClip } from "@/lib/types";

export default function FlaggedPage() {
  const [clips, setClips] = useState<FlaggedClip[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const loadFlagged = useCallback(async () => {
    try {
      const payload = await apiFetch<{ clips: FlaggedClip[] }>("/api/flagged");
      setClips(payload.clips || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load flagged clips");
    }
  }, []);

  useEffect(() => {
    void loadFlagged();
  }, [loadFlagged]);

  const unflag = async (key: string) => {
    setBusyKey(key);
    try {
      await apiFetch("/api/flagged/unflag", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key }),
      });
      await loadFlagged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unflag clip");
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <main className="page-container w-full py-6 text-[var(--foreground)]">
      <div className="w-full">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Flagged clips</h1>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Clips flagged here are excluded from all future b-roll fetches.
            </p>
          </div>
          <Link
            href="/"
            className="glow-btn-secondary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold"
          >
            Back to viewer
          </Link>
        </div>

        {error ? <p className="mb-4 text-sm text-[#ffc9c9]">{error}</p> : null}

        {clips.length === 0 ? (
          <div className="glow-card rounded-[14px] p-8 text-center text-[var(--muted)]">
            No flagged clips yet.
          </div>
        ) : (
          <div className="grid gap-3">
            {clips.map((clip) => (
              <article
                key={clip.key}
                className="glow-card glow-card-flagged flex flex-col gap-4 rounded-[14px] p-4 sm:flex-row sm:items-center"
              >
                <div className="glow-video-frame aspect-video w-full max-w-[220px] overflow-hidden rounded-[10px] bg-black">
                  {clip.thumbnail ? (
                    <img
                      src={clip.thumbnail}
                      alt=""
                      className="block h-full w-full object-cover"
                    />
                  ) : (
                    <div className="grid h-full place-items-center text-xs text-[var(--muted)]">
                      No thumbnail
                    </div>
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="glow-chip glow-chip-flagged px-2 py-0.5 text-[0.72rem] font-semibold">
                      Flagged
                    </span>
                    <span className="text-sm text-[var(--muted)]">
                      {clip.provider || "unknown"}
                      {clip.video_id != null ? ` · #${clip.video_id}` : ""}
                    </span>
                  </div>
                  {clip.photographer ? (
                    <p className="mt-1 text-sm text-[var(--foreground)]">{clip.photographer}</p>
                  ) : null}
                  {clip.segment_ids?.length ? (
                    <p className="mt-2 text-sm text-[var(--muted)]">
                      Used in segments: {clip.segment_ids.map((id) => `#${id}`).join(", ")}
                    </p>
                  ) : (
                    <p className="mt-2 text-sm text-[var(--muted)]">Not currently selected</p>
                  )}
                </div>
                <button
                  type="button"
                  disabled={busyKey === clip.key}
                  onClick={() => void unflag(clip.key)}
                  className="glow-btn-secondary shrink-0 rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:opacity-55"
                >
                  {busyKey === clip.key ? "Removing…" : "Unflag"}
                </button>
              </article>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
