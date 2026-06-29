"use client";

import { useEffect, useRef } from "react";

/** Default interval for background status sync across open tabs/users. */
export const STATUS_POLL_MS = 4000;

/**
 * Repeatedly invokes `callback` on a fixed interval while `enabled`.
 * Skips work while the tab is hidden and waits for in-flight callbacks to finish.
 */
export function usePolling(
  callback: () => void | Promise<void>,
  intervalMs: number,
  enabled = true,
) {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;
    let timer: number | null = null;
    let inFlight = false;

    const schedule = () => {
      if (!cancelled) {
        timer = window.setTimeout(() => void tick(), intervalMs);
      }
    };

    const tick = async () => {
      if (cancelled) return;
      if (document.hidden || inFlight) {
        schedule();
        return;
      }
      inFlight = true;
      try {
        await callbackRef.current();
      } catch {
        // Background polls should not crash the UI.
      } finally {
        inFlight = false;
        schedule();
      }
    };

    schedule();
    return () => {
      cancelled = true;
      if (timer != null) window.clearTimeout(timer);
    };
  }, [intervalMs, enabled]);
}
