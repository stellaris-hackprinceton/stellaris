"use client";
import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

/** `experiment` and `run` selection live in the URL (spec §3). */
export function useStudioParams() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const update = useCallback((next: { experiment?: string | null; run?: string | null }) => {
    const q = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(next)) {
      if (v === undefined) continue;
      if (v === null) q.delete(k); else q.set(k, v);
    }
    const qs = q.toString();
    router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
  }, [params, pathname, router]);
  return { experiment: params.get("experiment"), run: params.get("run"), update };
}
