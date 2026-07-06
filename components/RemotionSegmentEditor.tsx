"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, Play, RotateCcw, Save } from "lucide-react";
import type { ViewerSegment } from "@/lib/types";
import {
  buildRemotionPropsPayload,
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
};

export function RemotionSegmentEditor({
  segment,
  isBusy,
  previewUrl,
  onPreview,
  onSave,
}: RemotionSegmentEditorProps) {
  const composition = segment.remotion?.composition ?? "FactCard";
  const fields = useMemo(() => remotionFieldsFor(composition), [composition]);
  const savedValues = useMemo(
    () => propsFromRemotion(segment.remotion),
    [segment.remotion],
  );

  const [values, setValues] = useState<Record<string, string>>(savedValues);

  useEffect(() => {
    setValues(savedValues);
  }, [segment.segment_id, savedValues]);

  const dirty = remotionPropsDirty(composition, values, savedValues);
  const payload = buildRemotionPropsPayload(composition, values);

  const updateField = (key: string, value: string) => {
    setValues((current) => ({ ...current, [key]: value }));
  };

  const resetFields = () => setValues(savedValues);

  return (
    <div className="flex flex-col gap-2.5">
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
          disabled={isBusy}
          onClick={() => void onPreview(payload)}
          className="glow-btn-primary inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[0.78rem] font-semibold disabled:cursor-not-allowed disabled:opacity-55"
        >
          {isBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
          Preview
        </button>
        <button
          type="button"
          disabled={isBusy || !dirty}
          onClick={() => void onSave(payload)}
          className="glow-btn-secondary inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[0.78rem] font-semibold disabled:cursor-not-allowed disabled:opacity-55"
        >
          <Save className="h-3.5 w-3.5" />
          Save
        </button>
        <button
          type="button"
          disabled={isBusy || !dirty}
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
