import { apiFetch } from "@/lib/api";
import type { RemotionScriptSummary, ScriptFormat } from "@/lib/types";

export type ScriptTranscript = {
  transcript: string;
  segment_count: number;
  word_count: number;
  estimated_duration_seconds: number;
  estimated_duration_label: string;
  wpm?: number;
};

export type ScriptSummary = {
  title: string | null;
  channel: string | null;
  beat_count: number;
  segment_count: number;
  word_count: number;
  estimated_duration_seconds: number;
  estimated_duration_label: string;
  wpm?: number;
  script_format?: ScriptFormat | null;
  remotion?: RemotionScriptSummary | null;
};

type ScriptSegment = {
  segment_id?: number;
  content?: string;
  type?: string | string[];
  remotion?: { composition?: string };
  delivery?: unknown;
};

type ScriptBeatBlock = {
  segments?: ScriptSegment[];
};

export type ScriptJson = {
  title?: string;
  channel?: string;
  script?: ScriptBeatBlock[];
  segments?: unknown;
  thumbnail?: unknown;
  youtube_description?: unknown;
};

const KNOWN_REMOTION_COMPOSITIONS = new Set(["FactCard", "TitleCard"]);
const DEFAULT_WPM = 145;

/** Heuristic: clipboard text is likely a script.json payload. */
export function looksLikeScriptJson(text: string): boolean {
  const trimmed = text.trim();
  if (!trimmed.startsWith("{")) return false;
  return /"script"\s*:/.test(trimmed);
}

function isRemotionSegment(segment: ScriptSegment): boolean {
  const rawType = segment.type;
  if (typeof rawType === "string") {
    const lower = rawType.toLowerCase();
    if (lower.startsWith("remotion:") || lower === "remotion") return true;
  }
  if (Array.isArray(rawType) && rawType[0]?.toString().toLowerCase() === "remotion") {
    return true;
  }
  const remotion = segment.remotion;
  return Boolean(remotion && typeof remotion === "object" && remotion.composition);
}

function remotionComposition(segment: ScriptSegment): string {
  const explicit = segment.remotion?.composition;
  if (explicit && KNOWN_REMOTION_COMPOSITIONS.has(explicit)) return explicit;
  const rawType = segment.type;
  if (typeof rawType === "string" && rawType.toLowerCase().startsWith("remotion:")) {
    const slug = rawType.slice("remotion:".length).trim();
    if (slug === "TitleCard" || slug === "FactCard") return slug;
  }
  if (Array.isArray(rawType) && rawType.length >= 2) {
    const slug = String(rawType[1]).trim();
    if (slug === "TitleCard" || slug === "FactCard") return slug;
  }
  return "FactCard";
}

export function parseScriptJson(raw: string): unknown {
  const trimmed = raw.trim();
  if (!trimmed) {
    throw new Error("Paste script JSON or choose a file.");
  }
  try {
    return JSON.parse(trimmed);
  } catch (err) {
    const detail = err instanceof Error ? err.message : "syntax error";
    throw new Error(`Invalid JSON: ${detail}`);
  }
}

export function validateScriptPayload(data: unknown): asserts data is ScriptJson {
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new Error("Script JSON must be an object.");
  }
  const scriptData = data as ScriptJson;
  if (scriptData.segments && !scriptData.script) {
    throw new Error('Script must use a top-level "script" array, not "segments".');
  }
  const beats = scriptData.script;
  if (!Array.isArray(beats) || !beats.length) {
    throw new Error('Script must include a non-empty "script" array.');
  }

  const seenIds = new Set<number>();
  for (let beatIndex = 0; beatIndex < beats.length; beatIndex += 1) {
    const beatBlock = beats[beatIndex];
    if (!beatBlock || typeof beatBlock !== "object" || Array.isArray(beatBlock)) {
      throw new Error(`Beat block ${beatIndex + 1} must be an object.`);
    }
    const segments = beatBlock.segments;
    if (!Array.isArray(segments) || !segments.length) {
      throw new Error(`Beat block ${beatIndex + 1} must include segments.`);
    }
    for (const segment of segments) {
      if (!segment || typeof segment !== "object" || Array.isArray(segment)) {
        throw new Error("Each segment must be an object.");
      }
      if (segment.segment_id == null) {
        throw new Error("Each segment needs a segment_id.");
      }
      const segmentId = Number(segment.segment_id);
      if (seenIds.has(segmentId)) {
        throw new Error(`Duplicate segment_id: ${segmentId}`);
      }
      seenIds.add(segmentId);
      if (!String(segment.content ?? "").trim()) {
        throw new Error(`Segment ${segmentId} is missing content.`);
      }
      validateSegmentDelivery(segmentId, segment.delivery);
      if (isRemotionSegment(segment)) {
        const composition = remotionComposition(segment);
        if (!KNOWN_REMOTION_COMPOSITIONS.has(composition)) {
          throw new Error(
            `Segment ${segmentId} uses unknown Remotion composition '${composition}'. Supported: FactCard, TitleCard.`,
          );
        }
      }
    }
  }
  validateThumbnailBlock(scriptData.thumbnail);
  validateYoutubeDescription(scriptData.youtube_description);
}

const YOUTUBE_DESCRIPTION_MAX_CHARS = 5000;

function validateYoutubeDescription(description: unknown): void {
  if (description == null) return;
  if (typeof description !== "string") {
    throw new Error('"youtube_description" must be a string.');
  }
  if (/[<>]/.test(description)) {
    throw new Error('"youtube_description" must not contain < or > (YouTube rejects them).');
  }
  if (description.length > YOUTUBE_DESCRIPTION_MAX_CHARS) {
    throw new Error(
      `"youtube_description" must be at most ${YOUTUBE_DESCRIPTION_MAX_CHARS} characters (YouTube's limit, chapters included).`,
    );
  }
}

const DELIVERY_MAX_CHARS = 120;

function validateSegmentDelivery(segmentId: number, delivery: unknown): void {
  if (delivery == null) return;
  if (typeof delivery !== "string" || !delivery.trim()) {
    throw new Error(`Segment ${segmentId} "delivery" must be a non-empty string.`);
  }
  if (/[\[\].!?]/.test(delivery)) {
    throw new Error(`Segment ${segmentId} "delivery" must not contain square brackets or . ! ?`);
  }
  if (delivery.trim().length > DELIVERY_MAX_CHARS) {
    throw new Error(`Segment ${segmentId} "delivery" must be at most ${DELIVERY_MAX_CHARS} characters.`);
  }
}

function validateThumbnailBlock(thumbnail: unknown): void {
  if (thumbnail == null) return;
  if (typeof thumbnail !== "object" || Array.isArray(thumbnail)) {
    throw new Error('"thumbnail" must be an object.');
  }
  const block = thumbnail as Record<string, unknown>;
  const imagePrompt = block.image_prompt;
  if (typeof imagePrompt !== "string" || !imagePrompt.trim()) {
    throw new Error('"thumbnail.image_prompt" must be a non-empty string.');
  }
  const overlayText = block.overlay_text;
  if (overlayText == null) return;
  if (typeof overlayText !== "object" || Array.isArray(overlayText)) {
    throw new Error('"thumbnail.overlay_text" must be an object.');
  }
  for (const [key, value] of Object.entries(overlayText)) {
    if (typeof value !== "string") {
      throw new Error(`"thumbnail.overlay_text.${key}" must be a string.`);
    }
  }
}

export function estimateDurationSeconds(wordCount: number, wpm = DEFAULT_WPM): number {
  if (wordCount <= 0) return 0;
  return Math.round((wordCount / wpm) * 60 * 10) / 10;
}

export function formatDurationLabel(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours) return `${hours}h ${mins}m`;
  if (mins) return secs < 30 ? `~${mins} min` : `~${mins}m ${secs}s`;
  return `~${secs}s`;
}

function detectScriptFormat(scriptData: ScriptJson): ScriptFormat {
  const kinds = new Set<string>();
  for (const beatBlock of scriptData.script ?? []) {
    for (const segment of beatBlock.segments ?? []) {
      if (isRemotionSegment(segment)) {
        kinds.add("remotion");
        continue;
      }
      const rawType = segment.type;
      if (typeof rawType === "string") kinds.add("folder");
      else if (Array.isArray(rawType)) kinds.add("legacy");
      else if (rawType != null) kinds.add("other");
    }
  }
  return kinds.size === 1 && kinds.has("folder") ? "folder" : "legacy";
}

function analyzeScriptRemotion(scriptData: ScriptJson): RemotionScriptSummary {
  const compositions = new Set<string>();
  let remotionCount = 0;
  let total = 0;

  for (const beatBlock of scriptData.script ?? []) {
    for (const segment of beatBlock.segments ?? []) {
      if (segment.segment_id == null || segment.content == null) continue;
      total += 1;
      if (!isRemotionSegment(segment)) continue;
      remotionCount += 1;
      compositions.add(remotionComposition(segment));
    }
  }

  return {
    detected: remotionCount > 0,
    segment_count: remotionCount,
    segment_ids: [],
    compositions: [...compositions].sort(),
    total_segments: total,
    broll_segment_count: Math.max(0, total - remotionCount),
  };
}

/** Extract narration text from script.json (legacy or folder format). */
export function buildNarrationTranscript(scriptData: ScriptJson, separator = " "): string {
  const segments: Array<{ segment_id: number; content: string }> = [];

  for (const beatBlock of scriptData.script ?? []) {
    for (const segment of beatBlock.segments ?? []) {
      if (segment.content == null) continue;
      const text = String(segment.content).trim();
      if (!text) continue;
      segments.push({
        segment_id: Number(segment.segment_id ?? segments.length + 1),
        content: text,
      });
    }
  }

  segments.sort((a, b) => a.segment_id - b.segment_id);
  if (!segments.length) {
    throw new Error("No segment content found in script.");
  }

  return segments.map((segment) => segment.content).join(separator);
}

export function buildScriptSummary(scriptData: ScriptJson): ScriptSummary {
  const beats = scriptData.script ?? [];
  const beatCount = beats.length;
  const segmentCount = beats.reduce(
    (count, beat) => count + (beat.segments ?? []).filter((s) => String(s.content ?? "").trim()).length,
    0,
  );
  const transcript = buildNarrationTranscript(scriptData);
  const wordCount = transcript.split(/\s+/).filter(Boolean).length;
  const durationSeconds = estimateDurationSeconds(wordCount);

  const title = scriptData.title != null ? String(scriptData.title).trim() : "";
  const channel = scriptData.channel != null ? String(scriptData.channel).trim() : "";

  return {
    title: title || null,
    channel: channel || null,
    beat_count: beatCount,
    segment_count: segmentCount,
    word_count: wordCount,
    estimated_duration_seconds: durationSeconds,
    estimated_duration_label: formatDurationLabel(durationSeconds),
    wpm: DEFAULT_WPM,
    script_format: detectScriptFormat(scriptData),
    remotion: analyzeScriptRemotion(scriptData),
  };
}

export function prepareScriptImport(raw: string): ScriptJson {
  const parsed = parseScriptJson(raw);
  validateScriptPayload(parsed);
  return parsed;
}

export async function fetchScriptTranscript(): Promise<ScriptTranscript> {
  return apiFetch<ScriptTranscript>("/api/project/script/transcript");
}

/** Build transcript from a local script.json File before or after upload. */
export async function buildNarrationTranscriptFromFile(file: File): Promise<ScriptTranscript> {
  const scriptData = prepareScriptImport(await file.text());
  const transcript = buildNarrationTranscript(scriptData);
  const summary = buildScriptSummary(scriptData);
  return {
    transcript,
    segment_count: summary.segment_count,
    word_count: summary.word_count,
    estimated_duration_seconds: summary.estimated_duration_seconds,
    estimated_duration_label: summary.estimated_duration_label,
    wpm: summary.wpm,
  };
}
