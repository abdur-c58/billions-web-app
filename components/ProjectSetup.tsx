"use client";

import { FileAudio, FileJson, FileStack, Loader2, Sparkles } from "lucide-react";
import { SegmentationHardwarePanel } from "@/components/SegmentationHardwarePanel";
import type { useProjectSetup } from "@/hooks/useProjectSetup";
import type { ProjectStatus } from "@/lib/project";

function formatLogTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function TimestampJobLogs({ job }: { job?: ProjectStatus["timestamps_job"] }) {
  const logs = job?.logs ?? [];
  if (!logs.length) return null;

  return (
    <div className="mt-4 rounded-[10px] border border-[var(--border)] bg-[var(--surface-raised)]">
      <div className="border-b border-[var(--border)] px-3 py-2 text-xs font-medium text-[var(--muted)]">
        Segmentation log
      </div>
      <pre className="max-h-48 overflow-auto px-3 py-2 font-mono text-[11px] leading-5 text-[var(--foreground)]">
        {logs.map((entry, index) => (
          <span key={`${entry.ts}-${index}`} className="block">
            [{formatLogTime(entry.ts)}] {entry.progress_percent}% · {entry.stage}: {entry.message}
          </span>
        ))}
      </pre>
      {job?.error ? (
        <p className="border-t border-[rgba(255,107,107,0.35)] bg-[rgba(255,107,107,0.08)] px-3 py-2 text-xs text-[#ffc9c9]">
          {job.error}
        </p>
      ) : null}
    </div>
  );
}

type ProjectSetupProps = {
  setup: ReturnType<typeof useProjectSetup>;
  onBackToProjects?: () => void;
};

export function ProjectSetup({ setup, onBackToProjects }: ProjectSetupProps) {

  const step = setup.status?.next_step ?? "import_script";
  const timestampsRunning = setup.status?.timestamps_job.status === "running";
  const restartRequired = Boolean(setup.status?.timestamps_job.restart_required);
  const segmentProgress = Math.min(
    100,
    Math.max(0, setup.status?.timestamps_job.progress_percent ?? 0),
  );
  const isWhisperStage =
    timestampsRunning && setup.status?.timestamps_job.stage === "whisper";

  return (
    <section className="page-container flex min-h-[calc(100vh-3.5rem)] w-full flex-col justify-center py-10">
      <div className="glow-card w-full p-6 lg:p-8">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.12em] text-[var(--muted)]">Project setup</p>
            <h2 className="glow-title mt-2 text-3xl font-bold tracking-tight">
              Import script and narration
            </h2>
          </div>
          {onBackToProjects ? (
            <button
              type="button"
              className="glow-btn-secondary shrink-0 self-start rounded-[10px] px-3.5 py-2.5 text-sm font-semibold"
              onClick={onBackToProjects}
            >
              All projects
            </button>
          ) : null}
        </div>
        <p className="mt-3 text-[0.95rem] leading-7 text-[var(--muted)]">
          Load <code className="text-[var(--foreground)]">script.json</code>, then{" "}
          <code className="text-[var(--foreground)]">script.mp3</code>, then either import an
          existing <code className="text-[var(--foreground)]">segment_timestamps.json</code> or run
          Whisper alignment. The b-roll viewer unlocks after all three steps.
        </p>

        <ol className="mt-8 space-y-4">
          <li className={`glow-setup-step ${setup.status?.script_uploaded ? "is-done" : step === "import_script" ? "is-active" : ""}`}>
            <div className="flex items-center gap-3">
              <FileJson className="h-5 w-5 text-[var(--accent)]" />
              <div className="flex-1">
                <p className="font-semibold">1. Import script.json</p>
                <p className="text-sm text-[var(--muted)]">
                  {setup.status?.script_uploaded
                    ? setup.status.title || "Script uploaded"
                    : "Upload your documentary script JSON."}
                </p>
              </div>
              <label className="glow-btn-secondary cursor-pointer rounded-[10px] px-3.5 py-2.5 text-sm font-semibold">
                Choose file
                <input
                  type="file"
                  accept=".json,application/json"
                  className="hidden"
                  disabled={setup.busy || timestampsRunning}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void setup.importScript(file);
                  }}
                />
              </label>
            </div>
          </li>

          <li className={`glow-setup-step ${setup.status?.audio_uploaded ? "is-done" : step === "import_audio" ? "is-active" : ""}`}>
            <div className="flex items-center gap-3">
              <FileAudio className="h-5 w-5 text-[var(--accent)]" />
              <div className="flex-1">
                <p className="font-semibold">2. Import script.mp3</p>
                <p className="text-sm text-[var(--muted)]">
                  {setup.status?.audio_uploaded
                    ? "Narration audio uploaded"
                    : "Upload the narration MP3 that matches the script."}
                </p>
              </div>
              <label
                className={`glow-btn-secondary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold ${
                  setup.status?.script_uploaded ? "cursor-pointer" : "cursor-not-allowed opacity-50"
                }`}
              >
                Choose file
                <input
                  type="file"
                  accept=".mp3,audio/mpeg,audio/mp3"
                  className="hidden"
                  disabled={!setup.status?.script_uploaded || setup.busy || timestampsRunning}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void setup.importAudio(file);
                  }}
                />
              </label>
            </div>
          </li>

          <li className={`glow-setup-step ${setup.status?.timestamps_ready ? "is-done" : step === "segment_timestamps" ? "is-active" : ""}`}>
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <div className="flex flex-1 items-start gap-3">
                  <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-[var(--accent)]" />
                  <div className="flex-1">
                    <p className="font-semibold">3. Segment timestamps</p>
                    <p className="text-sm text-[var(--muted)]">
                      {timestampsRunning
                        ? setup.status?.timestamps_job.message || "Aligning segments with Whisper…"
                        : restartRequired
                          ? "Segmentation was interrupted — click Auto-segment to run it again."
                          : setup.status?.timestamps_ready
                            ? `${setup.status.aligned_segments}/${setup.status.segment_count} segments ready`
                            : "Generate timestamps with Whisper or import an existing JSON file."}
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 sm:shrink-0">
                <label
                  className={`glow-btn-secondary inline-flex cursor-pointer items-center gap-2 px-3.5 py-2.5 text-sm font-semibold ${
                    !setup.status?.script_uploaded || !setup.status?.audio_uploaded || setup.busy || timestampsRunning
                      ? "cursor-not-allowed opacity-50"
                      : ""
                  }`}
                >
                  <FileStack className="h-4 w-4" />
                  Import JSON
                  <input
                    type="file"
                    accept=".json,application/json"
                    className="hidden"
                    disabled={
                      !setup.status?.script_uploaded ||
                      !setup.status?.audio_uploaded ||
                      setup.busy ||
                      timestampsRunning
                    }
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void setup.importTimestamps(file);
                    }}
                  />
                </label>
                <button
                  type="button"
                  className="glow-btn-primary inline-flex items-center gap-2 px-3.5 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-55"
                  disabled={
                    !setup.status?.script_uploaded ||
                    !setup.status?.audio_uploaded ||
                    setup.busy ||
                    timestampsRunning
                  }
                  onClick={() => void setup.segmentTimestamps()}
                >
                  {timestampsRunning ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Running…
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" />
                      Auto-segment
                    </>
                  )}
                </button>
              </div>
              </div>

              {restartRequired && !timestampsRunning ? (
                <div className="sm:pl-8">
                  <div className="rounded-[10px] border border-[rgba(255,193,7,0.45)] bg-[rgba(255,193,7,0.1)] px-4 py-3 text-sm text-[#ffe8a3]">
                    <p>
                      {setup.status?.timestamps_job.error ||
                        "The server restarted while segmenting. Whisper cache and any partial timestamps were cleared to avoid corrupt files."}
                    </p>
                    <p className="mt-2 font-semibold text-[var(--foreground)]">
                      Not running anymore — click <span className="text-[var(--accent)]">Auto-segment</span>{" "}
                      above to start a new run.
                    </p>
                  </div>
                  <TimestampJobLogs job={setup.status?.timestamps_job} />
                </div>
              ) : timestampsRunning || (setup.status?.timestamps_job.logs?.length ?? 0) > 0 ? (
                <div className="sm:pl-8">
                  <div className="flex items-center justify-between gap-3 text-xs text-[var(--muted)]">
                    <span className="capitalize">
                      {setup.status?.timestamps_job.stage?.replace(/_/g, " ") || "Running"}
                    </span>
                    <span className="tabular-nums">
                      {setup.status?.timestamps_job.progress_percent ?? 0}%
                    </span>
                  </div>
                  <div className="mt-2">
                    {isWhisperStage ? (
                      <div className="whisper-progress-outer">
                        <div className="whisper-progress-track">
                          <div
                            className="whisper-progress-fill-group"
                            style={{ width: `${segmentProgress}%` }}
                          >
                            <div className="whisper-progress-fill-ambient" aria-hidden="true" />
                            <div className="whisper-progress-fill" />
                          </div>
                          <div
                            className="whisper-progress-shimmer-layer"
                            style={{ width: `${segmentProgress}%` }}
                          >
                            <span className="whisper-progress-shimmer-beam" aria-hidden="true" />
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="h-2 overflow-hidden rounded-full bg-[var(--surface-raised)]">
                        <div
                          className="h-full rounded-full bg-[var(--accent)] transition-[width] duration-300"
                          style={{ width: `${segmentProgress}%` }}
                        />
                      </div>
                    )}
                  </div>
                  {isWhisperStage ? (
                    <p className="mt-2 text-xs text-[var(--muted)]">
                      Whisper is transcribing your narration — progress updates every few seconds.
                    </p>
                  ) : null}
                  <SegmentationHardwarePanel
                    hardware={setup.status?.timestamps_job.hardware}
                    idleProbe={false}
                  />
                  <TimestampJobLogs job={setup.status?.timestamps_job} />
                </div>
              ) : step === "segment_timestamps" ? (
                <div className="sm:pl-8">
                  <SegmentationHardwarePanel idleProbe />
                </div>
              ) : null}
            </div>
          </li>
        </ol>

        {setup.loading ? (
          <p className="mt-6 inline-flex items-center gap-2 text-sm text-[var(--muted)]">
            <Loader2 className="h-4 w-4 animate-spin" />
            Checking project status…
          </p>
        ) : null}

        {setup.error ? (
          <p className="mt-6 rounded-[10px] border border-[rgba(255,107,107,0.35)] bg-[rgba(255,107,107,0.08)] px-4 py-3 text-sm text-[#ffc9c9]">
            {setup.error}
          </p>
        ) : null}
      </div>
    </section>
  );
}
