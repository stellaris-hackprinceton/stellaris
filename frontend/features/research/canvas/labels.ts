import type { Experiment, Source, Variable } from "@/contracts/api";
import type { StatusTone } from "@/components/ui";

export const PROVIDER_LABEL: Record<Source["provider"], string> = {
  arxiv: "arXiv", openalex: "OpenAlex", semantic_scholar: "Semantic Scholar", web: "Web", manual: "Added manually",
};

export const RETRIEVAL_LABEL: Record<Source["retrieval_status"], { text: string; tone: StatusTone }> = {
  metadata_only: { text: "Metadata only", tone: "neutral" },
  abstract_retrieved: { text: "Abstract retrieved", tone: "info" },
  full_text_retrieved: { text: "Full text retrieved", tone: "success" },
  failed: { text: "Retrieval failed", tone: "error" },
};

export const METHOD_LABEL: Record<Experiment["method"], string> = {
  physical: "Physical", computational: "Computational", hybrid: "Hybrid",
};

export const ROLE_LABEL: Record<Variable["role"], string> = {
  independent: "Independent", dependent: "Dependent", controlled: "Controlled",
};

export function authorLine(authors: string[], max = 3): string {
  if (authors.length === 0) return "Unknown authors";
  return authors.length > max ? `${authors.slice(0, max).join(", ")} et al.` : authors.join(", ");
}

/** Only http(s) links are rendered as live links. */
export function safeHref(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === "https:" || u.protocol === "http:" ? u.toString() : null;
  } catch {
    return null;
  }
}
