"use client";
import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

export const CANVAS_TABS = ["question", "sources", "findings", "experiments"] as const;
export type CanvasTab = (typeof CANVAS_TABS)[number];

/** Shareable selection lives in the URL so refresh and links reopen the same view. */
export function useCanvasParams() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const raw = params.get("tab");
  const source = params.get("source");
  const claim = params.get("claim");
  const tab: CanvasTab = (CANVAS_TABS as readonly string[]).includes(raw ?? "")
    ? (raw as CanvasTab)
    : source ? "sources" : claim ? "findings" : "question";

  const update = useCallback((next: Record<string, string | null>) => {
    const q = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(next)) {
      if (v === null) q.delete(k); else q.set(k, v);
    }
    const qs = q.toString();
    router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
  }, [params, pathname, router]);

  return { tab, source, claim, update };
}
