"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchProjectStatus,
  fetchSegmentTimestampsStatus,
  startSegmentTimestamps,
  uploadAudioFile,
  uploadScriptFile,
  uploadTimestampsFile,
  type ProjectStatus,
} from "@/lib/project";
import { STATUS_POLL_MS, usePolling } from "@/hooks/usePolling";
import { fetchScriptTranscript } from "@/lib/script";

export function useProjectSetup(projectId: string | null) {
  const [status, setStatus] = useState<ProjectStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [audioUploadProgress, setAudioUploadProgress] = useState<number | null>(null);
  const [copyingTranscript, setCopyingTranscript] = useState(false);
  const [transcriptNotice, setTranscriptNotice] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const sessionReady = Boolean(projectId);

  const refresh = useCallback(async () => {
    if (!sessionReady) {
      setStatus(null);
      setLoading(false);
      return null;
    }
    try {
      const next = await fetchProjectStatus();
      setStatus(next);
      setError(null);
      return next;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load project status");
      return null;
    } finally {
      setLoading(false);
    }
  }, [sessionReady]);

  const pollTimestamps = useCallback(async () => {
    try {
      const job = await fetchSegmentTimestampsStatus();
      setStatus((current) => (current ? { ...current, timestamps_job: job } : current));
      if (job.status === "running") {
        pollRef.current = window.setTimeout(() => {
          void pollTimestamps();
        }, 800);
        return;
      }
      if (job.status === "done") {
        await refresh();
      }
      if (job.status === "error") {
        setError(
          job.restart_required
            ? job.error || "Server restarted during segmentation — run Auto-segment again."
            : job.error || job.message || "Timestamp segmentation failed",
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to poll timestamp job");
    }
  }, [refresh]);

  useEffect(() => {
    if (!sessionReady) {
      setLoading(false);
      setStatus(null);
      return;
    }
    setLoading(true);
    void refresh().then((next) => {
      if (next?.timestamps_job.status === "running") {
        void pollTimestamps();
      }
    });
    return () => {
      if (pollRef.current) window.clearTimeout(pollRef.current);
    };
  }, [pollTimestamps, refresh, sessionReady, projectId]);

  usePolling(() => void refresh(), STATUS_POLL_MS, sessionReady);

  const importScript = useCallback(async (file: File) => {
    setBusy(true);
    setError(null);
    setTranscriptNotice(null);
    try {
      const next = await uploadScriptFile(file);
      setStatus(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Script upload failed");
    } finally {
      setBusy(false);
    }
  }, []);

  const importAudio = useCallback(async (file: File) => {
    setBusy(true);
    setError(null);
    setAudioUploadProgress(0);
    try {
      const next = await uploadAudioFile(file, (percent) => setAudioUploadProgress(percent));
      setStatus(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Audio upload failed");
    } finally {
      setBusy(false);
      setAudioUploadProgress(null);
    }
  }, []);

  const segmentTimestamps = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await startSegmentTimestamps();
      await pollTimestamps();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start timestamp segmentation");
    } finally {
      setBusy(false);
    }
  }, [pollTimestamps]);

  const importTimestamps = useCallback(async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const next = await uploadTimestampsFile(file);
      setStatus(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Timestamps import failed");
    } finally {
      setBusy(false);
    }
  }, []);

  const copyTranscript = useCallback(async () => {
    setCopyingTranscript(true);
    setTranscriptNotice(null);
    setError(null);
    try {
      const payload = await fetchScriptTranscript();
      await navigator.clipboard.writeText(payload.transcript);
      setTranscriptNotice(
        `Copied ${payload.segment_count} segments (${payload.word_count.toLocaleString()} words) to clipboard.`,
      );
      return payload;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to copy transcript");
      return null;
    } finally {
      setCopyingTranscript(false);
    }
  }, []);

  return {
    status,
    loading,
    busy,
    error,
    refresh,
    importScript,
    importAudio,
    importTimestamps,
    segmentTimestamps,
    copyTranscript,
    copyingTranscript,
    transcriptNotice,
    viewerReady: Boolean(status?.viewer_ready),
    audioUploadProgress,
  };
}
