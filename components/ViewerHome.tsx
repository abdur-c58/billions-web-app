"use client";

import { Loader2 } from "lucide-react";
import { BrollViewer } from "@/components/BrollViewer";
import { ProjectPicker } from "@/components/ProjectPicker";
import { ProjectSetup } from "@/components/ProjectSetup";
import { useSession } from "@/context/SessionContext";
import { useProjectSetup } from "@/hooks/useProjectSetup";

export function ViewerHome() {
  const session = useSession();
  const setup = useProjectSetup(session.projectId);

  if (!session.ready) {
    return (
      <div className="flex min-h-[60vh] w-full items-center justify-center text-[var(--muted)]">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading…
      </div>
    );
  }

  if (!session.projectId) {
    return <ProjectPicker />;
  }

  if (setup.loading) {
    return (
      <div className="flex min-h-[60vh] w-full items-center justify-center text-[var(--muted)]">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading project…
      </div>
    );
  }

  if (!setup.viewerReady) {
    return <ProjectSetup setup={setup} onBackToProjects={session.backToProjects} />;
  }

  return <BrollViewer onBackToProjects={session.backToProjects} />;
}
