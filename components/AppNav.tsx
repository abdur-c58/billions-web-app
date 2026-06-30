"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Clapperboard, HardDrive } from "lucide-react";
import { useSession } from "@/context/SessionContext";
import { BackendTunnelConnect } from "@/components/BackendTunnelConnect";
import { GlobalActivityIndicator } from "@/components/GlobalActivityIndicator";
import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "Viewer", icon: Clapperboard },
  { href: "/storage", label: "Storage", icon: HardDrive },
];

export function AppNav() {
  const pathname = usePathname();
  const session = useSession();

  return (
    <nav className="glow-header sticky top-0 z-30 w-full">
      <div className="flex w-full items-center gap-6 px-4 py-3 lg:px-6">
        <span className="text-sm font-semibold tracking-tight text-[var(--foreground)]">
          Billions
        </span>
        {session.projectId ? (
          <span className="rounded-full border border-[var(--border)] bg-[var(--surface-raised)] px-2.5 py-1 text-xs font-medium text-[var(--muted)]">
            {session.projectLabel || session.projectId.slice(0, 8)}
          </span>
        ) : (
          <span className="text-xs text-[var(--muted)]">No project selected</span>
        )}
        <div className="flex items-center gap-1">
          {links.map((link) => {
            const Icon = link.icon;
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "inline-flex items-center gap-2 rounded-[var(--radius)] px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-[var(--surface-raised)] text-[var(--foreground)]"
                    : "text-[var(--muted)] hover:bg-[var(--surface-raised)] hover:text-[var(--foreground)]",
                )}
              >
                <Icon className="h-4 w-4" />
                {link.label}
              </Link>
            );
          })}
        </div>
        <BackendTunnelConnect />
        <GlobalActivityIndicator />
      </div>
    </nav>
  );
}
