"use client";

import { cn } from "@/lib/utils";

type ExportStyleProgressBarProps = {
  percent: number;
  className?: string;
  trackClassName?: string;
  variant?: "default" | "gold";
};

function clampPercent(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

export function ExportStyleProgressBar({
  percent,
  className,
  trackClassName,
  variant = "gold",
}: ExportStyleProgressBarProps) {
  const clamped = clampPercent(percent);

  return (
    <div
      className={cn(
        "progress-bar-shell w-full",
        variant === "gold" && "progress-bar-gold",
        className,
      )}
    >
      <div
        className={cn(
          "export-progress-track !h-[9px] rounded-full bg-[rgba(255,255,255,0.07)]",
          trackClassName,
        )}
      >
        {clamped > 0 ? (
          <>
            <div className="export-progress-fill-group" style={{ width: `${clamped}%` }}>
              <div className="export-progress-fill-ambient !h-[18px]" />
              <div className="export-progress-fill !h-[5px]" />
            </div>
            <div className="export-progress-glow-layer" style={{ width: `${clamped}%` }}>
              <span className="export-progress-glow-beam !h-[7px]" aria-hidden="true" />
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
