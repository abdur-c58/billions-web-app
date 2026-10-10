import type { Metadata } from "next";
import { getEffectiveBackendUrl } from "@/lib/backend-tunnel";
import type { PublishQueue, PublishVideo } from "@/lib/publish";
import { MarkPublishedButton, PublishAutoRefresh } from "@/components/PublishControls";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Publish queue",
};

async function backendCandidates(): Promise<string[]> {
  const candidates: string[] = [];
  const effective = await getEffectiveBackendUrl();
  if (effective) candidates.push(effective);
  // A saved tunnel URL goes stale whenever cloudflared restarts; locally the
  // backend is always reachable directly.
  if (!process.env.VERCEL) {
    const local = `http://127.0.0.1:${process.env.BROLL_BACKEND_PORT || "8766"}`;
    if (!candidates.includes(local)) candidates.push(local);
  }
  return candidates;
}

async function loadQueue(): Promise<{ queue: PublishQueue | null; error: string | null }> {
  const candidates = await backendCandidates();
  if (!candidates.length) {
    return { queue: null, error: "Python backend is not configured." };
  }
  let lastError = "";
  for (const backendUrl of candidates) {
    try {
      const response = await fetch(`${backendUrl}/api/publish/queue`, { cache: "no-store" });
      const payload = (await response.json()) as PublishQueue & { error?: string };
      if (!response.ok) {
        lastError = payload.error || `Backend returned ${response.status}.`;
        continue;
      }
      return { queue: payload, error: null };
    } catch (err) {
      const message = err instanceof Error ? err.message : "request failed";
      lastError = `Cannot reach Python backend (${backendUrl}): ${message}`;
    }
  }
  return { queue: null, error: lastError };
}

function formatDate(seconds: number | null): string {
  if (!seconds) return "—";
  return new Date(seconds * 1000).toISOString().replace("T", " ").slice(0, 19) + " UTC";
}

function formatSize(bytes: number): string {
  if (!bytes) return "0 MB";
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** The script's whole `thumbnail` block, as written in the script JSON. */
function thumbnailPromptText(thumbnail: NonNullable<PublishVideo["thumbnail"]>): string {
  const block = JSON.stringify({ thumbnail }, null, 2);
  return block.slice(block.indexOf("\n") + 1, block.lastIndexOf("\n")).replace(/^ {2}/gm, "");
}

const STATUS_LABEL: Record<PublishVideo["state"], string> = {
  ready: "READY FOR PUBLISHING",
  not_ready: "NOT READY",
  published: "PUBLISHED",
};

const STATUS_CLASSES: Record<PublishVideo["state"], string> = {
  ready: "border-emerald-400/50 bg-emerald-400/15 text-emerald-300",
  not_ready: "border-amber-400/50 bg-amber-400/10 text-amber-300",
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

function VideoEntry({ video }: { video: PublishVideo }) {
  return (
    <article
      id={`video-${video.project_id}`}
      data-project-id={video.project_id}
      data-status={video.state}
      data-ready-for-publishing={video.ready_for_publishing ? "true" : "false"}
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
        <p className="text-lg font-semibold">{video.title || "(missing)"}</p>
      </Field>

      <Field label="Channel" name="channel">
        <p>{video.channel || "(missing)"}</p>
      </Field>

      <Field label="Video file path" name="video_path">
        <p className="break-all font-mono text-xs">{video.video_path || "(missing)"}</p>
        <p className="mt-1 text-xs text-[var(--muted)]">
          {video.video_exists ? `File found, ${formatSize(video.video_size_bytes)}` : "File not found on disk"}
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
        {video.chapters_text ? (
          <pre className="whitespace-pre-wrap rounded-lg border border-[var(--border)] bg-black/25 p-3 font-mono text-sm leading-relaxed">
            {video.chapters_text}
          </pre>
        ) : (
          <p>(missing)</p>
        )}
      </Field>

      <Field label="Checks" name="checks">
        <ul className="space-y-1">
          {video.checks.map((check) => (
            <li key={check.key} data-check={check.key} data-ok={check.ok ? "true" : "false"}>
              <span className={check.ok ? "text-emerald-400" : "text-red-400"}>
                {check.ok ? "[PASS]" : "[FAIL]"}
              </span>{" "}
              {check.label}
              {check.detail ? <span className="text-[var(--muted)]"> — {check.detail}</span> : null}
            </li>
          ))}
        </ul>
      </Field>
    </article>
  );
}

export default async function PublishPage() {
  const { queue, error } = await loadQueue();
  const videos = queue?.videos ?? [];

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8 lg:px-6">
      <PublishAutoRefresh />
      <h1 className="text-xl font-semibold text-[var(--foreground)]">Publish queue</h1>
      <p className="mt-1 text-sm text-[var(--muted)]">
        Every finished export with what&apos;s needed to publish it. A video is labelled READY FOR
        PUBLISHING only when all of its checks pass.
      </p>
      <p data-field="summary" className="mt-3 text-sm text-[var(--foreground)]">
        {queue
          ? `${queue.ready_count} ready for publishing · ${videos.length} exported · updated ${formatDate(queue.generated_at)}`
          : null}
      </p>

      {error ? (
        <div className="mt-4 rounded-[var(--radius-lg)] border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      ) : null}

      {queue && videos.length === 0 ? (
        <div className="mt-6 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--surface-raised)] px-4 py-8 text-center text-sm text-[var(--muted)]">
          No finished exports yet.
        </div>
      ) : null}

      <div className="mt-6 flex flex-col gap-4">
        {videos.map((video) => (
          <VideoEntry key={video.project_id} video={video} />
        ))}
      </div>
    </div>
  );
}
