"use client";

import { AnimatePresence, motion } from "framer-motion";

type FlagClipModalProps = {
  open: boolean;
  affectedCount: number;
  segmentIds: number[];
  onRefetchAffected: () => void;
  onLeaveAsIs: () => void;
};

export function FlagClipModal({
  open,
  affectedCount,
  segmentIds,
  onRefetchAffected,
  onLeaveAsIs,
}: FlagClipModalProps) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[80] grid place-items-center bg-black/65 p-4 backdrop-blur-[2px]"
          onClick={onLeaveAsIs}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 6 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98, y: 4 }}
            transition={{ duration: 0.2 }}
            className="export-confirm-shell relative w-full max-w-[560px] rounded-2xl p-[1.5px]"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="export-confirm-content rounded-2xl p-5">
              <h3 className="text-base font-semibold text-[var(--foreground)]">
                This clip is used in {affectedCount} segments
              </h3>
              <p className="mt-2 text-sm text-[var(--muted)]">
                The clip is now flagged and will be excluded from all future fetches. Segments{" "}
                {segmentIds.map((id) => `#${id}`).join(", ")} still have it selected.
              </p>
              <p className="mt-2 text-sm text-[var(--muted)]">
                Refetch all affected segments now to replace them, or leave the current selections
                as-is for this export only.
              </p>
              <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={onLeaveAsIs}
                  className="glow-btn-secondary rounded-[10px] px-3 py-2 text-sm font-semibold"
                >
                  Leave clips as-is
                </button>
                <button
                  type="button"
                  onClick={onRefetchAffected}
                  className="glow-btn-primary rounded-[10px] px-3 py-2 text-sm font-semibold"
                >
                  Refetch all affected
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
