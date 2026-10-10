import type { Metadata } from "next";
import { headers } from "next/headers";
import type { PublishVideo } from "@/lib/publish";
import { listPublishVideos } from "@/lib/publish-r2";
import { MarkPublishedButton, PublishAutoRefresh } from "@/components/PublishControls";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Publish queue",
};

async function loadVideos(): Promise<{
  videos: PublishVideo[] | null;
  loadedAt: number;
  error: string | null;
}> {
  const loadedAt = Date.now() / 1000;
  try {
    return { videos: await listPublishVideos(), loadedAt, error: null };
  } catch (err) {
    return {
      videos: null,
      loadedAt,
      error: err instanceof Error ? err.message : "Failed to read R2 publish folder.",
    };
  }
}

async function siteOrigin(): Promise<string> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "localhost:3001";
  const proto =
    requestHeaders.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  return `${proto}://${host}`;
}

function formatDate(seconds: number | null): string {
  if (!seconds) return "—";
  return new Date(seconds * 1000).toISOString().replace("T", " ").slice(0, 19) + " UTC";
}

function formatSize(bytes: number): string {
  if (!bytes) return "0 MB";
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Overlay fields the thumbnail prompt leaves out. */
const HIDDEN_OVERLAY_FIELDS = new Set(["corner_badge"]);

/** The script's whole `thumbnail` block, as written in the script JSON. */
function thumbnailPromptText(thumbnail: NonNullable<PublishVideo["thumbnail"]>): string {
  const overlayText = Object.fromEntries(
    Object.entries(thumbnail.overlay_text ?? {}).filter(([key]) => !HIDDEN_OVERLAY_FIELDS.has(key)),
  );
  const block = JSON.stringify({ thumbnail: { ...thumbnail, overlay_text: overlayText } }, null, 2);
  return block.slice(block.indexOf("\n") + 1, block.lastIndexOf("\n")).replace(/^ {2}/gm, "");
}

const STATUS_LABEL: Record<PublishVideo["state"], string> = {
  ready: "READY FOR PUBLISHING",
  published: "PUBLISHED",
};

const STATUS_CLASSES: Record<PublishVideo["state"], string> = {
  ready: "border-emerald-400/50 bg-emerald-400/15 text-emerald-300",
  published: "border-sky-400/50 bg-sky-400/10 text-sky-300",
};

function Field({ label, name, children }: { label: string; name: string; children: React.ReactNode }) {
  return (
    <div data-field={name} className="mt-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{label}</h3>
      <div className="mt-1 text-sm text-[var(--foreground)]">{children}</div>
    </div>
  );
}

function VideoEntry({ video, origin }: { video: PublishVideo; origin: string }) {
  const downloadUrl = `${origin}/api/publish/download/${video.project_id}`;
  return (
    <article
      id={`video-${video.project_id}`}
      data-project-id={video.project_id}
      data-status={video.state}
      data-ready-for-publishing={video.state === "ready" ? "true" : "false"}
      className="rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-raised)] px-5 py-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p
          data-field="status"
          className={cn(
            "rounded-full border px-3 py-1 text-xs font-bold tracking-wide",
            STATUS_CLASSES[video.state],
          )}
        >
          Status: {STATUS_LABEL[video.state]}
        </p>
        <MarkPublishedButton projectId={video.project_id} published={video.published} />
      </div>

      <Field label="Video title" name="title">
        <p className="text-lg font-semibold">{video.title}</p>
      </Field>

      <Field label="Channel" name="channel">
        <p>{video.channel}</p>
      </Field>

      <Field label="Video download" name="video_download">
        <a
          href={downloadUrl}
          data-download-url={downloadUrl}
          className="break-all font-mono text-xs text-sky-300 underline underline-offset-2"
        >
          {downloadUrl}
        </a>
        <p className="mt-1 text-xs text-[var(--muted)]">
          File name: <span className="font-mono">{video.video_filename}</span> · {formatSize(video.video_size_bytes)}
          {" · "}Exported {formatDate(video.exported_at)}
          {video.published ? ` · Published ${formatDate(video.published_at)}` : ""}
        </p>
      </Field>

      <Field label="Thumbnail prompt" name="thumbnail_prompt">
        {video.thumbnail ? (
          <>
            <p className="mb-2 text-xs text-[var(--muted)]">
              The full thumbnail brief: image prompt plus overlay text and styling. Use all of it.
            </p>
            <pre className="whitespace-pre-wrap break-words rounded-lg border border-[var(--border)] bg-black/25 p-3 font-mono text-xs leading-relaxed">
              {thumbnailPromptText(video.thumbnail)}
            </pre>
          </>
        ) : (
          <p>(missing)</p>
        )}
      </Field>

      <Field label="Chapters" name="chapters">
        <pre className="whitespace-pre-wrap rounded-lg border border-[var(--border)] bg-black/25 p-3 font-mono text-sm leading-relaxed">
          {video.chapters_text}
        </pre>
      </Field>
    </article>
  );
}

export default async function PublishPage() {
  const [{ videos, loadedAt, error }, origin] = await Promise.all([loadVideos(), siteOrigin()]);
  const readyCount = videos?.filter((video) => video.state === "ready").length ?? 0;

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8 lg:px-6">
      <PublishAutoRefresh />
      <h1 className="text-xl font-semibold text-[var(--foreground)]">Publish queue</h1>
      <p className="mt-1 text-sm text-[var(--muted)]">
        Finished exports that passed every check, stored in cloud storage so they can be published even
        when the editing PC is off. Download each video from its link.
      </p>
      <p data-field="summary" className="mt-3 text-sm text-[var(--foreground)]">
        {videos
          ? `${readyCount} ready for publishing · ${videos.length} total · updated ${formatDate(loadedAt)}`
          : null}
      </p>

      {error ? (
        <div className="mt-4 rounded-[var(--radius-lg)] border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      ) : null}

      {videos && videos.length === 0 ? (
        <div className="mt-6 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-raised)] px-4 py-8 text-center text-sm text-[var(--muted)]">
          No videos waiting to publish.
        </div>
      ) : null}

      <div className="mt-6 flex flex-col gap-4">
        {(videos ?? []).map((video) => (
          <VideoEntry key={video.project_id} video={video} origin={origin} />
        ))}
      </div>
    </div>
  );
}
