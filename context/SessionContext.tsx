"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  clearStoredProject,
  readStoredProject,
  readStoredProjectLabel,
  storeProject,
  storeProjectLabel,
} from "@/lib/session";

type SessionContextValue = {
  projectId: string | null;
  projectLabel: string | null;
  ready: boolean;
  selectProject: (projectId: string, label?: string) => void;
  backToProjects: () => void;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [projectLabel, setProjectLabel] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setProjectId(readStoredProject());
    setProjectLabel(readStoredProjectLabel());
    setReady(true);
  }, []);

  const selectProject = useCallback((nextProjectId: string, label?: string) => {
    storeProject(nextProjectId);
    setProjectId(nextProjectId);
    if (label) {
      storeProjectLabel(label);
      setProjectLabel(label);
    }
  }, []);

  const backToProjects = useCallback(() => {
    clearStoredProject();
    setProjectId(null);
    setProjectLabel(null);
  }, []);

  const value = useMemo<SessionContextValue>(
    () => ({
      projectId,
      projectLabel,
      ready,
      selectProject,
      backToProjects,
    }),
    [projectId, projectLabel, ready, selectProject, backToProjects],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used within SessionProvider");
  }
  return context;
}
