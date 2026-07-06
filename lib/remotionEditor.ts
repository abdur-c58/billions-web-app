import type { RemotionSegmentInfo } from "@/lib/types";
import schemaDocument from "@/lib/remotion-schemas.json";

export type TextAlign = "left" | "center" | "right";
export type VerticalAlign = "top" | "center" | "bottom";

export type RemotionFieldType =
  | "string"
  | "textarea"
  | "number"
  | "boolean"
  | "color"
  | "css"
  | "select";

export type RemotionSchemaProp = {
  type: RemotionFieldType;
  label?: string;
  min?: number;
  max?: number;
  step?: number;
  integer?: boolean;
  options?: string[];
  placeholder?: string;
  hidden?: boolean;
  default?: boolean | number | string;
};

export type RemotionCompositionSchema = {
  allowExtra?: boolean;
  props: Record<string, RemotionSchemaProp>;
};

type RemotionSchemaDocument = {
  compositions: Record<string, RemotionCompositionSchema>;
};

const SCHEMAS = schemaDocument as RemotionSchemaDocument;

export type RemotionFieldDef = {
  key: string;
  label: string;
  type: RemotionFieldType;
  min?: number;
  max?: number;
  step?: number;
  options?: { value: string; label: string }[];
  placeholder?: string;
};

function compositionSchema(composition: string): RemotionCompositionSchema {
  return SCHEMAS.compositions[composition] ?? SCHEMAS.compositions.FactCard;
}

function propDefinition(
  composition: string,
  key: string,
): RemotionSchemaProp | undefined {
  return compositionSchema(composition).props[key];
}

function fieldFromSchema(key: string, definition: RemotionSchemaProp): RemotionFieldDef {
  return {
    key,
    label: definition.label ?? key,
    type: definition.type,
    min: definition.min,
    max: definition.max,
    step: definition.step,
    placeholder: definition.placeholder,
    options: definition.options?.map((value) => ({ value, label: value })),
  };
}

export function remotionFieldsFor(composition: string): RemotionFieldDef[] {
  const props = compositionSchema(composition).props;
  return Object.entries(props)
    .filter(([, definition]) => !definition.hidden)
    .map(([key, definition]) => fieldFromSchema(key, definition));
}

export function remotionSchemaAllowsExtra(composition: string): boolean {
  return compositionSchema(composition).allowExtra !== false;
}

export function remotionKnownPropKeys(composition: string): Set<string> {
  return new Set(Object.keys(compositionSchema(composition).props));
}

export function propsFromRemotion(remotion?: RemotionSegmentInfo | null): Record<string, string> {
  const props = remotion?.props ?? {};
  const values: Record<string, string> = {};
  for (const [key, value] of Object.entries(props)) {
    if (value == null) continue;
    if (typeof value === "boolean") {
      values[key] = value ? "true" : "false";
      continue;
    }
    if (typeof value === "object") {
      values[key] = JSON.stringify(value);
      continue;
    }
    values[key] = String(value);
  }
  return values;
}

function coerceFormValue(
  composition: string,
  key: string,
  raw: string,
): unknown | undefined {
  if (raw === "") return undefined;

  const definition = propDefinition(composition, key);
  const type = definition?.type ?? inferExtraType(raw);

  if (type === "boolean") {
    const lowered = raw.trim().toLowerCase();
    if (["true", "1", "yes", "on"].includes(lowered)) return true;
    if (["false", "0", "no", "off"].includes(lowered)) return false;
    return undefined;
  }

  if (type === "number") {
    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) return undefined;
    if (definition?.integer) return Math.round(parsed);
    return parsed;
  }

  if (raw.trim().startsWith("{") || raw.trim().startsWith("[")) {
    try {
      return JSON.parse(raw);
    } catch {
      return raw;
    }
  }

  return raw;
}

function inferExtraType(raw: string): RemotionFieldType {
  const lowered = raw.trim().toLowerCase();
  if (["true", "false"].includes(lowered)) return "boolean";
  if (raw.trim() !== "" && Number.isFinite(Number(raw))) return "number";
  return "string";
}

export function buildRemotionPropsPayload(
  composition: string,
  values: Record<string, string>,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const [key, raw] of Object.entries(values)) {
    const coerced = coerceFormValue(composition, key, raw);
    if (coerced !== undefined) {
      payload[key] = coerced;
    }
  }
  return payload;
}

function allTrackedKeys(
  composition: string,
  current: Record<string, string>,
  saved: Record<string, string>,
): string[] {
  const keys = new Set<string>([
    ...Object.keys(compositionSchema(composition).props),
    ...Object.keys(current),
    ...Object.keys(saved),
  ]);
  return [...keys].sort();
}

export function remotionPropsDirty(
  composition: string,
  current: Record<string, string>,
  saved: Record<string, string>,
): boolean {
  for (const key of allTrackedKeys(composition, current, saved)) {
    if ((current[key] ?? "") !== (saved[key] ?? "")) {
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
  for (const [key, value] of Object.entries(updates)) {
    if (value == null || value === "") {
      delete next[key];
      continue;
    }
    if (typeof value === "boolean") {
      next[key] = value ? "true" : "false";
      continue;
    }
    if (typeof value === "object") {
      next[key] = JSON.stringify(value);
      continue;
    }
    next[key] = String(value);
  }
  return next;
}

export function extraPropKeys(
  composition: string,
  values: Record<string, string>,
): string[] {
  const known = remotionKnownPropKeys(composition);
  return Object.keys(values)
    .filter((key) => !known.has(key))
    .sort();
}

export function extraPropsJson(
  composition: string,
  values: Record<string, string>,
): string {
  const extras = extraPropKeys(composition, values);
  if (!extras.length) return "{}";
  const payload: Record<string, unknown> = {};
  for (const key of extras) {
    const coerced = coerceFormValue(composition, key, values[key] ?? "");
    if (coerced !== undefined) {
      payload[key] = coerced;
    }
  }
  return JSON.stringify(payload, null, 2);
}

export function applyExtraPropsJson(
  composition: string,
  current: Record<string, string>,
  jsonText: string,
): Record<string, string> {
  const next = { ...current };
  const known = remotionKnownPropKeys(composition);
  for (const key of Object.keys(next)) {
    if (!known.has(key)) {
      delete next[key];
    }
  }
  const trimmed = jsonText.trim();
  if (!trimmed || trimmed === "{}") {
    return next;
  }
  const parsed = JSON.parse(trimmed) as Record<string, unknown>;
  return mergePropsIntoFormValues(composition, next, parsed);
}
