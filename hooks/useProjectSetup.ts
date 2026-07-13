"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  cancelAudioGeneration,
  fetchAudioGenerationStatus,
  fetchProjectStatus,
  fetchSegmentTimestampsStatus,
  startAudioGeneration,
  startSegmentTimestamps,
  uploadAudioFile,
  uploadScriptPayload,
  uploadTimestampsFile,
  type ProjectStatus,
  type ScriptSummary,
  type TranscriptPreview,
} from "@/lib/project";
import { STATUS_POLL_MS, usePolling } from "@/hooks/usePolling";
import { fetchScriptTranscript, prepareScriptImport } from "@/lib/script";
import { useWhisperModel } from "@/hooks/useWhisperResegment";

const AUTO_TTS_DELAY_SECONDS = 10;
const TTS_POLL_MS = 2000;

export function useProjectSetup(projectId: string | null) {
  const [status, setStatus] = useState<ProjectStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { whisperModel, setWhisperModel } = useWhisperModel();
  const [audioUploadProgress, setAudioUploadProgress] = useState<number | null>(null);
  const [copyingTranscript, setCopyingTranscript] = useState(false);
  const [transcriptNotice, setTranscriptNotice] = useState<string | null>(null);
  const [transcriptPreview, setTranscriptPreview] = useState<TranscriptPreview | null>(null);
  const [scriptSummary, setScriptSummary] = useState<ScriptSummary | null>(null);
  const [autoTtsCountdown, setAutoTtsCountdown] = useState<number | null>(null);
  const pollRef = useRef<number | null>(null);
  const ttsPollRef = useRef<number | null>(null);
  const countdownRef = useRef<number | null>(null);
  const autoTtsStartedRef = useRef(false);
  const manualAudioChosenRef = useRef(false);
  const statusRef = useRef<ProjectStatus | null>(null);

  const sessionReady = Boolean(projectId);

  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  const refresh = useCallback(async () => {
    if (!sessionReady) {
      setStatus(null);
      setLoading(false);
      return null;
    }
    try {
      const next = await fetchProjectStatus();
      setStatus(next);
      if (next.script_summary) {
        setScriptSummary(next.script_summary);
      }
      if (next.transcript_preview) {
        setTranscriptPreview(next.transcript_preview);
      }
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

  const pollTts = useCallback(async () => {
    try {
      const job = await fetchAudioGenerationStatus();
      setStatus((current) => (current ? { ...current, tts_job: job } : current));
      if (job.status === "running") {
        ttsPollRef.current = window.setTimeout(() => {
          void pollTts();
        }, TTS_POLL_MS);
        return;
      }
      if (job.status === "done") {
        await refresh();
        if (statusRef.current?.timestamps_job.status === "running") {
          await pollTimestamps();
        } else {
          const tsJob = await fetchSegmentTimestampsStatus();
          if (tsJob.status === "running") {
            setStatus((current) => (current ? { ...current, timestamps_job: tsJob } : current));
            await pollTimestamps();
          }
        }
      }
      if (job.status === "error") {
        const cancelled =
          manualAudioChosenRef.current &&
          (job.error?.toLowerCase().includes("cancel") ||
            job.message?.toLowerCase().includes("cancel"));
        if (!cancelled) {
          setError(
            job.restart_required
              ? job.error || "Server restarted during narration generation — try again."
              : job.error || job.message || "Narration generation failed",
          );
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to poll narration job");
    }
  }, [pollTimestamps, refresh]);

  const clearAutoTtsCountdown = useCallback(() => {
    if (countdownRef.current) {
      window.clearInterval(countdownRef.current);
      countdownRef.current = null;
    }
    setAutoTtsCountdown(null);
  }, []);

  const beginAutoTtsCountdown = useCallback(() => {
    clearAutoTtsCountdown();
    autoTtsStartedRef.current = false;
    manualAudioChosenRef.current = false;
    let remaining = AUTO_TTS_DELAY_SECONDS;
    setAutoTtsCountdown(remaining);
    countdownRef.current = window.setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        clearAutoTtsCountdown();
        if (
          autoTtsStartedRef.current ||
          statusRef.current?.audio_uploaded ||
          manualAudioChosenRef.current
        ) {
          return;
        }
        autoTtsStartedRef.current = true;
        void (async () => {
          try {
            setError(null);
            await startAudioGeneration();
            await pollTts();
          } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to start narration generation");
          }
        })();
        return;
      }
      setAutoTtsCountdown(remaining);
    }, 1000);
  }, [clearAutoTtsCountdown, pollTts]);

  const loadTranscriptPreview = useCallback(async () => {
    try {
      const payload = await fetchScriptTranscript();
      setTranscriptPreview(payload);
      await navigator.clipboard.writeText(payload.transcript);
      setTranscriptNotice(
        `Copied ${payload.segment_count} segments (${payload.word_count.toLocaleString()} words) to clipboard.`,
      );
      return payload;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load transcript");
      return null;
    }
  }, []);

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
      if (next?.tts_job.status === "running") {
        void pollTts();
      }
      if (next?.script_summary) {
        setScriptSummary(next.script_summary);
      }
      if (next?.transcript_preview) {
        setTranscriptPreview(next.transcript_preview);
      }
    });
    return () => {
      if (pollRef.current) window.clearTimeout(pollRef.current);
      if (ttsPollRef.current) window.clearTimeout(ttsPollRef.current);
      clearAutoTtsCountdown();
    };
  }, [clearAutoTtsCountdown, pollTimestamps, pollTts, refresh, sessionReady, projectId]);

  usePolling(() => void refresh(), STATUS_POLL_MS, sessionReady);

  const finishScriptImport = useCallback(
    async (next: ProjectStatus) => {
      setStatus(next);
      if (next.script_summary) {
        setScriptSummary(next.script_summary);
      }
      if (next.transcript_preview) {
        setTranscriptPreview(next.transcript_preview);
      }
      await loadTranscriptPreview();
      if (!next.audio_uploaded) {
        beginAutoTtsCountdown();
      }
    },
    [beginAutoTtsCountdown, loadTranscriptPreview],
  );

  const importScript = useCallback(async (file: File) => {
    setBusy(true);
    setError(null);
    setTranscriptNotice(null);
    clearAutoTtsCountdown();
    manualAudioChosenRef.current = false;
    autoTtsStartedRef.current = false;
    try {
      const raw = await file.text();
      const parsed = prepareScriptImport(raw);
      const next = await uploadScriptPayload(parsed);
      await finishScriptImport(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Script upload failed");
    } finally {
      setBusy(false);
    }
  }, [clearAutoTtsCountdown, finishScriptImport]);

  const importScriptJson = useCallback(
    async (raw: string): Promise<string | null> => {
      setBusy(true);
      setError(null);
      setTranscriptNotice(null);
      clearAutoTtsCountdown();
      manualAudioChosenRef.current = false;
      autoTtsStartedRef.current = false;
      try {
        const parsed = prepareScriptImport(raw);
        const next = await uploadScriptPayload(parsed);
        await finishScriptImport(next);
        return null;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Script import failed";
        return message;
      } finally {
        setBusy(false);
      }
    },
    [clearAutoTtsCountdown, finishScriptImport],
  );

  const importAudio = useCallback(async (file: File) => {
    setBusy(true);
    setError(null);
    manualAudioChosenRef.current = true;
    clearAutoTtsCountdown();
    setAudioUploadProgress(0);
    try {
      const currentTts = statusRef.current?.tts_job.status;
      if (currentTts === "running") {
        await cancelAudioGeneration("Manual audio upload cancelled generation.");
      }
      const next = await uploadAudioFile(file, (percent) => setAudioUploadProgress(percent));
      setStatus(next);
      setTranscriptNotice("Using uploaded narration MP3.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Audio upload failed");
    } finally {
      setBusy(false);
      setAudioUploadProgress(null);
    }
  }, [clearAutoTtsCountdown]);

  const segmentTimestamps = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await startSegmentTimestamps(whisperModel, { retranscribe: false });
      await pollTimestamps();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start timestamp segmentation");
    } finally {
      setBusy(false);
    }
  }, [pollTimestamps, whisperModel]);

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
      setTranscriptPreview(payload);
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
    importScriptJson,
    importAudio,
    importTimestamps,
    segmentTimestamps,
    copyTranscript,
    copyingTranscript,
    transcriptNotice,
    transcriptPreview,
    scriptSummary,
    autoTtsCountdown,
    viewerReady: Boolean(status?.viewer_ready),
    audioUploadProgress,
    whisperModel,
    setWhisperModel,
  };
}
