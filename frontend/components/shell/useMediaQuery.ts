"use client";
import { useSyncExternalStore } from "react";

/** SSR returns `fallback`; the client then follows the live media query. */
export function useMediaQuery(query: string, fallback = false): boolean {
  return useSyncExternalStore(
    (cb) => {
      const m = window.matchMedia(query);
      m.addEventListener("change", cb);
      return () => m.removeEventListener("change", cb);
    },
    () => window.matchMedia(query).matches,
    () => fallback,
  );
}
