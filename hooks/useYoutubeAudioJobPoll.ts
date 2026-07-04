"use client";

import { useEffect, useRef, useState } from "react";
import { fetchYoutubeAudioJob, type YoutubeAudioJob } from "@/lib/youtube-audio";
import { STATUS_POLL_MS } from "@/hooks/usePolling";

export function useYoutubeAudioJobPoll(jobId: string | null, enabled = true) {
  const [job, setJob] = useState<YoutubeAudioJob | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled || !jobId) {
      setJob(null);
      return;
    }

    let cancelled = false;

    const poll = async () => {
      try {
        const next = await fetchYoutubeAudioJob(jobId);
        if (cancelled) return;
        setJob(next);
        if (next.status === "running") {
          timerRef.current = window.setTimeout(poll, STATUS_POLL_MS);
        }
      } catch {
        if (!cancelled) {
          timerRef.current = window.setTimeout(poll, STATUS_POLL_MS);
        }
      }
    };

    void poll();

    return () => {
      cancelled = true;
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [enabled, jobId]);

  return job;
}
