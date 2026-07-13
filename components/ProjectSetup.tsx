"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Copy, FileAudio, FileJson, FileStack, Loader2, Mic2, Sparkles, X } from "lucide-react";
import { SegmentationAlignmentSummary } from "@/components/SegmentationAlignmentSummary";
import { SegmentationHardwarePanel } from "@/components/SegmentationHardwarePanel";
import { WhisperModelSelect } from "@/components/WhisperModelSelect";
import type { useProjectSetup } from "@/hooks/useProjectSetup";
import type { ProjectStatus, ScriptSummary, TimestampAlignment } from "@/lib/project";
import { looksLikeScriptJson } from "@/lib/script";

function formatLogTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function JobLogsPanel({
  title,
  job,
}: {
  title: string;
  job?: ProjectStatus["timestamps_job"] | ProjectStatus["tts_job"];
}) {
  const logs = job?.logs ?? [];
  if (!logs.length && !job?.error) return null;

  return (
    <div className="mt-4 rounded-[10px] border border-[var(--border)] bg-[var(--surface-raised)]">
      <div className="border-b border-[var(--border)] px-3 py-2 text-xs font-medium text-[var(--muted)]">
        {title}
      </div>
      {logs.length ? (
        <pre className="max-h-48 overflow-auto px-3 py-2 font-mono text-[11px] leading-5 text-[var(--foreground)]">
          {logs.map((entry, index) => (
            <span key={`${entry.ts}-${index}`} className="block">
              [{formatLogTime(entry.ts)}] {entry.progress_percent}% · {entry.stage}: {entry.message}
            </span>
          ))}
        </pre>
      ) : null}
      {job?.error ? (
        <p className="border-t border-[rgba(255,107,107,0.35)] bg-[rgba(255,107,107,0.08)] px-3 py-2 text-xs text-[#ffc9c9]">
          {job.error}
        </p>
      ) : null}
    </div>
  );
}

function TimestampJobLogs({ job }: { job?: ProjectStatus["timestamps_job"] }) {
  return <JobLogsPanel title="Segmentation log" job={job} />;
}

function TtsJobLogs({ job }: { job?: ProjectStatus["tts_job"] }) {
  return <JobLogsPanel title="Narration generation log" job={job} />;
}

function ScriptSummaryPanel({
  summary,
  remotionRuntimeReady,
}: {
  summary: ScriptSummary;
  remotionRuntimeReady?: boolean;
}) {
  return (
    <div className="sm:pl-8">
      <div className="rounded-[10px] border border-[var(--border)] bg-[var(--surface-raised)] px-4 py-3">
        <dl className="space-y-2 text-sm">
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">Video title</dt>
            <dd className="mt-0.5 font-medium text-[var(--foreground)]">{summary.title || "Untitled"}</dd>
          </div>
          {summary.channel ? (
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">Channel</dt>
              <dd className="mt-0.5 text-[var(--foreground)]">{summary.channel}</dd>
            </div>
          ) : null}
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">Script stats</dt>
            <dd className="mt-0.5 text-[var(--muted)]">
              {summary.beat_count} beat{summary.beat_count === 1 ? "" : "s"} ·{" "}
              {summary.segment_count} segment{summary.segment_count === 1 ? "" : "s"} ·{" "}
              {summary.word_count.toLocaleString()} words · {summary.estimated_duration_label} at{" "}
              {summary.wpm ?? 145} wpm
            </dd>
          </div>
        </dl>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <p
            className={`inline-flex items-center gap-1.5 text-xs font-medium ${
              summary.script_format === "folder" ? "text-emerald-300" : "text-[var(--muted)]"
            }`}
          >
            {summary.script_format === "folder" ? (
              <Check className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            ) : (
              <X className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            )}
            Folder fetch
          </p>
          <p
            className={`inline-flex items-center gap-1.5 text-xs font-medium ${
              summary.remotion?.detected ? "text-violet-300" : "text-[var(--muted)]"
            }`}
          >
            {summary.remotion?.detected ? (
              <Sparkles className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            ) : (
              <X className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            )}
            Remotion
            {summary.remotion?.detected
              ? ` · ${summary.remotion.segment_count} scene${
                  summary.remotion.segment_count === 1 ? "" : "s"
                } (${summary.remotion.compositions.join(", ")})`
              : ""}
          </p>
        </div>
        {summary.remotion?.detected && remotionRuntimeReady === false ? (
          <p className="mt-2 text-xs text-amber-200">
            Run <code className="text-[var(--foreground)]">npm install</code> in{" "}
            <code className="text-[var(--foreground)]">remotion/</code> before export.
          </p>
        ) : null}
      </div>
    </div>
  );
}

type ProjectSetupProps = {
  setup: ReturnType<typeof useProjectSetup>;
  onBackToProjects?: () => void;
};

function resolveTimestampAlignment(status: ProjectStatus | null): TimestampAlignment | null {
  if (!status) return null;
  if (status.timestamp_alignment) return status.timestamp_alignment;
  const fromJob = status.timestamps_job.alignment_summary;
  if (fromJob) return fromJob;
  if (!status.timestamps_ready || !status.segment_count) return null;
  return {
    total_segments: status.segment_count,
    aligned_segments: status.aligned_segments,
    timed_segments: status.timed_segments ?? status.aligned_segments,
  };
}

export function ProjectSetup({ setup, onBackToProjects }: ProjectSetupProps) {
  const [pasteJson, setPasteJson] = useState("");
  const [pasteError, setPasteError] = useState<string | null>(null);
  const [pasteImporting, setPasteImporting] = useState(false);
  const setupCardRef = useRef<HTMLDivElement>(null);

  const step = setup.status?.next_step ?? "import_script";
  const ttsRunning = setup.status?.tts_job.status === "running";
  const ttsRestartRequired = Boolean(setup.status?.tts_job.restart_required);
  const timestampsRunning = setup.status?.timestamps_job.status === "running";
  const timestampsDone = setup.status?.timestamps_job.status === "done";
  const restartRequired = Boolean(setup.status?.timestamps_job.restart_required);
  const alignmentSummary = resolveTimestampAlignment(setup.status);
  const ttsProgress = Math.min(100, Math.max(0, setup.status?.tts_job.progress_percent ?? 0));
  const segmentProgress = Math.min(
    100,
    Math.max(0, setup.status?.timestamps_job.progress_percent ?? 0),
  );
  const isWhisperStage =
    timestampsRunning && setup.status?.timestamps_job.stage === "whisper";
  const segmentControlsDisabled =
    !setup.status?.script_uploaded ||
    !setup.status?.audio_uploaded ||
    setup.busy ||
    timestampsRunning ||
    ttsRunning;
  const audioControlsDisabled =
    !setup.status?.script_uploaded ||
    setup.busy ||
    timestampsRunning ||
    ttsRunning ||
    setup.audioUploadProgress != null;
  const scriptImportDisabled = setup.busy || timestampsRunning || ttsRunning;
  const scriptSummary = setup.scriptSummary ?? setup.status?.script_summary ?? null;
  const canGenerateNarration =
    Boolean(setup.status?.script_uploaded) &&
    !setup.status?.audio_uploaded &&
    !ttsRunning &&
    setup.audioUploadProgress == null &&
    !setup.busy;
  const ttsFailed =
    setup.status?.tts_job.status === "error" && !setup.status?.audio_uploaded && !ttsRunning;

  const runPasteImport = useCallback(
    async (raw: string) => {
      if (scriptImportDisabled || pasteImporting) return;
      setPasteImporting(true);
      setPasteError(null);
      try {
        const message = await setup.importScriptJson(raw);
        if (message) {
          setPasteError(message);
          return;
        }
        setPasteJson("");
        setPasteError(null);
      } finally {
        setPasteImporting(false);
      }
    },
    [pasteImporting, scriptImportDisabled, setup],
  );

  const handlePasteImport = async () => {
    await runPasteImport(pasteJson);
  };

  useEffect(() => {
    if (scriptImportDisabled) return;

    const onPaste = (event: ClipboardEvent) => {
      if (scriptImportDisabled || pasteImporting) return;

      const target = event.target;
      if (target instanceof HTMLElement) {
        if (target.closest("[data-skip-script-paste]")) return;
        const editable = target.closest("input, textarea, [contenteditable='true']");
        if (editable && !setupCardRef.current?.contains(editable)) {
          return;
        }
      }

      const text = event.clipboardData?.getData("text/plain") ?? "";
      if (!looksLikeScriptJson(text)) return;

      event.preventDefault();
      void runPasteImport(text);
    };

    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [pasteImporting, runPasteImport, scriptImportDisabled]);

  return (
    <section className="page-container flex min-h-[calc(100vh-3.5rem)] w-full flex-col justify-center py-10">
      <div
        ref={setupCardRef}
        tabIndex={0}
        className="glow-card w-full p-6 lg:p-8 outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        onMouseDown={() => setupCardRef.current?.focus({ preventScroll: true })}
      >
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
          Upload or paste <code className="text-[var(--foreground)]">script.json</code>, then upload or
          auto-generate <code className="text-[var(--foreground)]">script.mp3</code> with Fish Audio, then
          Whisper alignment runs automatically. The b-roll viewer unlocks after all three steps.
        </p>

        <ol className="mt-8 space-y-4">
          <li className={`glow-setup-step ${setup.status?.script_uploaded ? "is-done" : step === "import_script" ? "is-active" : ""}`}>
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-3">
                <FileJson className="h-5 w-5 text-[var(--accent)]" />
                <div className="flex-1">
                  <p className="font-semibold">1. Import script.json</p>
                  <p className="text-sm text-[var(--muted)]">
                    {setup.status?.script_uploaded
                      ? "Script imported — review details below or re-import."
                      : "Press Ctrl+V anywhere here to paste script JSON, or use the box below."}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {setup.status?.script_uploaded ? (
                    <button
                      type="button"
                      onClick={() => void setup.copyTranscript()}
                      disabled={setup.busy || setup.copyingTranscript || timestampsRunning || ttsRunning}
                      className="glow-btn-secondary inline-flex items-center gap-2 rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-55"
                    >
                      {setup.copyingTranscript ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                      Copy transcript
                    </button>
                  ) : null}
                  <label className="glow-btn-secondary cursor-pointer rounded-[10px] px-3.5 py-2.5 text-sm font-semibold">
                    Choose file
                    <input
                      type="file"
                      accept=".json,application/json"
                      className="hidden"
                      disabled={scriptImportDisabled}
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) void setup.importScript(file);
                        event.target.value = "";
                      }}
                    />
                  </label>
                </div>
              </div>

              <div className="sm:pl-8" data-script-paste-zone>
                <label className="block text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
                  Or paste JSON
                </label>
                <textarea
                  value={pasteJson}
                  onChange={(event) => {
                    setPasteJson(event.target.value);
                    if (pasteError) setPasteError(null);
                  }}
                  onPaste={(event) => {
                    const text = event.clipboardData.getData("text/plain");
                    if (!looksLikeScriptJson(text)) return;
                    event.preventDefault();
                    void runPasteImport(text);
                  }}
                  placeholder='Click here and Ctrl+V — imports automatically'
                  rows={5}
                  disabled={scriptImportDisabled || pasteImporting}
                  className="mt-2 w-full resize-y rounded-[10px] border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-2 font-mono text-xs leading-5 text-[var(--foreground)] placeholder:text-[var(--muted)] disabled:opacity-55"
                />
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    className="glow-btn-primary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-55"
                    disabled={scriptImportDisabled || pasteImporting || !pasteJson.trim()}
                    onClick={() => void handlePasteImport()}
                  >
                    {setup.busy || pasteImporting ? (
                      <span className="inline-flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Importing…
                      </span>
                    ) : (
                      "Import script"
                    )}
                  </button>
                  {pasteImporting ? (
                    <span className="text-xs text-[var(--muted)]">Validating and uploading…</span>
                  ) : null}
                </div>
                {pasteError ? (
                  <p className="mt-2 text-sm text-[#ffc9c9]">{pasteError}</p>
                ) : null}
              </div>

              {setup.transcriptNotice ? (
                <p className="text-sm text-emerald-300 sm:pl-8">{setup.transcriptNotice}</p>
              ) : null}
              {scriptSummary ? (
                <ScriptSummaryPanel
                  summary={scriptSummary}
                  remotionRuntimeReady={setup.status?.remotion_runtime_ready}
                />
              ) : null}
            </div>
          </li>

          <li className={`glow-setup-step ${setup.status?.audio_uploaded ? "is-done" : step === "import_audio" ? "is-active" : ""}`}>
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-3">
                <FileAudio className="h-5 w-5 shrink-0 text-[var(--accent)]" />
                <div className="flex-1">
                  <p className="font-semibold">2. Narration audio</p>
                  <p className="text-sm text-[var(--muted)]">
                    {setup.audioUploadProgress != null
                      ? "Uploading narration…"
                      : ttsRunning
                        ? setup.status?.tts_job.message || "Generating narration with Fish Audio…"
                        : setup.status?.audio_uploaded
                          ? "Narration audio ready"
                          : ttsFailed
                            ? "Generation failed — retry with Fish Audio or upload your own MP3."
                            : "Upload your own MP3 or generate narration with Fish Audio."}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  {canGenerateNarration ? (
                    <button
                      type="button"
                      className="glow-btn-primary inline-flex items-center gap-2 rounded-[10px] px-3.5 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-55"
                      disabled={!canGenerateNarration}
                      onClick={() => void setup.generateNarration()}
                    >
                      <Mic2 className="h-4 w-4" />
                      {setup.autoTtsCountdown != null
                        ? `Generate now (${setup.autoTtsCountdown}s)`
                        : "Generate MP3"}
                    </button>
                  ) : null}
                  <label
                    className={`glow-btn-secondary rounded-[10px] px-3.5 py-2.5 text-sm font-semibold ${
                      setup.status?.script_uploaded && !audioControlsDisabled
                        ? "cursor-pointer"
                        : "cursor-not-allowed opacity-50"
                    }`}
                  >
                  {setup.audioUploadProgress != null ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Uploading…
                    </span>
                  ) : (
                    "Choose file"
                  )}
                  <input
                    type="file"
                    accept=".mp3,audio/mpeg,audio/mp3"
                    className="hidden"
                    disabled={audioControlsDisabled}
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) void setup.importAudio(file);
                      event.target.value = "";
                    }}
                  />
                </label>
                </div>
              </div>
              {setup.audioUploadProgress != null ? (
                <div className="pl-8">
                  <div className="flex items-center justify-between gap-3 text-xs text-[var(--muted)]">
                    <span>Uploading to server</span>
                    <span className="tabular-nums">{setup.audioUploadProgress}%</span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--surface-raised)]">
                    <div
                      className="h-full rounded-full bg-[var(--accent)] transition-[width] duration-150 ease-out"
                      style={{ width: `${setup.audioUploadProgress}%` }}
                    />
                  </div>
                </div>
              ) : null}
              {setup.autoTtsCountdown != null && !setup.status?.audio_uploaded && !ttsRunning ? (
                <div className="sm:pl-8">
                  <div className="rounded-[10px] border border-[rgba(255,193,7,0.45)] bg-[rgba(255,193,7,0.1)] px-4 py-3 text-sm text-[#ffe8a3]">
                    Auto-generating voice in {setup.autoTtsCountdown}s… Click{" "}
                    <span className="font-semibold text-[var(--foreground)]">Generate MP3</span> to start
                    now, or upload your own MP3 to skip.
                  </div>
                </div>
              ) : null}
              {ttsFailed && !ttsRestartRequired ? (
                <div className="sm:pl-8">
                  <div className="rounded-[10px] border border-[rgba(255,107,107,0.35)] bg-[rgba(255,107,107,0.08)] px-4 py-3 text-sm text-[#ffc9c9]">
                    {setup.status?.tts_job.error || "Narration generation failed."}
                  </div>
                  <TtsJobLogs job={setup.status?.tts_job} />
                </div>
              ) : null}
              {ttsRestartRequired && !ttsRunning ? (
                <div className="sm:pl-8">
                  <div className="rounded-[10px] border border-[rgba(255,193,7,0.45)] bg-[rgba(255,193,7,0.1)] px-4 py-3 text-sm text-[#ffe8a3]">
                    {setup.status?.tts_job.error ||
                      "Narration generation was interrupted. Re-upload script.json or wait for auto-generation."}
                  </div>
                  <TtsJobLogs job={setup.status?.tts_job} />
                </div>
              ) : ttsRunning || (setup.status?.tts_job.logs?.length ?? 0) > 0 ? (
                <div className="sm:pl-8">
                  <div className="flex items-center justify-between gap-3 text-xs text-[var(--muted)]">
                    <span className="capitalize">
                      {setup.status?.tts_job.stage?.replace(/_/g, " ") || "Generating"}
                      {setup.status?.tts_job.chunk_total
                        ? ` · ${setup.status.tts_job.chunk_done ?? 0}/${setup.status.tts_job.chunk_total} chunks`
                        : ""}
                    </span>
                    <span className="tabular-nums">{ttsProgress}%</span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--surface-raised)]">
                    <div
                      className="h-full rounded-full bg-[var(--accent)] transition-[width] duration-300"
                      style={{ width: `${ttsProgress}%` }}
                    />
                  </div>
                  <p className="mt-2 text-xs text-[var(--muted)]">
                    Fish Audio synthesis can take several minutes for long scripts.
                  </p>
                  <TtsJobLogs job={setup.status?.tts_job} />
                </div>
              ) : null}
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
                          : setup.status?.timestamps_ready || timestampsDone
                            ? alignmentSummary
                              ? `${alignmentSummary.aligned_segments}/${alignmentSummary.total_segments} Whisper-aligned · ${alignmentSummary.timed_segments}/${alignmentSummary.total_segments} timestamps`
                              : `${setup.status?.aligned_segments ?? 0}/${setup.status?.segment_count ?? 0} segments ready`
                            : "Generate timestamps with Whisper or import an existing JSON file."}
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap items-end gap-2 sm:shrink-0">
                <WhisperModelSelect
                  value={setup.whisperModel}
                  onValueChange={setup.setWhisperModel}
                  disabled={segmentControlsDisabled}
                />
                <label
                  className={`glow-btn-secondary inline-flex cursor-pointer items-center gap-2 px-3.5 py-2.5 text-sm font-semibold ${
                    segmentControlsDisabled ? "cursor-not-allowed opacity-50" : ""
                  }`}
                >
                  <FileStack className="h-4 w-4" />
                  Import JSON
                  <input
                    type="file"
                    accept=".json,application/json"
                    className="hidden"
                    disabled={
                      segmentControlsDisabled
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
                  disabled={segmentControlsDisabled}
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
                  {!timestampsRunning && timestampsDone && alignmentSummary ? (
                    <SegmentationAlignmentSummary alignment={alignmentSummary} className="mb-4" />
                  ) : null}
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
              ) : alignmentSummary && setup.status?.timestamps_ready ? (
                <div className="sm:pl-8">
                  <SegmentationAlignmentSummary alignment={alignmentSummary} />
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
