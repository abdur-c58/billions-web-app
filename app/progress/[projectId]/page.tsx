"use client";

import { use } from "react";
import { ExportProgressView } from "@/components/ExportProgressView";
import { readStoredProjectLabel } from "@/lib/session";

export default function ProjectProgressPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  const storedLabel = readStoredProjectLabel();

  return <ExportProgressView projectId={projectId} projectLabel={storedLabel} />;
}
