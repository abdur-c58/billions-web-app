import type { SegmentationHardware } from "@/lib/project";

export type SegmentTiming = {
  start_seconds: number | null;
  end_seconds: number | null;
  duration_seconds: number | null;
  export_start_seconds?: number | null;
  export_end_seconds?: number | null;
  start_timecode?: string | null;
  end_timecode?: string | null;
};

export type PexelsVideo = {
  video_id: number | string;
  provider?: "pexels" | "pixabay" | "storage";
  url: string;
  thumbnail?: string;
  pexels_url?: string;
  pixabay_url?: string;
  photographer?: string;
  storage_key?: string;
  name?: string;
  duration?: number;
  loop?: boolean;
};

export type SegmentSelection = PexelsVideo & {
  search_query?: string;
  page?: number;
  result_index?: number;
  query_used?: string;
  custom_query?: string;
  confidence?: number;
  confidence_source?: "openai" | "heuristic" | "manual";
  needs_review?: boolean;
  ai_model?: string | null;
  ai_reason?: string | null;
  ai_skipped?: string | null;
  quality_tier?: "none" | "good" | "mid" | "review" | "unknown";
  quality_label?: string;
};

export type JudgmentSummary = {
  none: number;
  good: number;
  mid: number;
  review: number;
  unknown: number;
};

export type AiJudgeStatus = {
  enabled: boolean;
  calls_today?: number;
  max_calls?: number;
  remaining?: number;
};

export type ViewerSegment = {
  segment_id: number;
  beat: number;
  label: string;
  content: string;
  description: string;
  search_query: string;
  category: string;
  folder_status?: SegmentFolderStatus;
  timing: SegmentTiming;
  selection?: SegmentSelection | null;
  selection_flagged?: boolean;
  _alternatives?: PexelsVideo[];
};

export type DuplicateClip = {
  key: string;
  provider?: string;
  video_id?: number;
  url?: string;
  thumbnail?: string;
  photographer?: string;
  pexels_url?: string;
  pixabay_url?: string;
  segment_ids: number[];
  occurrences?: { segment_id: number; start_seconds: number }[];
  gaps?: { from_segment_id: number; to_segment_id: number; gap_seconds: number }[];
  count: number;
};

export type DuplicatesPayload = {
  duplicates: DuplicateClip[];
  total_groups: number;
  total_segments_affected: number;
};

export type FlaggedClip = {
  key: string;
  provider?: string;
  video_id?: number;
  url?: string;
  thumbnail?: string;
  photographer?: string;
  pexels_url?: string;
  pixabay_url?: string;
  flagged_at?: number;
  segment_ids?: number[];
};

export type FlagClipResponse = {
  clip: FlaggedClip;
  affected_segment_ids: number[];
  affected_count: number;
};

export type ScriptFormat = "legacy" | "folder";

export type FolderShortageStrategy = "leave_empty" | "reuse_spaced" | "random_api";

export type SegmentFolderStatus = {
  expects_folder: boolean;
  has_folder: boolean;
  clip_count: number;
  folder_prefix?: string;
  shortage?: boolean;
};

export type FolderFetchMode =
  | "folder"
  | "api"
  | "api_warning"
  | "unassigned"
  | "api_shortage";

export type FolderShortage = {
  category: string;
  segment_count: number;
  clip_count: number;
  deficit: number;
  folder_prefix: string;
};

export type FolderFetchAssignment = {
  segment_id: number;
  category: string;
  mode: FolderFetchMode;
  search_query: string;
  storage_key?: string;
  clip_name?: string;
  folder?: string;
  warning?: string;
  reused?: boolean;
};

export type FolderFetchPlan = {
  script_format?: ScriptFormat;
  assignments: FolderFetchAssignment[];
  shortages?: FolderShortage[];
  needs_shortage_choice?: boolean;
  shortage_strategy?: FolderShortageStrategy | null;
  summary: {
    folder: number;
    api: number;
    api_warning: number;
    api_shortage?: number;
    unassigned?: number;
    total: number;
  };
  folders: Record<
    string,
    {
      prefix: string;
      clip_count: number;
    }
  >;
};

export type SegmentsPayload = {
  title?: string;
  project_folder?: string;
  script?: string;
  script_format?: ScriptFormat;
  video_duration_s?: number | null;
  segments: ViewerSegment[];
  judgment_summary?: JudgmentSummary;
  ai_judge?: AiJudgeStatus;
  export_inputs_hash?: string;
};

export type FetchPayload = {
  segment_id: number;
  search_query: string;
  query_used?: string;
  provider_mode?: "mix" | "pexels" | "pixabay" | "random";
  selection: SegmentSelection;
  alternatives: PexelsVideo[];
  cached?: boolean;
  judgment?: {
    confidence?: number;
    confidence_source?: string;
    needs_review?: boolean;
    ai_skipped?: string | null;
    ai_reason?: string | null;
  } | null;
};

export type ExportSnapshot = {
  status: string;
  stage?: string;
  current?: number;
  total?: number;
  message?: string;
  output?: string | null;
  encoder?: string | null;
  error?: string | null;
  progress_percent?: number;
  elapsed_seconds?: number;
  eta_seconds?: number | null;
  download_seconds?: number;
  render_seconds?: number;
  hardware?: SegmentationHardware | null;
  /** Hash of selections/timestamps/audio at last successful export. */
  inputs_hash?: string | null;
  /** R2 key of the uploaded export file. */
  r2_key?: string | null;
  project_id?: string | null;
  project_name?: string | null;
};

export type BackgroundAudioFile = {
  key: string;
  name: string;
  size_bytes: number;
  duration_seconds: number | null;
};

export type BackgroundAudioListPayload = {
  files: BackgroundAudioFile[];
  configured?: boolean;
  storage_prefix?: string;
  narration: {
    name: string;
    duration_seconds: number | null;
  };
};

export type AudioBalanceInfo = {
  background: string | null;
  narration: string;
  narration_mean_db: number;
  background_mean_db: number;
  narration_gain_db: number;
  background_gain_db: number;
  background_under_narration_db: number;
  narration_adjust_db?: number;
  background_adjust_db?: number;
};

export type AudioPreviewResponse = AudioBalanceInfo & {
  preview_url: string;
  preview_data_url?: string;
  preview_seconds: number;
  background_audio: string | null;
};

export type AudioMixAdjustments = {
  narration_adjust_db: number;
  background_adjust_db: number;
};

export type ExportResolution = "1080p" | "1440p" | "4k";
export type ExportQuality = "high" | "balanced" | "compressed";

export type ExportAudioOptions = {
  backgroundAudio: string | null; // R2 key under Audio/
  mixAdjustments: AudioMixAdjustments;
  resolution: ExportResolution;
  quality: ExportQuality;
};
