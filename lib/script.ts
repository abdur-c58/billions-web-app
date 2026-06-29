import { apiFetch } from "@/lib/api";

export type ScriptTranscript = {
  transcript: string;
  segment_count: number;
  word_count: number;
};

type ScriptBeatBlock = {
  segments?: Array<{
    segment_id?: number;
    content?: string;
  }>;
};

type ScriptJson = {
  script?: ScriptBeatBlock[];
};

/** Extract narration text from script.json (legacy or folder format). */
export function buildNarrationTranscript(
  scriptData: ScriptJson,
  separator = " ",
): string {
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

export async function fetchScriptTranscript(): Promise<ScriptTranscript> {
  return apiFetch<ScriptTranscript>("/api/project/script/transcript");
}

/** Build transcript from a local script.json File before or after upload. */
export async function buildNarrationTranscriptFromFile(file: File): Promise<ScriptTranscript> {
  const scriptData = (await file.text().then((raw) => JSON.parse(raw))) as ScriptJson;
  const transcript = buildNarrationTranscript(scriptData);
  const segmentCount = (scriptData.script ?? []).reduce(
    (count, beat) =>
      count +
      (beat.segments ?? []).filter((segment) => String(segment.content ?? "").trim()).length,
    0,
  );
  const wordCount = transcript.split(/\s+/).filter(Boolean).length;
  return { transcript, segment_count: segmentCount, word_count: wordCount };
}
