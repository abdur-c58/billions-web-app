"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchSegmentTimestampsStatus,
  startSegmentTimestamps,
  type ProjectStatus,
} from "@/lib/project";
import {
  DEFAULT_WHISPER_MODEL,
  readStoredWhisperModel,
  storeWhisperModel,
  type WhisperModel,
} from "@/lib/whisper";

export function useWhisperModel() {
  const [whisperModel, setWhisperModelState] = useState<WhisperModel>(DEFAULT_WHISPER_MODEL);

  useEffect(() => {
    setWhisperModelState(readStoredWhisperModel());
  }, []);

  const setWhisperModel = useCallback((model: WhisperModel) => {
    setWhisperModelState(model);
    storeWhisperModel(model);
  }, []);

  return { whisperModel, setWhisperModel };
}

export function useWhisperResegment(onComplete?: () => void | Promise<void>) {
  const { whisperModel, setWhisperModel } = useWhisperModel();
  const [job, setJob] = useState<ProjectStatus["timestamps_job"] | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      window.clearTimeout(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const poll = useCallback(async () => {
    try {
      const next = await fetchSegmentTimestampsStatus();
      setJob(next);
      if (next.status === "running") {
        pollRef.current = window.setTimeout(() => {
          void poll();
        }, 800);
        return;
      }
      setRunning(false);
      if (next.status === "done") {
        await onComplete?.();
      }
      if (next.status === "error") {
        setError(next.error || next.message || "Segmentation failed");
      }
    } catch (err) {
      setRunning(false);
      setError(err instanceof Error ? err.message : "Failed to poll segmentation job");
    }
  }, [onComplete]);

  const resegment = useCallback(
    async (options?: { model?: WhisperModel; retranscribe?: boolean }) => {
      const model = options?.model ?? whisperModel;
      setRunning(true);
      setError(null);
      stopPolling();
      try {
        const snapshot = await startSegmentTimestamps(model, {
          retranscribe: options?.retranscribe ?? true,
        });
        setJob(snapshot);
        await poll();
      } catch (err) {
        setRunning(false);
        setError(err instanceof Error ? err.message : "Failed to start segmentation");
      }
    },
    [poll, stopPolling, whisperModel],
  );

  useEffect(() => () => stopPolling(), [stopPolling]);

  return {
    whisperModel,
    setWhisperModel,
    job,
    running,
    error,
    resegment,
  };
}
