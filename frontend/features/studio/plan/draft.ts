import type { Calibration, Experiment } from "@/contracts/api";
import type { CreateExperimentRequest } from "@/contracts/requests";

/** The editable subset of an Experiment: exactly the creation/PATCH fields. */
export type PlanDraft = CreateExperimentRequest;

export const PLAN_FIELDS = [
  "title", "hypothesis", "method", "protocol_markdown", "variables", "success_criteria",
  "input_artifact_ids", "calibration", "limitations",
] as const satisfies readonly (keyof PlanDraft)[];
export type PlanField = (typeof PLAN_FIELDS)[number];

export const FIELD_LABEL: Record<PlanField, string> = {
  title: "Title", hypothesis: "Hypothesis", method: "Method", protocol_markdown: "Protocol",
  variables: "Variables", success_criteria: "Success criteria", input_artifact_ids: "Attached inputs",
  calibration: "Calibration", limitations: "Limitations",
};

export function toDraft(x: Experiment): PlanDraft {
  return {
    title: x.title, hypothesis: x.hypothesis, method: x.method, protocol_markdown: x.protocol_markdown,
    variables: x.variables.map((v) => ({ ...v })), success_criteria: [...x.success_criteria],
    input_artifact_ids: [...x.input_artifact_ids], calibration: structuredClone(x.calibration),
    limitations: [...x.limitations],
  };
}

export function emptyDraft(): PlanDraft {
  return {
    title: "", hypothesis: "", method: "physical", protocol_markdown: "", variables: [], success_criteria: [],
    input_artifact_ids: [], calibration: { mode: "none", assumptions: [] }, limitations: [],
  };
}

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/** Fields where `a` and `b` differ. */
export function changedFields(a: PlanDraft, b: PlanDraft): PlanField[] {
  return PLAN_FIELDS.filter((f) => !same(a[f], b[f]));
}

/** Only the changed fields, for a PATCH (arrays replace whole arrays per contract). */
export function patchBody(base: PlanDraft, draft: PlanDraft): Partial<PlanDraft> {
  const out: Partial<PlanDraft> = {};
  for (const f of changedFields(base, draft)) (out as Record<string, unknown>)[f] = draft[f];
  return out;
}

export type DraftIssue = { field: PlanField | string; message: string };

/** Client-side guards mirroring the contract. The backend remains authoritative. */
export function validateDraft(d: PlanDraft): DraftIssue[] {
  const issues: DraftIssue[] = [];
  if (!d.title.trim()) issues.push({ field: "title", message: "Give the experiment a title." });
  if (!d.hypothesis.trim()) issues.push({ field: "hypothesis", message: "State the hypothesis being tested." });
  d.variables.forEach((v, i) => {
    if (!v.name.trim()) issues.push({ field: `variables/${i}`, message: `Variable ${i + 1} needs a name.` });
  });
  issues.push(...validateCalibration(d.calibration, d.input_artifact_ids));
  return issues;
}

export function validateCalibration(c: Calibration, inputs: string[]): DraftIssue[] {
  if (c.mode === "none") return [];
  const out: DraftIssue[] = [];
  const f = "calibration";
  if (!inputs.includes(c.artifact_id)) out.push({ field: f, message: "Calibration must refer to an attached input." });
  if (!Number.isInteger(c.frame_index) || c.frame_index < 0) out.push({ field: f, message: "Frame index must be a whole number ≥ 0." });
  const pts = [...c.point_a_px, ...c.point_b_px];
  if (!pts.every((n) => Number.isFinite(n) && n >= 0)) out.push({ field: f, message: "Points must be non-negative pixel coordinates." });
  if (c.point_a_px[0] === c.point_b_px[0] && c.point_a_px[1] === c.point_b_px[1]) out.push({ field: f, message: "The two points must differ." });
  if (!(c.reference_length_m > 0)) out.push({ field: f, message: "Reference length must be greater than 0 m." });
  if (c.reference_uncertainty_m != null && !(c.reference_uncertainty_m >= 0)) out.push({ field: f, message: "Uncertainty cannot be negative." });
  return out;
}

export function describeValue(field: PlanField, d: PlanDraft): string {
  const v = d[field];
  if (field === "calibration") {
    const c = d.calibration;
    return c.mode === "none" ? "None (native units)" : `Reference length ${c.reference_length_m} m on frame ${c.frame_index}`;
  }
  if (field === "variables") return d.variables.map((x) => `${x.name} (${x.role}${x.unit ? `, ${x.unit}` : ""})`).join("; ") || "None";
  if (Array.isArray(v)) return v.length ? v.join("; ") : "None";
  return String(v) || "Empty";
}
