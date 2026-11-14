// Route paths from the implementation spec §3. Routes themselves are C-owned; these builders only
// encode opaque IDs so every A link points at the documented paths.
import type { ID } from "@/contracts/api";

const e = encodeURIComponent;
export type ProjectView = "research" | "materials" | "studio" | "reports" | "graph" | "runs";

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
  artifact: (p: ID, a: ID) => `/projects/${e(p)}/materials?artifact=${e(a)}`,
  report: (p: ID, a: ID) => `/projects/${e(p)}/reports/${e(a)}`,
  /** Reports library. `compose` opens the composer; context IDs are validated there, never auto-submitted. */
  reports: (p: ID, ctx?: { compose?: boolean; experiment?: ID; evidence_run?: ID }) => {
    const q = new URLSearchParams();
    if (ctx?.compose) q.set("compose", "1");
    if (ctx?.experiment) q.set("experiment", ctx.experiment);
    if (ctx?.evidence_run) q.set("evidence_run", ctx.evidence_run);
    const qs = q.toString();
    return `/projects/${e(p)}/reports${qs ? `?${qs}` : ""}`;
  },
  materialsView: (p: ID, view: "literature" | "findings" | "measurements") => `/projects/${e(p)}/materials?view=${view}`,
};
