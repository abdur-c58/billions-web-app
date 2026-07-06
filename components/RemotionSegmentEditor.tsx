"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Play, RotateCcw, Save, Sparkles } from "lucide-react";
import type { ViewerSegment } from "@/lib/types";
import {
  buildRemotionPropsPayload,
  mergePropsIntoFormValues,
  propsFromRemotion,
  remotionFieldsFor,
  remotionPropsDirty,
} from "@/lib/remotionEditor";

type RemotionSegmentEditorProps = {
  segment: ViewerSegment;
  isBusy: boolean;
  previewUrl: string | null;
  onPreview: (props: Record<string, unknown>) => Promise<void>;
  onSave: (props: Record<string, unknown>) => Promise<void>;
  onSuggestPrompt: (
    prompt: string,
    currentProps: Record<string, unknown>,
  ) => Promise<{ props: Record<string, unknown>; summary: string }>;
};

export function RemotionSegmentEditor({
  segment,
  isBusy,
  previewUrl,
  onPreview,
  onSave,
  onSuggestPrompt,
}: RemotionSegmentEditorProps) {
  const composition = segment.remotion?.composition ?? "FactCard";
  const fields = useMemo(() => remotionFieldsFor(composition), [composition]);
  const savedValues = useMemo(
    () => propsFromRemotion(segment.remotion),
    [segment.remotion],
  );

  const [values, setValues] = useState<Record<string, string>>(savedValues);
  const [prompt, setPrompt] = useState("");
  const [promptBusy, setPromptBusy] = useState(false);
  const [promptSummary, setPromptSummary] = useState<string | null>(null);

  useEffect(() => {
    setValues(savedValues);
    setPromptSummary(null);
  }, [segment.segment_id, savedValues]);

  const dirty = remotionPropsDirty(composition, values, savedValues);
  const payload = buildRemotionPropsPayload(composition, values);
  const controlsBusy = isBusy || promptBusy;

  const updateField = (key: string, value: string) => {
    setValues((current) => ({ ...current, [key]: value }));
    setPromptSummary(null);
  };

  const resetFields = () => {
    setValues(savedValues);
    setPromptSummary(null);
  };

  const applyPrompt = async () => {
    const trimmed = prompt.trim();
    if (!trimmed) return;
    setPromptBusy(true);
    setPromptSummary(null);
    try {
      const result = await onSuggestPrompt(trimmed, payload);
      setValues((current) =>
        mergePropsIntoFormValues(composition, current, result.props),
      );
      setPromptSummary(result.summary || "Prompt applied — preview to check, then save.");
    } finally {
      setPromptBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-2.5">
      <div className="rounded-lg border border-violet-400/20 bg-violet-500/8 p-2.5">
        <label className="flex flex-col gap-1.5">
          <span className="text-[0.68rem] font-semibold uppercase tracking-[0.08em] text-violet-200/90">
            Describe the look
          </span>
          <textarea
            rows={2}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                event.preventDefault();
                void applyPrompt();
              }
            }}
            placeholder='e.g. "Center everything, smaller body text, blue accent"'
            className="glow-control min-h-[3.25rem] w-full resize-y rounded-lg px-2.5 py-1.5 text-[0.78rem] text-[var(--foreground)] placeholder:text-[var(--muted)]"
          />
        </label>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            disabled={controlsBusy || !prompt.trim()}
            onClick={() => void applyPrompt()}
            className="glow-btn-primary inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[0.78rem] font-semibold disabled:cursor-not-allowed disabled:opacity-55"
          >
            {promptBusy ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            Apply prompt
          </button>
          <span className="text-[0.65rem] text-[var(--muted)]">Ctrl+Enter</span>
        </div>
        {promptSummary ? (
          <p className="mt-2 text-[0.72rem] leading-snug text-violet-100/85">{promptSummary}</p>
        ) : null}
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {fields.map((field) => {
          const value = values[field.key] ?? "";
          const controlClass =
            "glow-control w-full rounded-lg px-2.5 py-1.5 text-[0.78rem] text-[var(--foreground)]";

          if (field.type === "textarea") {
            return (
              <label key={field.key} className="flex flex-col gap-1 sm:col-span-2">
                <span className="text-[0.68rem] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">
                  {field.label}
                </span>
                <textarea
                  rows={3}
                  value={value}
                  onChange={(event) => updateField(field.key, event.target.value)}
                  className={`${controlClass} min-h-[4.5rem] resize-y`}
                />
              </label>
            );
          }

          if (field.type === "select") {
            return (
              <label key={field.key} className="flex flex-col gap-1">
                <span className="text-[0.68rem] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">
                  {field.label}
                </span>
                <select
                  value={value}
                  onChange={(event) => updateField(field.key, event.target.value)}
                  className={controlClass}
                >
                  <option value="">Default</option>
                  {(field.options ?? []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            );
          }

          if (field.type === "color") {
            return (
              <label key={field.key} className="flex flex-col gap-1">
                <span className="text-[0.68rem] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">
                  {field.label}
                </span>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={value || "#5ecf8a"}
                    onChange={(event) => updateField(field.key, event.target.value)}
                    className="h-9 w-12 cursor-pointer rounded border border-white/10 bg-transparent"
                  />
                  <input
                    type="text"
                    value={value}
                    placeholder="#5ecf8a"
                    onChange={(event) => updateField(field.key, event.target.value)}
                    className={`${controlClass} min-w-0 flex-1`}
                  />
                </div>
              </label>
            );
          }

          return (
            <label key={field.key} className="flex flex-col gap-1">
              <span className="text-[0.68rem] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">
                {field.label}
              </span>
              <input
                type={field.type === "number" ? "number" : "text"}
                value={value}
                min={field.min}
                max={field.max}
                step={field.step}
                placeholder={field.placeholder}
                onChange={(event) => updateField(field.key, event.target.value)}
                className={controlClass}
              />
            </label>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          disabled={controlsBusy}
          onClick={() => void onPreview(payload)}
          className="glow-btn-primary inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[0.78rem] font-semibold disabled:cursor-not-allowed disabled:opacity-55"
        >
          {isBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
          Preview
        </button>
        <button
          type="button"
          disabled={controlsBusy || !dirty}
          onClick={() => void onSave(payload)}
          className="glow-btn-secondary inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[0.78rem] font-semibold disabled:cursor-not-allowed disabled:opacity-55"
        >
          <Save className="h-3.5 w-3.5" />
          Save
        </button>
        <button
          type="button"
          disabled={controlsBusy || !dirty}
          onClick={resetFields}
          className="glow-btn-secondary inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[0.78rem] font-semibold disabled:cursor-not-allowed disabled:opacity-55"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Reset
        </button>
        {dirty ? (
          <span className="text-[0.68rem] text-amber-200/85">Unsaved changes</span>
        ) : previewUrl ? (
          <span className="text-[0.68rem] text-violet-200/75">Preview uses current form values</span>
        ) : null}
      </div>
    </div>
  );
}
