"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Clapperboard } from "lucide-react";
import { fetchActivity } from "@/lib/activity";
import { readStoredProject } from "@/lib/session";

export default function ProgressIndexPage() {
  const router = useRouter();
  const [redirecting, setRedirecting] = useState(true);
  const [exportJobs, setExportJobs] = useState<
    Array<{ project_id: string; project_name: string | null; progress_percent: number }>
  >([]);

  useEffect(() => {
    const stored = readStoredProject();
    if (stored) {
      router.replace(`/progress/${stored}`);
      return;
    }

    setRedirecting(false);
    let cancelled = false;
    void fetchActivity()
      .then((snapshot) => {
        if (cancelled) return;
        const jobs = snapshot.jobs
          .filter((job) => job.type === "export" && job.project_id)
          .map((job) => ({
            project_id: job.project_id as string,
            project_name: job.project_name,
            progress_percent: job.progress_percent,
          }));
        setExportJobs(jobs);
      })
      .catch(() => {
        if (!cancelled) setExportJobs([]);
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  if (redirecting) {
    return null;
  }

  return (
    <main className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center gap-6 px-4 py-16">
      <h1 className="text-xl font-semibold text-[var(--foreground)]">Export progress</h1>
      {exportJobs.length > 0 ? (
        <ul className="flex w-full flex-col gap-2">
          {exportJobs.map((job) => (
            <li key={job.project_id}>
              <Link
                href={`/progress/${job.project_id}`}
                className="flex items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] px-4 py-3 transition-colors hover:bg-[var(--surface)]"
              >
                <Clapperboard className="h-4 w-4 shrink-0 text-[#e8c06a]" />
                <span className="min-w-0 flex-1 truncate text-sm">
                  {job.project_name || job.project_id.slice(0, 8)}
                </span>
                <span className="text-sm font-semibold tabular-nums text-[#e8c06a]">
                  {job.progress_percent}%
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-center text-sm text-[var(--muted)]">
          Open a project and start an export, or pick one from the navbar while it renders.
        </p>
      )}
      <Link href="/" className="text-sm text-[var(--muted)] underline-offset-2 hover:underline">
        Back to projects
      </Link>
    </main>
  );
}
