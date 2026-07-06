import type { RemotionSegmentInfo } from "@/lib/types";

export type TextAlign = "left" | "center" | "right";
export type VerticalAlign = "top" | "center" | "bottom";

export type RemotionFieldType = "text" | "textarea" | "number" | "color" | "select";

export type RemotionFieldOption = {
  value: string;
  label: string;
};

export type RemotionFieldDef = {
  key: string;
  label: string;
  type: RemotionFieldType;
  min?: number;
  max?: number;
  step?: number;
  options?: RemotionFieldOption[];
  placeholder?: string;
};

export const REMOTION_FIELD_DEFS: Record<string, RemotionFieldDef[]> = {
  FactCard: [
    { key: "title", label: "Title", type: "text" },
    { key: "body", label: "Body", type: "textarea" },
    { key: "factNumber", label: "Fact #", type: "number", min: 1, max: 99, step: 1 },
    { key: "accentColor", label: "Accent", type: "color" },
    {
      key: "textAlign",
      label: "Text align",
      type: "select",
      options: [
        { value: "left", label: "Left" },
        { value: "center", label: "Center" },
        { value: "right", label: "Right" },
      ],
    },
    {
      key: "verticalAlign",
      label: "Vertical",
      type: "select",
      options: [
        { value: "top", label: "Top" },
        { value: "center", label: "Center" },
        { value: "bottom", label: "Bottom" },
      ],
    },
    { key: "padding", label: "Padding", type: "number", min: 24, max: 240, step: 4 },
    { key: "titleSize", label: "Title size", type: "number", min: 24, max: 120, step: 2 },
    { key: "bodySize", label: "Body size", type: "number", min: 24, max: 120, step: 2 },
  ],
  TitleCard: [
    { key: "title", label: "Title", type: "text" },
    { key: "subtitle", label: "Subtitle", type: "textarea" },
    { key: "accentColor", label: "Accent", type: "color" },
    {
      key: "textAlign",
      label: "Text align",
      type: "select",
      options: [
        { value: "left", label: "Left" },
        { value: "center", label: "Center" },
        { value: "right", label: "Right" },
      ],
    },
    {
      key: "verticalAlign",
      label: "Vertical",
      type: "select",
      options: [
        { value: "top", label: "Top" },
        { value: "center", label: "Center" },
        { value: "bottom", label: "Bottom" },
      ],
    },
    { key: "padding", label: "Padding", type: "number", min: 24, max: 240, step: 4 },
    { key: "titleSize", label: "Title size", type: "number", min: 24, max: 120, step: 2 },
    { key: "subtitleSize", label: "Subtitle size", type: "number", min: 24, max: 120, step: 2 },
  ],
};

export function remotionFieldsFor(composition: string): RemotionFieldDef[] {
  return REMOTION_FIELD_DEFS[composition] ?? REMOTION_FIELD_DEFS.FactCard;
}

export function propsFromRemotion(remotion?: RemotionSegmentInfo | null): Record<string, string> {
  const props = remotion?.props ?? {};
  const values: Record<string, string> = {};
  for (const [key, value] of Object.entries(props)) {
    if (value == null) continue;
    values[key] = String(value);
  }
  return values;
}

export function buildRemotionPropsPayload(
  composition: string,
  values: Record<string, string>,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const field of remotionFieldsFor(composition)) {
    const raw = values[field.key];
    if (raw == null || raw === "") continue;
    if (field.type === "number") {
      const parsed = Number(raw);
      if (!Number.isFinite(parsed)) continue;
      payload[field.key] = parsed;
      continue;
    }
    payload[field.key] = raw;
  }
  return payload;
}

export function remotionPropsDirty(
  composition: string,
  current: Record<string, string>,
  saved: Record<string, string>,
): boolean {
  for (const field of remotionFieldsFor(composition)) {
    if ((current[field.key] ?? "") !== (saved[field.key] ?? "")) {
      return true;
    }
  }
  return false;
}

export function mergePropsIntoFormValues(
  composition: string,
  current: Record<string, string>,
  updates: Record<string, unknown>,
): Record<string, string> {
  const next = { ...current };
  for (const field of remotionFieldsFor(composition)) {
    if (!(field.key in updates)) continue;
    const value = updates[field.key];
    if (value == null || value === "") {
      delete next[field.key];
      continue;
    }
    next[field.key] = String(value);
  }
  return next;
}

export function propsToFormValues(
  composition: string,
  props: Record<string, unknown>,
): Record<string, string> {
  return mergePropsIntoFormValues(composition, {}, props);
}
