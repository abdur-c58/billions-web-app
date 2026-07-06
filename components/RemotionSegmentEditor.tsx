"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Play, RotateCcw, Save, Sparkles } from "lucide-react";
import type { ViewerSegment } from "@/lib/types";
import {
  applyExtraPropsJson,
  buildRemotionPropsPayload,
  extraPropsJson,
  mergePropsIntoFormValues,
  propsFromRemotion,
  remotionFieldsFor,
  remotionPropsDirty,
  remotionSchemaAllowsExtra,
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
  const [extraJson, setExtraJson] = useState("{}");
  const [extraJsonError, setExtraJsonError] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [promptBusy, setPromptBusy] = useState(false);
  const [promptSummary, setPromptSummary] = useState<string | null>(null);

  useEffect(() => {
    setValues(savedValues);
    setExtraJson(extraPropsJson(composition, savedValues));
    setExtraJsonError(null);
    setPromptSummary(null);
  }, [composition, segment.segment_id, savedValues]);

  const dirty = remotionPropsDirty(composition, values, savedValues);
  const payload = buildRemotionPropsPayload(composition, values);
  const controlsBusy = isBusy || promptBusy;
  const allowExtra = remotionSchemaAllowsExtra(composition);

  const syncValues = (next: Record<string, string>) => {
    setValues(next);
    setExtraJson(extraPropsJson(composition, next));
  };

  const updateField = (key: string, value: string) => {
    syncValues({ ...values, [key]: value });
    setPromptSummary(null);
  };

  const resetFields = () => {
    syncValues(savedValues);
    setExtraJsonError(null);
    setPromptSummary(null);
  };

  const updateExtraJson = (text: string) => {
    setExtraJson(text);
    try {
      syncValues(applyExtraPropsJson(composition, values, text));
      setExtraJsonError(null);
      setPromptSummary(null);
    } catch {
      setExtraJsonError("Invalid JSON");
    }
  };

  const applyPrompt = async () => {
    const trimmed = prompt.trim();
    if (!trimmed) return;
    setPromptBusy(true);
    setPromptSummary(null);
    try {
      const result = await onSuggestPrompt(trimmed, payload);
      const nextValues = mergePropsIntoFormValues(composition, values, result.props);
      syncValues(nextValues);
      const nextPayload = buildRemotionPropsPayload(composition, nextValues);
      await onSave(nextPayload);
      setPromptSummary(
        (result.summary || "Prompt applied.") + " Changes saved — click Preview to check.",
      );
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
            Apply & save
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

          if (field.type === "textarea" || field.type === "css") {
            return (
              <label key={field.key} className="flex flex-col gap-1 sm:col-span-2">
                <span className="text-[0.68rem] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">
                  {field.label}
                </span>
                <textarea
                  rows={field.type === "css" ? 2 : 3}
                  value={value}
                  placeholder={field.placeholder}
                  onChange={(event) => updateField(field.key, event.target.value)}
                  className={`${controlClass} min-h-[4.5rem] resize-y`}
                />
              </label>
            );
          }

          if (field.type === "boolean") {
            return (
              <label
                key={field.key}
                className="flex items-center gap-2 rounded-lg border border-white/8 bg-white/3 px-2.5 py-2"
              >
                <input
                  type="checkbox"
                  checked={value === "true"}
                  onChange={(event) =>
                    updateField(field.key, event.target.checked ? "true" : "false")
                  }
                  className="h-4 w-4 accent-violet-400"
                />
                <span className="text-[0.78rem] text-[var(--foreground)]">{field.label}</span>
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

      {allowExtra ? (
        <label className="flex flex-col gap-1">
          <span className="text-[0.68rem] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">
            Additional props (JSON)
          </span>
          <textarea
            rows={4}
            value={extraJson}
            onChange={(event) => updateExtraJson(event.target.value)}
            placeholder='{"customFlag": true, "glowStrength": 0.8}'
            className="glow-control min-h-[5rem] w-full resize-y rounded-lg px-2.5 py-1.5 font-mono text-[0.72rem] text-[var(--foreground)]"
          />
          {extraJsonError ? (
            <span className="text-[0.68rem] text-red-300">{extraJsonError}</span>
          ) : (
            <span className="text-[0.65rem] text-[var(--muted)]">
              Extra camelCase props pass through to Remotion for custom compositions.
            </span>
          )}
        </label>
      ) : null}

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
          <span className="text-[0.68rem] text-amber-200/85">
            Unsaved edits — click Save before export
          </span>
        ) : previewUrl ? (
          <span className="text-[0.68rem] text-violet-200/75">Preview uses current form values</span>
        ) : null}
      </div>
    </div>
  );
}
