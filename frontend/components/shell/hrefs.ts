// Route paths from the implementation spec §3. Routes themselves are C-owned; these builders only
// encode opaque IDs so every A link points at the documented paths.
import type { ID } from "@/contracts/api";

const e = encodeURIComponent;
export type ProjectView = "research" | "studio" | "runs" | "workspace";

export const hrefs = {
  projects: () => "/projects",
  project: (p: ID) => `/projects/${e(p)}`,
  view: (p: ID, v: ProjectView) => `/projects/${e(p)}/${v}`,
  research: (p: ID, sel?: { tab?: string; source?: ID; claim?: ID }) => {
    const q = new URLSearchParams();
    if (sel?.tab) q.set("tab", sel.tab);
    if (sel?.source) q.set("source", sel.source);
    if (sel?.claim) q.set("claim", sel.claim);
    const qs = q.toString();
    return `/projects/${e(p)}/research${qs ? `?${qs}` : ""}`;
  },
  studio: (p: ID, experiment?: ID) => `/projects/${e(p)}/studio${experiment ? `?experiment=${e(experiment)}` : ""}`,
  run: (p: ID, r: ID) => `/projects/${e(p)}/runs/${e(r)}`,
  artifact: (p: ID, a: ID) => `/projects/${e(p)}/workspace?artifact=${e(a)}`,
  report: (p: ID, a: ID) => `/projects/${e(p)}/reports/${e(a)}`,
};
