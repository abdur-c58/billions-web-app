export const DEFAULT_WHISPER_MODEL = "medium" as const;

export const WHISPER_MODELS = [
  "tiny",
  "base",
  "small",
  "medium",
  "large",
  "large-v2",
  "large-v3",
] as const;

export type WhisperModel = (typeof WHISPER_MODELS)[number];

export function isWhisperModel(value: string): value is WhisperModel {
  return (WHISPER_MODELS as readonly string[]).includes(value);
}

export const WHISPER_MODEL_OPTIONS: {
  value: WhisperModel;
  label: string;
  description: string;
}[] = [
  { value: "tiny", label: "Tiny", description: "Fastest, least accurate" },
  { value: "base", label: "Base", description: "Fast, low accuracy" },
  { value: "small", label: "Small", description: "Fast, good for drafts" },
  { value: "medium", label: "Medium", description: "Recommended balance" },
  { value: "large", label: "Large", description: "High accuracy, slower" },
  { value: "large-v2", label: "Large v2", description: "High accuracy" },
  { value: "large-v3", label: "Large v3", description: "Best accuracy, slowest" },
];

export const WHISPER_MODEL_STORAGE_KEY = "whisper-segmentation-model";

export function readStoredWhisperModel(): WhisperModel {
  if (typeof window === "undefined") return DEFAULT_WHISPER_MODEL;
  try {
    const stored = localStorage.getItem(WHISPER_MODEL_STORAGE_KEY);
    if (stored && isWhisperModel(stored)) return stored;
  } catch {
    // Ignore storage failures.
  }
  return DEFAULT_WHISPER_MODEL;
}

export function storeWhisperModel(model: WhisperModel) {
  try {
    localStorage.setItem(WHISPER_MODEL_STORAGE_KEY, model);
  } catch {
    // Ignore storage failures.
  }
}
