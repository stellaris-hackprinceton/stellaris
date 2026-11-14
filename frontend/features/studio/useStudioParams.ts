"use client";
import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

export const STUDIO_VIEWS = ["plan", "inputs", "analysis", "results"] as const;
export type StudioView = typeof STUDIO_VIEWS[number];
function validView(value: string | null): value is StudioView {
  return value != null && (STUDIO_VIEWS as readonly string[]).includes(value);
}

/** `experiment` and `run` selection live in the URL (spec §3). */
export function useStudioParams() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const update = useCallback((next: { experiment?: string | null; run?: string | null; view?: StudioView | null }) => {
    const q = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(next)) {
      if (v === undefined) continue;
      if (v === null) q.delete(k); else q.set(k, v);
    }
    const qs = q.toString();
    router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
  }, [params, pathname, router]);
  const run = params.get("run");
  const requestedView = params.get("view");
  const view = validView(requestedView) ? requestedView : run ? "results" : "plan";
  return { experiment: params.get("experiment"), run, view, update };
}
